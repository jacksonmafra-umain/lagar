"""Municipal regulations from the kommunala författningssamlingar into the corpus.

There is no national dataset: each kommun publishes its own författningssamling on
its own website, mostly as PDFs. A config file (collector/data/municipalities.json)
maps each kommun code to its listing pages and to one of three parsing strategies:

- `html_index`: a listing page whose links point straight at the documents. Links
  are kept when they sit under one of the configured section headings and match
  the configured link pattern.
- `domino_view`: an IBM Domino (Lotus Notes) database whose view is read as XML
  (`?ReadViewEntries`); each kept entry has a detail page with metadata, a short
  note and the PDF attachments.

- `html_pages`: a listing whose links lead to one web page per rule; the page
  text is the document, unless the page links a PDF, which then is.

Most kommuner run Sitevision and list their documents as one flat file list.
`"preset": "sitevision"` fills in the link pattern, number (the file's node id)
and title cleanup for such an `html_index` page, and `"resident_filter": true`
keeps only titles that name rules for residents (föreskrifter, taxor, avgifter
and the like) while dropping internal governance documents by title.

Only rules that bind residents are collected (local ordinances, fees and tariffs,
waste rules and the like); internal governance documents (reglementen,
bolagsordningar, delegationsordningar, instruktioner) are left out through the
config's sections and kinds.

PDF text is never extracted: the body holds the metadata, the kommun's own note
when it has one and a link to the official PDF, whose SHA-256 goes into the
manifest. robots.txt is read for every host before it is contacted, with
RFC 9309 wildcards; a document whose URL is disallowed is not fetched and is
recorded as a gap, its corpus file then pointing at the listing page instead.
"""

import argparse
import gzip
import hashlib
import json
import re
import sys
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ElementTree
import zlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

from . import frontmatter, htmlmd, writer
from .http import Blocked, PoliteClient
from .sfs import NETWORK_ERRORS, USER_AGENT, StateError, _save_state
from .vocabulary import TYPES

TYPE = "municipal_regulation"
DEFAULT_CONFIG = "collector/data/municipalities.json"
DEFAULT_STATE = "collector/data/municipal-state.json"
DEFAULT_MANIFEST = "sources/municipal-manifest.json"
DEFAULT_RATE = 1.0
MANIFEST_VERSION = 1
STRATEGIES = ("html_index", "domino_view", "html_pages")

# Defaults merged under a kommun entry that names a preset; the entry's own keys win.
PRESETS = {
    "sitevision": {
        "strategy": "html_index",
        "link_pattern": r"/download/18\.[0-9a-f]+/\d+/[^?#]+\.pdf$",
        "number": [{"from": "href", "pattern": r"/download/(18\.[0-9a-f]+)/"}],
        "title_strip": [
            r",?\s*(\(?\s*)?(ö|o)ppnas i (ett )?nytt f(ö|o)nster\.?\)?\s*$",
            r"\s*(\.pdf)?\s*,?\s*\(?pdf,?\s*[\d.,]+\s*[kMG]?B\)?\.?\s*$",
            r"\.(pdf|docx?)\s*$",
        ],
        "follow": r"[?&]lp-page=\d+",  # the file list's own pagination
        "embedded_json": True,
    },
}

# Titles of rules that bind residents, and of internal documents that never do. A title is
# kept when it matches an include pattern and no exclude pattern.
RESIDENT_INCLUDE = (
    r"f(ö|o)reskrift", r"taxa\b", r"\btaxor", r"avgift", r"avfall", r"renh(å|a)llning",
    r"sotning", r"brandskydd", r"h(ä|a)lsoskydd", r"naturreservat", r"hamnordning",
    r"torghandel", r"allm(ä|a)nna best(ä|a)mmelser", r"\bABVA\b", r"ordningsstadga",
    r"lokala ordnings", r"maxtaxa",
)
RESIDENT_EXCLUDE = (
    r"reglemente", r"arbetsordning", r"bolagsordning", r"delegation", r"instruktion",
    r"(ä|a)gardirektiv", r"informationshanteringsplan", r"dokumenthanteringsplan", r"arkiv",
    r"policy", r"riktlinje", r"strategi", r"handlingsplan", r"avfallsplan",
    r"\bplan\b(?!-)",  # but "Plan- och byggtaxa" is a fee
    r"program\b", r"budget", r"ans(ö|o)kan", r"blankett", r"revision", r"protokoll",
    r"tj(ä|a)nsteskrivelse", r"arvode", r"intern ?kontroll", r"attest", r"remiss",
    r"granskning", r"(ö|o)versyn", r"beslut om", r"f(ö|o)rslag", r"rapport", r"utredning",
)
ENCODING_ATTEMPTS = 3
MAX_LISTING_PAGES = 100
MIN_PAGE_TEXT = 200  # characters; less is a menu or an empty page, not a rule
# Page furniture that ends up in a rule page's text: print and feedback links, review dates.
PAGE_NOISE = re.compile(
    r"^(skriv ut( sidan)?|lämna synpunkter|dela( sidan)?|tipsa|lyssna|innehållsansvarig|"
    r"senast (uppdaterad|ändrad|granskad)|sidan (uppdaterades|granskades))\b",
    re.IGNORECASE,
)
AGENT_TOKEN = USER_AGENT.split("/", 1)[0].lower()

DOCUMENT_ERRORS = NETWORK_ERRORS + (UnicodeDecodeError, ValueError, KeyError, TypeError)

_KOMMUN_CODE = re.compile(r"(0[13-9]|1[02-47-9]|2[0-5])\d{2}", re.ASCII)
_SLUG_JUNK = re.compile(r"[^0-9a-z]+")
_US_DATE = re.compile(r"(\d{2})/(\d{2})/(\d{4})")


