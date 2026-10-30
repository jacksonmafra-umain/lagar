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
    return _SPACE.sub(" ", (value or "").replace(" ", " ")).strip()


def _date(text):
    match = _ISO_DATE.search(text or "")
    return match.group(0) if match else None


def number_key(number):
    match = _NUMBER.search(number)
    return (int(match.group(1)), int(match.group(2))) if match else (sys.maxsize, sys.maxsize)


def corpus_id(number):
    """`AFS 2023:1` -> `afs-2023-1`, `HSLF-FS 2016:40` -> `hslf-fs-2016-40`."""
    slug = number.lower().translate(str.maketrans({"å": "a", "ä": "a", "ö": "o"}))
    return re.sub(r"[^0-9a-z]+", "-", slug).strip("-")


def absolute(base, href):
    """An absolute URL for `href`, with spaces and other unsafe path characters quoted."""
    parts = urllib.parse.urlsplit(urllib.parse.urljoin(base, html.unescape(href.strip())))
    path = urllib.parse.quote(urllib.parse.unquote(parts.path), safe="/:@!$&'()*+,;=-._~")
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, path, parts.query, ""))


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


ADAPTERS = {a.series: a for a in (AfsAdapter(), FffsAdapter(), TsfsAdapter())}


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


def _get_listing(client, robots, url):
    if not robots.allows(url):
        raise Blocked(f"robots.txt disallows {url}")
    try:
        return client.get(url).decode("utf-8")
    except Blocked:
        raise
    except (*NETWORK_ERRORS, UnicodeDecodeError) as error:
        raise ListingError(f"{url}: {error}") from error


def _entries(client, robots, adapter, args):
    urls = adapter.listing_urls(args)
    if urls is None:  # TSFS without --year: every year of the index
        urls = [adapter.year_url(y) for y in adapter.parse_index(_get_listing(client, robots, adapter.index_url))]
    for url in urls:
        try:
            entries = adapter.parse_listing(_get_listing(client, robots, url), url)
        except ValueError as error:
            raise ListingError(f"{url}: {error}") from error
        yield from entries


def _selected(entry, args):
    if args.number and entry.number not in args.number:
        return False
    return not args.year or number_key(entry.number)[0] in args.year


def _snapshot_pdfs(client, robots, regulation, entry, manifest, refresh, detail=None):
    """Hash every PDF of `regulation` once; returns the number hashed.

    `detail` is the body of `entry.url` when that is itself a PDF: it is hashed
    without downloading it again.
    """
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
        if detail is not None and url == entry.url:
            body, content_type = detail, "application/pdf"
        else:
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
    if not robots.allows(entry.url):
        raise ValueError(f"robots.txt disallows {entry.url}")
    raw = client.get(entry.url)
    if getattr(adapter, "raw_detail", False):  # the detail is the PDF itself
        regulation = adapter.parse_detail(raw, entry)
        detail = raw
    else:
        regulation = adapter.parse_detail(raw.decode("utf-8"), entry)
        detail = None
    summary.pdfs += _snapshot_pdfs(client, robots, regulation, entry, manifest, args.refresh, detail)
    fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    meta = build_meta(adapter, entry, regulation, hashlib.sha256(raw).hexdigest(), fetched_at)
    other = _stored_source(meta["id"], args.corpus)
    if other is not None and other != meta["source"]:
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
                if not args.refresh and entry.number in state["done"] and doc_path.exists():
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
    code = value.strip().upper()
    if code not in ADAPTERS:
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
    number = _clean(value).upper()
    if not re.fullmatch(r"[A-ZÅÄÖ][A-ZÅÄÖ0-9-]* \d{4}:\d+", number):
        raise argparse.ArgumentTypeError(f"not a regulation number (e.g. 'AFS 2023:1'): {value}")
    return number


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
