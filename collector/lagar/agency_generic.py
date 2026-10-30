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

import re
import urllib.parse
from dataclasses import dataclass, field

from . import agency
from .agency import Entry, Regulation, _clean, absolute, number_key, parse_html

_AMENDING = re.compile(
    r"\b(om )?(ändring|ändringar|upphävande)\b( av| i| om)?|ändringsförfattning|ändringsföreskrift",
    re.IGNORECASE)
_PDF_NOISE = re.compile(
    r"\(?\s*\|?\s*\bpdf\b\s*[,|]?\s*(\d[\d.,]*\s*[km]?b\b)?\s*(,?\s*(öppnas i )?nytt fönster)?\s*[.)]?"
    r"|\s*,?\s*öppnas i nytt fönster\.?", re.IGNORECASE)


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
    return path.endswith(".pdf") or "/download/" in path or "/link/" in path


class PdfListAdapter(_LinkAdapter):
    """The listing links straight to the regulation PDFs."""

    raw_detail = True

    def parse_listing(self, text, url):
        root = parse_html(text)
        entries = {}
        for node in self._items(root):
            links = [a for a in self._links(node) if _is_pdf_link(a.attrs.get("href", ""))]
            if not links:
                continue
            item_text = node.text()
            number = self.item_number(item_text, [a.attrs.get("href", "") for a in links])
            if number is None:
                continue
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

    def entry_from_link(self, link, url):
        """An Entry for a listing link, or None when it is not a regulation of the series."""
        href = link.attrs.get("href", "")
        text = link.text()
        number = self.number(text, href)
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

    def parse_detail(self, text, entry):
        root = parse_html(text)
        page = self.page(root)
        if entry.number not in self.references(page.text()):
            raise ValueError(f"detail page does not name {entry.number}")
        heading = page.find("h1")
        title = self.clean_title(heading.text(), entry.number) if heading is not None else entry.title
        if title == entry.number:
            title = entry.title
        if is_amending(title):
            raise agency.NotBase(f"{entry.number} is an amending regulation")
        pdfs, seen = [], set()
        for link in page.find_all("a"):
            href = link.attrs.get("href", "")
            if not _is_pdf_link(href):
                continue
            pdf_url = absolute(entry.url, href)
            if pdf_url not in seen:
                seen.add(pdf_url)
                pdfs.append((_clean(_PDF_NOISE.sub(" ", link.text())) or entry.number, pdf_url))
        return Regulation(number=entry.number, title=title, in_force=entry.in_force,
                          repealed=entry.repealed, amended_by=list(entry.amended_by),
                          version="Grundförfattning", pdfs=pdfs)


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


SERIES = (MigrfsAdapter(), KamfsAdapter(), KfmfsAdapter(), KfsAdapter(), KrfsAdapter(), MemyfsAdapter())

agency.ADAPTERS.update({a.series: a for a in SERIES})
