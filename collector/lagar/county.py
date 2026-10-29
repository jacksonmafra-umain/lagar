"""Resumable collector for the county regulations (länets författningssamling).

Source: the shared Sitevision site of the county administrative boards,
https://www.lansstyrelsen.se. There is no API or open data set, and the texts
are free of copyright (9 § upphovsrättslagen). The counties publish their
collections in two layouts, configured per county in
`collector/data/counties.json`:

- `pages`: the landing page links one index page per year; each index entry
  links a detail page carrying the number, the publication note ("Utkom från
  trycket den …"), the title, the text as HTML and a link to the printed PDF.
  The body is taken from the HTML text; the PDFs are never parsed.
- `files`: the landing page lists the printed PDFs only, as plain links or in
  Sitevision's file-share module (either the files themselves or one folder per
  year, whose listing is read from the module's JSON endpoint). The number and
  title come from the link text or file name; the document records the
  metadata and links to the PDF.

Each linked PDF is downloaded once to record its size and SHA-256 in a
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
DEFAULT_CONFIG = str(Path(__file__).resolve().parents[1] / "data" / "counties.json")
DEFAULT_STATE = "collector/data/county-state.json"
DEFAULT_MANIFEST = "sources/county-pdf-manifest.json"
MANIFEST_VERSION = 1
TYPE = "county_regulation"

# county code -> county name. Landing pages and layouts live in DEFAULT_CONFIG.
COUNTIES = {
    "01": "Stockholms län",
    "03": "Uppsala län",
    "04": "Södermanlands län",
    "05": "Östergötlands län",
    "06": "Jönköpings län",
    "07": "Kronobergs län",
    "08": "Kalmar län",
    "09": "Gotlands län",
    "10": "Blekinge län",
    "12": "Skåne län",
    "13": "Hallands län",
    "14": "Västra Götalands län",
    "17": "Värmlands län",
    "18": "Örebro län",
    "19": "Västmanlands län",
    "20": "Dalarnas län",
    "21": "Gävleborgs län",
    "22": "Västernorrlands län",
    "23": "Jämtlands län",
    "24": "Västerbottens län",
    "25": "Norrbottens län",
}
LAYOUTS = ("pages", "files")

# File names and link texts of the `files` layout: "04FS 2026-1 …", "22 FS 2026-1 …",
# "18FS2025 1 …", "FS 2026-01 …" (Skåne prints no county code). Counties that print
# the number differently configure their own `number_patterns`.
DEFAULT_NUMBER_PATTERNS = (
    r"(?<![0-9])(?:(?P<code>[0-9]{2})\s*)?FS\s*(?P<year>(?:19|20)[0-9]{2})\s*[-:_. ]\s*0*(?P<n>[0-9]{1,3})(?![0-9])",
)

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
_PAGE_ID = re.compile(r"pageId:\s*'(4\.[0-9a-f]+)'")
_APP_STATE = re.compile(r"registerInitialState\('(12\.[0-9a-f]+)',(\{.*?\})\);</script>", re.S)
_SCRIPT = re.compile(r"<script\b.*?</script>", re.S | re.I)
_DOWNLOAD_LINK = re.compile(r'<a\b[^>]*href="(/download/[^"]+\.pdf)"[^>]*>(.*?)</a>', re.S | re.I)
# A paragraph right after the link's own paragraph describes it (Dalarna: title and decision date).
_LINK_NOTE = re.compile(r'\s*</p>\s*<p class="normal">(.*?)</p>', re.S)
_NOTE_DECIDED = re.compile(r"\s*Beslut(?:at|ad|ade)\b.*$", re.S | re.I)
_YEAR_FOLDER = re.compile(r"\s*((?:19|20)\d{2})\s*")
_ANY_YEAR = re.compile(r"(?<![0-9])((?:19|20)\d{2})(?![0-9])")
_REPEALED_MARK = re.compile(r"^\s*UPPHÄVD\b[\s:_-]*", re.I)
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
    files: "list[tuple[str, str]] | None" = None  # `files` layout: (PDF url, link text)
    marked_repealed: bool = False
    decided: "str | None" = None


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
    unnumbered: "list[str]" = field(default_factory=list)


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
    return "Länsstyrelsen i " + COUNTIES[region_code]


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


# --- configuration ---------------------------------------------------------


class ConfigError(Exception):
    """The county configuration is missing or malformed."""


def load_config(path):
    """{code: {"landing", "layout", "number_patterns", "title_strip"}} from the JSON config."""
    try:
        loaded = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ConfigError(f"county config unreadable: {path}: {error}") from None
    counties = loaded.get("counties") if isinstance(loaded, dict) else None
    if not isinstance(counties, dict):
        raise ConfigError(f"county config has no counties: {path}")
    config = {}
    for code, entry in counties.items():
        if code not in COUNTIES or not isinstance(entry, dict):
            raise ConfigError(f"county config: bad entry {code!r}")
        landing, layout = entry.get("landing"), entry.get("layout")
        if not isinstance(landing, str) or not _on_site(landing):
            raise ConfigError(f"county config: {code} landing must be on {HOST}")
        if layout not in LAYOUTS:
            raise ConfigError(f"county config: {code} layout must be one of {', '.join(LAYOUTS)}")
        try:
            patterns = [re.compile(p) for p in entry.get("number_patterns", DEFAULT_NUMBER_PATTERNS)]
            strip = [re.compile(p) for p in entry.get("title_strip", ())]
        except (re.error, TypeError) as error:
            raise ConfigError(f"county config: {code} pattern: {error}") from None
        for pattern in patterns:
            if not {"year", "n"} <= set(pattern.groupindex):
                raise ConfigError(f"county config: {code} number pattern needs groups year and n")
        config[code] = {"landing": landing, "layout": layout, "number_patterns": patterns, "title_strip": strip}
    return config


# --- `files` layout --------------------------------------------------------


def main_content(page):
    """The page's <main> element without scripts (the whole page when there is none)."""
    start = page.find("<main")
    end = page.find("</main>", start)
    body = page[start:end] if start >= 0 and end > start else page
    return _SCRIPT.sub("", body)


