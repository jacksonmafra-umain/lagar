"""Resumable collector for agency regulations (myndighetsföreskrifter).

There is no central database: every agency publishes its own series on its own
site. One small adapter per series lists the regulations and parses a detail
page; the shared run loop handles robots.txt, rate limiting, state, PDF
snapshots and writing. Pilot series:

- AFS (Arbetsmiljöverket): one HTML page per regulation with the full,
  consolidated text. The original PDFs sit under a path robots.txt disallows
  and are never requested.
- FFFS (Finansinspektionen): a register page per regulation with metadata,
  FI's summary and links to the base and consolidated PDFs.
- TSFS (Transportstyrelsen): a year listing and a detail page per regulation
  with the base, consolidated and amending PDFs.

Series whose official page is a plain list of links to the regulation PDFs need
no code: `collector/data/agency-series.json` lists them, and `ListedAdapter`
reads every regulation, its amendments and consolidated versions from the links.

Only base regulations (grundförfattningar) are stored; amending regulations are
listed in the base regulation's `amended_by`. PDFs are downloaded once to record
their SHA-256 in a manifest; their text is not extracted, so a regulation that is
published only as PDF gets a body with its metadata and links to the PDFs.
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
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

from . import frontmatter, htmlmd
from .caselaw import NETWORK_ERRORS, USER_AGENT, StateError, _load_state, _save_state
from .http import Blocked, PoliteClient
from .vocabulary import TYPES
from .writer import existing_path, path_for, write

DEFAULT_STATE = "collector/data/agency-state.json"
DEFAULT_MANIFEST = "sources/agency-pdf-manifest.json"
SERIES_CONFIG = Path(__file__).resolve().parents[1] / "data" / "agency-series.json"
MANIFEST_VERSION = 1
TYPE = "agency_regulation"
MIN_RATE = 1.0

DOCUMENT_ERRORS = NETWORK_ERRORS + (ValueError, KeyError, UnicodeDecodeError)

_SPACE = re.compile(r"\s+")
_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}", re.ASCII)
_NUMBER = re.compile(r"(\d{4}):(\d+)", re.ASCII)
_VOID = frozenset({"area", "base", "br", "col", "embed", "hr", "img", "input", "link",
                   "meta", "source", "track", "wbr"})


class NotBase(ValueError):
    """The detail page belongs to an amending regulation; it is not stored on its own."""


class ListingError(Exception):
    """A listing page (or robots.txt) could not be read; the run cannot continue."""


def _clean(value):
    value = (value or "").replace("\u00a0", " ").replace("\u00ad", "").replace("\u200b", "")
    return _SPACE.sub(" ", value).strip()


def _date(text):
    match = _ISO_DATE.search(text or "")
    return match.group(0) if match else None


def number_key(number):
    match = _NUMBER.search(number)
    return (int(match.group(1)), int(match.group(2))) if match else (sys.maxsize, sys.maxsize)


def corpus_id(number):
    """`AFS 2023:1` -> `afs-2023-1`, `HSLF-FS 2016:40` -> `hslf-fs-2016-40`.

    `å` becomes `aa`, so Åklagarmyndigheten's `ÅFS 2023:7` (`aafs-2023-7`) does
    not collide with Arbetsmiljöverket's `AFS 2023:7`.
    """
    slug = number.lower().translate(str.maketrans({"å": "aa", "ä": "a", "ö": "o"}))
    return re.sub(r"[^0-9a-z]+", "-", slug).strip("-")


def absolute(base, href):
    """An absolute URL for `href`, with spaces and other unsafe path and query characters quoted."""
    parts = urllib.parse.urlsplit(urllib.parse.urljoin(base, html.unescape(href.strip())))
    path = urllib.parse.quote(urllib.parse.unquote(parts.path), safe="/:@!$&'()*+,;=-._~")
    query = urllib.parse.quote(parts.query, safe="/:@!$&'()*+,;=-._~?%")  # keeps existing escapes
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, path, query, ""))


# --- a small DOM -----------------------------------------------------------

class Node:
    __slots__ = ("tag", "attrs", "children")

    def __init__(self, tag, attrs=None):
        self.tag = tag
        self.attrs = dict(attrs or {})
        self.children = []

    @property
    def classes(self):
        return set((self.attrs.get("class") or "").split())

    def iter(self):
        for child in self.children:
            if isinstance(child, Node):
                yield child
                yield from child.iter()

    def find_all(self, tag=None, cls=None):
        return [n for n in self.iter()
                if (tag is None or n.tag == tag) and (cls is None or cls in n.classes)]

    def find(self, tag=None, cls=None):
        return next(iter(self.find_all(tag, cls)), None)

    def text(self):
        parts = []

        def walk(node):
            for child in node.children:
                if isinstance(child, str):
                    parts.append(child)
                elif child.tag in ("script", "style"):
                    continue
                else:
                    if child.tag == "br":
                        parts.append(" ")
                    walk(child)

        walk(self)
        return _clean("".join(parts))


class _TreeBuilder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("#root")
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs)
        self.stack[-1].children.append(node)
        if tag not in _VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.stack[-1].children.append(Node(tag, attrs))

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def parse_html(text):
    builder = _TreeBuilder()
    builder.feed(text)
    builder.close()
    return builder.root


def to_html(node):
    if isinstance(node, str):
        return html.escape(node, quote=False)
    inner = "".join(to_html(c) for c in node.children)
    if node.tag == "#root":
        return inner
    attrs = "".join(f' {k}="{html.escape(v or "", quote=True)}"' for k, v in node.attrs.items())
    if node.tag in _VOID:
        return f"<{node.tag}{attrs}>"
    return f"<{node.tag}{attrs}>{inner}</{node.tag}>"


# --- the parsed model ------------------------------------------------------

@dataclass
class Entry:
    """One listing row."""
    number: str
    title: str
    url: str
    base: bool = True
    in_force: "str | None" = None
    repealed: "str | None" = None
    amended_by: "list[str]" = field(default_factory=list)
    pdfs: "list[tuple[str, str]]" = field(default_factory=list)  # listed series: (label, url)


@dataclass
class Amendment:
    number: str
    in_force: "str | None" = None
    scope: "str | None" = None
    url: "str | None" = None


@dataclass
class Regulation:
    """One parsed detail page."""
    number: str
    title: str
    issued: "str | None" = None
    in_force: "str | None" = None
    repealed: "str | None" = None
    amended_by: "list[str]" = field(default_factory=list)
    amended_through: "str | None" = None
    version: "str | None" = None  # "Grundförfattning" or "Konsoliderad version"
    published: "str | None" = None  # Utkom från tryck
    summary: str = ""  # agency's own summary, Markdown
    text: str = ""  # regulation text, Markdown
    footnotes: "list[str]" = field(default_factory=list)
    pdfs: "list[tuple[str, str]]" = field(default_factory=list)  # (label, url)
    amendments: "list[Amendment]" = field(default_factory=list)


def _check_number(found, entry):
    if _clean(found) != entry.number:
        raise ValueError(f"detail page shows {found!r}, expected {entry.number}")


# --- Arbetsmiljöverket (AFS) -----------------------------------------------

_AFS_REF = re.compile(r"AFS \d{4}:\d+")
_AFS_AMENDMENT = re.compile(r"(AFS \d{4}:\d+)\b.*?ändring av (AFS \d{4}:\d+)")
_AFS_THROUGH = re.compile(r"införda till och med (AFS \d{4}:\d+)")
_LIST_MARKERS = {
    "lower-alpha": lambda n: "abcdefghijklmnopqrstuvwxyz"[(n - 1) % 26],
    "upper-alpha": lambda n: "ABCDEFGHIJKLMNOPQRSTUVWXYZ"[(n - 1) % 26],
    "lower-roman": lambda n: _roman(n).lower(),
    "upper-roman": lambda n: _roman(n),
    "decimal": str,
}


def _roman(n):
    out = []
    for value, letters in ((1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"),
                           (90, "XC"), (50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"),
                           (4, "IV"), (1, "I")):
        while n >= value:
            out.append(letters)
            n -= value
    return "".join(out)


class _AfsText:
    """Rewrites the provision markup into plain HTML for htmlmd.

    - footnote dialogs are moved to `footnotes`; their buttons become `[n]`;
    - other buttons (close, "show the whole table") and guidance links are dropped;
    - table dialogs are unwrapped, and every table cell is flattened to text;
    - a section sign (`1 §`) is put in bold at the start of the next paragraph;
    - "Allmänna råd" captions become bold paragraphs;
    - lists numbered a), b) or i., ii. keep their markers.
    """

    def __init__(self):
        self.footnotes = []
        self.pending = ""

    def render(self, node):
        out = []
        self._children(node, out)
        return "".join(out)

    def _children(self, node, out):
        for child in node.children:
            self._node(child, out)

    def _node(self, node, out):
        if isinstance(node, str):
            out.append(html.escape(node, quote=False))
            return
        cls = node.classes
        if node.tag == "button":
            if "footnote" in cls:
                out.append(f"[{_clean(node.attrs.get('data-footnote') or node.text())}]")
            return
        if node.tag in ("script", "style") or "provisioncmsurl" in cls:
            return
        if "footnote" in cls:
            self.footnotes.append(node.text())
            return
        if cls & {"provision__dialog-wrapper", "provision__dialog", "provision__table-overlay"}:
            self._children(node, out)
            return
        if "section-sign" in cls:
            self.pending += f"<strong>{html.escape(node.text())}</strong> "
            return
        if node.tag == "div" and "h2" in cls:
            out.append(f"<p><strong>{html.escape(node.text())}</strong></p>")
            return
        if node.tag in ("td", "th"):
            cell = " ".join(p for p in (self._cell_text(c) for c in node.children) if p)
            out.append(f"<{node.tag}>{html.escape(cell)}</{node.tag}>")
            return
        if node.tag == "ol":
            self._list(node, out)
            return
        if node.tag == "p":
            out.append("<p>" + self.pending)
            self.pending = ""
            self._children(node, out)
            out.append("</p>")
            return
        out.append(f"<{node.tag}>")
        if node.tag not in _VOID:
            self._children(node, out)
            out.append(f"</{node.tag}>")

    def _cell_text(self, node):
        if isinstance(node, str):
            return _clean(node)
        if node.tag == "button" or "footnote" in node.classes:
            return ""
        if node.tag == "li":
            return "– " + node.text()
        if node.tag in ("ul", "ol", "div"):
            return " ".join(p for p in (self._cell_text(c) for c in node.children) if p)
        return node.text()

    def _list(self, node, out):
        cls = node.classes
        style = next((c.removeprefix("liststyle-") for c in cls if c.startswith("liststyle-")), "decimal")
        suffix = next((c.removeprefix("listsuffix-") for c in cls if c.startswith("listsuffix-")), ".")
        if style == "decimal" and suffix == ".":
            out.append("<ol>")
            self._children(node, out)
            out.append("</ol>")
            return
        marker = _LIST_MARKERS.get(style, str)
        out.append("<ul>")
        number = 0
        for child in node.children:
            if isinstance(child, Node) and child.tag == "li":
                number += 1
                self.pending += html.escape(f"{marker(number)}{suffix} ")
            self._node(child, out)
        out.append("</ul>")


def afs_text(provision):
    """(Markdown, footnotes) for the `div.provision` element of an AFS page."""
    writer = _AfsText()
    markup = writer.render(provision)
    return htmlmd.to_markdown(markup, heading_offset=1), writer.footnotes


class AfsAdapter:
    detail = True
    series = "AFS"
    issuer = "Arbetsmiljöverket"
    base_url = "https://www.av.se"
    listing_url = base_url + "/arbetsmiljoarbete-och-inspektioner/publikationer/foreskrifter/"
    has_text = True

    def listing_urls(self, args):
        return [self.listing_url]

    def parse_listing(self, text, url):
        """Base regulations in force (with their amendments in force) from the overview page.

        The page also lists the repealing regulations in force ("Gällande
        ändringsföreskrifter med upphävanden") in an accordion; they are not base
        regulations.
        """
        root = parse_html(text)
        amendments = {}
        for link in root.find_all("a"):
            match = _AFS_AMENDMENT.search(link.text())
            if match:
                amendments.setdefault(match.group(2), set()).add(match.group(1))
        amending = {id(block) for accordion in root.find_all("ul", "accordion")
                    for block in accordion.find_all("div", "pagelist__items")}
        entries = []
        for block in root.find_all("div", "pagelist__items"):
            for link in block.find_all("a"):
                number_node, title_node = link.find("span", "publication-id"), link.find("span", "publication-title")
                if number_node is None or not _AFS_REF.fullmatch(number_node.text()):
                    continue
                number = number_node.text()
                entries.append(Entry(
                    number=number,
                    title=title_node.text() if title_node else number,
                    url=absolute(url, link.attrs.get("href", "")),
                    base=id(block) not in amending,
                    amended_by=sorted(amendments.get(number, ()), key=number_key),
                ))
        if not entries:
            raise ValueError("no regulations found on the AFS overview page")
        return entries

    def parse_detail(self, text, entry):
        root = parse_html(text)
        abbr = root.find("span", "provision-abbr")
        if abbr is not None:
            _check_number(abbr.text(), entry)
        top = root.find("aside", "provision__top")
        heading = top.find("h1") if top else None
        if heading is None:
            raise ValueError("no title on the detail page")
        facts = {}
        info = root.find("div", "desktop-document-info") or top
        for row in info.find_all("div", "small-text"):
            label = row.find("span", "fat-text")
            if label is not None:
                facts[label.text().rstrip(":")] = row.text().removeprefix(label.text()).strip()
        through = None
        for block in root.find_all("div", "document-info"):
            match = _AFS_THROUGH.search(block.text())
            if match:
                through = match.group(1)
        provision = root.find("div", "provision")
        if provision is None:
            raise ValueError("no regulation text on the detail page")
        body, footnotes = afs_text(provision)
        kind = facts.get("Typ", "")
        return Regulation(
            number=entry.number,
            title=heading.text(),
            issued=_date(facts.get("Beslutad")),
            in_force=_date(facts.get("Träder i kraft")),
            published=_date(facts.get("Utkom från tryck")),
            amended_by=list(entry.amended_by),
            amended_through=through,
            version="Konsoliderad version" if "onsoliderad" in kind else ("Grundförfattning" if kind else None),
            text=body,
            footnotes=footnotes,
        )


# --- Finansinspektionen (FFFS) ---------------------------------------------

class FffsAdapter:
    detail = True
    series = "FFFS"
    issuer = "Finansinspektionen"
    base_url = "https://www.fi.se"
    listing_url = base_url + "/sv/vara-register/fffs/forteckning-fffs/"
    has_text = False

    def listing_urls(self, args):
        return [self.listing_url]

    def parse_listing(self, text, url):
        """All regulations in force, newest first; Typ tells base from amending ones."""
        root = parse_html(text)
        entries = []
        for item in root.find_all("li", "extended-click-area"):
            fields = _definition_list(item)
            number = fields.get("Nummer", (None, None))[0]
            title, link = fields.get("Rubrik", (None, None))
            if not number or not _NUMBER.fullmatch(number) or link is None:
                continue
            kind = fields.get("Typ", ("", None))[0]
            entries.append(Entry(
                number=f"FFFS {number}",
                title=title,
                url=absolute(url, link.attrs.get("href", "")),
                base=kind.startswith("Grundförfattning"),
            ))
        if not entries:
            raise ValueError("no regulations found in the FFFS register")
        return entries

    def parse_detail(self, text, entry):
        root = parse_html(text)
        page = root.find("div", "page") or root
        heading = page.find("h1")
        if heading is None:
            raise ValueError("no number on the detail page")
        _check_number(heading.text(), entry)
        title = page.find("h2")
        regulation = Regulation(number=entry.number, title=title.text() if title else entry.title,
                                version="Grundförfattning")
        regulation.in_force = _date((page.find("div", "date-and-category") or Node("x")).text())
        editor = page.find("div", "editor-content")
        if editor is not None:
            regulation.summary = htmlmd.to_markdown(to_html(editor), heading_offset=-1)
        section = None
        for node in _flat_blocks(page):
            if node.tag == "h3":
                section = node.text()
            elif section == "Dokument" and "link-list" in node.classes:
                for link in node.find_all("a"):
                    regulation.pdfs.append((link.text(), absolute(self.base_url, link.attrs.get("href", ""))))
            elif section == "Ändringar" and "changes" in node.classes:
                for item in node.find_all("li"):
                    fields = _definition_list(item)
                    number = fields.get("Nummer", ("", None))[0]
                    if not re.fullmatch(r"FFFS \d{4}:\d+", number):
                        continue
                    link = fields.get("Rubrik", (None, None))[1]
                    regulation.amendments.append(Amendment(
                        number=number,
                        in_force=_date(fields.get("Datum", ("", None))[0]),
                        url=absolute(self.base_url, link.attrs["href"]) if link is not None and link.attrs.get("href") else None,
                    ))
        regulation.amended_by = sorted({a.number for a in regulation.amendments}, key=number_key)
        return regulation


def _definition_list(node):
    """{dt text: (dd text, first link in dd)} for the first <dl> in `node`."""
    dl = node.find("dl")
    fields, label = {}, None
    for child in dl.children if dl is not None else ():
        if isinstance(child, Node) and child.tag == "dt":
            label = child.text()
        elif isinstance(child, Node) and child.tag == "dd" and label and label not in fields:
            fields[label] = (child.text(), child.find("a"))
    return fields


def _flat_blocks(page):
    """Direct children of `page`, in order (the register page is flat)."""
    return [c for c in page.children if isinstance(c, Node)]


# --- Transportstyrelsen (TSFS) ---------------------------------------------

_TSFS_AMENDING = re.compile(r"(Transportstyrelsens )?[Ff]öreskrifter om (ändring|ändringar|upphävande) ")
_TSFS_REF = re.compile(r"TSFS \d{4}:\d+")


class TsfsAdapter:
    detail = True
    series = "TSFS"
    issuer = "Transportstyrelsen"
    base_url = "https://www.transportstyrelsen.se"
    index_url = base_url + "/sv/om-oss/dina-rattigheter-lagar-och-regler/forfattningssamling/ts-foreskrifter-i-nummerordning/"
    listing_url = index_url
    has_text = False

    def year_url(self, year):
        return f"{self.index_url}{year}/"

    def listing_urls(self, args):
        return [self.year_url(y) for y in sorted(set(args.year), reverse=True)] if args.year else None

    def parse_index(self, text):
        """The years of the number-order index, newest first."""
        years = {int(m.group(1)) for m in re.finditer(
            r"ts-foreskrifter-i-nummerordning/(\d{4})/\"", text)}
        if not years:
            raise ValueError("no years found on the TSFS index")
        return sorted(years, reverse=True)

    def parse_listing(self, text, url):
        root = parse_html(text)
        entries = []
        for item in root.find_all("li", "tsfs-item"):
            cells = [c for c in item.children if isinstance(c, Node)]
            number = cells[0].text() if cells else ""
            link = item.find("a")
            if not _TSFS_REF.fullmatch(number) or link is None:
                continue
            title = link.text().removesuffix(", " + number)
            status = item.find("span", "small")
            badge = item.find("span", "badge")
            repealed = None
            if badge is not None and badge.text().startswith("Upphävd"):
                repealed = _date(badge.text())
            entries.append(Entry(
                number=number,
                title=title,
                url=absolute(url, link.attrs.get("href", "")),
                base=not _TSFS_AMENDING.match(title),
                in_force=_date(status.text()) if status is not None else None,
                repealed=repealed,
            ))
        return entries

    def parse_detail(self, text, entry):
        root = parse_html(text)
        main = root.find("main") or root
        heading = main.find("h1")
        if heading is None:
            raise ValueError("no number on the detail page")
        head = [_clean(c) if isinstance(c, str) else c for c in heading.children]
        first = next((c for c in head if isinstance(c, str) and c), "")
        if first != entry.number and re.search(re.escape(entry.number) + r"(?!\d)", main.text()):
            raise NotBase(f"{entry.number} is shown as an amendment of {first}")
        _check_number(first, entry)
        title = heading.text().removeprefix(first).strip() or entry.title
        regulation = Regulation(number=entry.number, title=title, in_force=entry.in_force,
                                repealed=entry.repealed, version="Grundförfattning")
        lead = main.find("div", "lead")
        if lead is not None:
            regulation.summary = htmlmd.to_markdown(to_html(lead))
        section = None
        for node in [c for c in main.children if isinstance(c, Node)]:
            if node.tag == "h2":
                section = node.text()
                continue
            if "list-group" not in node.classes:
                continue
            for item in node.find_all("div", "list-group-item"):
                link = item.find("a")
                if link is None:
                    continue
                url = absolute(self.base_url, link.attrs.get("href", ""))
                date = _date(item.text())
                if section == "Konsoliderad version":
                    regulation.pdfs.append((f"{entry.number} (konsoliderad version)", url))
                elif section == "Grundform":
                    regulation.pdfs.append((entry.number, url))
                    regulation.in_force = date or regulation.in_force
                elif section == "Ändringar":
                    ref = _TSFS_REF.search(link.text())
                    if ref is None:
                        continue
                    scope = [p.text() for p in item.find_all("p") if "small" not in p.classes]
                    regulation.amendments.append(Amendment(
                        number=ref.group(0), in_force=date, scope=" ".join(s for s in scope if s) or None, url=url,
                    ))
        regulation.amended_by = sorted({a.number for a in regulation.amendments}, key=number_key)
        return regulation


# --- Swedac (STAFS) ---------------------------------------------------------

_MD_HEADING = re.compile(r"^(#{1,5}) ", re.M)
_MD_ROOT_LINK = re.compile(r"\]\((/[^)\s]*)\)")
_STAFS_REF = re.compile(r"STAFS \d{4}:\d+")


class SwedacAdapter:
    """Swedac's regulation register: a JSON index and one Markdown file per regulation.

    `foreskrifter.json` lists every STAFS regulation, in force and repealed,
    with its dates, the regulation it amends (`andrar`) or repeals, and links
    to the PDF and to a Markdown version of the text (the consolidated version
    when there is one). The Markdown file is the source of the stored text.
    """

    series = "STAFS"
    issuer = "Styrelsen för ackreditering och teknisk kontroll"
    base_url = "https://regelverk.swedac.se"
    listing_url = base_url + "/foreskrifter.json"
    detail = True
    has_text = True

    def __init__(self):
        self.items, self.originals = {}, {}

    def listing_urls(self, args):
        return [self.listing_url]

    def parse_listing(self, text, url):
        # A regulation with a consolidated version is listed twice: as issued and consolidated.
        items, originals = {}, {}
        for item in json.loads(text):
            if not isinstance(item, dict) or not _STAFS_REF.fullmatch(item.get("id") or ""):
                continue
            if item["id"] in items and not item.get("konsoliderad_tom"):
                originals[item["id"]] = item
                continue
            if item["id"] in items:
                originals[item["id"]] = items[item["id"]]
            items[item["id"]] = item
        self.originals = originals
        items = list(items.values())
        amending = {}
        for item in items:
            targets = item.get("andrar") or []
            for target in [targets] if isinstance(targets, str) else targets:
                amending.setdefault(target, set()).add(item["id"])
        by_id = {item["id"]: item for item in items}
        entries = []
        for item in items:
            title = _clean(item.get("titel"))
            base = not item.get("andrar") and not _AMENDING.search(title)
            repealed = item.get("upphavd")
            if repealed is True:  # repealed, date not given: the repealing regulation's entry into force
                repealed = (by_id.get(item.get("upphavd_genom") or "") or {}).get("ikraft")
                # Without any date the regulation would read as in force; it is not stored.
                base = base and bool(repealed)
            if base:
                self.items[item["id"]] = item
            entries.append(Entry(
                number=item["id"],
                title=title,
                url=item.get("md_url") or item.get("html_url") or url,
                base=base and bool(item.get("md_url") or item.get("pdf_url")),
                in_force=_date(item.get("ikraft")),
                repealed=_date(repealed) if isinstance(repealed, str) else None,
                amended_by=sorted(amending.get(item["id"], ()), key=number_key),
            ))
        if not any(e.base for e in entries):
            raise ValueError("no regulations in Swedac's index")
        return entries

    def parse_detail(self, text, entry):
        item = self.items.get(entry.number, {})
        meta, body = _markdown_document(text)
        if meta.get("id") and meta["id"] != entry.number:
            raise ValueError(f"Markdown file shows {meta['id']!r}, expected {entry.number}")
        through = item.get("konsoliderad_tom")
        pdfs = [(entry.number, (self.originals.get(entry.number) or {}).get("pdf_url"))]
        if through:
            pdfs.append((f"{entry.number} (konsoliderad version)", item.get("pdf_url")))
        else:
            pdfs = [(entry.number, item.get("pdf_url"))]
        return Regulation(
            number=entry.number,
            title=entry.title,
            issued=_date(item.get("beslutad")),
            published=_date(item.get("publicerad")),
            in_force=entry.in_force,
            repealed=entry.repealed,
            amended_by=list(entry.amended_by),
            amended_through=through,
            version="Konsoliderad version" if through else "Grundförfattning",
            text=body,
            pdfs=[(label, url) for label, url in pdfs if url],
        )


def _markdown_document(text):
    """(frontmatter dict, body) of a Swedac Markdown file; the body loses its H1
    and its headings move one level down, under the document's own sections."""
    meta = {}
    if text.startswith("---\n"):
        head, _, text = text[4:].partition("\n---\n")
        for line in head.splitlines():
            key, sep, value = line.partition(":")
            if sep:
                meta[key.strip()] = value.strip()
    lines = text.strip().splitlines()
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
    body = "\n".join(lines).strip()
    body = _MD_HEADING.sub(lambda m: "#" + m.group(1) + " ", body)
    body = _MD_ROOT_LINK.sub(lambda m: f"]({SwedacAdapter.base_url}{m.group(1)})", body)
    return meta, body


# --- Patent- och registreringsverket (PRVFS) --------------------------------

_PRV_NUMBER = re.compile(r"(?:PRVFS\s*)?(\d{4}):\s?(\d+)\b")
_PRV_FILE = re.compile(r"(?<![0-9])(\d{2})-?prvfs[-_]?(\d+)", re.I)


class PrvAdapter:
    """PRV's division A1, the base regulations in force: one paragraph each.

    A paragraph starts with a link to the PDF labelled `2026:1, O:2` (number
    and PRV's subject code), then the title and the enabling provision; links
    to amending regulations follow, labelled with their number or unlabelled.
    """

    series = "PRVFS"
    issuer = "Patent- och registreringsverket"
    base_url = "https://www.prv.se"
    listing_url = base_url + "/sv/om-oss/var-verksamhet/styrdokument/prvs-forfattningssamling/avdelning-a1---gallande-grundforfattningar/"
    detail = False
    has_text = False

    def listing_urls(self, args):
        return [self.listing_url]

    def _file_number(self, href):
        match = _PRV_FILE.search(urllib.parse.unquote(href))
        if match is None:
            return None
        year = int(match.group(1))
        return f"PRVFS {year + (1900 if year >= 70 else 2000)}:{int(match.group(2))}"

    def parse_listing(self, text, url):
        main = parse_html(text).find("main")
        entries = []
        for paragraph in (main.find_all("p") if main is not None else []):
            links = [a for a in paragraph.find_all("a") if ".pdf" in (a.attrs.get("href") or "")]
            first = _PRV_NUMBER.match(links[0].text()) if links else None
            if first is None:
                continue
            number = f"PRVFS {first.group(1)}:{int(first.group(2))}"
            title = paragraph.text().removeprefix(links[0].text()).partition("Bemyndigande")[0]
            amended_by, pdfs = set(), [(number, absolute(url, links[0].attrs["href"]))]
            for link in links[1:]:
                if link.text() and link.text() in title:
                    continue  # a regulation the title refers to, e.g. the one it repeals
                ref = _PRV_NUMBER.match(link.text())
                other = f"PRVFS {ref.group(1)}:{int(ref.group(2))}" if ref else self._file_number(link.attrs["href"])
                if other and other != number:
                    amended_by.add(other)
            entries.append(Entry(number=number, title=_clean(title).rstrip(".") or number,
                                 url=pdfs[0][1], amended_by=sorted(amended_by, key=number_key), pdfs=pdfs))
        if not entries:
            raise ValueError("no regulations in PRV's division A1")
        return entries

    def regulation(self, entry):
        return Regulation(number=entry.number, title=entry.title, amended_by=list(entry.amended_by),
                          version="Grundförfattning", pdfs=list(entry.pdfs))


# --- Åklagarmyndigheten (ÅFS) ----------------------------------------------

_MONTHS = {name: i for i, name in enumerate((
    "januari", "februari", "mars", "april", "maj", "juni",
    "juli", "augusti", "september", "oktober", "november", "december"), 1)}
_SWEDISH_DATE = re.compile(r"(\d{1,2}) (" + "|".join(_MONTHS) + r") (\d{4})")
_AFS_A_REF = re.compile(r"ÅFS (\d{4}):0*(\d+)")
# "Riksåklagarens föreskrifter (1999:178) om ...": a change to an older series' regulation.
_OTHER_SERIES = re.compile(r"föreskrifter \((?:RÅFS )?\d{4}:\d+\)")


def _swedish_date(text):
    match = _SWEDISH_DATE.search(text or "")
    if match is None:
        return None
    return f"{match.group(3)}-{_MONTHS[match.group(2)]:02d}-{int(match.group(1)):02d}"


class AklagareAdapter:
    """Åklagarmyndigheten's ÅFS page: one card per regulation, with its PDF.

    A card has the number, the publication and decision dates, the title and
    tags: "Gällande grundförfattningar" (base regulations in force),
    "Ändringsförfattningar", "Upphävda författningar" (repealed) and "Notis".
    Base regulations are the cards whose title neither amends nor repeals
    another regulation; repealed ones and notices are not stored.
    """

    series = "ÅFS"
    issuer = "Åklagarmyndigheten"
    base_url = "https://www.aklagare.se"
    listing_url = base_url + "/om-oss/dokument/forfattningssamling"
    detail = False
    has_text = False

    def __init__(self):
        self.cards = {}

    def listing_urls(self, args):
        return [self.listing_url]

    def _cards(self, root, url):
        for item in root.find_all("li"):
            link, heading = item.find("a"), item.find("h2")
            match = _AFS_A_REF.fullmatch(heading.text()) if heading is not None else None
            if link is None or match is None or ".pdf" not in (link.attrs.get("href") or ""):
                continue
            paragraphs = [p.text() for p in item.find_all("p")]
            tags = {span.text() for span in item.find_all("span") if "rounded-full" in span.classes}
            published = item.find("time")
            dated = next((t for t in paragraphs if t.startswith("Publicerad")), "")
            yield {
                "number": f"ÅFS {match.group(1)}:{int(match.group(2))}",
                "url": absolute(url, link.attrs["href"]),
                "title": next((t for t in paragraphs if not t.startswith(("Storlek", "Publicerad", "Beslutad"))), ""),
                "issued": _swedish_date(dated.partition("Beslutad")[2]) if "Beslutad" in dated else None,
                "published": _date(published.attrs.get("datetime")) if published is not None else None,
                "tags": tags,
            }

    def parse_listing(self, text, url):
        entries, amending = {}, {}
        for card in self._cards(parse_html(text), url):
            title, tags = card["title"].rstrip(". "), card["tags"]
            changes = _AMENDING.search(title)
            if changes or "Ändringsförfattningar" in tags:
                for ref in _AFS_A_REF.finditer(title[changes.start():] if changes else title):
                    target = f"ÅFS {ref.group(1)}:{int(ref.group(2))}"
                    if target != card["number"]:
                        amending.setdefault(target, set()).add(card["number"])
                entries.setdefault(card["number"], Entry(card["number"], title, card["url"], base=False))
                continue
            if "Notis" in tags or "Upphävda författningar" in tags or _OTHER_SERIES.search(title):
                entries.setdefault(card["number"], Entry(card["number"], title, card["url"], base=False))
                continue
            card["title"] = title
            self.cards[card["number"]] = card
            entries[card["number"]] = Entry(card["number"], title, card["url"], pdfs=[(card["number"], card["url"])])
        for number, entry in entries.items():
            entry.amended_by = sorted(amending.get(number, ()), key=number_key)
        if not any(e.base for e in entries.values()):
            raise ValueError("no regulations found on the ÅFS page")
        return sorted(entries.values(), key=lambda e: (not e.base, number_key(e.number)))

    def regulation(self, entry):
        card = self.cards.get(entry.number, {})
        return Regulation(number=entry.number, title=entry.title, issued=card.get("issued"),
                          published=card.get("published"), amended_by=list(entry.amended_by),
                          version="Grundförfattning", pdfs=list(entry.pdfs))


# --- Polismyndigheten (PMFS) -------------------------------------------------

_PMFS_REF = re.compile(r"(PMFS|RPSFS) (\d{4}):0*(\d+)")


class PolisenAdapter:
    """Polismyndigheten's författningssamling: a paginated list of regulations in force.

    Each item has the title, the number (PMFS, or RPSFS for Rikspolisstyrelsen's
    regulations still in force), the FAP number, and sections "Grundföreskrift",
    "Ändringsföreskrift" and "Sammanställd version" with PDF links and dates.
    """

    series = "PMFS"
    issuer = "Polismyndigheten"
    base_url = "https://polisen.se"
    listing_url = base_url + "/lagar-och-regler/polismyndighetens-forfattningssamling/"
    detail = False
    has_text = False

    def listing_urls(self, args):
        return [self.listing_url]

    def more_pages(self, text, url):
        pages = {int(n) for n in re.findall(r'href="/lagar-och-regler/polismyndighetens-forfattningssamling/(\d+)/"', text)}
        return [f"{self.listing_url}{n}/" for n in sorted(pages) if n > 1]

    def parse_listing(self, text, url):
        entries = []
        for block in parse_html(text).find_all("div", "c-regulation"):
            heading = block.find("h3")
            labels = [d.text() for d in block.find_all("div", "c-regulation__label")]
            number = next((_PMFS_REF.fullmatch(t) for t in labels if _PMFS_REF.fullmatch(t)), None)
            if heading is None or number is None:
                continue
            number = f"{number.group(1)} {number.group(2)}:{int(number.group(3))}"
            section, pdfs, amended_by, in_force = None, [], [], None
            for node in block.iter():
                if node.tag == "h4":
                    section = node.text()
                elif node.tag == "a" and node.attrs.get("href"):
                    href = absolute(url, node.attrs["href"])
                    ref = _PMFS_REF.search(node.text())
                    if section == "Grundföreskrift":
                        pdfs.insert(0, (number, href))
                    elif section == "Ändringsföreskrift" and ref:
                        amended_by.append(f"{ref.group(1)} {ref.group(2)}:{int(ref.group(3))}")
                    elif section == "Sammanställd version":
                        pdfs.append((f"{number} (sammanställd version)", href))
                elif node.tag == "time" and section == "Grundföreskrift" and in_force is None:
                    in_force = _date(node.attrs.get("datetime"))
            if not pdfs:
                continue
            entries.append(Entry(number=number, title=heading.text(), url=pdfs[0][1], in_force=in_force,
                                 amended_by=sorted(set(amended_by), key=number_key), pdfs=pdfs))
        if not entries:
            raise ValueError("no regulations on the PMFS page")
        return entries

    def regulation(self, entry):
        return Regulation(number=entry.number, title=entry.title, in_force=entry.in_force,
                          amended_by=list(entry.amended_by), version="Grundförfattning", pdfs=list(entry.pdfs))


# --- Statistiska centralbyrån (SCB-FS) ----------------------------------------

_SCB_REF = re.compile(r"SCB-FS:? (\d{4}):0*(\d+)")


class ScbAdapter:
    """SCB's table of regulations on reporting duties, and one HTML page per regulation.

    Each table row gives the number, the title linking to the regulation's
    page, the area and the kind (Ändringsföreskrift, Upphävandeföreskrift).
    The page holds the text (`div.xhtmlText`), the publication date and the PDF.
    """

    series = "SCB-FS"
    issuer = "Statistiska centralbyrån"
    base_url = "https://www.scb.se"
    listing_url = base_url + "/om-scb/scbs-verksamhet/regelverk-och-policyer/foreskrifter/?currentpageId=98388&type=UL"
    detail = True
    has_text = True

    def listing_urls(self, args):
        return [self.listing_url]

    def parse_listing(self, text, url):
        rows, amending = [], {}
        for row in parse_html(text).find_all("tr"):
            cells = [c for c in row.children if isinstance(c, Node) and c.tag in ("td", "th")]
            match = _SCB_REF.fullmatch(cells[0].text()) if cells else None
            link = row.find("a")
            if match is None or link is None:
                continue
            number = f"SCB-FS {match.group(1)}:{int(match.group(2))}"
            title = link.text().rstrip(";").strip()
            changes = _AMENDING.search(title) or "föreskrifter som upphör att gälla" in title
            if changes or any(c.text() in ("Ändringsföreskrift", "Upphävandeföreskrift") for c in cells[1:]):
                for ref in _SCB_REF.finditer(title):
                    amending.setdefault(f"SCB-FS {ref.group(1)}:{int(ref.group(2))}", set()).add(number)
                rows.append(Entry(number, title, absolute(url, link.attrs.get("href", "")), base=False))
                continue
            rows.append(Entry(number, title, absolute(url, link.attrs.get("href", ""))))
        for entry in rows:
            entry.amended_by = sorted(amending.get(entry.number, ()), key=number_key)
        if not any(e.base for e in rows):
            raise ValueError("no regulations in SCB's table")
        return rows

    def parse_detail(self, text, entry):
        root = parse_html(text)
        label = next((b for b in root.find_all("b") if _SCB_REF.fullmatch(b.text())), None)
        if label is None:
            raise ValueError("no number on the detail page")
        found = _SCB_REF.fullmatch(label.text())
        _check_number(f"SCB-FS {found.group(1)}:{int(found.group(2))}", entry)
        heading = root.find("h1")
        body = root.find("div", "xhtmlText")
        pdfs = []
        for box in root.find_all("div", "box-highlight"):
            for link in box.find_all("a"):
                pdfs.append((entry.number, absolute(self.base_url, link.attrs.get("href", ""))))
        published = next((p.text() for p in root.find_all("p") if p.text().startswith("Publicerad")), "")
        return Regulation(
            number=entry.number,
            title=heading.text().rstrip(";").strip() if heading is not None else entry.title,
            published=_date(published),
            amended_by=list(entry.amended_by),
            version="Grundförfattning",
            text=htmlmd.to_markdown(to_html(body)) if body is not None else "",
            pdfs=pdfs[:1],
        )


# --- Energimyndigheten (STEMFS) ---------------------------------------------

_STEMFS_REF = re.compile(r"STEMFS (\d{4}):0*(\d+)")
_STEM_ITEM = re.compile(r'<div id="[^"]*_itemListControl_\d+_([0-9a-f]{32})_titleDiv')
_STEM_NEXT = re.compile(r'<a[^>]*class="next"[^>]*href="([^"]+)"|<a[^>]*href="([^"]+)"[^>]*class="next"')


class EnergimyndighetenAdapter:
    """Energimyndigheten's document archive, category Föreskrifter: 40 items a page.

    An item has the number (or a title holding it), a description that is the
    regulation's title, and a download link to the PDF. The site asks for a
    crawl delay of 10 s, which the run honours.
    """

    series = "STEMFS"
    issuer = "Statens energimyndighet"
    base_url = "https://energimyndigheten.a-w2m.se"
    listing_url = base_url + "/System/TemplateNavigate.aspx?p=Arkitektkopia&l=t&view=672&cat=%2FF%C3%B6reskrifter"
    detail = False
    has_text = False

    def listing_urls(self, args):
        return [self.listing_url]

    def more_pages(self, text, url):
        match = _STEM_NEXT.search(text)
        if match is None:
            return []
        parts = urllib.parse.urlsplit(absolute(url, match.group(1) or match.group(2)))
        return [urllib.parse.urlunsplit((parts.scheme, parts.hostname, parts.path, parts.query, ""))]

    def parse_listing(self, text, url):
        starts = list(_STEM_ITEM.finditer(text))
        items, amending = [], {}
        for here, after in zip(starts, starts[1:] + [None]):
            item = parse_html(text[here.start():after.start() if after else len(text)])
            names = [_clean(n.text()) for n in item.find_all("div", "value") if _clean(n.text())]
            title_link = item.find("a")
            heading = _clean(title_link.text()) if title_link is not None else ""
            match = _STEMFS_REF.search(heading) or next((_STEMFS_REF.search(n) for n in names if _STEMFS_REF.search(n)), None)
            pdf = next((a for a in item.find_all("a") if "GetTemplateResource" in (a.attrs.get("href") or "")), None)
            if match is None or pdf is None:
                continue
            number = f"STEMFS {match.group(1)}:{int(match.group(2))}"
            title = names[0] if names and not names[0].startswith("Dela") else heading
            title = re.sub(r"\s*\(STEMFS \d{4}:\d+\)", "", title).strip()
            changes = _AMENDING.search(title)
            if changes:
                for ref in _STEMFS_REF.finditer(names[0][changes.start():] if names else ""):
                    target = f"STEMFS {ref.group(1)}:{int(ref.group(2))}"
                    if target != number:
                        amending.setdefault(target, set()).add(number)
            parts = urllib.parse.urlsplit(absolute(url, pdf.attrs["href"]))
            query = urllib.parse.quote(urllib.parse.unquote(parts.query), safe="=&/:")  # a file name with spaces
            href = urllib.parse.urlunsplit(parts._replace(query=query))
            items.append(Entry(number=number, title=title or number, url=href, base=not changes,
                               pdfs=[(number, href)]))
        for entry in items:
            entry.amended_by = sorted(amending.get(entry.number, ()), key=number_key)
        if not items:
            raise ValueError("no regulations in Energimyndigheten's archive")
        return items

    def regulation(self, entry):
        return Regulation(number=entry.number, title=entry.title, amended_by=list(entry.amended_by),
                          version="Grundförfattning", pdfs=list(entry.pdfs))


# --- Riksdagsförvaltningen (RFS) ----------------------------------------------

_RFS_REF = re.compile(r"RFS (\d{4}):0*(\d+)")
_RFS_THROUGH = re.compile(r"Ändring införd:\s*\|?\s*t\.o\.m\. (RFS \d{4}:\d+)")
_RFS_ISSUED = re.compile(r"Utfärdad:\s*\|?\s*(\d{1,2} \w+ \d{4})")


class RiksdagenAdapter:
    """Riksdagsförvaltningen's RFS from Riksdagen's open data (doktyp rfs).

    The document list gives every RFS document with its kind (Grund, Ändring,
    Omtryck, Fulltext: a consolidated text) and status (Gällande, Upphävd).
    Base regulations in force are stored with the text of their consolidated
    version where there is one, else of the regulation as issued. Repealed
    regulations are not stored: the data gives no repeal date.
    """

    series = "RFS"
    issuer = "Riksdagsförvaltningen"
    base_url = "https://data.riksdagen.se"
    listing_url = base_url + "/dokumentlista/?doktyp=rfs&utformat=json&sz=500&sort=datum&sortorder=desc"
    detail = True
    has_text = True

    def listing_urls(self, args):
        return [self.listing_url]

    def parse_listing(self, text, url):
        documents = json.loads(text)["dokumentlista"].get("dokument") or []
        fulltext, amending, entries = {}, {}, []
        for doc in documents:
            if doc.get("subtyp") == "Fulltext":
                fulltext[(doc.get("rm"), doc.get("beteckning"))] = doc
        for doc in documents:
            number = f"RFS {doc.get('rm')}:{doc.get('beteckning')}"
            if not re.fullmatch(r"RFS \d{4}:\d+", number) or doc.get("subtyp") not in ("Grund", "Ändring", "Omtryck"):
                continue
            title = _clean(doc.get("titel")).rstrip(";")
            changes = _AMENDING.search(title)
            if doc["subtyp"] != "Grund" or changes:
                for ref in _RFS_REF.finditer(title[changes.start():] if changes else title):
                    amending.setdefault(f"RFS {ref.group(1)}:{int(ref.group(2))}", set()).add(number)
                entries.append(Entry(number, title, url, base=False))
                continue
            source = fulltext.get((doc.get("rm"), doc.get("beteckning"))) or doc
            entries.append(Entry(number, title, f"{self.base_url}/dokument/{source['dok_id']}.html",
                                 base=doc.get("status") == "Gällande"))
        for entry in entries:
            entry.amended_by = sorted(amending.get(entry.number, ()), key=number_key)
        if not any(e.base for e in entries):
            raise ValueError("no RFS regulations in the document list")
        return entries

    def parse_detail(self, text, entry):
        body = htmlmd.to_markdown(text)
        lines = body.splitlines()
        # The header block (RFS nr, Rubrik, Utfärdad, Ändring införd) is kept in the facts.
        start = max((i for i, line in enumerate(lines[:30]) if line.startswith(("Ändring införd", "Utfärdad"))),
                    default=-1)
        number = re.search(r"RFS nr:\s*\|?\s*(\d{4}:\d+)", body)
        if number and f"RFS {number.group(1)}" != entry.number:
            raise ValueError(f"document shows RFS {number.group(1)}, expected {entry.number}")
        through = _RFS_THROUGH.search(body)
        issued = _RFS_ISSUED.search(body)
        return Regulation(
            number=entry.number,
            title=entry.title,
            issued=_swedish_date(issued.group(1)) if issued else None,
            amended_by=list(entry.amended_by),
            amended_through=through.group(1) if through else None,
            version="Konsoliderad version" if through else "Grundförfattning",
            text="\n".join(lines[start + 1:]).strip() if start >= 0 else body,
        )


# --- Riksarkivet (RA-FS) ------------------------------------------------------

_RAFS_REPEALED_BY = re.compile(r"upphävda genom: (RA-FS \d{4}:\d+)")


class RiksarkivetAdapter:
    """Riksarkivet's register of general regulations (RA-FS), read through its JSON API.

    `api/rafs/sok` returns every regulation, in force (Giltig) and repealed
    (Upphävd), with its number, the base regulation it belongs to, entry into
    force, the regulations that amended or repealed it, and its PDF. A
    repealed base regulation gets the repealing regulation's entry into force
    as its `repealed` date; without one it is not stored.
    """

    series = "RA-FS"
    issuer = "Riksarkivet"
    base_url = "https://foreskrifter.riksarkivet.se"
    listing_url = (base_url + "/api/rafs/sok?nummer=&rubrik=&fulltext=&sokBlandGiltiga=true"
                   "&sokBlandUpphavda=true&rafsSort=1")
    detail = False
    has_text = False

    def listing_urls(self, args):
        return [self.listing_url]

    def _pdf(self, path):
        return f"{self.base_url}/api/rafs/pdf/{urllib.parse.quote(path, safe='')}"

    def parse_listing(self, text, url):
        items = [i for i in json.loads(text).get("traffLista") or [] if re.fullmatch(r"\d{4}:\d+", i.get("nummer") or "")]
        in_force = {f"RA-FS {i['nummer']}": _date(i.get("ikrafttradandedatum")) for i in items}
        amended = {}
        for item in items:
            if item.get("grundforfattning") and item["grundforfattning"] != item["nummer"]:
                amended.setdefault(f"RA-FS {item['grundforfattning']}", set()).add(f"RA-FS {item['nummer']}")
        entries = []
        for item in items:
            number = f"RA-FS {item['nummer']}"
            title = _clean(item.get("rubrik"))
            base = item.get("grundforfattning") == item["nummer"] and not _AMENDING.search(title)
            repealed = None
            if item.get("statusText") == "Upphävd":
                by = _RAFS_REPEALED_BY.search(item.get("efterfoljareString") or "")
                repealed = in_force.get(by.group(1)) if by else None
                base = base and bool(repealed)
            pdfs = [(number, self._pdf(d["path"])) for d in item.get("huvuddokument") or [] if d.get("path")][:1]
            entries.append(Entry(number=number, title=title, url=pdfs[0][1] if pdfs else url, base=base and bool(pdfs),
                                 in_force=_date(item.get("ikrafttradandedatum")), repealed=repealed,
                                 amended_by=sorted(amended.get(number, ()), key=number_key), pdfs=pdfs))
        if not any(e.base for e in entries):
            raise ValueError("no regulations in Riksarkivet's register")
        return entries

    def regulation(self, entry):
        return Regulation(number=entry.number, title=entry.title, in_force=entry.in_force, repealed=entry.repealed,
                          amended_by=list(entry.amended_by), version="Grundförfattning", pdfs=list(entry.pdfs))


# --- Skolverket (SKOLFS) ------------------------------------------------------

_SKOLFS_PAGE = 1000


class SkolverketAdapter:
    """Skolverket's SKOLFS register, read through the API behind its search app.

    `api/statute` pages through every SKOLFS document with its number, the base
    regulation it belongs to, its kind (GRUNDFORFATTNING, ANDRINGSFORFATTNING,
    SENASTE_LYDELSE: the latest consolidated text) and validity. Base
    regulations in force are stored; `api/document/<number>/ascending` gives
    their dates. Expired ones are not stored: the register gives no repeal date.
    """

    series = "SKOLFS"
    issuer = "Statens skolverk"
    base_url = "https://skolfs.skolverket.se"
    listing_url = base_url + f"/api/statute?sort=YEAR_DESC&size={_SKOLFS_PAGE}&start=0"
    detail = True
    has_text = False

    def __init__(self):
        self.consolidated = set()

    def listing_urls(self, args):
        return [self.listing_url]

    def more_pages(self, text, url):
        hits = sum(len(g.get("searchHits") or []) for g in json.loads(text).get("searchGroups") or [])
        start = int(urllib.parse.parse_qs(urllib.parse.urlsplit(url).query).get("start", ["0"])[0])
        return [self.listing_url.replace("start=0", f"start={start + _SKOLFS_PAGE}")] if hits >= _SKOLFS_PAGE else []

    def _pdf(self, kind, number):
        return f"{self.base_url}/api/document/{kind}/{number}/pdf"

    def parse_listing(self, text, url):
        hits = [h for g in json.loads(text).get("searchGroups") or [] for h in g.get("searchHits") or []]
        entries, amending = [], {}
        for hit in hits:
            number, base = hit.get("skolfsNumber") or "", hit.get("baseSkolfsNumber") or ""
            if not re.fullmatch(r"\d{4}:\d+", number):
                continue
            kind = hit.get("documentType")
            if kind == "SENASTE_LYDELSE":
                self.consolidated.add(f"SKOLFS {number}")
                continue
            if kind == "ANDRINGSFORFATTNING" and base and base != number:
                amending.setdefault(f"SKOLFS {base}", set()).add(f"SKOLFS {number}")
            entries.append(Entry(
                number=f"SKOLFS {number}",
                title=_clean(hit.get("statuteTitle")),
                url=f"{self.base_url}/api/document/{number}/ascending",
                base=kind == "GRUNDFORFATTNING" and hit.get("validity") == "VALID",
            ))
        for entry in entries:
            entry.amended_by = sorted(amending.get(entry.number, ()), key=number_key)
        return entries

    def parse_detail(self, text, entry):
        data = json.loads(text)
        if f"SKOLFS {data.get('skolfsNumber')}" != entry.number:
            raise ValueError(f"document shows SKOLFS {data.get('skolfsNumber')}, expected {entry.number}")
        number = entry.number.removeprefix("SKOLFS ")
        pdfs = [(entry.number, self._pdf("GRUNDFORFATTNING", number))]
        if entry.number in self.consolidated:
            pdfs.append((f"{entry.number} (senaste lydelse)", self._pdf("SENASTE_LYDELSE", number)))
        notes = [_clean(c) for c in data.get("externalComment") or [] if _clean(c)]
        return Regulation(
            number=entry.number,
            title=_clean(data.get("statuteTitle")) or entry.title,
            issued=_date(data.get("decisionDate")),
            published=_date(data.get("promulgationDate")),
            in_force=_date(data.get("effectiveDate")),
            amended_by=list(entry.amended_by),
            version="Grundförfattning",
            summary="\n\n".join(notes),
            pdfs=pdfs,
        )


# --- Sjöfartsverket (SJÖFS) ---------------------------------------------------

_SJOFS_NUMBER = re.compile(r"(\d{4}):(\d+)")


class SjofartsverketAdapter:
    """Sjöfartsverket's systematic list of regulations in force, one page per subject.

    The index links to the subject pages; each has a table whose rows give the
    base regulation's number (linked to its PDF), the title and the amending
    regulations. Regulations numbered before the series used plain ordinals
    (`1952:A9`) and rows marked repealed are not stored. A regulation listed
    under several subjects is read once.
    """

    series = "SJÖFS"
    issuer = "Sjöfartsverket"
    base_url = "https://www.sjofartsverket.se"
    listing_url = base_url + "/sv/om-oss/lagrum/systematisk-forteckning-n/"
    detail = False
    has_text = False

    def __init__(self):
        self.seen = set()

    def listing_urls(self, args):
        return [self.listing_url]

    def more_pages(self, text, url):
        if url != self.listing_url:
            return []
        pages = re.findall(r'href="(/sv/om-oss/lagrum/systematisk-forteckning-n/[a-z0-9-]+/)"', text)
        return [absolute(url, p) for p in dict.fromkeys(pages)]

    def parse_listing(self, text, url):
        entries = []
        for row in parse_html(text).find_all("tr"):
            cells = [c for c in row.children if isinstance(c, Node) and c.tag == "td"]
            if len(cells) < 2:
                continue
            link = cells[0].find("a")
            match = _SJOFS_NUMBER.fullmatch(link.text()) if link is not None else None
            if match is None or "Upphävd" in cells[0].text():
                continue
            number = f"SJÖFS {match.group(1)}:{int(match.group(2))}"
            if number in self.seen:
                continue
            self.seen.add(number)
            title = cells[1].text().partition("Ändringsföreskrifter")[0]
            amended_by = {f"SJÖFS {ref.group(1)}:{int(ref.group(2))}"
                          for ref in (_SJOFS_NUMBER.fullmatch(a.text()) for a in cells[1].find_all("a")) if ref}
            pdf = absolute(url, link.attrs.get("href", ""))
            entries.append(Entry(number=number, title=_clean(title) or number, url=pdf,
                                 amended_by=sorted(amended_by, key=number_key), pdfs=[(number, pdf)]))
        return entries

    def regulation(self, entry):
        return Regulation(number=entry.number, title=entry.title, amended_by=list(entry.amended_by),
                          version="Grundförfattning", pdfs=list(entry.pdfs))


# --- Trafikverket (TRVFS) -----------------------------------------------------

_TRVFS_FIRST_YEAR = 2010  # Trafikverket was formed on 1 April 2010
_TRVFS_ITEM = re.compile(r"(\d{4}):(\d+)\s+(Grundföreskrift|Ändringsföreskrift|Upphävandeföreskrift)?")


class TrafikverketAdapter:
    """Trafikverket's författningssamling app: a search form per year, one page per regulation.

    The search (a POST form, without speed regulations and repealed ones)
    lists the regulations of a year: number, kind, title and entry into
    force. Transportstyrelsen's regulations republished there keep their TSFS
    number and are not stored here. The page per regulation links the PDF.
    Road-specific speed regulations (hastighetsföreskrifter) are not collected.
    """

    series = "TRVFS"
    issuer = "Trafikverket"
    base_url = "https://trvfs.ea.trafikverket.se"
    search_url = base_url + "/TRVFS/Home/SearchInDocCollection"
    listing_url = search_url
    detail = True
    has_text = False

    def listing_urls(self, args):
        years = sorted(args.year, reverse=True) if args and args.year else range(
            datetime.now(timezone.utc).year, _TRVFS_FIRST_YEAR - 1, -1)
        return [f"{self.search_url}?Ar={year}" for year in years]

    def fetch_listing(self, client, url):
        year = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)["Ar"][0]
        form = {"Dokumentbeteckning": "", "Celexnummer": "", "Ikrafttradandefrom": "", "Ikrafttradandetom": "",
                "Titel": "", "Hastforeskrift": "false", "Upphavda": "false", "Ar": year}
        return client.post(self.search_url, form)

    def parse_listing(self, text, url):
        entries = []
        for link in parse_html(text).find_all("a"):
            href = link.attrs.get("href") or ""
            match = _TRVFS_ITEM.fullmatch(link.text())
            if "/DocumentHistory/" not in href or match is None:
                continue  # TSFS and VVFS numbers carry a prefix and do not match
            number = f"TRVFS {match.group(1)}:{int(match.group(2))}"
            entries.append(Entry(number=number, title=number, url=absolute(url, href),
                                 base=match.group(3) in (None, "Grundföreskrift")))
        return entries

    def parse_detail(self, text, entry):
        root = parse_html(text)
        flat = root.text()
        number = re.search(r"Dokumentbeteckning\s+(\d{4}:\d+)", flat)
        if number is None or f"TRVFS {number.group(1)}" != entry.number:
            raise ValueError(f"page shows {number.group(1) if number else None}, expected {entry.number}")
        title = re.search(r"Rubrik\s+(.*?)\s+(?:Bemyndigande|Ikraftträdande)", flat)
        in_force = re.search(r"Ikraftträdande\s+(\d{4}-\d{2}-\d{2})", flat)
        pdf = next((a for a in root.find_all("a") if (a.attrs.get("href") or "").lower().endswith(".pdf")), None)
        return Regulation(
            number=entry.number,
            title=title.group(1).rstrip(";").strip() if title else entry.title,
            in_force=in_force.group(1) if in_force else None,
            version="Grundförfattning",
            pdfs=[(entry.number, absolute(self.base_url, pdf.attrs["href"]))] if pdf is not None else [],
        )


