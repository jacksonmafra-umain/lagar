"""Sveriges internationella överenskommelser (SÖ) from regeringen.se into the corpus.

Every treaty binding Sweden is published in SÖ. Regeringen lists each one on a
page under /rattsliga-dokument/sveriges-internationella-overenskommelser/
with its title, the place and date of signature, the SÖ number, a short note
on the government's decision and the entry into force, and the treaty text as
PDF. The pages are found through the site's sitemap (one request), fetched at
most once a second, and only pages that carry an SÖ number are stored; the
declarations of intent and other non-binding documents published in the same
section are skipped.

The treaty text is only published as PDF. For treaties from `--text-from-year`
on, the PDFs are downloaded and their text extracted with the shared helper
(`pdftext`); for older ones, and for scanned PDFs, the document holds the
page's metadata and a link to the PDF. The SHA-256 and size of every
downloaded PDF go into `sources/so-pdf-manifest.json`; PDF bytes are never
kept. robots.txt is read once and honoured for every URL.
"""

import argparse
import hashlib
import html
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.robotparser
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path

from . import frontmatter, pdftext
from .caselaw import NETWORK_ERRORS, StateError, _load_state, _save_state, personal_numbers
from .http import Blocked, PoliteClient
from .vocabulary import TYPES
from .writer import path_for, write

USER_AGENT = "lagar-collector/0.1 (+https://github.com/jacksonmafra-umain/lagar)"
HOST = "www.regeringen.se"
BASE = "https://" + HOST
ROBOTS_URL = BASE + "/robots.txt"
SITEMAP_URL = BASE + "/sitemap.xml"
SECTION = "/rattsliga-dokument/sveriges-internationella-overenskommelser/"
DEFAULT_STATE = "collector/data/so-state.json"
DEFAULT_MANIFEST = "sources/so-pdf-manifest.json"
DEFAULT_TEXT_FROM_YEAR = 2010
MANIFEST_VERSION = 1
TYPE = "treaty"

DOCUMENT_ERRORS = (ValueError, KeyError, TypeError, UnicodeDecodeError, pdftext.PdfTextError)

MONTHS = {
    name: i + 1
    for i, name in enumerate((
        "januari", "februari", "mars", "april", "maj", "juni",
        "juli", "augusti", "september", "oktober", "november", "december",
    ))
}
_SV_DATE = re.compile(r"(\d{1,2})\s+(" + "|".join(MONTHS) + r")\s+(\d{4})", re.I)
_IN_FORCE = re.compile(r"(?:trädde|träder)\s+i\s+kraft\s+(?:för\s+Sveriges\s+del\s+)?(?:den\s+)?"
                       + _SV_DATE.pattern, re.I)
