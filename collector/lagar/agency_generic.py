"""Generic adapters for agency series published as plain lists of links.

Most agencies publish their series as a page of links, each link (or list item)
naming a regulation number and pointing either straight at the PDF or at a short
HTML page that links to it. Two configurable adapters cover these sites:

- `PdfListAdapter`: the listing links straight to the PDFs; one entry per item
  (a list item, table row or single link) that names a number of the series.
- `DetailPageAdapter`: the listing links to one HTML page per regulation; the
  page gives the title and links to the PDFs.

A series is one subclass that sets the class attributes. Amending and repealing
regulations are told apart by their titles ("om ändring i", "om upphävande
av") and listed in the `amended_by` of the base regulation they name.
"""

import html
import json
import re
import unicodedata
import urllib.parse
from dataclasses import dataclass, field

from . import agency, htmlmd
from .agency import Entry, Regulation, _clean, absolute, number_key, parse_html, to_html

_AMENDING = re.compile(
    r"\b(om )?(ändring|ändringar|upphävande)\b( av| i| om)?|ändringsförfattning|ändringsföreskrift",
    re.IGNORECASE)
# PDFs on a regulation page that are not the regulation: impact assessments, memos, errata.
_NOT_REGULATION = re.compile(r"konsekvens|\bPM\b|\bpm-|remiss|vägledning|rättelse|engelsk|english|skriv ut",
                             re.IGNORECASE)
# A link on a listing that is a companion document, not a regulation.
_COMPANION = re.compile(r"\s*([a-zåäö-]+\s+)?(\d{4}:\d+\s+)?(konsekvensutredning|vägledning|rättelse|pm\b|remiss)",
                        re.IGNORECASE)
_HEADINGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
_REPEALED = re.compile(r"\s*\(upphävd:?\s*(\d{4}-\d{2}-\d{2})\)", re.IGNORECASE)
_PDF_NOISE = re.compile(
    r"\(?\s*\|?\s*\bpdf\b\s*[,|]?\s*(\d[\d.,]*\s*[km]?b\b)?\s*(,?\s*(öppnas i )?nytt fönster)?\s*[.)]?"
    r"|\s*,?\s*öppnas i nytt fönster\.?", re.IGNORECASE)


_MONTHS = {name: i for i, name in enumerate(
    ("januari", "februari", "mars", "april", "maj", "juni", "juli", "augusti", "september", "oktober",
     "november", "december"), 1)}
_DATE = r":?\s+den\s+(\d{1,2})\s+(" + "|".join(_MONTHS) + r")\s+(\d{4})"
_ISSUED = re.compile(r"\bbeslutade?" + _DATE, re.IGNORECASE)
_PUBLISHED = re.compile(r"\butkom\s+från\s+trycket" + _DATE, re.IGNORECASE)


def _swedish_date(pattern, text):
    match = pattern.search(re.sub(r"\s+", " ", text or ""))
    if match is None:
        return None
    day, month, year = match.groups()
    return f"{int(year):04d}-{_MONTHS[month.lower()]:02d}-{int(day):02d}"


def issued_date(text):
    """`2025-04-15` for "Beslutade den 15 april 2025" (or "Beslutade: Den ..."), or None."""
    return _swedish_date(_ISSUED, text)


def published_date(text):
    """`2025-06-03` for "Utkom från trycket den 3 juni 2025", or None."""
    return _swedish_date(_PUBLISHED, text)


@dataclass
class LinkEntry(Entry):
    pdfs: "list[tuple[str, str]]" = field(default_factory=list)


def _series_pattern(series):
    """`MIGRFS 2026:14`, `MIGRFS_2026_14`, `migrfs-2026-14`, `AgVFS 2016:1`, `...fondKFMFS 2026:2`.

    Case-insensitive, but not preceded by an upper-case letter or a digit (so
    `KFS` does not match inside `KKFS`); a lower-case letter may precede it,
    since some sites glue the number to the title.
    """
    def letters(part):
        return "".join(f"[{c.upper()}{c.lower()}]" if c.isalpha() else re.escape(c) for c in part)

    name = r"[\s_-]*".join(letters(part) for part in re.split(r"[\s-]+", series))
    return re.compile(rf"(?<![A-ZÅÄÖ0-9]){name}[\s_.-]*(\d{{4}})\s*[:_.-]\s*(\d{{1,3}})(?!\d)")


def _slug_pattern(series):
    """`mcffs-202614`, `nfs-20269-...`: the number run together in a URL slug."""
    letters = re.sub(r"[^a-z]", "", series.lower().translate(str.maketrans("åäö", "aao")))
    return re.compile(rf"(?<![a-z]){letters}-?(\d{{4}})(\d{{1,3}})(?![\d])", re.IGNORECASE)


def _markdown(markup):
    """Markdown of the regulation text HTML; `**1** **§**` (two bold runs) becomes `**1 §**`."""
    text = htmlmd.to_markdown(markup, heading_offset=1)
    return re.sub(r"\*\*(\d+\s?[a-z]?)\s*\*\*\s*\*\*\s*§\s*\*\*", r"**\1 §**", text)


def is_amending(title):
    return bool(_AMENDING.search(title or ""))


