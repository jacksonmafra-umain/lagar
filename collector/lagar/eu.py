"""EU acts in Swedish from the Publications Office Cellar into the corpus.

Metadata comes from the Cellar SPARQL endpoint, one query per act. The Swedish
text comes from Cellar content negotiation: `/resource/celex/<CELEX>` with
`Accept-Language: swe` answers 303 with the Swedish manifestation, which is
converted to Markdown. Only publications.europa.eu (and op.europa.eu, where its
robots.txt lives) is ever contacted; eur-lex.europa.eu answers automated
clients with a WAF challenge and is refused, including as a redirect target.

Acts without a Swedish expression, or with Swedish only as PDF or print, are
recorded as coverage gaps; nothing is ever translated.
"""

import argparse
import hashlib
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path

from . import frontmatter, writer
from .http import Blocked, PoliteClient
from .sfs import NETWORK_ERRORS, USER_AGENT, StateError, _save_state
from .vocabulary import TYPES

BASE = "https://publications.europa.eu"
ROBOTS_URL = BASE + "/robots.txt"
SPARQL_URL = BASE + "/webapi/rdf/sparql"
CELEX_URL = BASE + "/resource/celex/{celex}"
# robots.txt of publications.europa.eu redirects to op.europa.eu.
ALLOWED_HOSTS = frozenset({"publications.europa.eu", "op.europa.eu"})
ROBOTS_PATHS = ("/webapi/rdf/sparql", "/resource/celex/", "/resource/cellar/")
DEFAULT_LIST = "collector/data/eu-acts.json"
DEFAULT_STATE = "collector/data/eu-state.json"
DEFAULT_MANIFEST = "sources/eu-manifest.json"
DEFAULT_RATE = 1.0
MANIFEST_VERSION = 1
NO_END = "9999-12-31"

SPARQL_HEADERS = {"Accept": "application/sparql-results+json"}
# Manifestation type -> (Accept header, content types accepted in the answer).
FORMATS = {
    "xhtml": ("application/xhtml+xml", ("application/xhtml+xml",)),
    "html": ("text/html", ("text/html",)),
}

DOCUMENT_ERRORS = NETWORK_ERRORS + (UnicodeDecodeError, ValueError, KeyError, TypeError)

# Acts (sector 3) and their consolidated versions (sector 0), regulations,
# directives and decisions only.
CELEX = re.compile(r"(?:3\d{4}[RLD]\d{4}|0\d{4}[RLD]\d{4}-\d{8})", re.ASCII)
_KINDS = {"R": "eu_regulation", "L": "eu_directive", "D": "eu_decision"}
_SCHEMA_CELEX = re.compile(r"[0-9CE]\d{4}[A-Z]{1,2}\d{4}(?:[A-Z]?\(\d{2}\))?(?:-\d{8})?", re.ASCII)
_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}", re.ASCII)
_CORRIGENDUM = re.compile(r"R\(\d{2}\)$", re.ASCII)

# Institutions that adopt acts, by Publications Office corporate-body code.
ISSUERS = {
    "EP": "Europaparlamentet",
    "CONSIL": "Europeiska unionens råd",
    "COM": "Europeiska kommissionen",
    "ECB": "Europeiska centralbanken",
}

_QUERY = """PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
SELECT ?field ?value WHERE {
  ?work cdm:resource_legal_id_celex "%(celex)s"^^xsd:string .
  { ?work cdm:work_date_document ?value BIND("date_document" AS ?field) }
  UNION { ?work cdm:resource_legal_eli ?value BIND("eli" AS ?field) }
  UNION { ?work cdm:resource_legal_in-force ?value BIND("in_force" AS ?field) }
  UNION { ?work cdm:resource_legal_date_entry-into-force ?value BIND("entry_into_force" AS ?field) }
  UNION { ?work cdm:resource_legal_date_end-of-validity ?value BIND("end_of_validity" AS ?field) }
  UNION { ?work cdm:work_created_by_agent ?value BIND("agent" AS ?field) }
  UNION { ?expr cdm:expression_belongs_to_work ?work ;
            cdm:expression_uses_language <http://publications.europa.eu/resource/authority/language/SWE> ;
            cdm:expression_title ?value BIND("title_sv" AS ?field) }
  UNION { ?expr cdm:expression_belongs_to_work ?work ;
            cdm:expression_uses_language <http://publications.europa.eu/resource/authority/language/SWE> .
          ?manifestation cdm:manifestation_manifests_expression ?expr ;
            cdm:manifestation_type ?value BIND("manifestation_sv" AS ?field) }
  UNION { ?amending cdm:resource_legal_amends_resource_legal ?work ;
            cdm:resource_legal_id_celex ?value BIND("amended_by" AS ?field) }
  UNION { ?consolidated cdm:act_consolidated_based_on_resource_legal ?work ;
            cdm:resource_legal_id_celex ?value BIND("consolidated" AS ?field) }
  UNION { ?work cdm:act_consolidated_based_on_resource_legal ?base .
          ?base cdm:work_date_document ?value BIND("base_date_document" AS ?field) }
  UNION { ?work cdm:act_consolidated_based_on_resource_legal ?base ;
            cdm:act_consolidated_date ?date .
          ?version cdm:act_consolidated_based_on_resource_legal ?base ;
            cdm:act_consolidated_date ?versionDate ;
            cdm:act_consolidated_consolidates_resource_legal ?act .
          FILTER(?versionDate <= ?date)
          ?act cdm:resource_legal_id_celex ?actCelex ;
            cdm:work_date_document ?actDate
          BIND(CONCAT(STR(?actCelex), " ", STR(?actDate)) AS ?value) BIND("consolidates" AS ?field) }
}
"""

