"""Text of a scanned PDF through optical character recognition.

Used only when `pdftext` finds no text layer. poppler's `pdftoppm` renders each
page to a grey-scale image and `tesseract` reads it with the Swedish model
(`apt-get install poppler-utils tesseract-ocr tesseract-ocr-swe`, `brew install
poppler tesseract tesseract-lang`). The collector stays stdlib-only: both tools
run as commands on a temporary copy of the bytes.

Recognised text can hold misread characters (`8` for `§` is common), so callers
mark it as OCR text (`text_source: ocr` in the frontmatter) and keep the PDF as
the authoritative source. Lines that tesseract reads with low confidence
(signatures, stamps, handwriting) are dropped; a file read with low confidence
overall comes back with a `gap`, like a scan `pdftext` cannot read.
"""

import shutil
import subprocess
import tempfile
from pathlib import Path

from . import pdftext

RENDER = "pdftoppm"
RECOGNISE = "tesseract"
LANGUAGE = "swe"
DPI = 300
TIMEOUT_SECONDS = 300  # per command: rendering the file, or reading one page
# Mean word confidence (0-100) below which a line is dropped: signatures,
# stamps and handwriting read as noise.
MIN_LINE_CONFIDENCE = 60
# Mean word confidence below which the whole file is not trusted.
MIN_CONFIDENCE = 70

LOW_CONFIDENCE = "OCR confidence too low (scanned PDF)"


class OcrError(Exception):
    """A tool is missing, failed or timed out."""


def available():
    """Whether both tools and the Swedish model are installed."""
    recognise = shutil.which(RECOGNISE)
    if shutil.which(RENDER) is None or recognise is None:
        return False
    try:
        listed = subprocess.run([recognise, "--list-langs"], capture_output=True, timeout=30, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return LANGUAGE in listed.stdout.decode("utf-8", "replace").split()


def extract(data, timeout=TIMEOUT_SECONDS):
    """Return the pdftext.PdfText of the scanned PDF bytes `data`, read by OCR."""
    render, recognise = shutil.which(RENDER), shutil.which(RECOGNISE)
    if render is None or recognise is None:
        raise OcrError(f"{RENDER} and {RECOGNISE} are needed (poppler-utils, tesseract-ocr-{LANGUAGE})")
    with tempfile.TemporaryDirectory(prefix="lagar-ocr-") as tmp:
        tmp = Path(tmp)
        (tmp / "document.pdf").write_bytes(data)
        _run([render, "-q", "-r", str(DPI), "-gray", "-png", "document.pdf", "page"], tmp, timeout)
        images = sorted(tmp.glob("page-*.png"), key=lambda p: int(p.stem.rsplit("-", 1)[1]))
        pages = []
        for image in images:
            _run([recognise, image.name, image.stem, "-l", LANGUAGE,
                  "-c", "tessedit_create_tsv=1", "-c", "tessedit_create_txt=0"], tmp, timeout)
            pages.append(parse_tsv((tmp / f"{image.stem}.tsv").read_text(encoding="utf-8", errors="replace")))
    return result(pages)


def result(pages):
    """PdfText of the pages read, each a (text, confidence sum, word count) triple."""
    words = sum(count for _text, _total, count in pages)
    confidence = sum(total for _text, total, _count in pages) / words if words else 0
    read = pdftext.classify("\f".join(text for text, _total, _count in pages))
    if read.usable and confidence < MIN_CONFIDENCE:
        return pdftext.PdfText(text=read.text, pages=read.pages, text_pages=read.text_pages, gap=LOW_CONFIDENCE)
    return read


def parse_tsv(tsv):
    """(text, confidence sum, word count) of one page from tesseract's TSV output.

    Rows at level 5 are words, keyed by block, paragraph and line. A line whose
    mean confidence is below MIN_LINE_CONFIDENCE is left out; paragraphs are
    separated by a blank line.
    """
    lines = {}
    for row in tsv.splitlines()[1:]:
        cells = row.split("\t")
        if len(cells) < 12 or cells[0] != "5":
            continue
        word, confidence = cells[11].strip(), float(cells[10])
        if not word or confidence < 0:
            continue
        lines.setdefault((int(cells[2]), int(cells[3]), int(cells[4])), []).append((word, confidence))
    out, total, count, paragraph = [], 0.0, 0, None
    for key in sorted(lines):
        words = lines[key]
        if sum(c for _w, c in words) / len(words) < MIN_LINE_CONFIDENCE:
            continue
        if paragraph is not None and key[:2] != paragraph:
            out.append("")
        paragraph = key[:2]
        out.append(" ".join(w for w, _c in words))
        total += sum(c for _w, c in words)
        count += len(words)
    return "\n".join(out), total, count


def _run(command, cwd, timeout):
    try:
        done = subprocess.run(command, cwd=cwd, capture_output=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as error:
        raise OcrError(f"{Path(command[0]).name} timed out after {timeout} s") from error
    if done.returncode != 0:
        message = done.stderr.decode("utf-8", "replace").strip() or f"exit status {done.returncode}"
        raise OcrError(f"{Path(command[0]).name} failed: {message}")