class _LinkAdapter:
    detail = True
    series = ""
    issuer = ""
    base_url = ""
    listings: "tuple[str, ...]" = ()
    item: "tuple[str, str | None] | None" = None  # (tag, class) of one listing item
    scope: "tuple[str, str | None] | None" = None  # (tag, class) holding the listing
    bare_numbers = False  # also accept a bare "2001:1" for this series
    has_text = False
    # An item is a heading and what follows it ("h3"), or a link and the text after it ("a").
    group_by: "str | None" = None
    skip_section: "re.Pattern | None" = None  # leave out items under a heading matching it (repealed lists)
    consolidated_section: "re.Pattern | None" = None  # PDFs under a heading matching it are consolidated

    @property
    def listing_url(self):
        return self.listings[0]

    def listing_urls(self, args):
        return list(self.listings)

    def pattern(self):
        return _series_pattern(self.series)

    def number(self, *texts):
        """`SERIES YYYY:N` from the first text that names one, or None."""
        pattern = self.pattern()
        for text in texts:
            match = pattern.search(text or "")
            if match is None and self.bare_numbers:
                match = re.search(r"(?<![\d:])(\d{4}):(\d{1,3})(?![\d:])", text or "")
            if match is not None:
                return f"{self.series} {match.group(1)}:{int(match.group(2))}"
        return None

    def item_number(self, text, hrefs):
        """The number of a listing item: one leading or ending its text, else in a link, else anywhere.

        An amending item often names the regulation it amends inside its title,
        while its own number is at either end of the text or only in the file
        name of the PDF.
        """
        text = _clean(_PDF_NOISE.sub(" ", text))
        ends = [m for m in self.pattern().finditer(text)
                if m.start() <= 1 or not text[m.end():].strip(" )].;,")]
        if ends:
            return self.number(ends[0].group(0))
        if self.bare_numbers:
            lead = self.number(text[:12])
            if lead is not None:
                return lead
        files = [urllib.parse.unquote(h.rsplit("/", 1)[-1]) for h in hrefs]
        return self.number(*files) or self.number(text)

    def slug_number(self, url):
        """The number run together in the last path segment of `url` (`.../nfs-20269/`), or None."""
        segment = urllib.parse.unquote(urllib.parse.urlsplit(url).path).rstrip("/").rsplit("/", 1)[-1]
        match = _slug_pattern(self.series).search(segment)
        return f"{self.series} {match.group(1)}:{int(match.group(2))}" if match else None

    def references(self, text):
        """Every number of this series named in `text`, also a bare one after "föreskrifter" ("(2022:4)")."""
        found = [(m.group(1), m.group(2)) for m in self.pattern().finditer(text or "")]
        found += re.findall(r"\bföreskrift(?:er|erna)?\s+\((\d{4}):(\d{1,3})\)", text or "", re.IGNORECASE)
        return [f"{self.series} {year}:{int(serial)}" for year, serial in found]

    def clean_title(self, text, number):
        title = re.sub(r"\s*·\s*[\d.,]+\s*[km]?b\b", " ", _PDF_NOISE.sub(" ", text), flags=re.IGNORECASE)
        year, serial = number.split(" ")[-1].split(":")
        own = self.pattern()
        title = own.sub(lambda m: "" if (m.group(1), int(m.group(2))) == (year, int(serial)) else m.group(0),
                        title, count=1)
        title = re.sub(r"\(\s*[,;]?\s*\)", "", title)
        title = re.sub(r"\(\s*[,;]\s*", "(", re.sub(r"\s*[,;]\s*\)", ")", title))
        title = re.sub(r"\s+\.$", "", title)
        if self.bare_numbers:
            title = re.sub(rf"^\s*{year}:{serial}(?!\d)", "", title)
        title = re.sub(r"(?<=[A-Za-zÅÄÖåäö]{2})\.\s*$", "", title)
        return _clean(title).strip(" -–:,|*") or number

    def _items(self, root):
        scope = root
        if self.scope is not None:
            scope = root.find(*self.scope)
            if scope is None:
                raise ValueError(f"no {self.scope} on the {self.series} listing page")
        if self.item is not None:
            return scope.find_all(*self.item)
        return scope.find_all("a")

    def _sections(self, root):
        """(item, section) pairs in document order; section is the text of the last heading before it.

        With `group_by` an item is a new node holding the heading or link that
        starts it and what follows, up to the next heading or start.
        """
        out = []
        section, group = "", None

        def is_item(node):
            if self.item is None:
                return node.tag == "a"
            return node.tag == self.item[0] and (self.item[1] is None or self.item[1] in node.classes)

        def start(node):
            nonlocal group
            group = agency.Node("div")
            group.children.append(node)
            out.append((group, section))

        def walk(node):
            nonlocal section, group
            for child in node.children:
                if isinstance(child, str):
                    if group is not None:
                        group.children.append(child)
                elif self.group_by is None and is_item(child):
                    out.append((child, section))
                elif child.tag == self.group_by:
                    start(child)
                elif child.tag in _HEADINGS:
                    section, group = child.text(), None
                elif child.tag == "a" and group is not None:
                    group.children.append(child)
                else:
                    walk(child)

        scope = root
        if self.scope is not None:
            scope = root.find(*self.scope)
            if scope is None:
                raise ValueError(f"no {self.scope} on the {self.series} listing page")
        walk(scope)
        return out

    @staticmethod
    def _links(node):
        return [node] if node.tag == "a" else node.find_all("a")

    @staticmethod
    def amending_title(entry, regulation):
        """True when a listing that only named the number hid an amending or repealing regulation."""
        return entry.title == entry.number and is_amending(regulation.title)

    def link_amendments(self, entries):
        """Fill each base entry's `amended_by` from the amending titles that name it."""
        bases = {e.number: e for e in entries if e.base}
        for entry in entries:
            if entry.base:
                continue
            for ref in self.references(entry.title):
                if ref != entry.number and ref in bases and entry.number not in bases[ref].amended_by:
                    bases[ref].amended_by.append(entry.number)
        for entry in bases.values():
            entry.amended_by.sort(key=number_key)
        return entries