# Curated acts whose work, consolidated versions or amending acts changed after a
# point in time, with the newest modification. %(values)s are CELEX literals.
_CHANGED_QUERY = """PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
PREFIX cmr: <http://publications.europa.eu/ontology/cdm/cmr#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
SELECT ?celex (MAX(?m) AS ?modified) WHERE {
  VALUES ?celex { %(values)s }
  ?work cdm:resource_legal_id_celex ?celex .
  { ?work cmr:lastModificationDate ?m }
  UNION { ?version cdm:act_consolidated_based_on_resource_legal ?work .
          ?version cmr:lastModificationDate ?m }
  UNION { ?amending cdm:resource_legal_amends_resource_legal ?work .
          ?amending cmr:lastModificationDate ?m }
  FILTER(?m > "%(since)s"^^xsd:dateTime)
} GROUP BY ?celex
"""


class ForbiddenHost(ValueError):
    """A request or redirect would leave the Cellar hosts (for example to eur-lex.europa.eu)."""


class ListingError(Exception):
    """robots.txt or the list file could not be read; the run cannot continue."""


class Gap(Exception):
    """The act has no Swedish text the collector may use; recorded as a coverage gap."""


def check_host(url):
    parts = urllib.parse.urlsplit(url)
    if parts.scheme not in ("http", "https") or (parts.hostname or "") not in ALLOWED_HOSTS:
        raise ForbiddenHost(f"refusing to fetch outside the Cellar hosts: {url}")
    return url


def _https(url):
    parts = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit(("https", *parts[1:])) if parts.scheme == "http" else url


