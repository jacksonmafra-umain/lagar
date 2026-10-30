"""Check the Riksdagen text of SFS statutes against the authoritative PDFs.

Reads the PDF snapshot manifest (`sources/sfs-pdf-manifest.json`), extracts the
text of each cached PDF and compares it, word by word, with the body of the
statute in the corpus. The corpus text stays the Riksdagen text; this only
records how much of it the printed statute confirms, in a committed report
(`sources/sfs-pdf-verification.json`).

Riksdagen serves the current (consolidated) text, the PDF the text as first
printed, so statutes amended or repealed since then are reported as `amended`
or `repealed` and never flagged; run it after the amendment register (sfsr).
A statute Riksdagen has only in print is reported as `print_only`: the PDF is
then the only text. A PDF whose number has no statute in the corpus is an amendment or a
statute Riksdagen does not publish; it is counted, not compared.
"""

import argparse
import difflib
import re
import sys
import unicodedata
import urllib.parse
from dataclasses import dataclass
from pathlib import Path

from . import frontmatter, pdftext, writer
from .riksdagen import PRINT_ONLY_NOTE
from .sfs import StateError, _save_state
from .sfspdf import DEFAULT_MANIFEST, load_manifest, number_key

DEFAULT_CACHE = "sources/cache"
DEFAULT_OUT = "sources/sfs-pdf-verification.json"
REPORT_VERSION = 1
# Share of the corpus words the PDF must confirm, in order, to count as a match.
THRESHOLD = 0.97
SNIPPET_WORDS = 12

_WORD = re.compile(r"\w+(?:[.,:]\d+)*")
# Line-end hyphenation in the PDF: "upp-\ngifter" is one word.
_SOFT_BREAK = re.compile(r"(\w)-[ \t]*\n[ \t]*(?=[a-zåäöé])")
# Riksdagen markers such as "/Träder i kraft I:2027-01-01/" are not in the print.
_MARKER = re.compile(r"/(?:Träder i kraft|Upphör att gälla|Rubriken träder|Rubriken upphör)[^/\n]*/")


class NoText(Exception):
    """The PDF has no usable text layer; the message is the pdftext gap reason."""


@dataclass
class Result:
    number: str
    status: str
    coverage: "float | None" = None
    corpus_words: "int | None" = None
    pdf_words: "int | None" = None
    first_difference: "str | None" = None
    error: "str | None" = None

    def entry(self):
        return {k: v for k, v in self.__dict__.items() if v is not None}


def pdf_words(text):
    text = unicodedata.normalize("NFC", text.replace("­", ""))
    text = _SOFT_BREAK.sub(r"\1", text)
    return [w.lower() for w in _WORD.findall(text)]


def corpus_words(body):
    lines = body.splitlines()
    if lines and lines[0].startswith("# "):
        lines = lines[1:]  # the heading joins number and title; the print splits them
    text = unicodedata.normalize("NFC", "\n".join(lines))
    text = _MARKER.sub(" ", text)
    return [w.lower() for w in _WORD.findall(text)]


def compare(corpus, printed):
    """Return (coverage, first_difference): the share of corpus words matched
    in order by the printed words, and the first unmatched run of corpus words."""
    if not corpus:
        return 0.0, None
    matcher = difflib.SequenceMatcher(None, corpus, printed, autojunk=False)
    matched = 0
    first = None
    position = 0
    for block in matcher.get_matching_blocks():
        if first is None and block.a > position:
            first = " ".join(corpus[position:block.a][:SNIPPET_WORDS])
        matched += block.size
        position = block.a + block.size
    return round(matched / len(corpus), 4), first


def _cache_path(cache, number, url):
    name = urllib.parse.unquote(urllib.parse.urlsplit(url).path.rsplit("/", 1)[-1])
    return Path(cache) / number.split(":", 1)[0] / name


def _doc_id(number):
    return "sfs-" + number.lower().replace(":", "-")


def verify(number, entry, corpus, cache, extract):
    path = writer.existing_path(_doc_id(number), corpus)
    if path is None:
        return Result(number, "no_corpus_document")
    pdfs = [_cache_path(cache, number, f["url"]) for f in entry.get("files", [])]
    if not pdfs or not all(p.exists() for p in pdfs):
        return Result(number, "pdf_not_cached")
    meta, body = frontmatter.load(path.read_text(encoding="utf-8"))
    if PRINT_ONLY_NOTE in body:
        return Result(number, "print_only")
    try:
        printed = [w for p in pdfs for w in pdf_words(extract(p))]
    except NoText as gap:
        return Result(number, "no_pdf_text", error=str(gap))
    except (pdftext.PdfTextError, OSError, ValueError) as error:
        return Result(number, "extract_failed", error=f"{type(error).__name__}: {error}")
    words = corpus_words(body)
    coverage, first = compare(words, printed)
    if meta.get("repealed"):
        status = "repealed"
    elif meta.get("amendments") or meta.get("amended_by"):
        status = "amended"
    elif coverage >= THRESHOLD:
        status = "match"
    else:
        status = "differs"
    return Result(
        number, status, coverage, len(words), len(printed),
        first if status == "differs" else None,
    )


def parse_args(argv):
    parser = argparse.ArgumentParser(prog="collect.py sfsverify")
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST)
    parser.add_argument("--cache", default=DEFAULT_CACHE, help="folder holding the PDF bytes")
    parser.add_argument("--corpus", default="corpus")
    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument("--number", action="append", metavar="YYYY:N", help="only these (repeatable)")
    return parser.parse_args(argv)


def _default_extract(path):
    result = pdftext.extract(Path(path).read_bytes())
    if not result.usable:
        raise NoText(result.gap)
    return result.text


def run(args, extract=None):
    extract = extract or _default_extract
    entries = load_manifest(args.manifest)
    numbers = sorted(args.number or entries, key=number_key)
    results = [verify(n, entries[n], args.corpus, args.cache, extract) for n in numbers if n in entries]
    summary = {}
    for result in results:
        summary[result.status] = summary.get(result.status, 0) + 1
    _save_state(args.out, {
        "version": REPORT_VERSION,
        "threshold": THRESHOLD,
        "summary": summary,
        "entries": [r.entry() for r in results],
    })
    return summary


def main(argv, extract=None):
    args = parse_args(argv)
    try:
        summary = run(args, extract)
    except StateError as error:
        print(f"error: {error}", file=sys.stderr, flush=True)
        return 1
    print("done: " + ", ".join(f"{v} {k}" for k, v in sorted(summary.items())), flush=True)
    return 0