def parse_files_landing(page, page_url):
    """PDF links and year folders of a `files` landing page.

    Returns (links, folders): links as [(url, text, note)] from the file-share modules
    and the plain /download/ links of the main content, where note is the paragraph
    describing a plain link (or None); folders as {year: [url]}, the module's JSON
    endpoint listing that folder.
    """
    links, folders = [], {}
    page_id = _PAGE_ID.search(page)
    for portlet_id, raw in _APP_STATE.findall(page):
        try:
            state = json.loads(raw)
        except ValueError:
            continue
        files = state.get("files") if isinstance(state, dict) else None
        if not isinstance(files, list):
            continue
        for entry in files:
            if not isinstance(entry, dict) or not isinstance(entry.get("name"), str):
                continue
            if entry.get("isFolder"):
                year = _YEAR_FOLDER.fullmatch(entry["name"])
                if year and page_id and isinstance(entry.get("id"), str):
                    url = (f"{BASE}/appresource/{page_id.group(1)}/{portlet_id}/files?"
                           + urllib.parse.urlencode({"folderId": entry["id"]}))
                    folders.setdefault(int(year.group(1)), []).append(url)
            elif isinstance(entry.get("uri"), str):
                links.append((urllib.parse.urljoin(page_url, entry["uri"]), entry["name"], None))
    main = main_content(page)
    for match in _DOWNLOAD_LINK.finditer(main):
        note = _LINK_NOTE.match(main, match.end())
        note = _text(note.group(1)) if note and "/download/" not in note.group(1) else None
        url = urllib.parse.urljoin(page_url, html.unescape(match.group(1)))
        links.append((url, _text(_ASSISTIVE.sub("", match.group(2))), note or None))
    return [link for link in links if _on_site(link[0]) and link[0].lower().endswith(".pdf")], folders


def parse_folder(raw, page_url):
    """PDF links of one file-share folder (the module's JSON listing)."""
    state = json.loads(raw)
    files = state.get("files") if isinstance(state, dict) else None
    if not isinstance(files, list):
        raise ValueError("folder listing has no files")
    links = []
    for entry in files:
        if (isinstance(entry, dict) and not entry.get("isFolder")
                and isinstance(entry.get("name"), str) and isinstance(entry.get("uri"), str)):
            url = urllib.parse.urljoin(page_url, entry["uri"])
            if _on_site(url) and url.lower().endswith(".pdf"):
                links.append((url, entry["name"], None))
    return links


def _file_name(url):
    return urllib.parse.unquote(urllib.parse.urlsplit(url).path.rsplit("/", 1)[-1])