class ConfigError(Exception):
    """The kommun config is unreadable or inconsistent; the run cannot start."""


class ListingError(Exception):
    """robots.txt or a listing could not be read; the kommun is skipped."""


class UnsupportedEncoding(ValueError):
    """The server answered with a Content-Encoding the standard library cannot decode."""


class ForbiddenHost(ValueError):
    """A request or redirect would leave the hosts configured for the kommun."""


# --- config -------------------------------------------------------------------


@dataclass
class Kommun:
    code: str
    name: str
    issuer: str
    region_code: str
    collection: str
    strategy: str
    hosts: "tuple[str, ...]"
    listings: "list[str]"
    sections: "list[str]" = field(default_factory=list)
    section_level: int = 2
    link_pattern: str = ""
    number_rules: "list[dict]" = field(default_factory=list)
    title_strip: "list[str]" = field(default_factory=list)
    kinds: "list[str]" = field(default_factory=list)
    kind_column: str = ""
    title_column: str = ""
    number_column: str = ""
    title_include: "list[str]" = field(default_factory=list)
    title_exclude: "list[str]" = field(default_factory=list)
    follow: str = ""
    embedded_json: bool = False
    document_pattern: str = ""
    content_id: str = ""


def _required(entry, key, code, kind=str):
    value = entry.get(key)
    if not isinstance(value, kind) or not value:
        raise ConfigError(f"{code}: {key} is missing or not a {kind.__name__}")
    return value


def _kommun(code, entry):
    if not _KOMMUN_CODE.fullmatch(code):
        raise ConfigError(f"{code}: not an SCB kommun code")
    if not isinstance(entry, dict):
        raise ConfigError(f"{code}: expected an object")
    if "preset" in entry:
        if entry["preset"] not in PRESETS:
            raise ConfigError(f"{code}: unknown preset {entry['preset']!r}")
        entry = {**PRESETS[entry["preset"]], **entry}
    resident = entry.get("resident_filter", False)
    region = _required(entry, "region_code", code)
    if not code.startswith(region):
        raise ConfigError(f"{code}: kommun is not in region {region}")
    strategy = _required(entry, "strategy", code)
    if strategy not in STRATEGIES:
        raise ConfigError(f"{code}: unknown strategy {strategy!r}")
    listings = _required(entry, "listings", code, list)
    for url in listings:
        if not isinstance(url, str) or urllib.parse.urlsplit(url).scheme != "https":
            raise ConfigError(f"{code}: listing {url!r} is not an https URL")
    hosts = tuple(_required(entry, "hosts", code, list))
    kommun = Kommun(
        code=code,
        name=_required(entry, "name", code),
        issuer=_required(entry, "issuer", code),
        region_code=region,
        collection=_required(entry, "collection", code),
        strategy=strategy,
        hosts=hosts,
        listings=listings,
        sections=list(entry.get("sections") or []),
        section_level=int(entry.get("section_level", 2)),
        link_pattern=entry.get("link_pattern", ""),
        number_rules=list(entry.get("number") or []),
        title_strip=list(entry.get("title_strip") or []),
        kinds=list(entry.get("kinds") or []),
        kind_column=entry.get("kind_column", ""),
        title_column=entry.get("title_column", ""),
        number_column=entry.get("number_column", ""),
        title_include=list(entry.get("title_include") or (RESIDENT_INCLUDE if resident else [])),
        title_exclude=list(entry.get("title_exclude") or (RESIDENT_EXCLUDE if resident else [])),
        follow=entry.get("follow", ""),
        embedded_json=bool(entry.get("embedded_json", False)),
        document_pattern=entry.get("document_pattern", ""),
        content_id=entry.get("content_id", ""),
    )
    for url in listings:
        if urllib.parse.urlsplit(url).hostname not in hosts:
            raise ConfigError(f"{code}: listing {url} is not on a configured host")
    try:
        patterns = [kommun.link_pattern, kommun.follow, kommun.document_pattern, *kommun.title_strip, *kommun.title_include, *kommun.title_exclude]
        for pattern in [*patterns, *(r["pattern"] for r in kommun.number_rules)]:
            re.compile(pattern)
    except (re.error, KeyError, TypeError) as error:
        raise ConfigError(f"{code}: bad pattern: {error}") from None
    if strategy in ("html_index", "html_pages") and not (kommun.link_pattern and kommun.number_rules):
        raise ConfigError(f"{code}: {strategy} needs link_pattern and number")
    if strategy == "domino_view" and not (
        kommun.kinds and kommun.kind_column and kommun.title_column and kommun.number_column
    ):
        raise ConfigError(f"{code}: domino_view needs kinds and the kind, title and number columns")
    return kommun


