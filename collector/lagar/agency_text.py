"""Regulation text and dates from the text layer of an agency regulation PDF.

The printed regulation starts with a masthead (series name, ISSN, publisher),
the title, the number and the publication date, then "beslutade den ...". The
text kept is what follows the masthead; the dates are read from it:

- `issued`: "beslutade den 20 oktober 2026";
- `published`: "Utkom från trycket den 23 juni 2026" or "Publicerad den 2026-10-20";
- `in_force`: "träder i kraft den 1 januari 2027", or the publication date for
  "träder i kraft samma dag som de publicerades" (and similar).
"""

import re
from dataclasses import dataclass, field

from . import pdftext

_MONTHS = {name: i for i, name in enumerate(
    ("januari", "februari", "mars", "april", "maj", "juni", "juli", "augusti", "september", "oktober",
     "november", "december"), 1)}
_SWEDISH_DATE = r"(\d{1,2})\s+(" + "|".join(_MONTHS) + r")\s+(\d{4})"
_ISSUED = re.compile(r"\bbeslutade?\s+den\s+" + _SWEDISH_DATE, re.IGNORECASE)
_PUBLISHED = re.compile(r"\b(?:utkom\s+från\s+trycket|publicerad)\s+den\s+(?:"
                        + _SWEDISH_DATE + r"|(\d{4}-\d{2}-\d{2}))", re.IGNORECASE)
_IN_FORCE = re.compile(r"\bträder\s+i\s+kraft\s+(?:den\s+" + _SWEDISH_DATE
                       + r"|(?:samma\s+dag|dagen)\s+(?:som|då)\s+(?:de|den|föreskrifterna?)\s+(?:publicera|utk))",
                       re.IGNORECASE)
_START = re.compile(r"^beslutade?\s+den\b", re.IGNORECASE)
_SECTION = re.compile(r"^(\d+\s?[a-z]?\s§)\s")
_TITLE = re.compile(r"\b(föreskrift(er)?|allmänna råd|förordning)\b", re.IGNORECASE)


@dataclass
class PdfRegulation:
    text: str = ""  # Markdown
    title: "str | None" = None  # from the masthead
    gap: "str | None" = None  # why there is no text
    issued: "str | None" = None
    published: "str | None" = None
    in_force: "str | None" = None
    notes: "list[str]" = field(default_factory=list)


def _iso(day, month, year):
    return f"{int(year):04d}-{_MONTHS[month.lower()]:02d}-{int(day):02d}"


def dates(text):
    """(issued, published, in_force) found in the regulation text."""
    flat = re.sub(r"\s+", " ", text)
    issued = _ISSUED.search(flat)
    published = _PUBLISHED.search(flat)
    published_iso = None
    if published is not None:
        published_iso = published.group(4) or _iso(*published.group(1, 2, 3))
    in_force = _IN_FORCE.search(flat)
    in_force_iso = None
    if in_force is not None:
        in_force_iso = _iso(*in_force.group(1, 2, 3)) if in_force.group(1) else published_iso
    return (_iso(*issued.group(1, 2, 3)) if issued else None), published_iso, in_force_iso


def _escape(paragraph):
    """Keep a paragraph from turning into a Markdown heading, list or quote by accident."""
    paragraph = paragraph.replace("\\", "\\\\").replace("*", "\\*").replace("_", "\\_")
    paragraph = re.sub(r"^([#>+])", r"\\\1", paragraph)
    return re.sub(r"^(\d+)\.(\s)", r"\1\\.\2", paragraph)


# Where the title ends: publication lines, the series code (`MIGRFS`, `KAMFS 2026:4`) or a number or date.
_TITLE_END = re.compile(r"^(?i:publicerad|utkom|issn|ansvarig|beslutade?)\b|^[A-ZÅÄÖ-]{2,}(\s+\d{4}:\d+)?$|^\d{4}[:-]")


def _lines(text):
    return [re.sub(r"\s+", " ", line).strip() for line in text.replace("\f", "\n").split("\n")]


def _start(lines):
    """Index of the "beslutade den" line that ends the masthead, or None."""
    return next((i for i, line in enumerate(lines) if _START.match(line)), None)


def to_markdown(text, number, series_name=None):
    """Markdown paragraphs of the regulation text, without the masthead and running headers.

    Section signs that open a paragraph (`1 §`) are set in bold; a "- " item
    stays a list item.
    """
    lines = _lines(text)
    start = _start(lines) or 0
    body = "\n".join(lines[start:])
    # A dash list item starts its own paragraph (pdftext joins it to the line before).
    paragraphs = pdftext.paragraphs(re.sub(r"\n(?=[-–•] )", "\n\n", body))
    out = []
    for paragraph in paragraphs:
        if paragraph == number or (series_name and paragraph == series_name):
            continue  # running header
        escaped = _escape(re.sub(r"^[–•] ", "- ", paragraph))
        if escaped.startswith("- "):
            out.append(escaped)
            continue
        out.append(_SECTION.sub(r"**\1** ", escaped))
    return "\n\n".join(out)


def title(text):
    """The regulation's title from the masthead: the lines naming its kind before "beslutade den"."""
    lines = _lines(text)
    end = _start(lines)
    if end is None:
        return None
    for i, line in enumerate(lines[:end]):
        if not _TITLE.search(line) or "författningssamling" in line.lower():
            continue
        parts = [line]
        for following in lines[i + 1:end]:
            if not following or _TITLE_END.search(following):
                break
            parts.append(following)
        title = " ".join(parts).strip().rstrip(";")
        return title if len(title) < 400 else None
    return None


def read(data, number, series_name=None):
    """PdfRegulation of the PDF bytes `data`; `gap` tells why text is missing."""
    try:
        extracted = pdftext.extract(data)
    except pdftext.PdfTextError as error:
        return PdfRegulation(gap=str(error))
    if not extracted.usable:
        return PdfRegulation(gap=extracted.gap)
    issued, published, in_force = dates(extracted.text)
    return PdfRegulation(text=to_markdown(extracted.text, number, series_name), title=title(extracted.text),
                         issued=issued,
                         published=published, in_force=in_force)
