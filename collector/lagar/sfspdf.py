"""Snapshot manifest of the authoritative SFS PDFs on svenskforfattningssamling.se.

Enumerates a year index (or the RSS feed), reads each detail page for its PDF
links, downloads every PDF once to hash it and records number, URLs, publication
date, size, SHA-256, content type and retrieval time in a JSON manifest. The
PDF bytes are never committed; `--cache` keeps them in a local folder.
"""

import argparse
import hashlib
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.robotparser
import xml.etree.ElementTree as ElementTree
from dataclasses import dataclass, field
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

from .http import Blocked, PoliteClient
from .sfs import NETWORK_ERRORS, USER_AGENT, StateError, _save_state

BASE = "https://svenskforfattningssamling.se"
HOST = urllib.parse.urlsplit(BASE).netloc
ROBOTS_URL = BASE + "/robots.txt"
YEAR_INDEX_URL = BASE + "/regulations/{year}/index.html"
RSS_URL = BASE + "/regulations/rss.xml/rss.xml"
ROBOTS_PATHS = ("/regulations/", "/doc/", "/sites/default/files/sfs/")
DEFAULT_MANIFEST = "sources/sfs-pdf-manifest.json"
DEFAULT_STATE = "collector/data/sfspdf-state.json"
MANIFEST_VERSION = 1
SAVE_EVERY = 25

DOCUMENT_ERRORS = NETWORK_ERRORS + (UnicodeDecodeError, ValueError)

_NUMBER = re.compile(r"(\d{4}):(\d+)", re.ASCII)
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}", re.ASCII)
_SAFE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\.pdf", re.ASCII)


class ListingError(Exception):
    """An index page, the RSS feed or robots.txt could not be read."""


@dataclass
class IndexItem:
    number: str
    detail_url: str
    published: "str | None" = None


@dataclass
class Detail:
    number: "str | None"
    published: "str | None"
    pdf_urls: "list[str]"


@dataclass
class RunSummary:
    recorded: "list[str]" = field(default_factory=list)
    skipped: int = 0
    failed: "list[str]" = field(default_factory=list)
    blocked: bool = False


def number_key(number):
    match = _NUMBER.fullmatch(number)
    if not match:
        return (sys.maxsize, sys.maxsize, number)
    return (int(match.group(1)), int(match.group(2)), number)


def _text(parts):
    return " ".join("".join(parts).split())


# --- parsers ---------------------------------------------------------------


class _IndexParser(HTMLParser):
    """Rows of the year index table and the pager's rel=next link."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows = []
        self.next_href = None
        self._row = None
        self._cell = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "tr":
            self._row = {"cells": [], "href": None}
        elif tag == "td" and self._row is not None:
            self._cell = []
        elif tag == "a":
            if (attrs.get("rel") or "").lower() == "next" and attrs.get("href"):
                self.next_href = attrs["href"]
            elif self._cell is not None and self._row["href"] is None:
                self._row["href"] = attrs.get("href")

    def handle_endtag(self, tag):
        if tag == "td" and self._cell is not None:
            self._row["cells"].append(_text(self._cell))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if self._row["cells"]:
                self.rows.append(self._row)
            self._row = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)


def parse_index(html, page_url):
    """Return ([IndexItem], next_page_url_or_None) for one year index page."""
    parser = _IndexParser()
    parser.feed(html)
    parser.close()
    items = []
    for row in parser.rows:
        cells = row["cells"]
        if not cells or not _NUMBER.fullmatch(cells[0]) or not row["href"]:
            continue
        published = next((c for c in cells[1:] if _DATE.fullmatch(c)), None)
        items.append(
            IndexItem(cells[0], urllib.parse.urljoin(page_url, row["href"]), published)
        )
    next_url = None
    if parser.next_href:
        next_url = urllib.parse.urljoin(page_url, parser.next_href)
    return items, next_url


class _DetailParser(HTMLParser):
    """SFS number, publication date and PDF links inside the detail article."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.fields = {}
        self.pdf_hrefs = []
        self._article_depth = 0
        self._field = None  # name of the field--name-* block being read
        self._item = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = (attrs.get("class") or "").split()
        if tag == "article":
            self._article_depth += 1
        if not self._article_depth:
            return
        if tag == "div":
            name = next((c[len("field--name-"):] for c in classes if c.startswith("field--name-")), None)
            if name:
                self._field = name
            elif "field--item" in classes and self._field and self._field not in self.fields:
                self._item = []
        elif tag == "a":
            href = attrs.get("href") or ""
            if urllib.parse.urlsplit(href).path.lower().endswith(".pdf"):
                self.pdf_hrefs.append(href)

    def handle_endtag(self, tag):
        if tag == "article" and self._article_depth:
            self._article_depth -= 1
        elif tag == "div" and self._item is not None:
            self.fields[self._field] = _text(self._item)
            self._item = None
            self._field = None

    def handle_data(self, data):
        if self._item is not None:
            self._item.append(data)