def file_number(text, url, region_code, patterns):
    """(number, matched text, source) for a link, trying its text and then the file name."""
    for source in (text, _file_name(url)):
        source = source.replace("\xa0", " ")
        for pattern in patterns:
            for match in pattern.finditer(source):
                code = match.groupdict().get("code")
                if code and code != region_code:
                    continue
                number = f"{region_code}FS {match.group('year')}:{int(match.group('n'))}"
                return number, match, source
    return None


def file_title(text, match, source, strip):
    """The link text without the number, the .pdf suffix and the repeal mark."""
    title = text
    if match is not None and source == text:
        title = text[:match.start()] + " " + text[match.end():]
    title = re.sub(r"\.pdf\s*$", "", title, flags=re.I)
    title = _REPEALED_MARK.sub("", title).replace("_", " ")
    for pattern in strip:
        title = pattern.sub(" ", title)
    return _SPACE.sub(" ", title).strip(" -–:;,.")


def group_files(links, region_code, config, landing):
    """ListingItems (one per number, all its PDFs) and the (url, text) links without a number."""
    items, unnumbered, seen = {}, [], set()
    for url, text, note in links:
        if url in seen:
            continue
        seen.add(url)
        found = file_number(text, url, region_code, config["number_patterns"])
        if found is None:
            unnumbered.append((url, text or _file_name(url)))
            continue
        number, match, source = found
        item = items.setdefault(number, ListingItem(number, landing, files=[]))
        item.files.append((url, text or _file_name(url)))
        title = file_title(text, match, source, config["title_strip"])
        if not title and note:
            title = _NOTE_DECIDED.sub("", note).strip()
        if not item.title and title:
            item.title = title
        if note and not item.decided:
            item.decided = _find_date(_DECIDED, note)
        if _REPEALED_MARK.match(text) or _REPEALED_MARK.match(_file_name(url)):
            item.marked_repealed = True
    return list(items.values()), unnumbered


# --- mapping ---------------------------------------------------------------


def _in_force(text):
    found = {swedish_date(m) for m in _IN_FORCE.finditer(text)} - {None}
    return found.pop() if len(found) == 1 else None


def _pdf_title(detail):
    """The first own PDF's label without its leading number (Gävleborg's pages have no ingress)."""
    for _url, label in detail.pdfs:
        match = _NUMBER.match(label)
        title = label[match.end():].strip(" -–:;,.") if match else ""
        if title:
            return title
    return None


def build_meta(detail, item, region_code, fetched_at):
    title = (detail.title or item.title or _pdf_title(detail) or detail.number).rstrip(". ")
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


def build_file_meta(item, region_code, source, source_sha256, fetched_at):
    """Frontmatter of a `files` layout regulation: only what the link gives."""
    return {
        "id": corpus_id(item.number),
        "title": (item.title or item.number).rstrip(". "),
        "type": TYPE,
        "layer": TYPES[TYPE],
        "number": item.number,
        "issued": item.decided,
        "in_force": None,
        "repealed": None,
        "amended_by": [],
        "amended_through": None,
        "reprinted_by": [],
        "ministry": None,
        "eli": None,
        "language": "sv",
        "authoritative": False,
        "source": source,
        "source_sha256": source_sha256,
        "fetched_at": fetched_at,
        "issuer": issuer(region_code),
        "court": None,
        "ecli": None,
        "celex": None,
        "region_code": region_code,
        "municipality_code": None,
    }


def file_markdown(meta, item):
    facts = [
        ("Författningssamling", meta["number"]),
        ("Beslutad", item.decided),
        ("Utfärdare", meta["issuer"]),
        ("Förteckning", item.url),
    ]
    blocks = ["# " + meta["title"], "  \n".join(f"{k}: {v}" for k, v in facts if v)]
    if item.marked_repealed:
        blocks.append("Länsstyrelsen markerar författningen som upphävd.")
    blocks.append("Författningen publiceras bara som pdf.")
    blocks.append("## Tryckt version")
    blocks.append(
        "Den tryckta författningen i länets författningssamling (pdf):\n\n"
        + "\n".join(f"- [{label}]({url})" for url, label in item.files)
    )
    return "\n\n".join(blocks) + "\n"


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


def _in_range(year, args):
    return (args.from_year is None or year >= args.from_year) and (
        args.to_year is None or year <= args.to_year
    )