class CellarRedirects(urllib.request.HTTPRedirectHandler):
    """Follow redirects only within the Cellar hosts, always over https."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = _https(urllib.parse.urljoin(req.full_url, newurl))
        check_host(target)
        return super().redirect_request(req, fp, code, msg, headers, target)


def cellar_opener():
    return urllib.request.build_opener(CellarRedirects()).open


# --- metadata -----------------------------------------------------------------


@dataclass
class Metadata:
    celex: str
    fields: "dict[str, list[str]]"

    def all(self, name):
        return self.fields.get(name, [])

    def first(self, name):
        values = sorted(self.all(name))
        return values[0] if values else None

    @property
    def title(self):
        title = self.first("title_sv")
        return " ".join(title.split()) if title else None

    @property
    def manifestations(self):
        return set(self.all("manifestation_sv"))

    @property
    def consolidated(self):
        return sorted(c for c in set(self.all("consolidated")) if CELEX.fullmatch(c))

    @property
    def amendments(self):
        """(date of document, CELEX) of the amending acts a consolidated version incorporates.

        The base act, earlier consolidated versions and corrigenda (`R(nn)`) are left out.
        """
        base = "3" + self.celex[1:10]
        out = set()
        for value in self.all("consolidates"):
            celex, _, day = value.partition(" ")
            day = _date(day)
            if (day and _SCHEMA_CELEX.fullmatch(celex) and celex != base
                    and not celex.startswith("0") and not _CORRIGENDUM.search(celex)):
                out.add((day, celex))
        return sorted(out)


def metadata_url(celex):
    if not CELEX.fullmatch(celex):
        raise ValueError(f"unsupported CELEX number: {celex!r}")
    query = _QUERY % {"celex": celex}
    return SPARQL_URL + "?" + urllib.parse.urlencode({"query": query})


def parse_metadata(celex, raw):
    data = json.loads(raw.decode("utf-8"))
    fields = {}
    for row in data["results"]["bindings"]:
        name, value = row["field"]["value"], row["value"]["value"]
        if row["value"].get("type") == "uri" and name == "agent":
            value = value.rstrip("/").rsplit("/", 1)[-1]
        values = fields.setdefault(name, [])
        if value not in values:
            values.append(value)
    if not fields:
        raise ValueError(f"{celex} is not in Cellar")
    return Metadata(celex, fields)


def _utc(value):
    """An ISO date or date-time as UTC `YYYY-MM-DDTHH:MM:SS.fffZ`; naive values are UTC."""
    moment = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    moment = moment.astimezone(timezone.utc)
    return moment.strftime("%Y-%m-%dT%H:%M:%S.") + f"{moment.microsecond // 1000:03d}Z"


def changed_url(celexes, since):
    """SPARQL for the acts among `celexes` changed in Cellar after `since`."""
    for celex in celexes:
        if not CELEX.fullmatch(celex):
            raise ValueError(f"unsupported CELEX number: {celex!r}")
    values = " ".join(f'"{c}"^^xsd:string' for c in celexes)
    query = _CHANGED_QUERY % {"values": values, "since": _utc(since)}
    return SPARQL_URL + "?" + urllib.parse.urlencode({"query": query})


def parse_changed(raw):
    """CELEX -> newest modification (UTC) from a changed_url answer."""
    data = json.loads(raw.decode("utf-8"))
    out = {}
    for row in data["results"]["bindings"]:
        celex, latest = row["celex"]["value"], _utc(row["modified"]["value"])
        if CELEX.fullmatch(celex) and latest > out.get(celex, ""):
            out[celex] = latest
    return out


def _before(moment):
    """One millisecond before a UTC `_utc` value, so a strict `>` filter includes `moment`."""
    value = datetime.fromisoformat(moment.replace("Z", "+00:00")) - timedelta(milliseconds=1)
    return _utc(value.isoformat())


def latest_consolidated(metadata, today):
    """The newest consolidated version that applies on `today`, or None."""
    current = [c for c in metadata.consolidated if c[-8:] <= today.strftime("%Y%m%d")]
    return max(current, key=lambda c: c[-8:]) if current else None


# --- numbers ------------------------------------------------------------------

_INSTITUTIONS = r"(?:EU|EG|EEG|EKSG|Euratom|Gusp)(?:, (?:EU|EG|EEG|Euratom))?"
_NUMBER_IN_TITLE = re.compile(
    rf"\({_INSTITUTIONS}\) (?:nr )?\d{{1,4}}/\d{{1,4}}"
    rf"|(?<![\d/])\d{{2,4}}/\d{{1,4}}/(?:EU|EG|EEG|EKSG|Euratom|Gusp|RIF)(?:, (?:EU|EG|EEG|Euratom))?"
)
_NR_FORM = re.compile(rf"\({_INSTITUTIONS}\) nr (\d+)/(\d+)")
_YEAR_FORM = re.compile(rf"\({_INSTITUTIONS}\) (\d+)/(\d+)")
_SLASH_FORM = re.compile(r"(\d+)/(\d+)/.+")


def number_parts(number):
    """(year, ordinal) of a Swedish citation number, or None."""
    m = _NR_FORM.fullmatch(number)
    if m:
        return int(m.group(2)), int(m.group(1))
    m = _YEAR_FORM.fullmatch(number) or _SLASH_FORM.fullmatch(number)
    if not m:
        return None
    year = int(m.group(1))
    return (year + 1900 if year < 100 else year), int(m.group(2))


def derived_number(celex):
    """The Swedish citation form rebuilt from the CELEX number alone."""
    year, kind, ordinal = int(celex[1:5]), celex[5], int(celex[6:10])
    if year >= 2015:
        return f"(EU) {year}/{ordinal}"
    institution = "EEG" if year <= 1993 else "EG" if year <= 2009 else "EU"
    if kind == "R":
        return f"({institution}) nr {ordinal}/{year}"
    return f"{year % 100:02d}/{ordinal}/{institution}" if year < 2000 else f"{year}/{ordinal}/{institution}"


def citation_number(celex, title):
    """The number as cited in the Swedish title when it agrees with the CELEX number."""
    expected = (int(celex[1:5]), int(celex[6:10]))
    match = _NUMBER_IN_TITLE.search(title or "")
    if match and number_parts(match.group(0)) == expected:
        return match.group(0)
    return derived_number(celex)


# --- frontmatter --------------------------------------------------------------


def corpus_id(celex):
    return "eu-" + celex.lower()


def _date(value):
    value = (value or "")[:10]
    return value if _ISO_DATE.fullmatch(value) else None


def build_meta(metadata, raw_sha256, source, fetched_at):
    celex = metadata.celex
    type_ = _KINDS[celex[5]]
    consolidated = celex.startswith("0")
    entry = sorted(d for d in (_date(v) for v in metadata.all("entry_into_force")) if d)
    end = _date(metadata.first("end_of_validity"))
    issued = metadata.first("base_date_document") if consolidated else metadata.first("date_document")
    issuers = [ISSUERS[a] for a in ISSUERS if a in metadata.all("agent")]
    amended_by = {c for c in metadata.all("amended_by") if _SCHEMA_CELEX.fullmatch(c)}
    amendments = metadata.amendments if consolidated else []
    amended_by.update(c for _, c in amendments)
    return {
        "id": corpus_id(celex),
        "title": metadata.title,
        "type": type_,
        "layer": TYPES[type_],
        "number": citation_number(celex, metadata.title),
        "issued": _date(issued),
        "in_force": entry[0] if entry else None,
        "repealed": end if end and end != NO_END else None,
        "amended_by": sorted(amended_by),
        # The latest amending act a consolidated version incorporates; the OJ text has none.
        "amended_through": amendments[-1][1] if amendments else None,
        "reprinted_by": [],
        "ministry": None,
        "eli": metadata.first("eli"),
        "language": "sv",
        # The Official Journal text; consolidated versions have no legal effect.
        "authoritative": not consolidated,
        "source": source,
        "source_sha256": raw_sha256,
        "fetched_at": fetched_at,
        "issuer": " och ".join(issuers) or None,
        "celex": celex,
    }


# --- text ---------------------------------------------------------------------

_BLOCK_TAGS = frozenset(
    "address article aside blockquote body dd div dl dt figure footer h1 h2 h3 h4 h5 h6 "
    "header li main nav ol p section table tbody td tfoot th thead tr txt_te ul".split()
)
_VOID_TAGS = frozenset("area base br col embed hr img input link meta source wbr".split())
_SKIP_TAGS = frozenset({"head", "script", "style", "title"})
# OJ header, modification markers of consolidated texts and their reference line.
_SKIP_CLASSES = frozenset({"hd-date", "hd-lg", "hd-ti", "hd-oj", "arrow", "modref", "reference"})
# Class (without the `oj-` prefix of OJ XHTML) -> role in the Markdown.
_ROLES = {
    "ti-art": "article",
    "title-article-norm": "article",
    "sti-art": "subtitle",
    "stitle-article-norm": "subtitle",
    "ti-section-1": "division",
    "title-division-1": "division",
    "ti-section-2": "subtitle",
    "title-division-2": "subtitle",
}
_ARTICLE = re.compile(r"Artikel \d+[a-z]?")
_DIVISION = re.compile(
    r"(?:KAPITEL|AVDELNING|AVSNITT|DEL|Kapitel|Avdelning|Avsnitt|Del) [IVXLC\d]+[A-Za-z]?"
    r"|(?:BILAGA|Bilaga)(?: [IVXLC\d]+[A-Za-z]?)?"
)
_MARKERS = re.compile(r"[►▼][A-Z]\d*|◄")
# A point label alone in its cell or span: "(1)", "1.", "a)", "(iv)", "—".
_LABEL = re.compile(r"\(?\d{1,3}[a-z]?[.)]?|\(?[a-z]{1,2}\)|\(?[ivxlc]{1,6}\)|[–—•-]")


class _Blocks(HTMLParser):
    """Text blocks of a Cellar XHTML or HTML manifestation, with their role."""

    def __init__(self, scoped):
        super().__init__(convert_charrefs=True)
        self.blocks = []  # (role or None, text)
        self._stack = []  # (tag, role, skip, scope)
        self._text = []
        self._scoped = scoped  # old EUR-Lex HTML: only the text inside #TexteOnly
        self._rows = []  # open table rows: list of cells, each a list of blocks
        self._tables = []  # number of open rows when each open table started

    def handle_starttag(self, tag, attrs):
        if tag in _VOID_TAGS:
            if tag == "br":
                self._text.append(" ")
            elif tag == "hr":
                self._flush()
            return
        if tag in _BLOCK_TAGS:
            self._flush()
        if tag == "table":
            self._tables.append(len(self._rows))
        elif tag == "tr":
            self._rows.append([])
        elif tag in ("td", "th") and self._rows:
            self._rows[-1].append([])
        attrs = dict(attrs)
        classes = {c.removeprefix("oj-") for c in (attrs.get("class") or "").split()}
        role = next((_ROLES[c] for c in sorted(classes) if c in _ROLES), None)
        skip = tag in _SKIP_TAGS or bool(classes & _SKIP_CLASSES)
        self._stack.append((tag, role, skip, attrs.get("id") == "TexteOnly"))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in _VOID_TAGS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if tag in _VOID_TAGS or not any(entry[0] == tag for entry in self._stack):
            return
        if tag in _BLOCK_TAGS:
            self._flush()
        if tag == "tr" and self._rows:
            self._end_row()
        elif tag == "table" and self._tables:
            opened = self._tables.pop()
            while len(self._rows) > opened:  # rows left open by malformed markup
                self._end_row()
        while self._stack:
            if self._stack.pop()[0] == tag:
                break

    def handle_data(self, data):
        if any(entry[2] for entry in self._stack):
            return
        if self._scoped and not any(entry[3] for entry in self._stack):
            return
        self._text.append(data)

    def close(self):
        super().close()
        self._flush()
        while self._rows:
            self._end_row()

    def _emit(self, block):
        if not self._rows:
            self.blocks.append(block)
            return
        row = self._rows[-1]
        if not row:
            row.append([])
        row[-1].append(block)

    def _end_row(self):
        """A row whose first cell is a point label stays a list item; other rows become one line."""
        cells = [cell for cell in self._rows.pop() if cell]
        if len(cells) == 1 or (len(cells) == 2 and len(cells[0]) == 1 and _LABEL.fullmatch(cells[0][0][1])):
            for cell in cells:
                for block in cell:
                    self._emit(block)
        elif cells:
            self._emit((None, " | ".join(" ".join(text for _, text in cell) for cell in cells)))

    def _flush(self):
        # Modification markers of consolidated texts: ►M3 … ◄, ▼B.
        text = " ".join(_MARKERS.sub(" ", "".join(self._text)).split())
        self._text = []
        if text:
            role = next((entry[1] for entry in reversed(self._stack) if entry[1]), None)
            self._emit((role, text))


def text_blocks(raw):
    html = raw.decode("utf-8")
    parser = _Blocks(scoped='id="TexteOnly"' in html)
    parser.feed(html)
    parser.close()
    return parser.blocks


def to_markdown(title, raw):
    """Markdown for one manifestation: divisions as `##`, articles as `###`."""
    out = ["# " + title]
    label = None
    for role, text in text_blocks(raw):
        if role is None:
            if _ARTICLE.fullmatch(text):
                role = "article"
            elif _DIVISION.fullmatch(text):
                role = "division"
            elif _LABEL.fullmatch(text):
                label = text if label is None else f"{label} {text}"
                continue
        if label is not None:
            if role is None:
                text = f"{label} {text}"
            else:
                out.append(label)
            label = None
        if role == "article":
            out.append("### " + text)
        elif role == "division":
            out.append("## " + text)
        elif role == "subtitle":
            out.append(f"**{text}**")
        else:
            out.append(text)
    if label is not None:
        out.append(label)
    if len(out) == 1:
        raise ValueError("manifestation has no text")
    return "\n\n".join(out) + "\n"


# --- run ----------------------------------------------------------------------


@dataclass
class RunSummary:
    written: "list[str]" = field(default_factory=list)
    unchanged: "list[str]" = field(default_factory=list)
    skipped: int = 0
    gaps: "list[str]" = field(default_factory=list)
    failed: "list[str]" = field(default_factory=list)
    blocked: bool = False
    # --changed-since: the newest Cellar modification among the changed acts, and the
    # point to resume from when some of them were not collected.
    latest_modified: "str | None" = None
    retry_from: "str | None" = None


def _celex_arg(value):
    items = [v.strip().upper() for v in value.split(",") if v.strip()]
    for item in items:
        if not CELEX.fullmatch(item):
            raise argparse.ArgumentTypeError(
                f"not a CELEX number of a regulation, directive or decision: {item}"
            )
    return items


def _rate(value):
    rate = float(value)
    if rate < DEFAULT_RATE:
        raise argparse.ArgumentTypeError(f"must be at least {DEFAULT_RATE} seconds: {value}")
    return rate


def _since(value):
    try:
        return _utc(value)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"expected YYYY-MM-DD or an ISO date-time such as 2026-10-29T05:00:00Z: {value}"
        ) from None


def _non_negative(value):
    number = int(value)
    if number < 0:
        raise argparse.ArgumentTypeError(f"must not be negative: {value}")
    return number


def parse_args(argv):
    parser = argparse.ArgumentParser(prog="collect.py eu")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--celex", type=_celex_arg, action="extend", metavar="CELEX[,CELEX...]")
    source.add_argument("--list", metavar="FILE", help=f"JSON list of acts, e.g. {DEFAULT_LIST}")
    parser.add_argument("--consolidated", action="store_true",
                        help="also collect each act's latest consolidated version")
    parser.add_argument("--refresh", action="store_true", help="refetch acts already collected")
    parser.add_argument("--changed-since", type=_since, metavar="DATE[TIME]",
                        help="only (re)collect acts that Cellar changed after this moment (UTC)")
    parser.add_argument("--limit", type=_non_negative, help="stop after N written documents")
    parser.add_argument("--cache", metavar="DIR", help="keep the fetched bytes in DIR")
    parser.add_argument("--offline", action="store_true",
                        help="read metadata and text from --cache instead of the network")
    parser.add_argument("--report", metavar="FILE", help="write a JSON run report")
    parser.add_argument("--rate", type=_rate, default=DEFAULT_RATE, metavar="SECONDS")
    parser.add_argument("--state", default=DEFAULT_STATE)
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST)
    parser.add_argument("--corpus", default="corpus")
    args = parser.parse_args(argv)
    if args.offline and not args.cache:
        parser.error("--offline needs --cache")
    if args.offline and args.changed_since:
        parser.error("--offline cannot ask Cellar what changed")
    return args


def load_list(path):
    """CELEX numbers of a list file: `[{"celex": "32016R0679", "name": "..."}, ...]`."""
    try:
        entries = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ListingError(f"list file {path}: {error}") from None
    if not isinstance(entries, list):
        raise ListingError(f"list file {path}: expected a JSON list")
    out = []
    for entry in entries:
        celex = entry.get("celex") if isinstance(entry, dict) else None
        if not isinstance(celex, str) or not CELEX.fullmatch(celex):
            raise ListingError(f"list file {path}: bad entry {entry!r}")
        out.append(celex)
    return out


def _candidates(args):
    items = args.celex if args.celex else load_list(args.list)
    return list(dict.fromkeys(items))


def _load_state(path):
    state = {"done": {}, "failed": {}, "gaps": {}, "blocked": None}
    try:
        loaded = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return state
    except (ValueError, OSError):
        raise StateError(f"state file corrupt: {path}") from None
    if not isinstance(loaded, dict) or not all(
        isinstance(loaded.get(k, {}), dict) for k in ("done", "failed", "gaps")
    ):
        raise StateError(f"state file corrupt: {path}")
    for key in state:
        if key in loaded:
            state[key] = loaded[key]
    return state


def load_manifest(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"version": MANIFEST_VERSION, "source": BASE, "acts": [], "gaps": []}
    except (OSError, ValueError):
        raise StateError(f"manifest corrupt: {path}") from None
    if not isinstance(data, dict) or not isinstance(data.get("acts"), list):
        raise StateError(f"manifest corrupt: {path}")
    data.setdefault("gaps", [])
    return data


def save_manifest(path, manifest):
    manifest["acts"].sort(key=lambda e: e["celex"])
    manifest["gaps"].sort(key=lambda e: e["celex"])
    _save_state(path, manifest)


def _record_act(manifest, entry):
    manifest["gaps"] = [g for g in manifest["gaps"] if g["celex"] != entry["celex"]]
    old = next((e for e in manifest["acts"] if e["celex"] == entry["celex"]), None)
    if old is not None and old.get("sha256") == entry["sha256"] and old.get("url") == entry["url"]:
        return  # same bytes: keep the first retrieval date
    manifest["acts"] = [e for e in manifest["acts"] if e["celex"] != entry["celex"]]
    manifest["acts"].append(entry)


def _record_gap(manifest, celex, reason):
    manifest["gaps"] = [g for g in manifest["gaps"] if g["celex"] != celex]
    manifest["gaps"].append({"celex": celex, "reason": reason})


def _robots_allows(client):
    try:
        raw = client.get(check_host(ROBOTS_URL))
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return True
        raise ListingError(f"robots.txt: HTTP {error.code}") from error
    except (*NETWORK_ERRORS, ForbiddenHost) as error:
        raise ListingError(f"robots.txt: {error}") from error
    parser = urllib.robotparser.RobotFileParser()
    parser.parse(raw.decode("utf-8", errors="replace").splitlines())
    return all(parser.can_fetch(USER_AGENT, BASE + path) for path in ROBOTS_PATHS)


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class _Cache:
    """Fetched bytes under DIR: `<CELEX>.sparql.json`, `<CELEX>.<format>` and `<CELEX>.source.json`."""

    def __init__(self, directory, offline):
        self.dir = Path(directory) if directory else None
        self.offline = offline

    def read(self, name):
        try:
            return (self.dir / name).read_bytes()
        except OSError as error:
            raise ValueError(f"not in the cache: {name}") from error

    def write(self, name, raw):
        if self.dir is not None and not self.offline:
            self.dir.mkdir(parents=True, exist_ok=True)
            (self.dir / name).write_bytes(raw)


def fetch_metadata(client, celex, cache=None):
    cache = cache or _Cache(None, False)
    name = f"{celex}.sparql.json"
    if cache.offline:
        raw = cache.read(name)
    else:
        raw = client.get(check_host(metadata_url(celex)), SPARQL_HEADERS)
        cache.write(name, raw)
    return parse_metadata(celex, raw)


def fetch_changed(client, celexes, since):
    """CELEX -> newest Cellar modification, for the acts changed after `since`."""
    return parse_changed(client.get(check_host(changed_url(celexes, since)), SPARQL_HEADERS))


def _text_format(metadata):
    if metadata.title is None:
        raise Gap("no Swedish expression")
    for name in FORMATS:
        if name in metadata.manifestations:
            return name
    found = ", ".join(sorted(metadata.manifestations)) or "none"
    raise Gap(f"no Swedish XHTML or HTML manifestation (found: {found})")


def _fetch_text(client, celex, fmt, cache):
    accept, expected = FORMATS[fmt]
    if cache.offline:
        raw = cache.read(f"{celex}.{fmt}")
        source = json.loads(cache.read(f"{celex}.source.json").decode("utf-8"))
        content_type, final = source["content_type"], source["url"]
    else:
        url = check_host(CELEX_URL.format(celex=celex))
        raw, content_type, final = client.fetch_final(url, {"Accept": accept, "Accept-Language": "swe"})
    final = _https(final)
    check_host(final)
    if content_type not in expected:
        raise ValueError(f"expected {fmt}, got {content_type}")
    cache.write(f"{celex}.{fmt}", raw)
    cache.write(f"{celex}.source.json", json.dumps({"url": final, "content_type": content_type}).encode())
    return raw, content_type, final


def _unchanged(meta, body, corpus):
    """True when the stored file matches apart from `fetched_at`; a converter change rewrites it."""
    path = writer.path_for(meta, corpus)
    try:
        stored, stored_body = frontmatter.load(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    stored.pop("fetched_at", None)
    return stored_body == body and stored == {k: v for k, v in meta.items() if k != "fetched_at"}


def _done(state, celex, corpus):
    if celex not in state["done"]:
        return False
    meta = {"id": corpus_id(celex), "type": _KINDS[celex[5]]}
    return writer.path_for(meta, corpus).exists()


def _drop_older_consolidated(celex, corpus):
    """Remove stored consolidated versions of the same act other than `celex`."""
    path = writer.path_for({"id": corpus_id(celex), "type": _KINDS[celex[5]]}, corpus)
    removed = []
    for other in sorted(path.parent.glob(celex[:10].lower() + "-*.md")):
        if other != path:
            other.unlink()
            removed.append(other.name)
    return removed


def _store(client, celex, metadata, args, manifest, cache):
    """Fetch, convert and write one act; returns True when the corpus changed."""
    fmt = _text_format(metadata)
    raw, content_type, source = _fetch_text(client, celex, fmt, cache)
    sha = hashlib.sha256(raw).hexdigest()
    meta = build_meta(metadata, sha, source, _now())
    body = to_markdown(meta["title"], raw)
    _record_act(manifest, {
        "celex": celex,
        "id": meta["id"],
        "url": source,
        "content_type": content_type,
        "bytes": len(raw),
        "sha256": sha,
        "retrieved_at": meta["fetched_at"],
    })
    if _unchanged(meta, body, args.corpus):
        return sha, False
    writer.write(meta, body, args.corpus)
    if celex.startswith("0"):
        _drop_older_consolidated(celex, args.corpus)
    return sha, True


def _write_report(path, summary):
    report = {
        "written": summary.written,
        "unchanged": summary.unchanged,
        "skipped": summary.skipped,
        "gaps": summary.gaps,
        "failed": summary.failed,
        "blocked": summary.blocked,
        "latest_modified": summary.latest_modified,
        "retry_from": summary.retry_from,
    }
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run(client, args, today=None):
    today = today or date.today()
    summary = RunSummary()
    state = _load_state(args.state)
    manifest = load_manifest(args.manifest)
    state["blocked"] = None

    def finish():
        _save_state(args.state, state)
        save_manifest(args.manifest, manifest)
        if args.report:
            _write_report(args.report, summary)
        return summary

    def finish_blocked(message):
        summary.blocked = True
        state["blocked"] = message
        return finish()

    cache = _Cache(args.cache, args.offline)
    if not args.offline:
        try:
            if not _robots_allows(client):
                return finish_blocked("robots.txt disallows the Cellar SPARQL or resource paths")
        except Blocked as error:
            return finish_blocked(str(error))
    candidates = _candidates(args)
    changed = None  # --changed-since: CELEX -> newest modification
    if args.changed_since:
        try:
            changed = fetch_changed(client, candidates, args.changed_since) if candidates else {}
        except Blocked as error:
            return finish_blocked(str(error))
        except DOCUMENT_ERRORS as error:
            finish()
            raise ListingError(f"changed acts: {type(error).__name__}: {error}") from error
        candidates = [c for c in candidates if c in changed]
        summary.latest_modified = max(changed.values(), default=None)
    refresh = args.refresh or changed is not None
    complete = set()  # acts collected (or recorded as gaps) together with their consolidated version

    def settle():
        if changed:
            pending = [changed[c] for c in candidates if c not in complete]
            summary.retry_from = _before(min(pending)) if pending else None

    def collect(celex, metadata=None):
        """Collect one act; returns its metadata (None when it failed or was skipped)."""
        if args.limit is not None and len(summary.written) >= args.limit:
            return None
        try:
            if metadata is None:
                metadata = fetch_metadata(client, celex, cache)
            if _done(state, celex, args.corpus) and not refresh:
                summary.skipped += 1
                return metadata
            sha, written = _store(client, celex, metadata, args, manifest, cache)
        except Blocked:
            raise
        except Gap as gap:
            summary.gaps.append(celex)
            state["gaps"][celex] = str(gap)
            state["failed"].pop(celex, None)
            _record_gap(manifest, celex, str(gap))
            return metadata
        except DOCUMENT_ERRORS as error:
            summary.failed.append(celex)
            state["failed"][celex] = f"{type(error).__name__}: {error}"
            return metadata
        (summary.written if written else summary.unchanged).append(celex)
        state["done"][celex] = sha
        state["failed"].pop(celex, None)
        state["gaps"].pop(celex, None)
        return metadata

    try:
        for celex in candidates:
            if args.limit is not None and len(summary.written) >= args.limit:
                break
            if not args.consolidated and not refresh and _done(state, celex, args.corpus):
                summary.skipped += 1
                complete.add(celex)
                continue
            failed_before = len(summary.failed)
            metadata = collect(celex)
            if args.consolidated and metadata is not None and not celex.startswith("0"):
                latest = latest_consolidated(metadata, today)
                if latest:
                    collect(latest)
            if metadata is not None and len(summary.failed) == failed_before:
                complete.add(celex)
            _save_state(args.state, state)
    except Blocked as error:
        settle()
        return finish_blocked(str(error))
    except ListingError:
        settle()
        finish()
        raise
    settle()
    return finish()


def main(argv, client=None):
    if argv and argv[0] == "eu":
        argv = argv[1:]
    args = parse_args(argv)
    if client is None:
        client = PoliteClient(USER_AGENT, min_interval=args.rate, opener=cellar_opener())
    try:
        summary = run(client, args)
    except (ListingError, StateError) as error:
        print(f"error: {error}", file=sys.stderr, flush=True)
        return 1
    print(
        f"done: {len(summary.written)} written, {len(summary.unchanged)} unchanged, "
        f"{summary.skipped} skipped, {len(summary.gaps)} gaps, {len(summary.failed)} failed"
        + (", BLOCKED" if summary.blocked else ""),
        flush=True,
    )
    if summary.gaps:
        print("gaps: " + ", ".join(summary.gaps), flush=True)
    if summary.failed:
        print("failed: " + ", ".join(summary.failed), flush=True)
    if summary.blocked:
        print("blocked: see state file", file=sys.stderr)
        return 2
    return 0