def load_config(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ConfigError(f"config {path}: {error}") from None
    kommuner = data.get("kommuner") if isinstance(data, dict) else None
    if not isinstance(kommuner, dict) or not kommuner:
        raise ConfigError(f"config {path}: expected a non-empty `kommuner` object")
    return {code: _kommun(code, entry) for code, entry in kommuner.items()}


# --- robots.txt ----------------------------------------------------------------


def _robots_regex(pattern):
    anchored = pattern.endswith("$")
    body = re.escape(pattern.rstrip("$")).replace(r"\*", ".*")
    return re.compile(body + ("$" if anchored else ""))


class Robots:
    """robots.txt rules for this collector (RFC 9309: groups, `*`, `$`, longest match wins)."""

    def __init__(self, text):
        groups, agents, rules, in_rules = [], [], [], False
        for raw in text.lstrip("﻿").splitlines():
            line = raw.split("#", 1)[0].strip()
            if ":" not in line:
                continue
            key, value = (part.strip() for part in line.split(":", 1))
            key = key.lower()
            if key == "user-agent":
                if in_rules:
                    groups.append((agents, rules))
                    agents, rules, in_rules = [], [], False
                agents.append(value.lower())
            elif key in ("allow", "disallow") and agents:
                in_rules = True
                if value:
                    rules.append((value, key == "allow"))
        if agents:
            groups.append((agents, rules))
        mine = [r for a, r in groups if any(x != "*" and x in AGENT_TOKEN for x in a)]
        chosen = mine or [r for a, r in groups if "*" in a]
        self.rules = [
            (len(pattern), allow, _robots_regex(urllib.parse.unquote(pattern)))
            for group in chosen
            for pattern, allow in group
        ]

    def allows(self, url):
        parts = urllib.parse.urlsplit(url)
        path = urllib.parse.unquote(parts.path or "/") + ("?" + parts.query if parts.query else "")
        best = None
        for length, allow, regex in self.rules:
            if regex.match(path) and (best is None or length > best[0] or (length == best[0] and allow)):
                best = (length, allow)
        return True if best is None else best[1]


ALLOW_ALL = Robots("")


# --- fetching -----------------------------------------------------------------


class _Bits:
    def __init__(self, data):
        self.data, self.pos = data, 0

    def read(self, count):
        value = 0
        for i in range(count):
            byte = self.pos >> 3
            if byte >= len(self.data):
                raise UnsupportedEncoding("truncated brotli stream")
            value |= ((self.data[byte] >> (self.pos & 7)) & 1) << i
            self.pos += 1
        return value

    def align(self):
        self.pos = (self.pos + 7) & ~7


def _stored_brotli(body):
    """Decode a brotli stream made only of uncompressed meta-blocks (RFC 7932, 9.2).

    Some servers send small files this way even when brotli was not asked for.
    Compressed meta-blocks need a full decoder, which the standard library lacks.
    """
    bits = _Bits(body)
    if bits.read(1) and not bits.read(3):
        bits.read(3)  # large-window or 17-bit WBITS forms
    out = bytearray()
    while True:
        last = bits.read(1)
        if last and bits.read(1):  # ISLASTEMPTY
            return bytes(out)
        nibbles = bits.read(2)
        if nibbles == 3:
            raise UnsupportedEncoding("brotli metadata block")
        length = bits.read(4 * (nibbles + 4)) + 1
        if last or not bits.read(1):
            raise UnsupportedEncoding("compressed brotli meta-block")
        bits.align()
        start = bits.pos >> 3
        if start + length > len(body):
            raise UnsupportedEncoding("truncated brotli stream")
        out += body[start:start + length]
        bits.pos = (start + length) * 8


def _decode_body(body, encoding):
    encoding = (encoding or "identity").strip().lower()
    if encoding in ("", "identity"):
        return body
    if encoding in ("gzip", "x-gzip"):
        return gzip.decompress(body)
    if encoding == "deflate":
        try:
            return zlib.decompress(body)
        except zlib.error:
            return zlib.decompress(body, -zlib.MAX_WBITS)
    if encoding == "br":
        return _stored_brotli(body)
    raise UnsupportedEncoding(f"unsupported Content-Encoding {encoding!r}")


class _Decoded:
    def __init__(self, body, headers, url):
        self._body, self.headers, self._url = body, headers, url

    def read(self):
        return self._body

    def geturl(self):
        return self._url

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def decoding_opener(request, timeout):
    """urlopen that asks for gzip and decodes it; some sites send brotli anyway."""
    request.add_header("Accept-Encoding", "gzip")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = _decode_body(response.read(), response.headers.get("Content-Encoding"))
        return _Decoded(body, response.headers, response.geturl())


class Fetcher:
    """Robots-aware fetching within a kommun's hosts; robots.txt is read once per host."""

    def __init__(self, client):
        self.client = client
        self._robots = {}

    def robots(self, url):
        parts = urllib.parse.urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin not in self._robots:
            try:
                raw, _, _ = self._fetch(origin + "/robots.txt")
            except urllib.error.HTTPError as error:
                if error.code not in (404, 410):
                    raise ListingError(f"{origin}/robots.txt: HTTP {error.code}") from error
                self._robots[origin] = ALLOW_ALL
            except (*NETWORK_ERRORS, ValueError) as error:
                raise ListingError(f"{origin}/robots.txt: {error}") from error
            else:
                self._robots[origin] = Robots(raw.decode("utf-8", errors="replace"))
        return self._robots[origin]

    def allows(self, url):
        return self.robots(url).allows(url)

    def _fetch(self, url):
        url = _uri(url)
        for attempt in range(ENCODING_ATTEMPTS):
            try:
                return self.client.fetch_final(url)
            except UnsupportedEncoding:
                if attempt == ENCODING_ATTEMPTS - 1:
                    raise
        raise AssertionError("unreachable")

    def get(self, kommun, url):
        """(body, content_type, final_url); the caller has checked robots.txt."""
        check_host(kommun, url)
        raw, content_type, final = self._fetch(url)
        check_host(kommun, final)
        return raw, content_type, final


def check_host(kommun, url):
    parts = urllib.parse.urlsplit(url)
    if parts.scheme not in ("http", "https") or parts.hostname not in kommun.hosts:
        raise ForbiddenHost(f"{url} is not on a host configured for {kommun.code}")
    return url


def _text(raw):
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp1252", errors="replace")


# --- listings -----------------------------------------------------------------


@dataclass
class Entry:
    kommun: str
    number: str
    title: str
    url: str  # the PDF (html_index) or the detail page (domino_view)
    listing: str
    listing_sha256: str


def slug(text):
    text = text.lower().translate(str.maketrans({"å": "a", "ä": "a", "ö": "o", "é": "e", "ü": "u"}))
    return _SLUG_JUNK.sub("-", text).strip("-")


def corpus_id(kommun_code, number):
    return f"{kommun_code}-{slug(number)}"


def _uri(url):
    """Percent-encode what some listings leave raw in their links (spaces, å, ä, ö)."""
    return urllib.parse.quote(url, safe=":/?#[]@!$&'()*+,;=%~")


def _clean(text):
    """Whitespace collapsed and NFC: file names often spell ä as a plus a combining diaeresis."""
    return unicodedata.normalize("NFC", " ".join((text or "").split()))


_INITIAL_STATE = re.compile(r"registerInitialState\(\s*'[^']*'\s*,\s*")


def _state_files(script):
    """(href, title) of the files in Sitevision `AppRegistry.registerInitialState` JSON.

    File-share and file-list modules render their list in the browser from this
    state; the static HTML then carries no anchors for the files.
    """
    found = []
    for match in _INITIAL_STATE.finditer(script):
        try:
            state, _ = json.JSONDecoder().raw_decode(script, match.end())
        except ValueError:
            continue
        stack = [state]
        while stack:
            node = stack.pop()
            if isinstance(node, list):
                stack.extend(reversed(node))
            elif isinstance(node, dict):
                href = node.get("url") or node.get("uri")
                title = node.get("title") or node.get("name")
                if isinstance(href, str) and isinstance(title, str) and "/download/" in href:
                    found.append((href, title))
                else:
                    stack.extend(reversed(list(node.values())))
    return found


class _Links(HTMLParser):
    """Anchors with the heading they sit under (the latest heading at or above `level`).

    With `embedded_json`, files listed in Sitevision's embedded module state count as
    anchors under the heading that precedes the script.
    """

    def __init__(self, level, embedded_json=False):
        super().__init__(convert_charrefs=True)
        self.level = level
        self.embedded_json = embedded_json
        self.links = []  # (section, href, text)
        self.section = None
        self._heading = None  # [level, parts]
        self._anchor = None  # [href, parts]
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "template"):
            self._skip += 1
        elif re.fullmatch(r"h[1-6]", tag) and int(tag[1]) <= self.level:
            self._heading = [int(tag[1]), []]
        elif tag == "a":
            href = dict(attrs).get("href")
            self._anchor = [href, []] if href else None

    def handle_endtag(self, tag):
        if tag in ("script", "style", "template"):
            self._skip = max(0, self._skip - 1)
        elif self._heading and tag == f"h{self._heading[0]}":
            self.section = _clean("".join(self._heading[1]))
            self._heading = None
        elif tag == "a" and self._anchor:
            self.links.append((self.section, self._anchor[0], _clean("".join(self._anchor[1]))))
            self._anchor = None

    def handle_data(self, data):
        if self._skip:
            if self.embedded_json and "registerInitialState" in data:
                self.links += [(self.section, href, _clean(title)) for href, title in _state_files(data)]
            return
        if self._heading:
            self._heading[1].append(data)
        if self._anchor:
            self._anchor[1].append(data)


