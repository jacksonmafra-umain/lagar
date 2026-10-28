"""Parse Riksdagen SFS listings and plain-text documents; convert to Markdown."""

import json
import re
from dataclasses import dataclass

FUNDAMENTAL_LAWS = {
    "sfs-1974-152": "Regeringsformen",
    "sfs-1949-105": "Tryckfrihetsförordningen",
    "sfs-1991-1469": "Yttrandefrihetsgrundlagen",
    "sfs-1810-0926": "Successionsordningen",
}

_HEADER_LINE = re.compile(r"^([^:]+):(.*)$")
# A chapter heading is a title; "7 kap. 3 § gäller inte." is a sentence.
_CHAPTER = re.compile(r"^\d+ ?[a-z]? kap\. (?!\d+ ?[a-z]? ?§)")
_PARAGRAPH = re.compile(r"^(\d+ ?[a-z]? ?§)")
_AMENDMENT = re.compile(r"(?:Lag|Förordning) \((N?\d{4}:\d+)\)\.(?=\s|$)")
_SOURCE_KEY = "Källa"
_SENTENCE_END = ".!?:;)\"»”"
# Blank lines may separate header entries (e.g. between `Övrig text` and
# `Upphävd`), so the header is delimited by its known keys, not by blank lines.
HEADER_KEYS = frozenset({
    "SFS nr", "Departement/myndighet", "Utfärdad", "Omtryck", "Ändrad",
    "Övrig text", "Upphävd", "Ikraft", "Tidsbegränsad", _SOURCE_KEY,
})
PRINT_ONLY_NOTE = "_Text available only in print._"


def collapse_whitespace(text):
    """Collapse every whitespace run (newlines included) to one space and strip."""
    return " ".join(text.split())


_RUBRIK_MARKER = re.compile(r"/Rubriken\b([^/]*)/")


def clean_title(raw):
    """Single-line title; for renamed statutes keep the currently valid one.

    Transitional titles interleave `/Rubriken upphör att gälla U:.../` and
    `/Rubriken träder i kraft I:.../` markers with the titles they apply to.
    """
    parts = _RUBRIK_MARKER.split(raw)
    if len(parts) == 1:
        return collapse_whitespace(raw)
    # parts: [before, marker1, text1, marker2, text2, ...]
    current = future = None
    for marker, text in zip(parts[1::2], parts[2::2]):
        text = collapse_whitespace(text)
        if not text:
            continue
        if "upphör" in marker and current is None:
            current = text
        elif "träder" in marker and future is None:
            future = text
    return current or future or collapse_whitespace(parts[0])


@dataclass
class ListingItem:
    dok_id: str
    number: str
    title: str
    issued: "str | None"
    systemdatum: str
    ministry: "str | None"


@dataclass
class ParsedText:
    header: "dict[str, str]"
    body: str


def parse_listing(raw):
    root = json.loads(raw)["dokumentlista"]
    pages = int(root.get("@sidor") or 0)
    items = []
    for doc in root.get("dokument") or []:
        items.append(
            ListingItem(
                dok_id=doc["dok_id"],
                number=doc["beteckning"],
                title=clean_title(doc.get("titel") or ""),
                issued=(doc.get("datum") or "").strip() or None,
                systemdatum=doc.get("systemdatum") or "",
                ministry=(doc.get("organ") or "").strip() or None,
            )
        )
    return items, pages


def _header_key(line):
    """The known header key a line starts, or None."""
    match = _HEADER_LINE.match(line)
    if not match:
        return None
    key = match.group(1).strip()
    return key if key in HEADER_KEYS else None


def parse_text(raw):
    lines = raw.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    header = {}
    last_header = None
    for index, line in enumerate(lines):
        if not line.strip():
            continue
        key = _header_key(line)
        if key is None:
            if header:
                # The header is a run of known keys; the first other line ends it.
                break
            continue  # title line or preamble before the header
        header[key] = _HEADER_LINE.match(line).group(2).strip()
        last_header = index
        if key == _SOURCE_KEY:
            break
    body_start = 0 if last_header is None else last_header + 1
    body = "\n".join(line.rstrip() for line in lines[body_start:]).strip()
    return ParsedText(header=header, body=body)


def classify(title, dok_id):
    if dok_id in FUNDAMENTAL_LAWS:
        return "fundamental_law"
    words = title.split()
    first = words[0].lower() if words else ""
    if first.endswith("förordning"):
        return "ordinance"
    if first == "lag" or first.endswith("lag") or first.endswith("balk"):
        return "act"
    return "other_statute"


def _number_order(number):
    """(year, ordinal, is_n_series): the N prefix only breaks ties, plain first."""
    n_series = number.startswith("N")
    year, _, ordinal = number.removeprefix("N").partition(":")
    return (int(year), int(ordinal), n_series)


def amendments(body):
    found = set()
    paragraph = []
    for line in body.split("\n") + [""]:
        if line.strip():
            paragraph.append(line.strip())
            continue
        if paragraph:
            text = " ".join(paragraph)
            for match in _AMENDMENT.finditer(text):
                # An amendment note closes a sentence; "se Lag (2000:1)." is a
                # reference inside one.
                before = text[: match.start()].rstrip()
                if not before or before[-1] in _SENTENCE_END:
                    found.add(match.group(1))
            paragraph = []
    return sorted(found, key=_number_order)


def to_markdown(title, body):
    blocks = ["# " + collapse_whitespace(title)]
    paragraphs = []
    current = []
    for line in body.split("\n"):
        if line.strip():
            current.append(line.strip())
        elif current:
            paragraphs.append(current)
            current = []
    if current:
        paragraphs.append(current)
    if not paragraphs:
        blocks.append(PRINT_ONLY_NOTE)
    for lines in paragraphs:
        text = " ".join(lines)
        # Only a standalone line is a heading; wrapped prose may start with "8 kap. ".
        if len(lines) == 1 and _CHAPTER.match(text):
            blocks.append("## " + text)
            continue
        match = _PARAGRAPH.match(text)
        if match:
            text = "**" + match.group(1) + "**" + text[match.end():]
        blocks.append(text)
    return "\n\n".join(blocks) + "\n"
