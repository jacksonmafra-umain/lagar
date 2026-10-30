"""Text of a PDF through poppler's `pdftotext`, with a check for scanned files.

Shared by every collector that reads official PDFs (county, agency and
municipal regulations, SFS prints). The collector stays stdlib-only: the text
comes from the `pdftotext` command of poppler-utils (`apt-get install
poppler-utils`, `brew install poppler`), run on a temporary copy of the bytes.

A PDF made of page images has no text layer, and one whose fonts lack a
Unicode map yields symbols instead of letters. Both come back with `usable`
false and a `gap` reason; callers record the gap and never guess the text.
"""

import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

TOOL = "pdftotext"
TIMEOUT_SECONDS = 120
# A page with fewer letters and digits than this carries no text layer (a scan,
# or only a stamp or page number added on top of one).
MIN_PAGE_CHARS = 40
# Share of pages that must carry text for the file to count as text.
MIN_TEXT_PAGES = 0.5
# Share of letters and digits among the visible characters below which the text
# layer is unreadable (fonts without a Unicode map).
MIN_ALNUM_SHARE = 0.5
# A line shorter than this share of the text width ends its paragraph when the
# next line starts with a capital letter or a digit.
SHORT_LINE = 0.75

NO_TEXT_LAYER = "no text layer (scanned PDF)"
UNREADABLE_TEXT = "text layer is not readable (fonts without a Unicode map)"

_PAGE_NUMBER = re.compile(r"^\s*(?:-\s*)?(?:sid(?:a|an)?\s+)?\d{1,4}(?:\s*\(\d{1,4}\))?(?:\s*-)?\s*$", re.I)
_HYPHENATED = re.compile(r"(\w)-$")
_RULE = re.compile(r"^[_\-–—=*. ]{3,}$")
# Section, chapter and list markers that open a paragraph of their own.
_BREAK_BEFORE = re.compile(r"^(?:\d+\s?[a-z]?\s?§|\d+\s?kap\.|\d{1,2}[.)]\s|[a-z]\)\s|Bilaga\b|Övergångsbestämmelser\b|På .{0,40}vägnar\b)")
_SPACES = re.compile(r"[ \t ]+")
# "miljö- och hälsoskydd": a hyphen before these words is not a line-break hyphen.
_CONJUNCTIONS = frozenset({"och", "eller", "samt", "respektive", "resp", "till", "som"})


class PdfTextError(Exception):
    """The PDF could not be read: the tool is missing, failed or timed out."""


@dataclass(frozen=True)
class PdfText:
    text: str
    pages: int
    text_pages: int
    gap: str | None

    @property
    def usable(self):
        return self.gap is None


def available():
    return shutil.which(TOOL) is not None


def extract(data, timeout=TIMEOUT_SECONDS):
    """Return the PdfText of the PDF bytes `data`."""
    tool = shutil.which(TOOL)
    if tool is None:
        raise PdfTextError(f"{TOOL} is not installed (poppler-utils)")
    with tempfile.TemporaryDirectory(prefix="lagar-pdf-") as tmp:
        path = Path(tmp) / "document.pdf"
        path.write_bytes(data)
        try:
            result = subprocess.run(
                [tool, "-q", "-enc", "UTF-8", str(path), "-"],
                capture_output=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            raise PdfTextError(f"{TOOL} timed out after {timeout} s") from error
    if result.returncode != 0:
        message = result.stderr.decode("utf-8", "replace").strip() or f"exit status {result.returncode}"
        raise PdfTextError(f"{TOOL} failed: {message}")
    return classify(result.stdout.decode("utf-8", "replace"))


def classify(raw):
    """PdfText for the raw `pdftotext` output: pages split by form feeds."""
    pages = raw.split("\f")
    if pages and not pages[-1].strip():
        pages.pop()
    count = max(len(pages), 1)
    text_pages = sum(1 for page in pages if _alnum(page) >= MIN_PAGE_CHARS)
    visible = sum(1 for c in raw if not c.isspace())
    gap = None
    if text_pages < count * MIN_TEXT_PAGES:
        gap = NO_TEXT_LAYER
    elif _alnum(raw) < visible * MIN_ALNUM_SHARE:
        gap = UNREADABLE_TEXT
    return PdfText(text=raw.replace("\f", "\n\n"), pages=count, text_pages=text_pages, gap=gap)


def paragraphs(text):
    """Reflow extracted text into paragraphs.

    `pdftotext` ends every printed line, and often runs paragraphs together without
    a blank line. A new paragraph starts after a blank line, before a section or
    list marker (`3 §`, `2 kap.`, `1.`, `a)`), and after a line noticeably shorter
    than the text width when the next line starts with a capital letter or a
    digit. Other lines are joined; a word hyphenated across a line break is
    rejoined when the next line goes on in lower case. Lines holding only a page
    number or a rule (`_____`) are dropped.
    """
    lines = [_SPACES.sub(" ", line).strip() for line in text.replace("\f", "\n\n").split("\n")]
    width = _text_width(lines)
    result = []
    current = []

    def flush():
        if current:
            result.append(" ".join(current))
            current.clear()

    for line in lines:
        if not line or _RULE.match(line):
            flush()
            continue
        if _PAGE_NUMBER.match(line):
            continue
        if current:
            previous = current[-1]
            if (
                _HYPHENATED.search(previous)
                and line[:1].islower()
                and line.split(" ", 1)[0].rstrip(",.;:") not in _CONJUNCTIONS
            ):
                current[-1] = previous[:-1] + line
                continue
            if _BREAK_BEFORE.match(line) or (
                len(previous) < width * SHORT_LINE and (line[:1].isupper() or line[:1].isdigit())
            ):
                flush()
        current.append(line)
    flush()
    return result


def _text_width(lines):
    """The usual length of a full line: the 90th percentile of the longer lines."""
    lengths = sorted(len(line) for line in lines if len(line) >= 20)
    if not lengths:
        return 0
    return lengths[min(len(lengths) - 1, int(len(lengths) * 0.9))]


def _alnum(text):
    return sum(1 for c in text if c.isalnum())