# --- series listed as links to their PDFs ----------------------------------

_DOCUMENT_HREF = re.compile(r"\.pdf(?:$|[?#/])|/download/|/GetTemplateResource/", re.I)
_AMENDING = re.compile(r"\b(?:om|till) (?:ändring|ändringar|upphävande)\b|\bändring (?:i|av)\b", re.I)
_REPRINT = re.compile(r"\bomtryck", re.I)
_CONSOLIDATED = re.compile(r"\bkonsoliderad|\bsenaste lydelse", re.I)
_SIZE = re.compile(r"[\s,(.]*\b(?:pdf|PDF)\b[\s,)-]*(?:[\d.,]+\s*(?:kB|KB|kb|MB|Mb|mb|B)\b)?\.?\s*\)?\s*$")
_DEFAULT_EXCLUDE = (r"tillämpningsstöd|förarbete|hemställan|beslutspromemoria|förteckning|register|"
                    r"remiss|konsekvensutredning|vägledning|rättelse|\bbilag")


class ListedAdapter:
    """A series whose listing pages link straight to the regulation PDFs.

    Each link to a document is read by its label (and, failing that, its file
    name): a base regulation, an amending or repealing regulation (`om ändring
    i ... (XFS 2015:2)`), or a consolidated version or reprint of a base
    regulation. Amending regulations are not stored; they end up in their base
    regulation's `amended_by`. The listing is the only page read, so every run
    rebuilds the series from it; PDFs already in the manifest are not fetched
    again.
    """

    has_text = False

    def __init__(self, series, issuer, listing_urls, prefix=None, exclude=None, separator=None, base_href=None,
                 detail_pages=False, documents=None):
        self.series = series
        self.issuer = issuer
        self.urls = list(listing_urls)
        parts = urllib.parse.urlsplit(self.urls[0])
        self.base_url = f"{parts.scheme}://{parts.netloc}"
        self.listing_url = self.urls[0]
        prefix = prefix or re.escape(series)
        separator = separator or ":"
        self.number = re.compile(rf"(?<![A-Za-zÅÄÖåäö])(?:{prefix})\s?(\d{{4}})\s?(?:{separator})\s?(\d+)(?!\d)")
        slug = "[^a-z0-9]?".join(re.escape(p) for p in re.split(r"[^a-z0-9]+", series.lower()) if p)
        self.file_number = re.compile(
            rf"(?<![a-z]){slug}[^a-z0-9]*(?:(\d{{4}})[^0-9]{{1,3}}(\d{{1,3}})(?!\d)|(\d{{1,3}})[^0-9]{{1,3}}(\d{{4}})(?!\d))")
        self.exclude = re.compile(exclude or _DEFAULT_EXCLUDE, re.I)
        # A site that files every amendment under its base regulation's folder:
        # the year and ordinal of the base regulation in the link.
        self.base_href = re.compile(base_href, re.I) if base_href else None
        # The listing links to one page per base regulation, which links to its PDFs.
        self.detail = detail_pages
        self.documents = re.compile(documents, re.I) if documents else _DOCUMENT_HREF

    def listing_urls(self, args):
        return list(self.urls)

    def _numbers(self, text):
        return [(m.start(), f"{self.series} {m.group(1)}:{int(m.group(2))}") for m in self.number.finditer(text)]

    def _file_number(self, href):
        name = urllib.parse.unquote_plus(urllib.parse.urlsplit(href).path).lower()
        name = name.rsplit("/", 1)[-1] or name
        match = self.file_number.search(name) or self.file_number.search(urllib.parse.unquote_plus(href).lower())
        if match is None:
            return None
        year, number = (match.group(1), match.group(2)) if match.group(1) else (match.group(4), match.group(3))
        return f"{self.series} {year}:{int(number)}"

    def title(self, label, number):
        """The link label without the number, the file size and a trailing `pdf`."""
        title = _SIZE.sub("", label)
        title = re.sub(rf"\(\s*{self.number.pattern}\s*\)", lambda m: "" if self._numbers(m.group(0))[0][1] == number
                       else m.group(0), title)
        for _, found in self._numbers(title)[:1]:
            if found == number:
                title = self.number.sub("", title, count=1)
        title = _clean(re.sub(r"\s+([,.])", r"\1", title)).strip(" -–,:")
        return title or number

    def classify(self, label, href):
        """(kind, own number, base number) for one document link; kind is None to skip it."""
        if self.exclude.search(label):
            return None, None, None
        numbers = self._numbers(label)
        own = self._file_number(href)
        if _CONSOLIDATED.search(label):
            return ("consolidated", None, numbers[0][1]) if numbers else (None, None, None)
        amending = _AMENDING.search(label)
        folder = self.base_href.search(href) if self.base_href else None
        if folder and numbers:
            base = f"{self.series} {folder.group(1)}:{int(folder.group(2))}"
            if numbers[0][1] != base:
                reprint = _REPRINT.search(label) or _REPRINT.search(href)
                return ("reprint" if reprint else "amending"), numbers[0][1], base
        reprint = _REPRINT.search(label)
        if reprint and numbers:
            # "XFS 2015:1 omtryckt genom ... XFS 2021:1" or "XFS 2021:1 ... (XFS 2015:1) Omtryck"
            before = [n for at, n in numbers if at < reprint.start()]
            after = [n for at, n in numbers if at > reprint.start()]
            if before and after:
                return "reprint", after[-1], before[0]
            if len(before) > 1:
                return "reprint", before[0], before[1]
            return "reprint", own if own != numbers[0][1] else None, numbers[0][1]
        if amending:
            before = [n for at, n in numbers if at < amending.start()]
            after = [n for at, n in numbers if at > amending.start()]
            # "XFS 2024:3 Föreskrifter om ändring i ... (XFS 2015:1)" or
            # "Föreskrifter om ändring i ... (XFS 2015:1) om ... (XFS 2024:3)"
            target = after[0] if after else None
            if before:
                own = before[0]
            elif len(after) > 1:
                own = after[-1]
            elif own == target:
                own = None
            return "amending", own, target
        if numbers:
            return "base", numbers[0][1], None
        return ("base", own, None) if own else (None, None, None)

    def parse_listing(self, text, url):
        if not self.detail:
            return self.read_links(parse_html(text), url)
        entries = {}
        for link in parse_html(text).find_all("a"):
            href = link.attrs.get("href") or ""
            numbers = self._numbers(link.text())
            if not href or href.startswith(("#", "mailto:")) or len(numbers) != 1:
                continue
            number = numbers[0][1]
            if number not in entries and not self.exclude.search(link.text()):
                entries[number] = Entry(number=number, title=self.title(link.text(), number), url=absolute(url, href))
        if not entries:
            raise ValueError(f"no {self.series} regulations found")
        return list(entries.values())

    def parse_detail(self, text, entry):
        root = parse_html(text)
        found = {e.number: e for e in self.read_links(root, entry.url)}.get(entry.number)
        if found is None:
            raise ValueError(f"{entry.number} has no PDF on its page")
        if not found.base:
            raise NotBase(f"{entry.number} is an amending regulation")
        heading = (root.find("main") or root).find("h1")
        title = self.title(heading.text(), entry.number) if heading is not None else ""
        found.title = title if title and title != entry.number else found.title
        return self.regulation(found)

    def read_links(self, root, url):
        """Entries for the document links on one page: base regulations first, then amending ones."""
        entries, amending, own_folder = {}, set(), set()

        def entry(number, title=None):
            if number not in entries:
                entries[number] = Entry(number=number, title=title or number, url="")
            elif title and entries[number].title == number:
                entries[number].title = title
            return entries[number]

        for link in root.find_all("a"):
            href = link.attrs.get("href") or ""
            if not href or href.startswith(("#", "mailto:")) or not self.documents.search(href):
                continue
            label = link.text()
            kind, own, target = self.classify(label, href)
            if kind is None:
                continue
            pdf = absolute(url, href)
            if kind == "base" and self.base_href and self.base_href.search(href):
                own_folder.add(own)  # filed in its own folder: a base regulation even if it also amends one
            if kind == "base":
                base = entry(own, self.title(label, own))
                if not base.url:
                    base.url = pdf
                    base.pdfs.insert(0, (own, pdf))
            elif kind == "consolidated":
                entry(target).pdfs.append((f"{target} (konsoliderad version)", pdf))
            elif kind == "reprint":
                entry(target).pdfs.append((f"{target} (omtryck genom {own})" if own else f"{target} (omtryck)", pdf))
                if own:
                    amending.add(own)
                    entry(target).amended_by.append(own)
            else:
                if own:
                    amending.add(own)
                if target:
                    if own:
                        entry(target).amended_by.append(own)
        result = []
        for number, item in entries.items():
            if number in amending and number not in own_folder:
                continue
            item.pdfs = list(dict(reversed(item.pdfs)).items())[::-1]  # one PDF per label, the first
            if not item.pdfs:
                continue
            item.url = item.url or item.pdfs[0][1]
            item.amended_by = sorted(set(item.amended_by), key=number_key)
            result.append(item)
        for number in sorted(amending - own_folder, key=number_key):
            result.append(Entry(number=number, title=number, url=url, base=False))
        if not any(e.base for e in result):
            raise ValueError(f"no {self.series} regulations found")
        return result

    def regulation(self, entry):
        return Regulation(number=entry.number, title=entry.title, amended_by=list(entry.amended_by),
                          version="Grundförfattning", pdfs=list(entry.pdfs))


