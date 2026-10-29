"""Resumable collector for the county regulations (länets författningssamling).

Source: the shared Sitevision site of the county administrative boards,
https://www.lansstyrelsen.se. Each county has a landing page that links one
index page per year; each index entry links a detail page carrying the number,
the publication note ("Utkom från trycket den …"), the title, the text as HTML
and a link to the printed PDF under /download/. There is no API or open data
set, and the texts are free of copyright (9 § upphovsrättslagen).

The body is taken from the HTML text on the detail page; the PDFs are never
parsed. Each linked PDF is downloaded once to record its size and SHA-256 in a
committed manifest (`sources/county-pdf-manifest.json`); the bytes are not kept.
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

from . import frontmatter, htmlmd
from .caselaw import NETWORK_ERRORS, StateError, _load_state, _save_state, personal_numbers
from .http import Blocked, PoliteClient
from .vocabulary import TYPES
from .writer import existing_path, path_for, write

USER_AGENT = "lagar-collector/0.1 (+https://github.com/jacksonmafra-umain/lagar)"
BASE = "https://www.lansstyrelsen.se"
HOST = urllib.parse.urlsplit(BASE).netloc
ROBOTS_URL = BASE + "/robots.txt"
LANDING_URL = BASE + "/{slug}/om-oss/om-lansstyrelsen-{slug}/lanets-forfattningssamling.html"
DEFAULT_STATE = "collector/data/county-state.json"
DEFAULT_MANIFEST = "sources/county-pdf-manifest.json"
MANIFEST_VERSION = 1
TYPE = "county_regulation"

# county code -> (site slug, county name). Only Stockholm (01) has been checked
# against the live site; the landing URL of the others follows the same pattern
# and can be overridden with --landing-url.
COUNTIES = {
    "01": ("stockholm", "Stockholms län"),
    "03": ("uppsala", "Uppsala län"),
    "04": ("sodermanland", "Södermanlands län"),
    "05": ("ostergotland", "Östergötlands län"),
    "06": ("jonkoping", "Jönköpings län"),
    "07": ("kronoberg", "Kronobergs län"),
    "08": ("kalmar", "Kalmar län"),
    "09": ("gotland", "Gotlands län"),
    "10": ("blekinge", "Blekinge län"),
    "12": ("skane", "Skåne län"),
    "13": ("halland", "Hallands län"),
    "14": ("vastra-gotaland", "Västra Götalands län"),
    "17": ("varmland", "Värmlands län"),
    "18": ("orebro", "Örebro län"),
    "19": ("vastmanland", "Västmanlands län"),
    "20": ("dalarna", "Dalarnas län"),
    "21": ("gavleborg", "Gävleborgs län"),
    "22": ("vasternorrland", "Västernorrlands län"),
    "23": ("jamtland", "Jämtlands län"),
    "24": ("vasterbotten", "Västerbottens län"),
    "25": ("norrbotten", "Norrbottens län"),
}

MONTHS = {
    name: i + 1
    for i, name in enumerate((
        "januari", "februari", "mars", "april", "maj", "juni",
        "juli", "augusti", "september", "oktober", "november", "december",
    ))
}

DOCUMENT_ERRORS = (ValueError, KeyError, UnicodeDecodeError)

_NUMBER = re.compile(r"(\d{2})\s*FS\s+(\d{4})\s*:\s*0*(\d+)", re.IGNORECASE)
_YEAR_LINK = re.compile(r"""href="([^"]*/lanets-forfattningssamling/forfattningar-(\d{4})\.html)\"""")
_ITEM = re.compile(r'<li class="sv-channel-item[^"]*"[^>]*>(.*?)</li>', re.S)
_ITEM_LINK = re.compile(r'<h2[^>]*>\s*<a href="([^"]+)"[^>]*>(.*?)</a>', re.S)
_INGRESS = re.compile(r'<span class="sv-font-ingress">(.*?)</span>', re.S)
_DIV = re.compile(r"<(/?)div\b[^>]*>", re.I)
_PARAGRAPH = re.compile(r"<p\b[^>]*>.*?</p>", re.S | re.I)
_PDF_LINK = re.compile(r'<a\b[^>]*href="([^"]+\.pdf)"[^>]*>(.*?)</a>', re.S | re.I)
_ASSISTIVE = re.compile(r'<span class="env-assistive-text">.*?</span>|<svg\b.*?</svg>', re.S | re.I)
_TAG = re.compile(r"<[^>]+>")
_SPACE = re.compile(r"\s+")
_SV_DATE = re.compile(r"(\d{1,2}) (" + "|".join(MONTHS) + r") (\d{4})", re.I)
_PUBLISHED = re.compile(r"Utkom från trycket\s+(?:den\s+)?" + _SV_DATE.pattern, re.I)
_DECIDED = re.compile(r"Beslut(?:at|ad|ade)\s+(?:den\s+)?" + _SV_DATE.pattern, re.I)
_IN_FORCE = re.compile(r"träder i kraft\s+(?:den\s+)?" + _SV_DATE.pattern, re.I)


class ListingError(Exception):
    """robots.txt, the landing page or a year index could not be read."""


@dataclass
class ListingItem:
    number: str
    url: str
    published: "str | None" = None
    title: "str | None" = None


@dataclass
class Detail:
    number: str
    title: "str | None"
    published: "str | None"
    decided: "str | None"
    text_html: str
    pdfs: "list[tuple[str, str]]"
    canonical: bytes


@dataclass
class RunSummary:
    written: int = 0
    unchanged: int = 0
    skipped: int = 0
    failed: "list[str]" = field(default_factory=list)
    blocked: bool = False
    written_numbers: "list[str]" = field(default_factory=list)


# --- text helpers ----------------------------------------------------------


def _text(fragment):
    return _SPACE.sub(" ", html.unescape(_TAG.sub(" ", fragment or "")).replace("\xa0", " ")).strip()


def swedish_date(match):
    """`16 februari 2026` (groups day, month, year) -> `2026-02-16`, or None."""
    day, month, year = match.groups()[-3:]
    try:
        return date(int(year), MONTHS[month.lower()], int(day)).isoformat()
    except (ValueError, KeyError):
        return None


def _find_date(pattern, text):
    match = pattern.search(text or "")
    return swedish_date(match) if match else None


def normalise_number(raw, region_code=None):
    """`01FS 2026:01` -> `01FS 2026:1`; raises ValueError when not a county number."""
    match = _NUMBER.search(raw or "")
    if not match:
        raise ValueError(f"not a county regulation number: {raw!r}")
    code, year, ordinal = match.groups()
    if region_code is not None and code != region_code:
        raise ValueError(f"{raw!r} is not in the {region_code}FS series")
    return f"{code}FS {year}:{int(ordinal)}"


def corpus_id(number):
    """`01FS 2026:1` -> `01fs-2026-1`."""
    return re.sub(r"[^0-9a-z]+", "-", number.lower()).strip("-")


def number_key(number):
    match = _NUMBER.fullmatch(number)
    if not match:
        return ("", sys.maxsize, sys.maxsize, number)
    code, year, ordinal = match.groups()
    return (code, int(year), int(ordinal), number)


def issuer(region_code):
    return "Länsstyrelsen i " + COUNTIES[region_code][1]


# --- parsing ---------------------------------------------------------------


def _on_site(url):
    parts = urllib.parse.urlsplit(url)
    return parts.scheme == "https" and parts.netloc == HOST


def parse_landing(page, page_url):
    """Year index URLs linked from a county landing page, as {year: url}."""
    years = {}
    for href, year in _YEAR_LINK.findall(page):
        url = urllib.parse.urljoin(page_url, html.unescape(href))
        if _on_site(url):
            years[int(year)] = url
    return years


def parse_year(page, page_url, region_code):
    """Entries of a year index page, in page order."""
    items = []
    for chunk in _ITEM.findall(page):
        link = _ITEM_LINK.search(chunk)
        if not link:
            continue
        number = normalise_number(_text(link.group(2)), region_code)
        ingress = [_text(s) for s in _INGRESS.findall(chunk)]
        ingress = [s for s in ingress if s]
        published = next((d for d in (_find_date(_PUBLISHED, s) for s in ingress) if d), None)
        title = next((s for s in ingress if not _PUBLISHED.search(s)), None)
        url = urllib.parse.urljoin(page_url, html.unescape(link.group(1)))
        items.append(ListingItem(number, url, published, title))
    return items


def portlet(page, marker):
    """Inner HTML of the text portlet that follows `<div id="{marker}">`, or None."""
    start = page.find(f'<div id="{marker}">')
    if start < 0:
        return None
    open_tag = page.find('<div class="sv-text-portlet-content">', start)
    if open_tag < 0:
        return None
    content_start = page.find(">", open_tag) + 1
    depth = 1
    for match in _DIV.finditer(page, content_start):
        depth += -1 if match.group(1) else 1
        if depth == 0:
            return page[content_start:match.start()]
    return None


def parse_detail(page, page_url, region_code):
    heading = portlet(page, "Rubrik")
    if heading is None:
        raise ValueError("detail page has no heading")
    number = normalise_number(_text(heading), region_code)
    ingress = portlet(page, "Ingress") or ""
    text = portlet(page, "Text") or ""
    paragraphs = [_text(p) for p in _PARAGRAPH.findall(ingress)]
    published = next((d for d in (_find_date(_PUBLISHED, p) for p in paragraphs) if d), None)
    title = next((p for p in paragraphs if p and not _PUBLISHED.search(p)), None)
    # Paragraphs made only of PDF links are the regulation's own printed
    # versions; PDF links inside running text point at other regulations and
    # stay in the body as plain text.
    pdfs = []
    body_html = _ASSISTIVE.sub("", text)
    for para in _PARAGRAPH.findall(body_html):
        links = _PDF_LINK.findall(para)
        if not links or _text(_PDF_LINK.sub("", para)):
            continue
        for href, label in links:
            url = urllib.parse.urljoin(page_url, html.unescape(href))
            pdfs.append((url, _text(label) or url.rsplit("/", 1)[-1]))
        body_html = body_html.replace(para, "", 1)
    if not paragraphs and not _text(body_html) and not pdfs:
        raise ValueError("detail page has no content")
    canonical = "\n".join((heading, ingress, text)).encode("utf-8")
    return Detail(
        number=number,
        title=title,
        published=published,
        decided=_find_date(_DECIDED, _text(body_html)),
        text_html=body_html,
        pdfs=pdfs,
        canonical=canonical,
    )


# --- mapping ---------------------------------------------------------------


def _in_force(text):
    found = {swedish_date(m) for m in _IN_FORCE.finditer(text)} - {None}
    return found.pop() if len(found) == 1 else None


def build_meta(detail, item, region_code, fetched_at):
    title = (detail.title or item.title or detail.number).rstrip(". ")
    return {
        "id": corpus_id(detail.number),
        "title": title,
        "type": TYPE,
        "layer": TYPES[TYPE],
        "number": detail.number,
        "issued": detail.decided or detail.published or item.published,
        "in_force": _in_force(htmlmd.to_markdown(detail.text_html)),
        "repealed": None,
        "amended_by": [],
        "amended_through": None,
        "reprinted_by": [],
        "ministry": None,
        "eli": None,
        "language": "sv",
        "authoritative": False,
        "source": item.url,
        "source_sha256": hashlib.sha256(detail.canonical).hexdigest(),
        "fetched_at": fetched_at,
        "issuer": issuer(region_code),
        "court": None,
        "ecli": None,
        "celex": None,
        "region_code": region_code,
        "municipality_code": None,
    }


def to_markdown(meta, detail):
    published = detail.published
    facts = [
        ("Författningssamling", meta["number"]),
        ("Utkom från trycket", published),
        ("Beslutad", detail.decided),
        ("Ikraftträdande", meta["in_force"]),
        ("Utfärdare", meta["issuer"]),
    ]
    blocks = ["# " + meta["title"], "  \n".join(f"{k}: {v}" for k, v in facts if v)]
    text = htmlmd.to_markdown(detail.text_html, heading_offset=1)
    if text:
        blocks.append(text)
    else:
        blocks.append("Författningen publiceras bara som pdf.")
    if detail.pdfs:
        blocks.append("## Tryckt version")
        blocks.append(
            "Den tryckta författningen i länets författningssamling (pdf):\n\n"
            + "\n".join(f"- [{label}]({url})" for url, label in detail.pdfs)
        )
    return "\n\n".join(b for b in blocks if b) + "\n"


# --- manifest --------------------------------------------------------------


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
    _save_state(path, {
        "version": MANIFEST_VERSION,
        "source": BASE,
        "entries": [entries[n] for n in sorted(entries, key=number_key)],
    })


# --- network ---------------------------------------------------------------


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


def _get_page(client, robots, url, what):
    if not _on_site(url):
        raise ListingError(f"{what} leaves {HOST}: {url}")
    if not robots.allows(url):
        raise Blocked(f"robots.txt disallows {url}")
    try:
        return client.get(url).decode("utf-8")
    except Blocked:
        raise
    except (*NETWORK_ERRORS, UnicodeDecodeError) as error:
        raise ListingError(f"{what}: {error}") from error


def _candidates(client, robots, args):
    landing = args.landing_url or LANDING_URL.format(slug=COUNTIES[args.county][0])
    years = parse_landing(_get_page(client, robots, landing, "landing page"), landing)
    if not years:
        raise ListingError(f"no year index linked from {landing}")
    wanted = sorted(
        (y for y in years if (args.from_year is None or y >= args.from_year)
         and (args.to_year is None or y <= args.to_year)),
        reverse=args.newest_first,
    )
    for year in wanted:
        page = _get_page(client, robots, years[year], f"year {year} index")
        try:
            items = parse_year(page, years[year], args.county)
        except ValueError as error:
            raise ListingError(f"year {year} index: {error}") from error
        items.sort(key=lambda i: number_key(i.number), reverse=args.newest_first)
        yield from items


def _hash_pdfs(client, robots, detail, download):
    files = []
    for url, _label in detail.pdfs:
        entry = {"url": url, "bytes": None, "sha256": None, "content_type": None, "retrieved_at": None}
        if download and _on_site(url) and robots.allows(url):
            body, content_type = client.fetch(url)
            if not body.startswith(b"%PDF-"):
                raise ValueError(f"not a PDF ({content_type}): {url}")
            entry.update(
                bytes=len(body),
                sha256=hashlib.sha256(body).hexdigest(),
                content_type=content_type,
                retrieved_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            )
        files.append(entry)
    return files


def _unchanged(meta, body, corpus):
    try:
        stored, stored_body = frontmatter.load(path_for(meta, corpus).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    stored.pop("fetched_at", None)
    return stored_body == body and stored == {k: v for k, v in meta.items() if k != "fetched_at"}


def _store(client, robots, item, args, manifest):
    """Fetch, map and write one regulation; returns (meta, written)."""
    if not _on_site(item.url):
        raise ValueError(f"detail page is not on {HOST}: {item.url}")
    if not robots.allows(item.url):
        raise Blocked(f"robots.txt disallows {item.url}")
    detail = parse_detail(client.get(item.url).decode("utf-8"), item.url, args.county)
    if detail.number != item.number:
        raise ValueError(f"detail page shows {detail.number}, expected {item.number}")
    fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    meta = build_meta(detail, item, args.county, fetched_at)
    other = existing_path(meta["id"], args.corpus)
    if other is not None and other != path_for(meta, args.corpus):
        raise ValueError(f"{meta['number']} is already stored as {other}")
    body = to_markdown(meta, detail)
    found = personal_numbers(body)
    if found:
        raise ValueError(f"possible personal identity number in the text ({len(found)} found)")
    stored = manifest.get(meta["number"])
    stored_urls = [f["url"] for f in (stored or {}).get("files", [])]
    if stored is None or stored_urls != [u for u, _ in detail.pdfs] or (
        args.pdf and any(f.get("sha256") is None for f in stored["files"])
    ):
        manifest[meta["number"]] = {
            "number": meta["number"],
            "detail_url": item.url,
            "published": detail.published or item.published,
            "files": _hash_pdfs(client, robots, detail, args.pdf),
        }
    if _unchanged(meta, body, args.corpus):
        return meta, False
    write(meta, body, args.corpus)
    return meta, True


def _already_done(state, item, corpus):
    if item.number not in state["done"]:
        return False
    return path_for({"id": corpus_id(item.number), "type": TYPE}, corpus).exists()


def _write_report(path, summary):
    report = {
        "written": summary.written_numbers,
        "unchanged": summary.unchanged,
        "skipped": summary.skipped,
        "failed": summary.failed,
        "blocked": summary.blocked,
    }
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


# --- run -------------------------------------------------------------------


def _county(value):
    code = value.strip().zfill(2)
    if code.upper().endswith("FS"):
        code = code[:-2]
    if code not in COUNTIES:
        raise argparse.ArgumentTypeError(
            f"not a county code ({', '.join(COUNTIES)}): {value}"
        )
    return code


def _year(value):
    number = int(value)
    if not 1900 <= number <= 2999:
        raise argparse.ArgumentTypeError(f"not a year: {value}")
    return number


def _non_negative(value):
    number = int(value)
    if number < 0:
        raise argparse.ArgumentTypeError(f"must not be negative: {value}")
    return number


def _rate(value):
    seconds = float(value)
    if seconds < 1.0:
        raise argparse.ArgumentTypeError(f"must be at least 1 second: {value}")
    return seconds


def parse_args(argv):
    parser = argparse.ArgumentParser(prog="collect.py county")
    parser.add_argument(
        "--county", "--region", dest="county", type=_county, required=True, metavar="CODE",
        help="county code, 01 (Stockholm) to 25 (Norrbotten)",
    )
    parser.add_argument("--from-year", type=_year, metavar="YYYY")
    parser.add_argument("--to-year", type=_year, metavar="YYYY")
    parser.add_argument(
        "--newest-first", action="store_true",
        help="walk years and numbers from the newest (default: oldest first)",
    )
    parser.add_argument("--limit", type=_non_negative, help="stop after N written documents")
    parser.add_argument("--report", metavar="FILE", help="write a JSON run report")
    parser.add_argument(
        "--no-pdf", dest="pdf", action="store_false",
        help="record PDF links without downloading them to hash",
    )
    parser.add_argument("--landing-url", help="override the county's landing page URL")
    parser.add_argument("--rate", type=_rate, default=1.0, metavar="SECONDS")
    parser.add_argument("--state", default=DEFAULT_STATE)
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST)
    parser.add_argument("--corpus", default="corpus")
    args = parser.parse_args(argv)
    if args.from_year and args.to_year and args.from_year > args.to_year:
        parser.error("--from-year is after --to-year")
    return args


def run(client, args):
    summary = RunSummary()
    state = _load_state(args.state)
    state["blocked"] = None
    manifest = load_manifest(args.manifest)

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
        for item in _candidates(client, robots, args):
            if args.limit is not None and summary.written >= args.limit:
                break
            if _already_done(state, item, args.corpus):
                summary.skipped += 1
                continue
            try:
                meta, changed = _store(client, robots, item, args, manifest)
            except (*DOCUMENT_ERRORS, *NETWORK_ERRORS) as error:
                summary.failed.append(item.number)
                state["failed"][item.number] = f"{type(error).__name__}: {error}"
            else:
                if changed:
                    summary.written += 1
                    summary.written_numbers.append(meta["number"])
                else:
                    summary.unchanged += 1
                state["done"][item.number] = meta["source_sha256"]
                state["failed"].pop(item.number, None)
            _save_state(args.state, state)
            save_manifest(args.manifest, manifest)
    except Blocked as error:
        return finish(str(error))
    return finish()


def main(argv, client=None):
    if argv and argv[0] == "county":
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
        f"done: {summary.written} written, {summary.unchanged} unchanged, "
        f"{summary.skipped} skipped, {len(summary.failed)} failed"
        + (", BLOCKED" if summary.blocked else ""),
        flush=True,
    )
    if summary.failed:
        print("failed: " + ", ".join(summary.failed), flush=True)
    if summary.blocked:
        print("blocked: see state file", file=sys.stderr)
        return 2
    return 0