_NUMBER = re.compile(r"SÖ\s*(\d{4})\s*:\s*(\d{1,4})")
# `so-20233` is SÖ 2023:3: the slug gives the year when the page follows that form.
_SLUG_YEAR = re.compile(r"/so-((?:19|20)\d{2})\d{1,4}/?$")
_LOC = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>\s*(?:<lastmod>\s*([^<\s]+)\s*</lastmod>)?")
_TAG = re.compile(r"<[^>]+>")
_SPACE = re.compile(r"\s+")
_H1 = re.compile(r'<h1[^>]*id="h1id"[^>]*>(.*?)</h1>', re.S)
_SUB = re.compile(r'<span class="h1-sub">(.*?)</span>', re.S)
_VIGNETTE = re.compile(r'<span class="h1-vignette">(.*?)</span>', re.S)
_CATEGORIES = re.compile(r'<div class="categories-text">(.*?)</div>', re.S)
_INGRESS = re.compile(r'<p class="ingress[^"]*">(.*?)</p>', re.S)
_DOWNLOADS = re.compile(r'<p class="h4">\s*Ladda ner:\s*</p>(.*?)</div>\s*</div>', re.S)
_LINK = re.compile(r'<a\s[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.S)
_MINISTRY = re.compile(r"\b(\w+departementet|Statsrådsberedningen)\b")


class ListingError(Exception):
    """robots.txt or the sitemap could not be read; the run cannot continue."""


# --- parsing ---------------------------------------------------------------


def _text(fragment):
    return _SPACE.sub(" ", html.unescape(_TAG.sub(" ", fragment or "")).replace("\xa0", " ")).strip()


def swedish_date(text):
    """The first `12 juli 2023` in `text` as `2023-07-12`, or None."""
    match = _SV_DATE.search(text or "")
    if not match:
        return None
    day, month, year = match.groups()
    try:
        return date(int(year), MONTHS[month.lower()], int(day)).isoformat()
    except ValueError:
        return None


def in_force(text):
    match = _IN_FORCE.search(text or "")
    return swedish_date(match.group(0)) if match else None


def parse_sitemap(raw):
    """URL -> lastmod (or None) of the SÖ pages in the sitemap, the section page itself left out."""
    out = {}
    for url, lastmod in _LOC.findall(raw.decode("utf-8", errors="replace")):
        url = html.unescape(url)
        parts = urllib.parse.urlsplit(url)
        if parts.hostname == HOST and parts.path.startswith(SECTION) and parts.path != SECTION:
            out[url] = lastmod or None
    return out


def slug_year(url):
    match = _SLUG_YEAR.search(urllib.parse.urlsplit(url).path)
    return int(match.group(1)) if match else None


def _on_site(url):
    parts = urllib.parse.urlsplit(url)
    return parts.scheme == "https" and parts.hostname == HOST


@dataclass
class Page:
    url: str
    title: str
    number: "str | None"
    signed: "str | None"
    place_date: str
    ministry: "str | None"
    note: str
    pdfs: "list[tuple[str, str]]"


def parse_page(raw, url):
    """The SÖ page's fields; `number` is None for pages without an SÖ number."""
    h1 = _H1.search(raw)
    if not h1:
        raise ValueError("no heading on the page")
    heading = h1.group(1)
    sub = _SUB.search(heading)
    vignette = _VIGNETTE.search(heading)
    title = _text(_SUB.sub("", _VIGNETTE.sub("", heading)))
    place_date = _text(sub.group(1)) if sub else ""
    number = None
    match = _NUMBER.search(_text(vignette.group(1)) if vignette else "") or _NUMBER.search(title)
    if match:
        number = f"SÖ {match.group(1)}:{int(match.group(2))}"
    categories = _CATEGORIES.search(raw)
    ministry = _MINISTRY.search(_text(categories.group(1))) if categories else None
    ingress = _INGRESS.search(raw)
    pdfs = []
    downloads = _DOWNLOADS.search(raw)
    for href, label in _LINK.findall(downloads.group(1) if downloads else ""):
        link = urllib.parse.urljoin(url, html.unescape(href))
        if _on_site(link) and urllib.parse.urlsplit(link).path.startswith("/contentassets/"):
            pdfs.append((link, _text(label)))
    if not title:
        raise ValueError("empty title")
    return Page(
        url=url,
        title=title,
        number=number,
        signed=swedish_date(place_date),
        place_date=place_date,
        ministry=ministry.group(1) if ministry else None,
        note=_text(ingress.group(1)) if ingress else "",
        pdfs=list(dict.fromkeys(pdfs)),
    )


def corpus_id(number):
    """`SÖ 2023:3` -> `so-2023-3`."""
    year, ordinal = number[3:].split(":")
    return f"so-{year}-{ordinal}"


def year_of(number):
    return int(number[3:7])


# --- documents -------------------------------------------------------------


def build_meta(page, source_sha256, fetched_at):
    return {
        "id": corpus_id(page.number),
        "title": page.title,
        "type": TYPE,
        "layer": TYPES[TYPE],
        "number": page.number,
        "issued": page.signed,
        "in_force": in_force(page.note),
        "repealed": None,
        "amended_by": [],
        "amended_through": None,
        "reprinted_by": [],
        "ministry": page.ministry,
        "eli": None,
        "language": "sv",
        # The text is extracted from the PDF, not tied to a verified snapshot of the print.
        "authoritative": False,
        "source": page.url,
        "source_sha256": source_sha256,
        "fetched_at": fetched_at,
    }


def to_markdown(page, texts):
    """Heading, signature, note, PDF links and, where extracted, the text of each PDF.

    `texts` maps a PDF URL to its paragraphs, or to None when no text was extracted.
    """
    lines = [f"Undertecknad: {page.place_date}"] if page.place_date else []
    lines.append(page.number)
    blocks = [f"# {page.title}", "  \n".join(lines)]
    if page.note:
        blocks.append(page.note)
    if page.pdfs:
        blocks.append("\n".join(f"- [{label or 'PDF'}]({url})" for url, label in page.pdfs))
    for url, label in page.pdfs:
        paragraphs = texts.get(url)
        if paragraphs:
            if len(page.pdfs) > 1:
                blocks.append(f"## {label or 'PDF'}")
            blocks.extend(p.replace("\n", " ") for p in paragraphs)
    return "\n\n".join(b for b in blocks if b) + "\n"


def page_sha256(page):
    """SHA-256 of the page fields the document is built from (the HTML carries volatile parts)."""
    data = json.dumps([page.title, page.number, page.place_date, page.ministry, page.note, page.pdfs],
                      ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(data.encode()).hexdigest()


# --- state and manifest ----------------------------------------------------


def load_manifest(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError):
        raise StateError(f"manifest corrupt: {path}") from None
    if not isinstance(data, dict) or not isinstance(data.get("entries"), list):
        raise StateError(f"manifest corrupt: {path}")
    return {e["number"]: e for e in data["entries"]}


def _number_key(number):
    year, ordinal = number[3:].split(":")
    return int(year), int(ordinal)


def save_manifest(path, entries):
    _save_state(path, {
        "version": MANIFEST_VERSION,
        "source": BASE + SECTION,
        "entries": [entries[n] for n in sorted(entries, key=_number_key)],
    })


# --- run -------------------------------------------------------------------


@dataclass
class RunSummary:
    written: "list[str]" = field(default_factory=list)
    unchanged: "list[str]" = field(default_factory=list)
    skipped: int = 0
    excluded: "list[str]" = field(default_factory=list)
    failed: "list[str]" = field(default_factory=list)
    text_gaps: "list[str]" = field(default_factory=list)
    blocked: bool = False


def _year(value):
    year = int(value)
    if not 1800 <= year <= 2100:
        raise argparse.ArgumentTypeError(f"not a plausible year: {value}")
    return year


def _day(value):
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected YYYY-MM-DD: {value}") from None


def _rate(value):
    rate = float(value)
    if rate < 1.0:
        raise argparse.ArgumentTypeError(f"must be at least 1 second: {value}")
    return rate


def _non_negative(value):
    number = int(value)
    if number < 0:
        raise argparse.ArgumentTypeError(f"must not be negative: {value}")
    return number


def parse_args(argv):
    parser = argparse.ArgumentParser(prog="collect.py so")
    parser.add_argument("--from-year", type=_year, help="only SÖ numbers from this year on")
    parser.add_argument("--to-year", type=_year, help="only SÖ numbers up to this year")
    parser.add_argument("--text-from-year", type=_year, default=DEFAULT_TEXT_FROM_YEAR,
                        help=f"extract the PDF text from this SÖ year on (default {DEFAULT_TEXT_FROM_YEAR})")
    parser.add_argument("--url", action="append", metavar="URL", help="collect only these SÖ pages")
    parser.add_argument("--changed-since", type=_day, metavar="YYYY-MM-DD",
                        help="only pages whose sitemap lastmod is on or after this day (weekly sync)")
    parser.add_argument("--refresh", action="store_true", help="refetch pages already collected")
    parser.add_argument("--limit", type=_non_negative, help="stop after N written documents")
    parser.add_argument("--report", metavar="FILE", help="write a JSON run report")
    parser.add_argument("--rate", type=_rate, default=1.0, metavar="SECONDS")
    parser.add_argument("--state", default=DEFAULT_STATE)
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST)
    parser.add_argument("--corpus", default="corpus")
    return parser.parse_args(argv)


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Robots:
    def __init__(self, client):
        self.parser = urllib.robotparser.RobotFileParser()
        try:
            raw = client.get(ROBOTS_URL)
        except urllib.error.HTTPError as error:
            if error.code != 404:
                raise ListingError(f"robots.txt: HTTP {error.code}") from error
            raw = b""
        except NETWORK_ERRORS as error:
            raise ListingError(f"robots.txt: {error}") from error
        self.parser.parse(raw.decode("utf-8", errors="replace").splitlines())

    def allows(self, url):
        return self.parser.can_fetch(USER_AGENT, url)


def _get(client, robots, url):
    if not _on_site(url):
        raise ValueError(f"refusing to leave {HOST}: {url}")
    if not robots.allows(url):
        raise Blocked(f"robots.txt disallows {url}")
    return client.get(url)


def _in_range(year, args):
    return year is None or ((args.from_year is None or year >= args.from_year)
                            and (args.to_year is None or year <= args.to_year))


def _stored(meta, corpus):
    try:
        return frontmatter.load(path_for(meta, corpus).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None, None


def _extract(client, robots, page, args, manifest, summary):
    """PDF URL -> paragraphs (None when not extracted); records each downloaded PDF in the manifest."""
    texts = {}
    if year_of(page.number) < args.text_from_year:
        return texts
    entries = []
    for url, label in page.pdfs:
        data = _get(client, robots, url)
        result = pdftext.extract(data)
        gap = result.gap
        if gap is None:
            paragraphs = pdftext.paragraphs(result.text)
            found = personal_numbers("\n".join(paragraphs))
            if found:
                raise ValueError(f"possible personal identity number in {url} ({len(found)} found)")
            texts[url] = paragraphs
        else:
            texts[url] = None
            summary.text_gaps.append(page.number)
        entries.append({"url": url, "label": label, "bytes": len(data),
                        "sha256": hashlib.sha256(data).hexdigest(), "pages": result.pages,
                        "text": "extracted" if gap is None else gap})
    manifest[page.number] = {"number": page.number, "page": page.url, "pdfs": entries, "retrieved_at": _now()}
    return texts


def _store(client, robots, url, args, manifest, owners, summary):
    """Fetch one page; returns (SÖ number or None, "written" | "unchanged" | "excluded" | "out_of_range")."""
    page = parse_page(_get(client, robots, url).decode("utf-8"), url)
    if page.number is None:
        return None, "excluded"
    if not _in_range(year_of(page.number), args):
        return page.number, "out_of_range"
    other = owners.get(page.number)
    if other and other != url:
        raise ValueError(f"{page.number} is already stored from {other}")
    owners[page.number] = url
    texts = _extract(client, robots, page, args, manifest, summary)
    meta = build_meta(page, page_sha256(page), _now())
    body = to_markdown(page, texts)
    stored, stored_body = _stored(meta, args.corpus)
    if stored is not None:
        if stored_body == body and {k: v for k, v in stored.items() if k != "fetched_at"} == {
                k: v for k, v in meta.items() if k != "fetched_at"}:
            return page.number, "unchanged"
    write(meta, body, args.corpus)
    return page.number, "written"


def _write_report(path, summary):
    report = {
        "written": summary.written,
        "unchanged": summary.unchanged,
        "skipped": summary.skipped,
        "excluded": len(summary.excluded),
        "failed": summary.failed,
        "text_gaps": summary.text_gaps,
        "blocked": summary.blocked,
    }
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run(client, args):
    summary = RunSummary()
    state = _load_state(args.state)
    manifest = load_manifest(args.manifest)
    state["blocked"] = None
    # SÖ number -> page URL, so that two pages never write the same document.
    owners = {v: k for k, v in state["done"].items() if v.startswith("SÖ ")}

    def finish(blocked=None):
        if blocked:
            summary.blocked = True
            state["blocked"] = blocked
        _save_state(args.state, state)
        save_manifest(args.manifest, manifest)
        if args.report:
            _write_report(args.report, summary)
        return summary

    try:
        robots = Robots(client)
        if args.url:
            pages = {u: None for u in args.url}
        else:
            if not robots.allows(SITEMAP_URL):
                return finish("robots.txt disallows the sitemap")
            try:
                pages = parse_sitemap(client.get(SITEMAP_URL))
            except NETWORK_ERRORS as error:
                raise ListingError(f"sitemap: {error}") from error
        for url in sorted(pages):
            if args.limit is not None and len(summary.written) >= args.limit:
                break
            if not _in_range(slug_year(url), args):
                continue
            if args.changed_since and (pages[url] or "")[:10] < args.changed_since:
                continue
            if url in state["done"] and not args.refresh and not args.changed_since:
                summary.skipped += 1
                continue
            try:
                number, status = _store(client, robots, url, args, manifest, owners, summary)
            except Blocked:
                raise
            except (*NETWORK_ERRORS, *DOCUMENT_ERRORS) as error:
                summary.failed.append(url)
                state["failed"][url] = f"{type(error).__name__}: {error}"
                continue
            state["failed"].pop(url, None)
            if status == "excluded":
                summary.excluded.append(url)
                state["done"][url] = "excluded: no SÖ number"
                continue
            if status == "out_of_range":
                continue
            (summary.written if status == "written" else summary.unchanged).append(number)
            state["done"][url] = number
            if status == "written" and len(summary.written) % 50 == 0:
                _save_state(args.state, state)
                save_manifest(args.manifest, manifest)
                print(f"{len(summary.written)} written", flush=True)
    except Blocked as error:
        return finish(str(error))
    except ListingError:
        finish()
        raise
    return finish()


def main(argv, client=None):
    if argv and argv[0] == "so":
        argv = argv[1:]
    args = parse_args(argv)
    if client is None:
        client = PoliteClient(USER_AGENT, min_interval=args.rate)
    try:
        summary = run(client, args)
    except (ListingError, StateError) as error:
        print(f"error: {error}", file=sys.stderr, flush=True)
        return 1
    print(
        f"done: {len(summary.written)} written, {len(summary.unchanged)} unchanged, "
        f"{summary.skipped} skipped, {len(summary.excluded)} excluded, {len(summary.failed)} failed, "
        f"{len(summary.text_gaps)} without text" + (", BLOCKED" if summary.blocked else ""),
        flush=True,
    )
    if summary.failed:
        print("failed: " + ", ".join(summary.failed), flush=True)
    if summary.blocked:
        print("blocked: see state file", file=sys.stderr)
        return 2
    return 0