def parse_detail(html, page_url):
    parser = _DetailParser()
    parser.feed(html)
    parser.close()
    urls = []
    for href in parser.pdf_hrefs:
        url = urllib.parse.urljoin(page_url, href)
        if url not in urls:
            urls.append(url)
    published = parser.fields.get("announcement")
    return Detail(
        number=parser.fields.get("sfs-number"),
        published=published if published and _DATE.fullmatch(published) else None,
        pdf_urls=urls,
    )


_DC = "{http://purl.org/dc/elements/1.1/}"


def parse_rss(raw):
    """Return [IndexItem] from the RSS feed; the number is in dc:creator."""
    root = ElementTree.fromstring(raw)
    items = []
    for node in root.iter("item"):
        number = (node.findtext(_DC + "creator") or "").strip()
        link = (node.findtext("link") or "").strip()
        if _NUMBER.fullmatch(number) and link:
            items.append(IndexItem(number, link))
    return items


# --- manifest and state ----------------------------------------------------


def load_manifest(path):
    try:
        loaded = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (ValueError, OSError):
        raise StateError(f"manifest corrupt: {path}") from None
    entries = loaded.get("entries") if isinstance(loaded, dict) else None
    if not isinstance(entries, list) or not all(
        isinstance(e, dict) and isinstance(e.get("number"), str) for e in entries
    ):
        raise StateError(f"manifest corrupt: {path}")
    return {entry["number"]: entry for entry in entries}


def save_manifest(path, entries):
    manifest = {
        "version": MANIFEST_VERSION,
        "source": BASE,
        "entries": [entries[n] for n in sorted(entries, key=number_key)],
    }
    _save_state(path, manifest)


def _load_state(path):
    state = {"failed": {}, "blocked": None}
    try:
        loaded = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return state
    except (ValueError, OSError):
        raise StateError(f"state file corrupt: {path}") from None
    failed = loaded.get("failed", {}) if isinstance(loaded, dict) else None
    if not isinstance(failed, dict) or not all(isinstance(v, str) for v in failed.values()):
        raise StateError(f"state file corrupt: {path}")
    state["failed"] = failed
    return state


# --- network ---------------------------------------------------------------


def _robots_allows(client):
    try:
        raw = client.get(ROBOTS_URL)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return True
        raise ListingError(f"robots.txt: HTTP {error.code}") from error
    except NETWORK_ERRORS as error:
        raise ListingError(f"robots.txt: {error}") from error
    parser = urllib.robotparser.RobotFileParser()
    parser.parse(raw.decode("utf-8", errors="replace").splitlines())
    return all(parser.can_fetch(USER_AGENT, BASE + path) for path in ROBOTS_PATHS)


def _on_site(url):
    parts = urllib.parse.urlsplit(url)
    return parts.scheme == "https" and parts.netloc == HOST


def _year_items(client, year):
    url = YEAR_INDEX_URL.format(year=year)
    seen = set()
    while url and url not in seen:
        seen.add(url)
        if not _on_site(url):
            raise ListingError(f"index page link leaves the site: {url}")
        try:
            items, url = parse_index(client.get(url).decode("utf-8"), url)
        except Blocked:
            raise
        except (*NETWORK_ERRORS, UnicodeDecodeError) as error:
            raise ListingError(f"year {year} index: {error}") from error
        yield from items


def _rss_items(client):
    try:
        return parse_rss(client.get(RSS_URL))
    except Blocked:
        raise
    except (*NETWORK_ERRORS, ElementTree.ParseError) as error:
        raise ListingError(f"RSS feed: {error}") from error


def _cache_path(cache, number, url):
    name = urllib.parse.unquote(urllib.parse.urlsplit(url).path.rsplit("/", 1)[-1])
    if not _SAFE_NAME.fullmatch(name):
        raise ValueError(f"unexpected PDF file name: {url}")
    return Path(cache) / number.split(":", 1)[0] / name