def _candidates(client, robots, args, config, unnumbered):
    landing = args.landing_url or config["landing"]
    if config["layout"] == "files":
        yield from _file_candidates(client, robots, args, config, landing, unnumbered)
        return
    years = parse_landing(_get_page(client, robots, landing, "landing page"), landing)
    if not years:
        raise ListingError(f"no year index linked from {landing}")
    wanted = sorted((y for y in years if _in_range(y, args)), reverse=args.newest_first)
    for year in wanted:
        page = _get_page(client, robots, years[year], f"year {year} index")
        try:
            items = parse_year(page, years[year], args.county)
        except ValueError as error:
            raise ListingError(f"year {year} index: {error}") from error
        items.sort(key=lambda i: number_key(i.number), reverse=args.newest_first)
        yield from items


def _file_candidates(client, robots, args, config, landing, unnumbered):
    links, folders = parse_files_landing(_get_page(client, robots, landing, "landing page"), landing)
    in_folders = set()
    for year in sorted(y for y in folders if _in_range(y, args)):
        for url in folders[year]:
            raw = _get_page(client, robots, url, f"year {year} folder")
            try:
                found = parse_folder(raw, url)
            except ValueError as error:
                raise ListingError(f"year {year} folder: {error}") from error
            links.extend(found)
            in_folders.update(u for u, _, _ in found)
    if not links:
        raise ListingError(f"no PDF linked from {landing}")
    items, loose = group_files(links, args.county, config, landing)
    # Unnumbered links are reported when they sit in a requested year's folder or name
    # a year in the requested range.
    unnumbered.extend(
        t for u, t in loose
        if u in in_folders or any(_in_range(int(y), args) for y in _ANY_YEAR.findall(t))
    )
    items = [i for i in items if _in_range(number_key(i.number)[1], args)]
    items.sort(key=lambda i: number_key(i.number), reverse=args.newest_first)
    yield from items


def _hash_pdfs(client, robots, pdfs, download):
    files = []
    for url, _label in pdfs:
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
    if item.files is not None:
        return _store_files(client, robots, item, args, manifest)
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
            "files": _hash_pdfs(client, robots, detail.pdfs, args.pdf),
        }
    return _write_if_changed(meta, body, args.corpus)


def _write_if_changed(meta, body, corpus):
    if _unchanged(meta, body, corpus):
        return meta, False
    write(meta, body, corpus)
    return meta, True


def _store_files(client, robots, item, args, manifest):
    """Hash the PDFs of one `files` layout regulation, then map and write it."""
    urls = [u for u, _ in item.files]
    stored = manifest.get(item.number)
    stored_urls = [f["url"] for f in (stored or {}).get("files", [])]
    if stored is None or stored_urls != urls or (
        args.pdf and any(f.get("sha256") is None for f in stored["files"])
    ):
        stored = manifest[item.number] = {
            "number": item.number,
            "detail_url": item.url,
            "published": None,
            "files": _hash_pdfs(client, robots, item.files, args.pdf),
        }
    first = stored["files"][0]
    sha = first.get("sha256") or hashlib.sha256(
        "\n".join(f"{u}\t{t}" for u, t in item.files).encode("utf-8")
    ).hexdigest()
    fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    meta = build_file_meta(item, args.county, first["url"], sha, fetched_at)
    other = existing_path(meta["id"], args.corpus)
    if other is not None and other != path_for(meta, args.corpus):
        raise ValueError(f"{meta['number']} is already stored as {other}")
    body = file_markdown(meta, item)
    if personal_numbers(body):
        raise ValueError("possible personal identity number in the title")
    return _write_if_changed(meta, body, args.corpus)


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
        "unnumbered": summary.unnumbered,
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
    parser.add_argument(
        "--config", default=DEFAULT_CONFIG, help="county landing pages and layouts (JSON)",
    )
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
    config = load_config(args.config).get(args.county)
    if config is None:
        raise ConfigError(f"county {args.county} is not in {args.config}")
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
        for item in _candidates(client, robots, args, config, summary.unnumbered):
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
    except (ListingError, StateError, ConfigError) as error:
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
    if summary.unnumbered:
        print(f"unnumbered (not collected): {len(summary.unnumbered)}", flush=True)
    if summary.blocked:
        print("blocked: see state file", file=sys.stderr)
        return 2
    return 0