def _is_pdf_link(href):
    path = href.lower().split("?", 1)[0]
    return path.endswith(".pdf") or any(part in path for part in ("/download/", "/downloads/", "/link/"))


class PdfListAdapter(_LinkAdapter):
    """The listing links straight to the regulation PDFs."""

    detail = False  # the PDF is the document; the run loop hashes it
    number_node: "tuple[str, str | None] | None" = None  # (tag, class) in the item holding the number
    title_node: "tuple[str, str | None] | None" = None  # (tag, class) in the item holding the title

    def parse_listing(self, text, url):
        root = parse_html(text)
        entries = {}
        sectioned = self.group_by or self.skip_section or self.consolidated_section
        items = self._sections(root) if sectioned else [(node, "") for node in self._items(root)]
        for node, section in items:
            if self.skip_section is not None and self.skip_section.search(section):
                continue
            anchors = self._links(node)
            if not anchors and node.attrs.get("data-href"):  # a clickable row without a link
                anchors = [agency.Node("a", {"href": node.attrs["data-href"]})]
            links = [a for a in anchors
                     if _is_pdf_link(a.attrs.get("href", "")) and not _COMPANION.match(a.text())]
            if not links:
                continue
            item_text = node.text()
            number_node = node.find(*self.number_node) if self.number_node else None
            if number_node is not None:
                number = self.number(number_node.text())
            else:
                number = self.item_number(item_text, [a.attrs.get("href", "") for a in links])
            if number is None:
                continue
            title_node = node.find(*self.title_node) if self.title_node else None
            if title_node is not None:
                item_text = title_node.text()
            elif self.group_by in _HEADINGS:  # the heading holds the number, the rest the title
                rest = agency.Node("div")
                rest.children = node.children[1:]
                item_text = rest.text()
            in_section = bool(self.consolidated_section and self.consolidated_section.search(section))
            pdfs = []
            for a in links:
                named = "konsolid" in a.text().lower()  # a "konsoliderad version" link next to the title
                if named and title_node is None:
                    item_text = item_text.replace(a.text(), " ")
                consolidated = in_section or named
                pdfs.append((f"{number} (konsoliderad version)" if consolidated else number,
                             absolute(url, a.attrs.get("href", ""))))
            pdfs.sort(key=lambda p: "konsolid" in p[0])  # the source is the regulation as issued
            if number in entries:
                entry = entries[number]
                known = {u for _, u in entry.pdfs}
                entry.pdfs.extend(p for p in pdfs if p[1] not in known)
                issued = [u for label, u in entry.pdfs if "konsolid" not in label]
                if issued and entry.url not in issued:
                    entry.url = issued[0]
                continue
            title = self.clean_title(item_text, number)
            entries[number] = LinkEntry(number=number, title=title, url=pdfs[0][1],
                                        base=not is_amending(title), pdfs=pdfs)
        if not entries:
            raise ValueError(f"no {self.series} regulations found on {url}")
        return self.link_amendments(list(entries.values()))

    def regulation(self, entry):
        pdfs = list(getattr(entry, "pdfs", ()) or [(entry.number, entry.url)])
        return Regulation(number=entry.number, title=entry.title, in_force=entry.in_force,
                          repealed=entry.repealed, amended_by=list(entry.amended_by),
                          version="Grundförfattning", pdfs=pdfs)


class DetailPageAdapter(_LinkAdapter):
    """The listing links to one HTML page per regulation, which links to the PDFs."""

    main: "tuple[str, str | None]" = ("main", None)  # (tag, class) of the page content
    heading_title = True  # the page's h1 is the regulation's title
    title_prefix = ""  # put before a heading that starts in lower case ("om kemiska produkter")
    text_nodes: "tuple[str, str | None] | None" = None  # (tag, class) of the HTML text blocks, if any

    def entry_from_link(self, link, url):
        """An Entry for a listing link, or None when it is not a regulation of the series."""
        href = link.attrs.get("href", "")
        text = link.text()
        number = self.number(text, href) or self.slug_number(absolute(url, href))
        if number is None or _is_pdf_link(href) or href.startswith("#"):
            return None
        title = self.clean_title(text, number)
        return Entry(number=number, title=title, url=absolute(url, href), base=not is_amending(title))

    def parse_listing(self, text, url):
        root = parse_html(text)
        entries = {}
        for node in self._items(root):
            for link in self._links(node):
                entry = self.entry_from_link(link, url)
                if entry is not None and entry.number not in entries:
                    entries[entry.number] = entry
        if not entries:
            raise ValueError(f"no {self.series} regulations found on {url}")
        return self.link_amendments(list(entries.values()))

    def page(self, root):
        return root.find(*self.main) or root.find("main") or root

    def title(self, page, entry):
        """The regulation's title: the page heading when it is one, else the listing's."""
        heading = page.find("h1") if self.heading_title else None
        title = self.clean_title(heading.text(), entry.number) if heading is not None else entry.title
        if title == entry.number:
            return entry.title
        if self.title_prefix and title[:1].islower():
            return f"{self.title_prefix} {title}"
        return title

    def html_text(self, page):
        """Markdown of the regulation text published on the page, or ""."""
        if self.text_nodes is None:
            return ""
        blocks = [n for n in page.find_all(*self.text_nodes) if n.find("h1") is None]
        return _markdown("".join(to_html(n) for n in blocks)) if blocks else ""

    def amending(self, page, title):
        return is_amending(title)

    def names_number(self, page, entry):
        return entry.number in self.references(page.text())

    def parse_detail(self, text, entry):
        root = parse_html(text)
        page = self.page(root)
        if not self.names_number(page, entry):
            raise ValueError(f"detail page does not name {entry.number}")
        title = self.title(page, entry)
        repealed = _REPEALED.search(title)
        if repealed is not None:
            title = _clean(title[:repealed.start()] + title[repealed.end():])
        else:  # shown next to the heading
            repealed = _REPEALED.search(page.text()[:len(title) + 200])
        if self.amending(page, title):
            raise agency.NotBase(f"{entry.number} is an amending regulation")
        pdfs, seen = [], set()
        for link in page.find_all("a"):
            href = link.attrs.get("href", "")
            label = _clean(re.sub(r"(?i)pdf\s*[\d.,]+\s*[km]?b\s*$", "", _PDF_NOISE.sub(" ", link.text())))
            if not _is_pdf_link(href) or _NOT_REGULATION.search(label + " " + href.rsplit("/", 1)[-1]):
                continue
            pdf_url = absolute(entry.url, href)
            if pdf_url not in seen:
                seen.add(pdf_url)
                pdfs.append((label or entry.number, pdf_url))
        text = self.html_text(page)
        facts = page.text()
        return Regulation(number=entry.number, title=title, in_force=entry.in_force,
                          issued=issued_date(text) or (issued_date(facts) if text else None),
                          published=published_date(facts) if text else None,
                          repealed=repealed.group(1) if repealed else entry.repealed,
                          amended_by=list(entry.amended_by), version="Grundförfattning", pdfs=pdfs, text=text)