def _snapshot(client, item, cache):
    """Fetch the detail page and every PDF it links; return the manifest entry."""
    if not _on_site(item.detail_url):
        raise ValueError(f"detail page is not on {HOST}: {item.detail_url}")
    detail = parse_detail(client.get(item.detail_url).decode("utf-8"), item.detail_url)
    if detail.number != item.number:
        raise ValueError(f"detail page shows {detail.number!r}, expected {item.number}")
    if not detail.pdf_urls:
        raise ValueError("detail page links no PDF")
    files = []
    for url in detail.pdf_urls:
        if not _on_site(url):
            raise ValueError(f"PDF is not on {HOST}: {url}")
        body, content_type = client.fetch(url)
        if not body.startswith(b"%PDF-"):
            raise ValueError(f"not a PDF ({content_type}): {url}")
        retrieved_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        if cache:
            target = _cache_path(cache, item.number, url)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(body)
        files.append(
            {
                "url": url,
                "bytes": len(body),
                "sha256": hashlib.sha256(body).hexdigest(),
                "content_type": content_type,
                "retrieved_at": retrieved_at,
            }
        )
    return {
        "number": item.number,
        "detail_url": item.detail_url,
        "published": detail.published or item.published,
        "files": files,
    }


# --- run -------------------------------------------------------------------


def parse_args(argv):
    parser = argparse.ArgumentParser(prog="collect.py sfspdf")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--year", type=int, action="append", metavar="YYYY",
        help="walk the year index (repeatable)",
    )
    source.add_argument("--rss", action="store_true", help="only the items in the RSS feed")
    parser.add_argument("--limit", type=int, metavar="N", help="stop after N new entries")
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST)
    parser.add_argument("--state", default=DEFAULT_STATE)
    parser.add_argument("--cache", metavar="DIR", help="keep the PDF bytes in DIR")
    parser.add_argument("--report", metavar="FILE", help="write a JSON run report")
    parser.add_argument("--rate", type=float, default=1.0, metavar="SECONDS")
    args = parser.parse_args(argv)
    if args.limit is not None and args.limit < 0:
        parser.error("--limit must not be negative")
    return args


def _candidates(client, args):
    if args.rss:
        yield from _rss_items(client)
        return
    for year in args.year:
        yield from _year_items(client, year)


def _write_report(path, summary):
    report = {
        "recorded": summary.recorded,
        "skipped": summary.skipped,
        "failed": summary.failed,
        "blocked": summary.blocked,
    }
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run(client, args):
    summary = RunSummary()
    entries = load_manifest(args.manifest)
    state = _load_state(args.state)
    unsaved = 0

    def flush():
        nonlocal unsaved
        if unsaved:
            save_manifest(args.manifest, entries)
            unsaved = 0
        _save_state(args.state, state)

    try:
        if not _robots_allows(client):
            state["blocked"] = "robots.txt disallows the SFS paths"
            summary.blocked = True
            return summary
        seen = set()
        for item in _candidates(client, args):
            if args.limit is not None and len(summary.recorded) >= args.limit:
                break
            if item.number in seen:
                continue
            seen.add(item.number)
            if item.number in entries:
                summary.skipped += 1
                continue
            try:
                entries[item.number] = _snapshot(client, item, args.cache)
            except Blocked:
                raise
            except DOCUMENT_ERRORS as error:
                summary.failed.append(item.number)
                state["failed"][item.number] = f"{type(error).__name__}: {error}"
                continue
            state["failed"].pop(item.number, None)
            summary.recorded.append(item.number)
            unsaved += 1
            if unsaved >= SAVE_EVERY:
                flush()
                print(
                    f"{len(summary.recorded)} recorded, {summary.skipped} skipped, "
                    f"{len(summary.failed)} failed",
                    flush=True,
                )
    except Blocked as error:
        state["blocked"] = str(error)
        summary.blocked = True
    finally:
        # Also on ListingError or an interrupt: keep what was hashed so far.
        flush()
        if args.report:
            _write_report(args.report, summary)
    return summary


def main(argv, client=None):
    args = parse_args(argv)
    if client is None:
        client = PoliteClient(USER_AGENT, min_interval=args.rate)
    try:
        summary = run(client, args)
    except (ListingError, StateError) as error:
        print(f"error: {error}", file=sys.stderr, flush=True)
        return 1
    print(
        f"done: {len(summary.recorded)} recorded, {summary.skipped} skipped, "
        f"{len(summary.failed)} failed" + (", BLOCKED" if summary.blocked else ""),
        flush=True,
    )
    if summary.failed:
        print("failed: " + ", ".join(summary.failed), flush=True)
    if summary.blocked:
        print("blocked: see state file", file=sys.stderr)
        return 2
    return 0
