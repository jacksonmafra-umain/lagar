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
import urllib.parse
from dataclasses import dataclass, field

from . import agency, htmlmd
from .agency import Entry, Regulation, _clean, absolute, number_key, parse_html, to_html

_AMENDING = re.compile(
    r"\b(om )?(ändring|ändringar|upphävande)\b( av| i| om)?|ändringsförfattning|ändringsföreskrift",
    re.IGNORECASE)
# PDFs on a regulation page that are not the regulation: impact assessments, memos, errata.
_NOT_REGULATION = re.compile(r"konsekvens|\bPM\b|\bpm-|remiss|vägledning|rättelse|engelsk|english", re.IGNORECASE)
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
    series = ""
    issuer = ""
    base_url = ""
    listings: "tuple[str, ...]" = ()
    item: "tuple[str, str | None] | None" = None  # (tag, class) of one listing item
    scope: "tuple[str, str | None] | None" = None  # (tag, class) holding the listing
    bare_numbers = False  # also accept a bare "2001:1" for this series
    has_text = False

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
        """Every number of this series named in `text`."""
        return [f"{self.series} {m.group(1)}:{int(m.group(2))}" for m in self.pattern().finditer(text or "")]

    def clean_title(self, text, number):
        title = _PDF_NOISE.sub(" ", text)
        year, serial = number.split(" ")[-1].split(":")
        own = self.pattern()
        title = own.sub(lambda m: "" if (m.group(1), int(m.group(2))) == (year, int(serial)) else m.group(0),
                        title, count=1)
        title = re.sub(r"\(\s*[,;]?\s*\)", "", title)
        title = re.sub(r"\(\s*[,;]\s*", "(", re.sub(r"\s*[,;]\s*\)", ")", title))
        title = re.sub(r"\s+\.$", "", title)
        return _clean(title).strip(" -–:,|") or number

    def _items(self, root):
        scope = root
        if self.scope is not None:
            scope = root.find(*self.scope)
            if scope is None:
                raise ValueError(f"no {self.scope} on the {self.series} listing page")
        if self.item is not None:
            return scope.find_all(*self.item)
        return scope.find_all("a")

    @staticmethod
    def _links(node):
        return [node] if node.tag == "a" else node.find_all("a")

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

    raw_detail = True
    number_node: "tuple[str, str | None] | None" = None  # (tag, class) in the item holding the number
    title_node: "tuple[str, str | None] | None" = None  # (tag, class) in the item holding the title

    def parse_listing(self, text, url):
        root = parse_html(text)
        entries = {}
        for node in self._items(root):
            links = [a for a in self._links(node) if _is_pdf_link(a.attrs.get("href", ""))]
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
            pdfs = [(number, absolute(url, a.attrs.get("href", ""))) for a in links]
            if number in entries:
                known = {u for _, u in entries[number].pdfs}
                entries[number].pdfs.extend(p for p in pdfs if p[1] not in known)
                continue
            title = self.clean_title(item_text, number)
            entries[number] = LinkEntry(number=number, title=title, url=pdfs[0][1],
                                        base=not is_amending(title), pdfs=pdfs)
        if not entries:
            raise ValueError(f"no {self.series} regulations found on {url}")
        return self.link_amendments(list(entries.values()))

    def parse_detail(self, raw, entry):
        if not raw.startswith(b"%PDF-"):
            raise ValueError(f"not a PDF: {entry.url}")
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
            label = _clean(_PDF_NOISE.sub(" ", link.text()))
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
            if not urllib.parse.urlsplit(page_url).path.startswith(self.path_prefix):
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
    raw_detail = False
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


SERIES = (MigrfsAdapter(), KamfsAdapter(), KfmfsAdapter(), KfsAdapter(), KrfsAdapter(), MemyfsAdapter(),
          ElsakfsAdapter(), McffsAdapter(), MdffsAdapter(), NfsAdapter(), KifsAdapter(), AgvfsAdapter(),
          KovfsAdapter(), HvmfsAdapter(), FkfsAdapter(), IaffsAdapter(), AffsAdapter())

agency.ADAPTERS.update({a.series: a for a in SERIES})
