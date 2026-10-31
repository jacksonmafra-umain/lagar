"""Text of a PDF through poppler's `pdftotext`, with a check for scanned files.

Shared by every collector that reads official PDFs (county, agency and
municipal regulations, SFS prints). The collector stays stdlib-only: the text
comes from the `pdftotext` command of poppler-utils (`apt-get install
poppler-utils`, `brew install poppler`), run on a temporary copy of the bytes.

A PDF made of page images has no text layer, and one whose fonts lack a
Unicode map yields symbols instead of letters. Both come back with `usable`
false and a `gap` reason; callers record the gap and never guess the text.
The one exception is a known font encoding that shifts every character by a
fixed amount: such text is decoded, and kept only when the result passes the
same checks.
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
# Fonts with a shifted encoding read as accented Latin letters with "=" for each
# space ("i®åëëíóêÉäëÉå=g®ãíä~åÇë=ä®å" for "Länsstyrelsen Jämtlands län"): the
# text is unreadable when both shares reach these values. Swedish text, Sami
# names and other languages in a parallel text stay well below either.
MIN_FOREIGN_LATIN_SHARE = 0.1
MIN_EQUALS_SHARE = 0.02
# Glyphs drawn with wrong widths come out letter-spaced, with word breaks lost
# ("Läns s t y r e l s e niKr onobe r g sl änskung"). The text is unreadable when
# at least this share of its words are single letters and this share at most two
# letters long (common short Swedish words aside); readable text stays far below.
MIN_WORDS = 50
MIN_SINGLE_LETTER_SHARE = 0.25
MIN_SHORT_WORD_SHARE = 0.4
# A line shorter than this share of the text width ends its paragraph when the
# next line starts with a capital letter or a digit.
SHORT_LINE = 0.75

NO_TEXT_LAYER = "no text layer (scanned PDF)"
UNREADABLE_TEXT = "text layer is not readable (fonts without a Unicode map)"
LETTER_SPACED = "text layer is not readable (letter-spaced, word breaks lost)"

_PAGE_NUMBER = re.compile(r"^\s*(?:-\s*)?(?:sid(?:a|an)?\s+)?\d{1,4}(?:\s*\(\d{1,4}\))?(?:\s*-)?\s*$", re.I)
_HYPHENATED = re.compile(r"(\w)-$")
_RULE = re.compile(r"^[_\-–—=*. ]{3,}$")
# Section, chapter and list markers that open a paragraph of their own.
_BREAK_BEFORE = re.compile(r"^(?:\d+\s?[a-z]?\s?§|\d+\s?kap\.|\d{1,2}[.)]\s|[a-z]\)\s|Bilaga\b|Övergångsbestämmelser\b|På .{0,40}vägnar\b)")
_SWEDISH_LETTERS = frozenset("åäöéüÅÄÖÉÜ")
_SPACES = re.compile(r"[ \t ]+")
# "miljö- och hälsoskydd": a hyphen before these words is not a line-break hyphen.
_CONJUNCTIONS = frozenset({"och", "eller", "samt", "respektive", "resp", "till", "som"})
# One- and two-letter words that ordinary Swedish text is full of.
_SHORT_WORDS = frozenset("i e s m a b c d av om en på är de ut nu så få se ny ha ej än ur st kr ca nr km".split())


def _shift_table():
    """Shifted character -> original character, for the Jämtland fonts.

    Their embedded TrueType fonts number the glyphs in Apple's standard order and
    the PDF draws each character with its glyph number, which `pdftotext` reads
    as WinAnsi/MacRoman: ASCII comes out 0x1D higher ("=" for a space, "~" for
    "a"), and from "b" on the code lands in the MacRoman upper half one further
    along ("É" for "e", "®" for "ä", "∏" for "ö").
    """
    table = {chr(code): chr(code - 0x1D) for code in range(0x3D, 0x7F)}
    for code in range(0x80, 0x100):
        original = code - 0x1E
        shifted = bytes([code]).decode("mac_roman")
        table[shifted] = bytes([original]).decode("mac_roman") if original >= 0x80 else chr(original)
    return table


_UNSHIFT = _shift_table()


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


def classify(raw, decode=True):
    """PdfText for the raw `pdftotext` output: pages split by form feeds.

    Text in the shifted font encoding is decoded once when `decode` is true.
    """
    pages = raw.split("\f")
    if pages and not pages[-1].strip():
        pages.pop()
    count = max(len(pages), 1)
    text_pages = sum(1 for page in pages if _alnum(page) >= MIN_PAGE_CHARS)
    visible = sum(1 for c in raw if not c.isspace())
    gap = None
    if text_pages < count * MIN_TEXT_PAGES:
        gap = NO_TEXT_LAYER
    elif _shifted_encoding(raw, visible):
        if decode:
            result = classify(unshift(raw), decode=False)
            if result.usable:
                return result
        gap = UNREADABLE_TEXT
    elif _alnum(raw) < visible * MIN_ALNUM_SHARE:
        gap = UNREADABLE_TEXT
    elif _letter_spaced(raw):
        gap = LETTER_SPACED
    return PdfText(text=raw.replace("\f", "\n\n"), pages=count, text_pages=text_pages, gap=gap)


def unshift(text):
    """Decode text drawn with the shifted font encoding (see `_shift_table`)."""
    return "".join(_UNSHIFT.get(c, c) for c in text)


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


def _shifted_encoding(raw, visible):
    letters = _alnum(raw)
    foreign = sum(1 for c in raw if "\u00c0" <= c <= "\u024f" and c not in _SWEDISH_LETTERS)
    return (
        letters > 0
        and foreign >= letters * MIN_FOREIGN_LATIN_SHARE
        and raw.count("=") >= visible * MIN_EQUALS_SHARE
    )


def _letter_spaced(raw):
    words = [w for w in (t.strip(".,;:()") for t in raw.split()) if w.isalpha()]
    if len(words) < MIN_WORDS:
        return False
    unusual = [w for w in words if len(w) <= 2 and w.lower() not in _SHORT_WORDS]
    single = sum(1 for w in unusual if len(w) == 1)
    return single >= len(words) * MIN_SINGLE_LETTER_SHARE and len(unusual) >= len(words) * MIN_SHORT_WORD_SHARE


def _alnum(text):
    return sum(1 for c in text if c.isalnum())