def _number(kommun, href, text):
    for rule in kommun.number_rules:
        source = text if rule.get("from", "text") == "text" else urllib.parse.unquote(href)
        match = re.search(rule["pattern"], source, re.IGNORECASE)
        if not match:
            continue
        if rule.get("format"):
            return rule["format"].format(*match.groups())
        return _clean(match.group(1) if match.groups() else match.group(0))
    return None


def _title(kommun, text):
    text = _clean(text)
    for pattern in kommun.title_strip:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)
    return _clean(text)


def binds_residents(kommun, title):
    """Whether the title passes the kommun's include and exclude title patterns."""
    if kommun.title_include and not any(re.search(p, title, re.IGNORECASE) for p in kommun.title_include):
        return False
    return not any(re.search(p, title, re.IGNORECASE) for p in kommun.title_exclude)


def parse_html_index(kommun, raw, listing_url):
    """(entries, problems) of a listing page; problems are links that match but carry no number."""
    parser = _Links(kommun.section_level, kommun.embedded_json)
    parser.feed(_text(raw))
    parser.close()
    sha = hashlib.sha256(raw).hexdigest()
    sections = {s.casefold() for s in kommun.sections}
    entries, problems = [], []
    # Icon links next to the titled link carry no text; they are not documents of their own.
    titled = {_uri(urllib.parse.urljoin(listing_url, href.strip())) for _, href, text in parser.links if text}
    for section, href, text in parser.links:
        if sections and (section or "").casefold() not in sections:
            continue
        url = _uri(urllib.parse.urljoin(listing_url, href.strip()))
        if not re.search(kommun.link_pattern, url, re.IGNORECASE) or (not text and url in titled):
            continue
        number = _number(kommun, url, text)
        title = _title(kommun, text)
        if not title or not binds_residents(kommun, title):
            continue  # an image or icon link carries no title to judge or store
        if not number:
            problems.append(url)
            continue
        entries.append(Entry(kommun.code, number, title, url, listing_url, sha))
    return entries, problems


def more_pages(kommun, raw, listing_url):
    """Further listing pages linked from this one (pagination), matched by `follow`."""
    if not kommun.follow:
        return []
    parser = _Links(kommun.section_level)
    parser.feed(_text(raw))
    parser.close()
    pages = []
    for _, href, _ in parser.links:
        url = _uri(urllib.parse.urldefrag(urllib.parse.urljoin(listing_url, href))[0])
        if re.search(kommun.follow, url) and urllib.parse.urlsplit(url).hostname in kommun.hosts:
            pages.append(url)
    return list(dict.fromkeys(pages))