class SitemapAdapter(DetailPageAdapter):
    """The regulation pages are found in the site's XML sitemap (the listing needs JavaScript)."""

    path_prefix = ""  # only sitemap URLs whose path starts with this
    path_pattern: "re.Pattern | None" = None  # and, when set, matches this (one page per base regulation)

    def names_number(self, page, entry):
        """The page text, or the file name of a PDF it links to, names the number of its URL."""
        if super().names_number(page, entry):
            return True
        return any(self.slug_number(a.attrs.get("href", "")) == entry.number
                   or self.number(a.attrs.get("href", "").rsplit("/", 1)[-1]) == entry.number
                   for a in page.find_all("a") if _is_pdf_link(a.attrs.get("href", "")))

    def parse_listing(self, text, url):
        entries = {}
        for loc in re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", text):
            page_url = html.unescape(loc)
            path = urllib.parse.urlsplit(page_url).path
            if not path.startswith(self.path_prefix):
                continue
            if self.path_pattern is not None and not self.path_pattern.search(path):
                continue
            number = self.slug_number(page_url)
            if number is not None and number not in entries:
                entries[number] = Entry(number=number, title=number, url=page_url)
        if not entries:
            raise ValueError(f"no {self.series} regulations found in {url}")
        return sorted(entries.values(), key=lambda e: number_key(e.number), reverse=True)


# --- series ----------------------------------------------------------------

class MigrfsAdapter(PdfListAdapter):
    series = "MIGRFS"
    issuer = "Migrationsverket"
    base_url = "https://www.migrationsverket.se"
    listings = (base_url + "/om-migrationsverket/styrning-och-uppfoljning/foreskrifter.html",)
    item = ("li", "sv-channel-item")


class KamfsAdapter(PdfListAdapter):
    series = "KAMFS"
    issuer = "Kammarkollegiet"
    base_url = "https://www.kammarkollegiet.se"
    listings = (base_url + "/om-oss/kammarkollegiets-forfattningssamling-kamfs",)


class KfmfsAdapter(PdfListAdapter):
    series = "KFMFS"
    issuer = "Kronofogdemyndigheten"
    base_url = "https://www.kronofogden.se"
    listings = (base_url + "/om-kronofogden/dina-rattigheter-lagar-och-regler/foreskrifter-allmanna-rad-och-meddelanden",)


class KrfsAdapter(PdfListAdapter):
    series = "KRFS"
    issuer = "Statens kulturråd"
    base_url = "https://www.kulturradet.se"
    listings = (base_url + "/om-oss/forfattningssamling/",)


class KfsAdapter(PdfListAdapter):
    series = "KFS"
    issuer = "Kommerskollegium"
    base_url = "https://www.kommerskollegium.se"
    listings = (base_url + "/uppdrag/forfattningssamling/",)
    bare_numbers = True


class MemyfsAdapter(PdfListAdapter):
    series = "MEMYFS"
    issuer = "Mediemyndigheten"
    base_url = "https://mediemyndigheten.se"
    listings = (base_url + "/om-oss/lagar-forordningar-och-foreskrifter/",)


class ElsakfsAdapter(DetailPageAdapter):
    series = "ELSÄK-FS"
    issuer = "Elsäkerhetsverket"
    base_url = "https://elsakerhetsverket.se"
    listings = (base_url + "/lag-och-ratt/foreskrifter",)

    def title(self, page, entry):
        """The h1 is the number; the title is the download link's text."""
        for link in page.find_all("a"):
            text = _clean(_PDF_NOISE.sub(" ", link.text()))
            if text.startswith("Ladda ner föreskrifter "):
                return text.removeprefix("Ladda ner föreskrifter ").removesuffix(".").strip()
        return entry.title


class McffsAdapter(DetailPageAdapter):
    series = "MCFFS"
    issuer = "Myndigheten för civilt försvar"
    base_url = "https://www.mcf.se"
    listings = (base_url + "/sv/regler/gallande-regler/",)
    title_prefix = "Myndigheten för civilt försvars"

    def entry_from_link(self, link, url):
        entry = super().entry_from_link(link, url)
        return entry if entry is not None and "/regler/" in entry.url else None