def load_series(path=SERIES_CONFIG):
    """Listed series from the config file: {series: ListedAdapter}."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    return {code: ListedAdapter(code, item["issuer"], item["listing_urls"], item.get("prefix"),
                                item.get("exclude"), item.get("separator"), item.get("base_href"),
                                item.get("detail_pages", False), item.get("documents"))
            for code, item in data["series"].items() if item.get("listing_urls")}


ADAPTERS = {a.series: a for a in (AfsAdapter(), FffsAdapter(), TsfsAdapter(), AklagareAdapter(), SwedacAdapter(),
                                   PrvAdapter(), PolisenAdapter(), ScbAdapter(),
                                   EnergimyndighetenAdapter(), RiksdagenAdapter(),
                                   RiksarkivetAdapter(), SkolverketAdapter(),
                                   SjofartsverketAdapter(), TrafikverketAdapter())}
ADAPTERS.update({code: a for code, a in load_series().items() if code not in ADAPTERS})


# --- mapping ---------------------------------------------------------------

def build_meta(adapter, entry, regulation, raw_sha256, fetched_at):
    return {
        "id": corpus_id(regulation.number),
        "title": regulation.title,
        "type": TYPE,
        "layer": TYPES[TYPE],
        "number": regulation.number,
        "issued": regulation.issued,
        "in_force": regulation.in_force,
        "repealed": regulation.repealed,
        "amended_by": list(regulation.amended_by),
        "amended_through": regulation.amended_through,
        "reprinted_by": [],
        "ministry": None,
        "eli": None,
        "language": "sv",
        "authoritative": False,
        "source": entry.url,
        "source_sha256": raw_sha256,
        "fetched_at": fetched_at,
        "issuer": adapter.issuer,
    }


def _link(label, url):
    label = label.replace("[", "(").replace("]", ")")
    return f"[{label}](<{url}>)"


def to_markdown(adapter, meta, regulation):
    facts = [
        ("Författningssamling", adapter.series),
        ("Utgivare", adapter.issuer),
        ("Beslutad", regulation.issued),
        ("Utkom från tryck", regulation.published),
        ("Ikraftträdande", regulation.in_force),
        ("Upphävd", regulation.repealed),
        ("Version", regulation.version),
        ("Ändringar införda till och med", regulation.amended_through),
    ]
    blocks = ["# " + meta["title"], "  \n".join(f"{k}: {v}" for k, v in facts if v)]
    if regulation.summary:
        if regulation.summary.lstrip().startswith("## "):
            blocks.append(regulation.summary)
        else:
            blocks.extend(["## Sammanfattning", regulation.summary])
    if regulation.amendments:
        lines = []
        for amendment in regulation.amendments:
            line = amendment.number
            if amendment.in_force:
                line += f", i kraft {amendment.in_force}"
            if amendment.scope:
                line += f": {amendment.scope}"
            lines.append("- " + line)
        blocks.extend(["## Ändringsförfattningar", "\n".join(lines)])
    elif regulation.amended_by:
        blocks.extend(["## Ändringsförfattningar", "\n".join("- " + n for n in regulation.amended_by)])
    if regulation.pdfs:
        blocks.extend(["## Dokument", "\n".join("- " + _link(label, url) for label, url in regulation.pdfs)])
    if regulation.text:
        blocks.extend(["## Författningstext", regulation.text])
        if regulation.footnotes:
            blocks.extend(["## Fotnoter", "\n\n".join(
                f"[{i}] {note}" for i, note in enumerate(regulation.footnotes, 1))])
    else:
        blocks.extend(["## Författningstext", (
            f"{adapter.issuer} publicerar texten endast som pdf; se Dokument ovan. "
            "Den tryckta författningssamlingen är den officiella versionen.")])
    return "\n\n".join(b for b in blocks if b) + "\n"


# --- state, manifest, report -----------------------------------------------

def load_manifest(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError):
        raise StateError(f"manifest corrupt: {path}") from None
    if not isinstance(data, dict) or not isinstance(data.get("entries"), list):
        raise StateError(f"manifest corrupt: {path}")
    return {e["number"]: e for e in data["entries"] if isinstance(e, dict) and "number" in e}


def save_manifest(path, entries):
    ordered = sorted(entries.values(), key=lambda e: (e["number"].split(" ")[0], number_key(e["number"])))
    data = {"version": MANIFEST_VERSION, "entries": ordered}
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    if not path.exists() or path.read_text(encoding="utf-8") != text:
        path.write_text(text, encoding="utf-8")


@dataclass
class RunSummary:
    written: "list[str]" = field(default_factory=list)
    unchanged: int = 0
    skipped: int = 0
    excluded: int = 0
    pdfs: int = 0
    failed: "list[str]" = field(default_factory=list)
    blocked: bool = False


def _write_report(path, summary):
    report = {
        "written": summary.written,
        "unchanged": summary.unchanged,
        "skipped": summary.skipped,
        "excluded": summary.excluded,
        "pdfs": summary.pdfs,
        "failed": summary.failed,
        "blocked": summary.blocked,
    }
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


# --- run -------------------------------------------------------------------

class _Robots:
    """robots.txt of one host; a missing file (404) allows everything."""

    def __init__(self, client, base_url):
        self.parser = None
        try:
            raw = client.get(base_url + "/robots.txt")
        except urllib.error.HTTPError as error:
            if error.code in (404, 410):
                return
            raise ListingError(f"{base_url}/robots.txt: HTTP {error.code}") from error
        except NETWORK_ERRORS as error:
            raise ListingError(f"{base_url}/robots.txt: {error}") from error
        self.parser = urllib.robotparser.RobotFileParser()
        self.parser.parse(raw.decode("utf-8", errors="replace").splitlines())

    def allows(self, url):
        return self.parser is None or self.parser.can_fetch(USER_AGENT, url)

    def crawl_delay(self):
        delay = self.parser.crawl_delay(USER_AGENT) if self.parser is not None else None
        return float(delay) if delay else 0.0


def _get_listing(client, robots, url, adapter=None):
    if not robots.allows(url):
        raise Blocked(f"robots.txt disallows {url}")
    fetch = getattr(adapter, "fetch_listing", None)  # e.g. a search form that is POSTed
    try:
        return (fetch(client, url) if fetch else client.get(url)).decode("utf-8")
    except Blocked:
        raise
    except (*NETWORK_ERRORS, UnicodeDecodeError) as error:
        raise ListingError(f"{url}: {error}") from error


def _entries(client, robots, adapter, args):
    urls = adapter.listing_urls(args)
    if urls is None:  # TSFS without --year: every year of the index
        urls = [adapter.year_url(y) for y in adapter.parse_index(_get_listing(client, robots, adapter.index_url))]
    urls, seen = list(urls), set(urls)
    for url in urls:  # grows while a paginated listing names further pages
        text = _get_listing(client, robots, url, adapter)
        try:
            entries = adapter.parse_listing(text, url)
        except ValueError as error:
            raise ListingError(f"{url}: {error}") from error
        for page in getattr(adapter, "more_pages", lambda text, url: ())(text, url):
            if page not in seen:
                seen.add(page)
                urls.append(page)
        yield from entries


def _selected(entry, args):
    if args.number and entry.number not in args.number:
        return False
    return not args.year or number_key(entry.number)[0] in args.year


def _snapshot_pdfs(client, robots, regulation, entry, manifest, refresh):
    """Hash every PDF of `regulation` once; returns the number downloaded."""
    previous = {f["url"]: f for f in manifest.get(regulation.number, {}).get("files", [])}
    files, downloaded = [], 0
    for label, url in regulation.pdfs:
        if url in previous and not refresh:
            files.append(previous[url])
            continue
        if not robots.allows(url):
            files.append({"label": label, "url": url, "bytes": None, "sha256": None,
                          "content_type": None, "retrieved_at": None,
                          "note": "robots.txt disallows this path; not downloaded"})
            continue
        body, content_type = client.fetch(url)
        if not body.startswith(b"%PDF-"):
            raise ValueError(f"not a PDF: {url}")
        files.append({
            "label": label,
            "url": url,
            "bytes": len(body),
            "sha256": hashlib.sha256(body).hexdigest(),
            "content_type": content_type,
            "retrieved_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        })
        downloaded += 1
    if files:
        manifest[regulation.number] = {"number": regulation.number, "detail_url": entry.url, "files": files}
    return downloaded


def _unchanged(meta, body, corpus):
    """Same body and frontmatter, ignoring `fetched_at` and `source_sha256`.

    Agency pages carry navigation that changes without the regulation changing,
    so a new page hash alone does not rewrite the file.
    """
    try:
        stored, stored_body = frontmatter.load(path_for(meta, corpus).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    volatile = ("fetched_at", "source_sha256")
    return stored_body == body and {k: v for k, v in stored.items() if k not in volatile} == {
        k: v for k, v in meta.items() if k not in volatile}


def _stored_source(doc_id, corpus):
    path = existing_path(doc_id, corpus)
    if path is None:
        return None
    try:
        stored, _ = frontmatter.load(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return stored.get("source")


def _collect_one(client, robots, adapter, entry, args, manifest, summary):
    if adapter.detail:
        if not robots.allows(entry.url):
            raise ValueError(f"robots.txt disallows {entry.url}")
        raw = client.get(entry.url)
        regulation = adapter.parse_detail(raw.decode("utf-8"), entry)
        sha256 = hashlib.sha256(raw).hexdigest()
    else:
        regulation = adapter.regulation(entry)
    summary.pdfs += _snapshot_pdfs(client, robots, regulation, entry, manifest, args.refresh)
    if not adapter.detail:
        # The source is the regulation's own PDF; its hash is in the manifest.
        files = {f["url"]: f for f in manifest.get(regulation.number, {}).get("files", [])}
        sha256 = (files.get(entry.url) or {}).get("sha256")
        if sha256 is None:
            raise ValueError(f"source PDF not downloaded: {entry.url}")
    fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    meta = build_meta(adapter, entry, regulation, sha256, fetched_at)
    other = _stored_source(meta["id"], args.corpus)
    if adapter.detail and other is not None and other != meta["source"]:
        raise ValueError(f"{meta['number']} is already stored from {other}")
    body = to_markdown(adapter, meta, regulation)
    if _unchanged(meta, body, args.corpus):
        return meta, False
    write(meta, body, args.corpus)
    return meta, True


def run(client, args):
    summary = RunSummary()
    state = _load_state(args.state)
    manifest = load_manifest(args.manifest)
    state["blocked"] = None

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
        for series in args.series:
            adapter = ADAPTERS[series]
            robots = _Robots(client, adapter.base_url)
            if hasattr(client, "min_interval"):
                client.min_interval = max(args.rate, robots.crawl_delay())
            written = 0
            for entry in _entries(client, robots, adapter, args):
                if args.limit is not None and written >= args.limit:
                    break
                if not _selected(entry, args):
                    continue
                if not entry.base:
                    summary.excluded += 1
                    continue
                doc_path = path_for({"id": corpus_id(entry.number), "type": TYPE}, args.corpus)
                if adapter.detail and not args.refresh and entry.number in state["done"] and doc_path.exists():
                    summary.skipped += 1
                    continue
                try:
                    meta, changed = _collect_one(client, robots, adapter, entry, args, manifest, summary)
                except NotBase:
                    summary.excluded += 1
                    state["failed"].pop(entry.number, None)
                except DOCUMENT_ERRORS as error:
                    summary.failed.append(entry.number)
                    state["failed"][entry.number] = f"{type(error).__name__}: {error}"
                else:
                    if changed:
                        written += 1
                        summary.written.append(meta["number"])
                    else:
                        summary.unchanged += 1
                    state["done"][entry.number] = meta["source_sha256"]
                    state["failed"].pop(entry.number, None)
                _save_state(args.state, state)
    except Blocked as error:
        return finish(str(error))
    except BaseException:
        finish()
        raise
    return finish()


# --- command line ----------------------------------------------------------

def _series(value):
    codes = {code.upper(): code for code in ADAPTERS}
    code = codes.get(value.strip().upper())
    if code is None:
        raise argparse.ArgumentTypeError(f"unknown series {value!r}; known: {', '.join(ADAPTERS)}")
    return code


def _rate(value):
    seconds = float(value)
    if seconds < MIN_RATE:
        raise argparse.ArgumentTypeError(f"must be at least {MIN_RATE} s: {value}")
    return seconds


def _non_negative(value):
    number = int(value)
    if number < 0:
        raise argparse.ArgumentTypeError(f"must not be negative: {value}")
    return number


def _year(value):
    year = int(value)
    if not 1900 <= year <= 2100:
        raise argparse.ArgumentTypeError(f"not a year: {value}")
    return year


def _regulation_number(value):
    number = _clean(value)
    if not re.fullmatch(r"[A-ZÅÄÖa-zåäö][A-ZÅÄÖa-zåäö0-9-]* \d{4}:\d+", number):
        raise argparse.ArgumentTypeError(f"not a regulation number (e.g. 'AFS 2023:1'): {value}")
    prefix, rest = number.split(" ", 1)
    codes = {code.upper(): code for code in ADAPTERS}
    return f"{codes.get(prefix.upper(), prefix.upper())} {rest}"


def parse_args(argv):
    parser = argparse.ArgumentParser(prog="collect.py agency")
    parser.add_argument("--series", action="append", type=_series, required=True,
                        help=f"series to collect ({', '.join(ADAPTERS)}); repeatable")
    parser.add_argument("--year", action="append", type=_year, default=[],
                        help="only regulations numbered in this year; repeatable "
                             "(TSFS reads only these year listings)")
    parser.add_argument("--number", action="append", type=_regulation_number, default=[],
                        metavar="'AFS 2023:1'", help="only this regulation; repeatable")
    parser.add_argument("--limit", type=_non_negative, help="stop after N written documents per series")
    parser.add_argument("--refresh", action="store_true",
                        help="refetch regulations and PDFs already done")
    parser.add_argument("--report", metavar="FILE", help="write a JSON run report")
    parser.add_argument("--rate", type=_rate, default=MIN_RATE, metavar="SECONDS",
                        help=f"minimum interval between requests (at least {MIN_RATE} s)")
    parser.add_argument("--state", default=DEFAULT_STATE)
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST)
    parser.add_argument("--corpus", default="corpus")
    args = parser.parse_args(argv)
    args.series = list(dict.fromkeys(args.series))
    args.year = set(args.year)
    for number in args.number:
        if number_key(number)[0] not in args.year and args.year:
            parser.error(f"--number {number} is outside --year")
    if args.number and not args.year:
        args.year = {number_key(n)[0] for n in args.number}
    return args


def main(argv, client=None):
    if argv and argv[0] == "agency":
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
        f"done: {len(summary.written)} written, {summary.unchanged} unchanged, "
        f"{summary.skipped} skipped, {summary.excluded} excluded (amending), "
        f"{summary.pdfs} PDFs hashed, {len(summary.failed)} failed"
        + (", BLOCKED" if summary.blocked else ""),
        flush=True,
    )
    if summary.failed:
        print("failed: " + ", ".join(summary.failed), flush=True)
    if summary.blocked:
        print("blocked: see state file", file=sys.stderr)
        return 2
    return 0


from . import agency_generic  # noqa: E402,F401  (registers the generic series)