def parse_domino_view(kommun, raw, listing_url):
    """Entries of a Domino `?ReadViewEntries` XML view, filtered by document kind."""
    if b"<!DOCTYPE" in raw[:2048].upper():
        raise ValueError("view XML must not carry a DOCTYPE")
    root = ElementTree.fromstring(raw)
    sha = hashlib.sha256(raw).hexdigest()
    database = listing_url.split("?", 1)[0].rsplit("/", 1)[0]
    kinds = {k.casefold() for k in kommun.kinds}
    entries, seen = [], set()
    for row in root.iter("viewentry"):
        unid = row.get("unid")
        if not unid or unid in seen:
            continue
        columns = {
            d.get("name"): _clean("".join(d.itertext())) for d in row.findall("entrydata")
        }
        if columns.get(kommun.kind_column, "").casefold() not in kinds:
            continue
        number, title = columns.get(kommun.number_column), columns.get(kommun.title_column)
        if not number or not title or not binds_residents(kommun, title):
            continue
        seen.add(unid)
        url = f"{database}/0/{unid}?OpenDocument"
        entries.append(Entry(kommun.code, number, title, url, listing_url, sha))
    return entries, []


# html_pages lists its rule pages the way html_index lists documents.
PARSERS = {"html_index": parse_html_index, "domino_view": parse_domino_view, "html_pages": parse_html_index}


# --- Domino detail pages ------------------------------------------------------


@dataclass
class Detail:
    fields: "dict[str, str]"
    note: str
    attachments: "list[tuple[str, str]]"  # (url, label)

    def text_ok(self):
        return len(self.note) >= MIN_PAGE_TEXT


_DETAIL_IDS = {
    "textomradehuvudlopnr": "serial",
    "textomradehuvudgallande": "valid",
    "textomradehuvudfaststallare": "adopted_by",
    "textomradehuvuddokument": "heading",
}


class _DetailParser(HTMLParser):
    def __init__(self, base):
        super().__init__(convert_charrefs=True)
        self.base = base
        self.fields = {}
        self.attachments = []
        self._field = None
        self._anchor = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "div" and attrs.get("id") in _DETAIL_IDS:
            self._field = [_DETAIL_IDS[attrs["id"]], []]
        elif tag == "a":
            href = (attrs.get("href") or "").replace("\\", "/")
            if "/$File/" in href:
                self._anchor = [urllib.parse.urljoin(self.base, href), []]

    def handle_endtag(self, tag):
        if tag == "div" and self._field:
            self.fields[self._field[0]] = _clean("".join(self._field[1]))
            self._field = None
        elif tag == "a" and self._anchor:
            self.attachments.append((self._anchor[0], _clean("".join(self._anchor[1]))))
            self._anchor = None

    def handle_data(self, data):
        if self._field:
            self._field[1].append(data)
        if self._anchor:
            self._anchor[1].append(data)


def _body_field(html):
    """Inner HTML of `<div id="BodyField">`, nested divs included."""
    start = re.search(r"<div[^>]*\bid\s*=\s*\"?BodyField\b[^>]*>", html, re.IGNORECASE)
    if not start:
        return ""
    depth, pos = 1, start.end()
    for tag in re.finditer(r"<(/?)div\b[^>]*>", html[pos:], re.IGNORECASE):
        depth += -1 if tag.group(1) else 1
        if depth == 0:
            return html[pos:pos + tag.start()]
    return html[pos:]


def _element(html, content_id):
    """Inner HTML of the element with id `content_id`, else of `<main>`, else the whole page."""
    if content_id:
        start = re.search(r"<([a-z0-9]+)\b[^>]*\bid\s*=\s*[\"']?%s[\"'\s>]" % re.escape(content_id), html, re.IGNORECASE)
        if start:
            tag = start.group(1)
            begin = html.index(">", start.start()) + 1
            depth = 1
            for match in re.finditer(r"<(/?)%s\b[^>]*>" % tag, html[begin:], re.IGNORECASE):
                depth += -1 if match.group(1) else 1
                if depth == 0:
                    return html[begin:begin + match.start()]
            return html[begin:]
    main = re.search(r"<main\b[^>]*>(.*)</main\s*>", html, re.IGNORECASE | re.DOTALL)
    return main.group(1) if main else html