class MdffsAdapter(DetailPageAdapter):
    series = "MDFFS"
    issuer = "Myndigheten för digital förvaltning"
    base_url = "https://www.digg.se"
    listings = (base_url + "/om-oss/forfattningssamling",)
    text_nodes = ("div", "sv-text-portlet-content")


class NfsAdapter(SitemapAdapter):
    series = "NFS"
    issuer = "Naturvårdsverket"
    base_url = "https://www.naturvardsverket.se"
    listings = (base_url + "/sitemap.xml",)
    path_prefix = "/lagar-och-regler/foreskrifter-och-allmanna-rad/"

    def amending(self, page, title):
        """The page text starts with its kind: "Grundföreskrift" or "Ändring"."""
        return page.text().startswith("Ändring") or is_amending(title)


class KifsAdapter(DetailPageAdapter):
    series = "KIFS"
    issuer = "Kemikalieinspektionen"
    base_url = "https://www.kemi.se"
    listings = (base_url + "/lagar-och-regler/lagstiftningar-inom-kemikalieomradet/kemikalieinspektionens-foreskrifter-kifs",)
    title_prefix = "Kemikalieinspektionens föreskrifter"


class AgvfsAdapter(DetailPageAdapter):
    series = "AGVFS"
    issuer = "Arbetsgivarverket"
    base_url = "https://www.arbetsgivarverket.se"
    listings = (base_url + "/avtal-och-skrifter?category=32", base_url + "/avtal-och-skrifter?category=32&page=2")
    heading_title = False

    def clean_title(self, text, number):
        """Drops the agency's internal code after the number (`AGVFS 2026:2 B2 Förordning ...`)."""
        return re.sub(r"^[AB]\s?\d+\s+", "", super().clean_title(text, number))


class KovfsAdapter(DetailPageAdapter):
    series = "KOVFS"
    issuer = "Konsumentverket"
    base_url = "https://publikationer.konsumentverket.se"
    listings = (base_url + "/filtrera-fram-forfattningssamling",)


class HvmfsAdapter(DetailPageAdapter):
    series = "HVMFS"
    issuer = "Havs- och vattenmyndigheten"
    base_url = "https://www.havochvatten.se"
    listings = (base_url + "/vagledning-foreskrifter-och-lagar/foreskrifter.html",)


class IaffsAdapter(PdfListAdapter):
    series = "IAFFS"
    issuer = "Inspektionen för arbetslöshetsförsäkringen"
    base_url = "https://www.iaf.se"
    listings = (base_url + "/Lag-ratt/Foreskrifter/",)
    item = ("div", "c-calendarlist__item")
    number_node = ("span", "c-calendarlist__badge")
    title_node = ("h3", None)


class AffsAdapter(DetailPageAdapter):
    """Arbetsförmedlingen: the list is Sitevision state JSON; each page has the full text as HTML."""

    series = "AFFS"
    issuer = "Arbetsförmedlingen"
    base_url = "https://arbetsformedlingen.se"
    listings = (base_url + "/om-oss/var-verksamhet/styrning-och-resultat/forfattningssamling-AFFS",)

    def parse_listing(self, text, url):
        entries = {}
        for match in re.finditer(r"registerInitialState\('[^']*',(\{.*?\})\);\s*</script>", text, re.S):
            try:
                state = json.loads(match.group(1))
            except ValueError:
                continue
            for item in (state.get("returnObject") or {}).get("list") or []:
                number = self.number(item.get("displayName", ""))
                if number is None or not item.get("URI") or number in entries:
                    continue
                title = _clean(item.get("description")) or number
                entries[number] = Entry(number=number, title=title, url=absolute(url, item["URI"]),
                                        base=not is_amending(title))
        if not entries:
            raise ValueError(f"no AFFS regulations in the page state on {url}")
        return self.link_amendments(list(entries.values()))

    def title(self, page, entry):
        ingress = page.find("p", "ingress")
        return _clean(ingress.text()).removesuffix(", föreskrifter").removesuffix(", allmänna råd") \
            if ingress is not None else entry.title

    def html_text(self, page):
        blocks = []
        for portlet in page.find_all("div", "sv-text-portlet"):
            marker = next((c for c in portlet.children if isinstance(c, agency.Node) and c.tag == "div"
                           and c.attrs.get("id", "").startswith("Innehall")), None)
            content = portlet.find("div", "sv-text-portlet-content")
            if marker is not None and content is not None:
                blocks.append(to_html(content))
        return _markdown("".join(blocks)) if blocks else ""


