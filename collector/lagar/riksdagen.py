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
_CHAPTER = re.compile(r"^\d+ ?[a-z]? kap\. ")
_PARAGRAPH = re.compile(r"^(\d+ ?[a-z]? ?§)")
_AMENDMENT = re.compile(r"^(?:Lag|Förordning) \((\d{4}:\d+)\)")
_AMENDMENT_ANY = re.compile(r"\((\d{4}:\d+)\)")
_SOURCE_KEY = "Källa"
PRINT_ONLY_NOTE = "_Text available only in print._"


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
                title=(doc.get("titel") or "").strip(),
                issued=(doc.get("datum") or "").strip() or None,
                systemdatum=doc.get("systemdatum") or "",
                ministry=(doc.get("organ") or "").strip() or None,
            )
        )
    return items, pages


def parse_text(raw):
    lines = raw.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    header = {}
    body_start = len(lines)
    for index, line in enumerate(lines):
        match = _HEADER_LINE.match(line)
        if not match:
            continue
        key = match.group(1).strip()
        # Header keys are short labels; a long prefix is body prose.
        if len(key) > 40:
            continue
        header[key] = match.group(2).strip()
        if key == _SOURCE_KEY:
            body_start = index + 1
            break
    body = "\n".join(line.rstrip() for line in lines[body_start:]).strip("\n")
    return ParsedText(header=header, body=body.strip())


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


def amendments(body):
    found = set()
    for line in body.split("\n"):
        match = _AMENDMENT.match(line.strip())
        if match:
            found.add(match.group(1))
    return sorted(found, key=lambda n: tuple(int(p) for p in n.split(":")))


def to_markdown(title, body):
    blocks = ["# " + title.strip()]
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