class _PageLinks(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []
        self._anchor = None

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            href = dict(attrs).get("href")
            self._anchor = [href, []] if href else None

    def handle_endtag(self, tag):
        if tag == "a" and self._anchor:
            self.links.append((self._anchor[0], _clean("".join(self._anchor[1]))))
            self._anchor = None

    def handle_data(self, data):
        if self._anchor:
            self._anchor[1].append(data)


def parse_page(kommun, raw, url):
    """A rule's own page (html_pages): its text as Markdown and the documents it links to."""
    content = _element(_text(raw), kommun.content_id)
    lines = htmlmd.to_markdown(content, heading_offset=2).splitlines()
    text = "\n".join(line for line in lines if not PAGE_NOISE.match(line.strip())).strip()
    text = re.sub(r"\n{3,}", "\n\n", text)
    attachments = []
    if kommun.document_pattern:
        links = _PageLinks()
        links.feed(content)
        links.close()
        for href, label in links.links:
            target = _uri(urllib.parse.urljoin(url, href.strip()))
            if re.search(kommun.document_pattern, target, re.IGNORECASE):
                attachments.append((target, label or _label(target)))
    return Detail({}, text, list(dict.fromkeys(attachments)))


def parse_detail(raw, url):
    html = _text(raw)
    parser = _DetailParser(url)
    parser.feed(html)
    parser.close()
    fields = dict(parser.fields)
    serial = fields.get("serial", "")
    if " Version:" in serial:
        fields["serial"], fields["version"] = (_clean(p) for p in serial.split(" Version:", 1))
    valid = _US_DATE.search(fields.get("valid", ""))  # Domino prints MM/DD/YYYY
    fields["valid"] = f"{valid.group(3)}-{valid.group(1)}-{valid.group(2)}" if valid else None
    adopted = fields.get("adopted_by", "")
    fields["adopted_by"] = _clean(adopted.split(":", 1)[1]) if ":" in adopted else None
    attachments = list(dict.fromkeys(parser.attachments))
    return Detail(fields, htmlmd.to_markdown(_body_field(html), heading_offset=2).strip(), attachments)


# --- documents ----------------------------------------------------------------


def _is_pdf(raw, content_type):
    return raw[:5] == b"%PDF-" or content_type == "application/pdf"


def _label(url):
    name = urllib.parse.unquote(urllib.parse.urlsplit(url).path.rsplit("/", 1)[-1])
    return name or url


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_meta(kommun, entry, source, sha, fetched_at):
    return {
        "id": corpus_id(kommun.code, entry.number),
        "title": entry.title,
        "type": TYPE,
        "layer": TYPES[TYPE],
        "number": entry.number,
        "issued": None,
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
        "source_sha256": sha,
        "fetched_at": fetched_at,
        "issuer": kommun.issuer,
        "region_code": kommun.region_code,
        "municipality_code": kommun.code,
    }


def build_body(kommun, entry, documents, detail=None, gap=None, text=None):
    """Markdown body: metadata, the kommun's own note and links to the official documents.

    With `text` (a rule published as an HTML page), the body holds that text instead.
    """
    lines = [
        f"# {entry.title}",
        "",
        f"Kommun: {kommun.name} ({kommun.code})  ",
        f"Författningssamling: {kommun.collection}  ",
        f"Nummer: {entry.number}",
    ]
    if detail is not None:
        if detail.fields.get("version"):
            lines[-1] += "  "
            lines.append(f"Version: {detail.fields['version']}")
        if detail.fields.get("adopted_by"):
            lines[-1] += "  "
            lines.append(f"Fastställd av: {detail.fields['adopted_by']}")
        if detail.fields.get("valid"):
            lines[-1] += "  "
            lines.append(f"Gällande från: {detail.fields['valid']}")
    if detail is not None:
        lines += ["", f"Kommunens sida: <{entry.url}>"]
    else:
        lines += ["", f"Förteckning: <{entry.listing}>"]
    if text is not None:
        lines += ["", "## Text", "", "Texten är hämtad från kommunens webbsida.", "", text]
        return "\n".join(lines) + "\n"
    if detail is not None and detail.note:
        lines += ["", "## Uppgifter från kommunen", "", detail.note]
    lines += [
        "",
        "## Dokument",
        "",
        "Kommunen publicerar texten som PDF. Texten har inte konverterats; "
        "den gällande lydelsen finns i kommunens dokument.",
        "",
    ]
    lines += [f"- [{label}](<{url}>)" for url, label in documents]
    if gap:
        lines += ["", f"Dokumentet har inte hämtats: {gap}."]
    return "\n".join(lines) + "\n"


def _unchanged(meta, body, corpus):
    path = writer.path_for(meta, corpus)
    try:
        stored, stored_body = frontmatter.load(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    stored.pop("fetched_at", None)
    return stored_body == body and stored == {k: v for k, v in meta.items() if k != "fetched_at"}


def _fetch_pdf(fetcher, kommun, url):
    """(sha256, record) of a PDF, or (None, gap reason) when robots.txt disallows it."""
    if not fetcher.allows(url):
        return None, "robots.txt disallows the document URL"
    raw, content_type, final = fetcher.get(kommun, url)
    if not _is_pdf(raw, content_type):
        raise ValueError(f"expected a PDF, got {content_type}: {url}")
    sha = hashlib.sha256(raw).hexdigest()
    return sha, {"url": final, "content_type": content_type, "bytes": len(raw), "sha256": sha}


def _collect_page(fetcher, kommun, entry, args, manifest):
    """A rule published as an HTML page: the page text is the document; a linked PDF wins."""
    if not fetcher.allows(entry.url):
        raise ListingError(f"robots.txt disallows {entry.url}")
    raw, _, final = fetcher.get(kommun, entry.url)
    detail = parse_page(kommun, raw, final)
    if detail.attachments:
        return None, detail, final
    if not detail.text_ok():
        raise ValueError(f"no text on {entry.url}")
    doc_id = corpus_id(kommun.code, entry.number)
    data = detail.note.encode("utf-8")
    sha = hashlib.sha256(data).hexdigest()  # of the text, so markup changes do not count
    now = _now()
    _record_document(manifest, {"id": doc_id, "municipality_code": kommun.code, "url": final,
                                "content_type": "text/markdown", "bytes": len(data), "sha256": sha,
                                "retrieved_at": now})
    meta = build_meta(kommun, entry, final, sha, now)
    body = build_body(kommun, entry, [], detail, None, text=detail.note)
    if _unchanged(meta, body, args.corpus):
        return (meta, False, None), detail, final
    writer.write(meta, body, args.corpus)
    return (meta, True, None), detail, final


def collect_document(fetcher, kommun, entry, args, manifest):
    """Write one document; returns (meta, changed, gap reason or None)."""
    detail = None
    if kommun.strategy == "html_pages":
        done, detail, final = _collect_page(fetcher, kommun, entry, args, manifest)
        if done is not None:
            return done
        documents = detail.attachments
        fallback = (final, hashlib.sha256(detail.note.encode("utf-8")).hexdigest())
    elif kommun.strategy == "domino_view":
        if not fetcher.allows(entry.url):
            raise ListingError(f"robots.txt disallows {entry.url}")
        raw, _, final = fetcher.get(kommun, entry.url)
        detail = parse_detail(raw, final)
        if not detail.attachments:
            raise ValueError(f"no attachment on {entry.url}")
        documents = detail.attachments
        fallback = (final, hashlib.sha256(raw).hexdigest())
    else:
        documents = [(entry.url, entry.title)]
        fallback = (entry.listing, entry.listing_sha256)
    pdf_url = documents[0][0]
    sha, record = _fetch_pdf(fetcher, kommun, pdf_url)
    doc_id = corpus_id(kommun.code, entry.number)
    now = _now()
    if sha is None:
        gap, (source, sha) = record, fallback
        _record_gap(manifest, {"id": doc_id, "municipality_code": kommun.code, "url": pdf_url, "reason": gap})
    else:
        gap, source = None, record["url"]
        _record_document(manifest, {"id": doc_id, "municipality_code": kommun.code, **record, "retrieved_at": now})
    meta = build_meta(kommun, entry, source, sha, now)
    body = build_body(kommun, entry, documents, detail, gap)
    if _unchanged(meta, body, args.corpus):
        return meta, False, gap
    writer.write(meta, body, args.corpus)
    return meta, True, gap


# --- state and manifest -------------------------------------------------------


def _load_state(path):
    state = {"done": {}, "failed": {}, "gaps": {}, "blocked": {}}
    try:
        loaded = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return state
    except (ValueError, OSError):
        raise StateError(f"state file corrupt: {path}") from None
    if not isinstance(loaded, dict) or not all(isinstance(loaded.get(k, {}), dict) for k in state):
        raise StateError(f"state file corrupt: {path}")
    state.update({k: loaded[k] for k in state if k in loaded})
    return state


def load_manifest(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"version": MANIFEST_VERSION, "documents": [], "gaps": []}
    except (OSError, ValueError):
        raise StateError(f"manifest corrupt: {path}") from None
    if not isinstance(data, dict) or not isinstance(data.get("documents"), list):
        raise StateError(f"manifest corrupt: {path}")
    data.setdefault("gaps", [])
    return data


def save_manifest(path, manifest):
    manifest["documents"].sort(key=lambda e: e["id"])
    manifest["gaps"].sort(key=lambda e: e["id"])
    _save_state(path, manifest)


def _record_document(manifest, entry):
    manifest["gaps"] = [g for g in manifest["gaps"] if g["id"] != entry["id"]]
    old = next((e for e in manifest["documents"] if e["id"] == entry["id"]), None)
    if old is not None and old.get("sha256") == entry["sha256"] and old.get("url") == entry["url"]:
        return  # same bytes: keep the first retrieval date
    manifest["documents"] = [e for e in manifest["documents"] if e["id"] != entry["id"]]
    manifest["documents"].append(entry)


def _record_gap(manifest, entry):
    manifest["documents"] = [e for e in manifest["documents"] if e["id"] != entry["id"]]
    manifest["gaps"] = [g for g in manifest["gaps"] if g["id"] != entry["id"]]
    manifest["gaps"].append(entry)


# --- run ----------------------------------------------------------------------


@dataclass
class RunSummary:
    written: "list[str]" = field(default_factory=list)
    unchanged: "list[str]" = field(default_factory=list)
    skipped: int = 0
    gaps: "list[str]" = field(default_factory=list)
    failed: "list[str]" = field(default_factory=list)
    blocked: "dict[str, str]" = field(default_factory=dict)


def _write_report(path, summary):
    report = {
        "written": summary.written,
        "unchanged": summary.unchanged,
        "skipped": summary.skipped,
        "gaps": summary.gaps,
        "failed": summary.failed,
        "blocked": summary.blocked,
    }
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def list_entries(fetcher, kommun):
    """Entries of all the kommun's listings; raises ListingError when one cannot be read."""
    entries, problems = [], []
    queue, seen = list(kommun.listings), set(kommun.listings)
    while queue and len(seen) <= MAX_LISTING_PAGES:
        url = queue.pop(0)
        if not fetcher.allows(url):
            raise ListingError(f"robots.txt disallows the listing {url}")
        try:
            raw, _, final = fetcher.get(kommun, url)
            found, bad = PARSERS[kommun.strategy](kommun, raw, final)
        except Blocked:
            raise
        except (*DOCUMENT_ERRORS, ElementTree.ParseError) as error:
            raise ListingError(f"listing {url}: {type(error).__name__}: {error}") from error
        entries += found
        problems += bad
        for page in more_pages(kommun, raw, final):
            if page not in seen and fetcher.allows(page):
                seen.add(page)
                queue.append(page)
    unique = {}
    for entry in entries:
        unique.setdefault(corpus_id(kommun.code, entry.number), entry)
    return list(unique.values()), problems


def _known(manifest):
    """Document URL per id already in the manifest (fetched or recorded as a gap)."""
    known = {e["id"]: e.get("url") for e in manifest["documents"]}
    known.update({g["id"]: g.get("url") for g in manifest["gaps"]})
    return known


def _collect_kommun(fetcher, kommun, args, state, manifest, summary):
    entries, problems = list_entries(fetcher, kommun)
    known = _known(manifest)
    for url in problems:
        summary.failed.append(url)
        state["failed"][url] = "listing link without a number"
    written = 0
    for entry in entries:
        if args.limit is not None and written >= args.limit:
            break
        doc_id = corpus_id(kommun.code, entry.number)
        path = writer.path_for({"id": doc_id, "type": TYPE}, args.corpus)
        done = doc_id in state["done"] or (kommun.strategy == "html_index" and known.get(doc_id) == entry.url)
        if not args.refresh and done and path.exists():
            summary.skipped += 1
            continue
        try:
            meta, changed, gap = collect_document(fetcher, kommun, entry, args, manifest)
        except Blocked:
            raise
        except (*DOCUMENT_ERRORS, ListingError) as error:
            summary.failed.append(doc_id)
            state["failed"][doc_id] = f"{type(error).__name__}: {error}"
            continue
        (summary.written if changed else summary.unchanged).append(doc_id)
        written += changed
        state["done"][doc_id] = meta["source_sha256"]
        state["failed"].pop(doc_id, None)
        if gap:
            summary.gaps.append(doc_id)
            state["gaps"][doc_id] = gap
        else:
            state["gaps"].pop(doc_id, None)
        _save_state(args.state, state)
        save_manifest(args.manifest, manifest)


def _codes(config, args):
    codes = list(config) if args.all else args.kommun
    unknown = [c for c in codes if c not in config]
    if unknown:
        raise ConfigError(f"not in {args.config}: {', '.join(unknown)}")
    return codes


def dry_run(client, args, out=sys.stdout):
    """Print what each listing yields (id, title, URL) without fetching any document."""
    config = load_config(args.config)
    fetcher = Fetcher(client)
    blocked = 0
    for code in _codes(config, args):
        try:
            entries, problems = list_entries(fetcher, config[code])
        except (Blocked, ListingError, ForbiddenHost) as error:
            print(f"{code}\tBLOCKED\t{error}", file=out, flush=True)
            blocked += 1
            continue
        for entry in entries:
            print(f"{corpus_id(code, entry.number)}\t{entry.title}\t{entry.url}", file=out, flush=True)
        for url in problems:
            print(f"{code}\tNO NUMBER\t{url}", file=out, flush=True)
    return 2 if blocked else 0


def run(client, args):
    config = load_config(args.config)
    codes = _codes(config, args)
    summary = RunSummary()
    state = _load_state(args.state)
    manifest = load_manifest(args.manifest)
    fetcher = Fetcher(client)
    for code in codes:
        state["blocked"].pop(code, None)
        try:
            _collect_kommun(fetcher, config[code], args, state, manifest, summary)
        except (Blocked, ListingError, ForbiddenHost) as error:
            summary.blocked[code] = str(error)
            state["blocked"][code] = str(error)
    _save_state(args.state, state)
    save_manifest(args.manifest, manifest)
    if args.report:
        _write_report(args.report, summary)
    return summary


def _rate(value):
    rate = float(value)
    if rate < DEFAULT_RATE:
        raise argparse.ArgumentTypeError(f"must be at least {DEFAULT_RATE} seconds: {value}")
    return rate


def _non_negative(value):
    number = int(value)
    if number < 0:
        raise argparse.ArgumentTypeError(f"must not be negative: {value}")
    return number


def _code(value):
    if not _KOMMUN_CODE.fullmatch(value):
        raise argparse.ArgumentTypeError(f"not an SCB kommun code: {value}")
    return value


def parse_args(argv):
    parser = argparse.ArgumentParser(prog="collect.py municipal")
    which = parser.add_mutually_exclusive_group(required=True)
    which.add_argument("--kommun", type=_code, action="append", metavar="CODE",
                       help="SCB kommun code from the config, e.g. 0180 (repeatable)")
    which.add_argument("--all", action="store_true", help="every kommun in the config")
    parser.add_argument("--limit", type=_non_negative, help="stop after N written documents per kommun")
    parser.add_argument("--refresh", action="store_true", help="refetch documents already collected")
    parser.add_argument("--dry-run", action="store_true",
                        help="list what the listings yield without fetching documents or writing")
    parser.add_argument("--report", metavar="FILE", help="write a JSON run report")
    parser.add_argument("--rate", type=_rate, default=DEFAULT_RATE, metavar="SECONDS")
    parser.add_argument("--config", default=DEFAULT_CONFIG)
    parser.add_argument("--state", default=DEFAULT_STATE)
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST)
    parser.add_argument("--corpus", default="corpus")
    return parser.parse_args(argv)


def main(argv, client=None):
    if argv and argv[0] == "municipal":
        argv = argv[1:]
    args = parse_args(argv)
    if client is None:
        client = PoliteClient(USER_AGENT, min_interval=args.rate, opener=decoding_opener)
    try:
        if args.dry_run:
            return dry_run(client, args)
        summary = run(client, args)
    except (ConfigError, StateError) as error:
        print(f"error: {error}", file=sys.stderr, flush=True)
        return 1
    print(
        f"done: {len(summary.written)} written, {len(summary.unchanged)} unchanged, "
        f"{summary.skipped} skipped, {len(summary.gaps)} gaps, {len(summary.failed)} failed"
        + (f", BLOCKED: {', '.join(summary.blocked)}" if summary.blocked else ""),
        flush=True,
    )
    if summary.gaps:
        print("gaps: " + ", ".join(summary.gaps), flush=True)
    if summary.failed:
        print("failed: " + ", ".join(summary.failed), flush=True)
    for code, reason in summary.blocked.items():
        print(f"blocked {code}: {reason}", file=sys.stderr)
    return 2 if summary.blocked else 0