class FkfsAdapter:
    """Försäkringskassan's lagrummet: the register and each document page carry their data as JSON.

    The register page holds every regulation in force (FKFS and the predecessor
    series RFFS) in a `data-props` attribute; a document page holds the base
    document, the consolidated version and the amending documents with their
    dates and PDF links.
    """

    series = "FKFS"
    issuer = "Försäkringskassan"
    base_url = "https://lagrummet.forsakringskassan.se"
    listing_url = base_url + "/foreskrifter"
    detail = True
    has_text = False

    def listing_urls(self, args):
        return [self.listing_url]

    @staticmethod
    def _props(text):
        for match in re.finditer(r'data-props="([^"]*)"', text):
            props = json.loads(html.unescape(match.group(1)))
            if isinstance(props, dict):
                yield props

    def parse_listing(self, text, url):
        props = next((p for p in self._props(text) if isinstance(p.get("documents"), list)), None)
        if props is None:
            raise ValueError("no register data on the FKFS page")
        view = absolute(url, props.get("viewUrl") or "/foreskrifter/dokument")
        entries = []
        for document in props["documents"]:
            if document.get("forfattningssamling") != self.series or not document.get("nummer"):
                continue
            number = f"{self.series} {document['nummer']}"
            title = _clean(document.get("titel")) or number
            entries.append(Entry(
                number=number, title=title,
                url=f"{view}?id={urllib.parse.quote(document['id'])}",
                base=not document.get("isChangeDocument") and not is_amending(title),
                repealed=document.get("upphavdDatum") or None,
            ))
        if not entries:
            raise ValueError("no FKFS regulations in the register data")
        return entries

    def parse_detail(self, text, entry):
        props = next((p for p in self._props(text) if isinstance(p.get("baseDocument"), dict)), None)
        if props is None:
            raise ValueError("no document data on the FKFS page")
        base = props["baseDocument"]
        meta = {k: (v or {}).get("value") for k, v in (base.get("metadata") or {}).items()}
        if f"{self.series} {meta.get('dokument_nr')}" != entry.number:
            raise ValueError(f"document page shows {meta.get('dokument_nr')!r}, expected {entry.number}")
        regulation = Regulation(
            number=entry.number, title=_clean(meta.get("titel") or base.get("headline")) or entry.title,
            issued=meta.get("beslutsdatum") or None, in_force=meta.get("ikrafttradande") or None,
            published=meta.get("tryckdatum") or None, repealed=meta.get("upphavd_datum") or entry.repealed,
            version="Grundförfattning")
        if base.get("url"):
            regulation.pdfs.append((entry.number, absolute(self.base_url, base["url"])))
        current = props.get("currentDocument")
        if isinstance(current, dict) and current.get("url"):
            regulation.pdfs.append((f"{entry.number} (konsoliderad version)", absolute(self.base_url, current["url"])))
        for change in props.get("changeDocuments") or []:
            change_meta = {k: (v or {}).get("value") for k, v in (change.get("metadata") or {}).items()}
            if not change_meta.get("dokument_nr"):
                continue
            number = f"{change_meta.get('forfattningssamling') or self.series} {change_meta['dokument_nr']}"
            url = absolute(self.base_url, change["url"]) if change.get("url") else None
            regulation.amendments.append(agency.Amendment(
                number=number, in_force=change_meta.get("ikrafttradande") or None, url=url))
            if url:
                regulation.pdfs.append((number, url))
        regulation.amended_by = sorted({a.number for a in regulation.amendments}, key=number_key)
        # A few old documents are Word files; only PDFs are hashed and linked.
        regulation.pdfs = [(label, url) for label, url in regulation.pdfs if url.lower().endswith(".pdf")]
        return regulation



_REPEALED_SECTION = re.compile(r"upphävda", re.IGNORECASE)


class BfnarAdapter(PdfListAdapter):
    series = "BFNAR"
    issuer = "Bokföringsnämnden"
    base_url = "https://www.bfn.se"
    listings = (base_url + "/redovisningsregler/allmanna-rad/",)
    item = ("tr", None)  # number, original PDF, consolidated PDF
    number_node = ("td", None)
    pdf_title = True  # the table gives a short name ("Årsbokslut"); the PDF the full title


class CsnfsAdapter(PdfListAdapter):
    series = "CSNFS"
    issuer = "Centrala studiestödsnämnden"
    base_url = "https://www.csn.se"
    listings = (base_url + "/om-csn/lag-och-ratt/forfattningssamling",)
    item = ("li", None)
    bare_numbers = True  # "2001:6 Centrala studiestödsnämndens föreskrifter ..."
    consolidated_section = re.compile(r"fulltext", re.IGNORECASE)  # "Fulltext - studiehjälp"


class ImyfsAdapter(PdfListAdapter):
    series = "IMYFS"
    issuer = "Integritetsskyddsmyndigheten"
    base_url = "https://www.imy.se"
    listings = (base_url + "/om-oss/beslut-publikationer-och-remisser/foreskrifter-och-allmanna-rad/",)
    scope = ("main", None)
    group_by = "a"  # the link names the number, the text after it is the title


class LmfsAdapter(PdfListAdapter):
    series = "LMFS"
    issuer = "Lantmäteriet"
    base_url = "https://www.lantmateriet.se"
    listings = (base_url + "/sv/Om-Lantmateriet/Rattsinformation/Foreskrifter/",)
    group_by = "h3"  # "LMFS 2023:3", then the title and the PDF link
    number_node = ("h3", None)
    skip_section = _REPEALED_SECTION


class MtfsAdapter(PdfListAdapter):
    series = "MTFS"
    issuer = "Myndigheten för tillväxtpolitiska utvärderingar och analyser"
    base_url = "https://www.tillvaxtanalys.se"
    listings = (base_url + "/statistik/tillvaxtanalysforeskrifter.125740.html",)
    group_by = "h3"
    number_node = ("h3", None)
    skip_section = _REPEALED_SECTION

class KvfsAdapter(SitemapAdapter):
    """Kriminalvården: the listing is a server-side Blazor component, so the pages come from the sitemap.

    A page's heading is a short name (`KVFS 2024:5 – FARK Frivård`); the full
    title is the paragraph under it.
    """

    series = "KVFS"
    issuer = "Kriminalvården"
    base_url = "https://www.kriminalvarden.se"
    listings = (base_url + "/sitemap_kriminalvarden.se.xml",)
    path_prefix = "/om-oss/styrning-och-uppfoljning/foreskrifter-och-allmanna-rad/kriminalvardens-forfattningssamling/"
    main = ("div", "regulationPage")

    def title(self, page, entry):
        intro = page.find("div", "intro")
        lead = intro.find("p") if intro is not None else None
        if lead is None:
            return super().title(page, entry)
        return self.clean_title(lead.text(), entry.number).rstrip(".") or entry.title


class LivsfsAdapter(PdfListAdapter):
    """Livsmedelsverket: one table per year (number, status, subject); titles come from the PDFs.

    The status cell names the regulation an amendment changes ("Ändrar LIVSFS
    2021:8") and whether the regulation is in force ("Gällande", "Upphävd
    genom LIVSFS 2024:2"). A repealed regulation has no repeal date on the
    page, so only regulations in force are collected. Before 2005 the series
    was SLVFS, which is not collected. The index page links the year pages
    (not every year has one); they are read newest first, so the amendments
    of a base regulation are known when its own year is read.
    """

    series = "LIVSFS"
    issuer = "Livsmedelsverket"
    base_url = "https://www.livsmedelsverket.se"
    listings = (base_url + "/om-oss/lagstiftning1/foreskrifter-i-nummerordning/",)
    _YEAR_PAGE = re.compile(r'href="(/om-oss/lagstiftning1/foreskrifter-i-nummerordning/'
                            r'foreskrifter-i-nummerordning-(\d{4})/)"')
    _AMENDS = re.compile(r"^(Ändrar|Ändring|Rättar)", re.IGNORECASE)
    _REPEALED = re.compile(r"upphävd|inte gällande", re.IGNORECASE)

    def __init__(self):
        self._amended_by = {}

    def more_pages(self, text, url):
        if url != self.listings[0]:
            return []
        years = {int(year): absolute(url, path) for path, year in self._YEAR_PAGE.findall(text)}
        return [years[year] for year in sorted(years, reverse=True) if year >= 2005]

    def parse_listing(self, text, url):
        if url == self.listings[0]:
            self._amended_by = {}
            return []
        entries = {}
        for row in parse_html(text).find_all("tr"):
            cells = row.find_all("td")
            if len(cells) < 2:
                continue
            link = next((a for a in cells[0].find_all("a") if _is_pdf_link(a.attrs.get("href", ""))), None)
            number = self.number(link.text(), link.attrs.get("title", "")) if link is not None else None
            if number is None or number in entries or _COMPANION.match(link.text()):
                continue
            status = cells[1].text()
            base = not self._AMENDS.match(status) and not self._REPEALED.search(status)
            pdf = absolute(url, link.attrs["href"])
            # The status of an amendment names what it amends, for `amended_by`. A base gets its title from the
            # PDF, unless the subject cell is a full title ("Livsmedelsverkets förteckning över ...").
            subject = cells[2].text() if len(cells) > 2 else ""
            title = subject if subject.startswith("Livsmedelsverkets ") else number
            entries[number] = LinkEntry(number=number, title=title if base else status, url=pdf, base=base,
                                        pdfs=[(number, pdf)])
        if not entries:
            raise ValueError(f"no {self.series} regulations found on {url}")
        for entry in entries.values():
            if not entry.base:  # "Ändrar LIVSFS 2005:20 Upphävd genom LIVSFS 2011:3": only the first names a base
                for ref in self.references(self._REPEALED.split(entry.title)[0]):
                    if ref != entry.number:
                        self._amended_by.setdefault(ref, set()).add(entry.number)
        for entry in entries.values():
            entry.amended_by = sorted(self._amended_by.get(entry.number, ()), key=number_key)
        return list(entries.values())


class MyhfsAdapter(PdfListAdapter):
    """Myndigheten för yrkeshögskolan: PDF lists of the regulations in force and the repealed ones.

    Each item gives the title, `MYHFS-nummer 2026:5`, `I kraft: <date>` and,
    for a repealed one, `Upphävd: <date>` or nothing. A regulation that repeals
    another says so ("Genom föreskrifterna upphävs ... (MYHFS 2022:2)", or a
    title "om upphävande av ... (2017:2)"), and its date in force is then the
    repeal date. The lists are read in order, in force first, so the repealed
    list can use the dates of both; a repealed regulation without a date is
    left out.
    """

    series = "MYHFS"
    issuer = "Myndigheten för yrkeshögskolan"
    base_url = "https://www.myh.se"
    listings = (base_url + "/lag-och-ratt/foreskrifter-och-allmanna-rad/gallande-foreskrifter-och-allmanna-rad",
                base_url + "/lag-och-ratt/foreskrifter-och-allmanna-rad/upphavda-foreskrifter-och-allmanna-rad")
    _NUMBER = re.compile(r"MYHFS-nummer:?\s*(\d{4}):(\d{1,3})", re.IGNORECASE)
    _IN_FORCE = re.compile(r"I kraft:?\s*(\d{4}-\d{2}-\d{2})", re.IGNORECASE)
    _REPEAL_DATE = re.compile(r"Upphävd:?\s*(\d{4}-\d{2}-\d{2})", re.IGNORECASE)
    _REPEALS = re.compile(r"upphäv(?:s|ande|er)\b(.*)", re.IGNORECASE)
    _BARE = re.compile(r"\((?:MYHFS\s*)?(\d{4}):(\d{1,3})\)")

    def __init__(self):
        self._repealed_on = {}

    def repeals(self, text):
        """Numbers of the regulations that `text` says are repealed."""
        match = self._REPEALS.search(text)
        if match is None:
            return []
        rest = match.group(1)
        found = self.references(rest) + [f"{self.series} {y}:{int(n)}" for y, n in self._BARE.findall(rest)]
        return list(dict.fromkeys(found))

    def parse_listing(self, text, url):
        if url == self.listings[0]:
            self._repealed_on = {}
        repealed_list = url != self.listings[0]
        items = []
        for link in parse_html(text).find_all("a"):
            href = link.attrs.get("href", "")
            facts = link.find("div", "link-text")
            title_node = link.find("div", "v-list-item__title")
            if not _is_pdf_link(href) or facts is None or title_node is None:
                continue
            lines = [p.text() for p in facts.find_all("p")] or [facts.text()]
            match = next((m for m in map(self._NUMBER.search, lines) if m), None)
            if match is None:
                continue
            number = f"{self.series} {match.group(1)}:{int(match.group(2))}"
            in_force = next((m.group(1) for m in map(self._IN_FORCE.search, lines) if m), None)
            repealed = next((m.group(1) for m in map(self._REPEAL_DATE.search, lines) if m), None)
            title = self.clean_title(title_node.text(), number)
            for ref in self.repeals(" ".join([title] + lines)):
                if in_force and ref != number:
                    self._repealed_on.setdefault(ref, in_force)
            items.append((number, title, absolute(url, href), in_force, repealed))
        if not items:
            raise ValueError(f"no {self.series} regulations found on {url}")
        entries = {}
        for number, title, pdf, in_force, repealed in items:
            if number in entries:
                continue
            if repealed_list:
                repealed = repealed or self._repealed_on.get(number)
            base = not is_amending(title) and (not repealed_list or repealed is not None)
            entries[number] = LinkEntry(number=number, title=title, url=pdf, base=base, in_force=in_force,
                                        repealed=repealed if repealed_list else None, pdfs=[(number, pdf)])
        return self.link_amendments(list(entries.values()))



class DvfsAdapter(SitemapAdapter):
    series = "DVFS"
    issuer = "Domstolsverket"
    base_url = "https://www.domstol.se"
    listings = (base_url + "/sitemap.xml",)
    path_prefix = "/om-sveriges-domstolar/for-dig-som-aktor-i-domstol/stod-for-aktorer-i-domstol/dvfs/"
    # `.../dvfs/2020/dvfs-20202/`; the pages below it are its amendments
    path_pattern = re.compile(r"/dvfs/\d{4}/dvfs-\d+/$")


class EifsAdapter(DetailPageAdapter):
    series = "EIFS"
    issuer = "Energimarknadsinspektionen"
    base_url = "https://ei.se"
    listings = (base_url + "/om-oss/lagar-och-regler/foreskrifter/foreskrifter---el",
                base_url + "/om-oss/lagar-och-regler/foreskrifter/foreskrifter---naturgas",
                base_url + "/om-oss/lagar-och-regler/foreskrifter/foreskrifter---fjarrvarme-och-fjarrkyla")
    item = ("tr", None)
    heading_title = False  # the page heading is "Föreskrift"; the title comes from the PDF


class KbvfsAdapter(PdfListAdapter):
    series = "KBVFS"
    issuer = "Kustbevakningen"
    base_url = "https://www.kustbevakningen.se"
    listings = (base_url + "/om-oss/kustbevakningens-forfattningssamling/",)
    item = ("tr", None)  # the row itself links to the PDF (data-href)
    title_node = ("p", "ml-6")


class FfsAdapter(PdfListAdapter):
    """Försvarsmakten lists FFS on four pages whose lists come from the site's content API (JSON).

    Each list item is a PDF named by its file name (`ffs-2015-5-militar-grundutbildning.pdf`),
    so the title, and whether it is an amendment, comes from the PDF.
    """

    series = "FFS"
    issuer = "Försvarsmakten"
    base_url = "https://www.forsvarsmakten.se"
    # gallande-ffs-1978-1994, -1995-2011, -2012-2013 and -2014-
    listings = tuple(f"https://www.forsvarsmakten.se/api/episerver/v3.0/content/{page}?expand=PDFFilesArea"
                     for page in (2562, 2563, 2564, 2565))

    def parse_listing(self, text, url):
        entries = {}
        for item in json.loads(text).get("pdfFilesArea") or []:
            pdf = (item.get("contentLink") or {}).get("expanded") or {}
            name = unicodedata.normalize("NFC", pdf.get("name") or "")  # the API decomposes å, ä, ö
            pdf_url = pdf.get("url") or ""
            number = self.item_number(name, [pdf_url])
            if number is None or not pdf_url or number in entries:
                continue
            entries[number] = LinkEntry(number=number, title=number, url=pdf_url, pdfs=[(number, pdf_url)],
                                        base=not is_amending(re.sub(r"\bandring", "ändring", re.sub(r"[-_]", " ", name))))
        if not entries:
            raise ValueError(f"no {self.series} regulations found on {url}")
        return list(entries.values())

SERIES = (MigrfsAdapter(), KamfsAdapter(), KfmfsAdapter(), KfsAdapter(), KrfsAdapter(), MemyfsAdapter(),
          ElsakfsAdapter(), McffsAdapter(), MdffsAdapter(), NfsAdapter(), KifsAdapter(), AgvfsAdapter(),
          KovfsAdapter(), HvmfsAdapter(), FkfsAdapter(), IaffsAdapter(), AffsAdapter(), BfnarAdapter(),
          CsnfsAdapter(), ImyfsAdapter(), LmfsAdapter(), MtfsAdapter(),
          KvfsAdapter(), LivsfsAdapter(), MyhfsAdapter(), DvfsAdapter(), EifsAdapter(), KbvfsAdapter(),
          FfsAdapter())

agency.ADAPTERS.update({a.series: a for a in SERIES})
