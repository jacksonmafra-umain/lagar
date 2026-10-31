"""OCR accuracy, measured on PDFs that have a text layer.

A sample of official PDFs whose text `pdftotext` reads is downloaded and read a
second time by OCR (`lagar.ocr`), and the two texts are compared:

- word recall: the share of the text layer's words that OCR also found;
- word precision: the share of OCR's words that are in the text layer;
- character similarity: `difflib`'s ratio between the two texts, letters and
  digits only, lower case.

Words are compared as multisets, so reading order does not matter. The sample
is fixed by the SHA-256 of each file (the lowest hashes per source) and limited
to short files. Pages rendered from a text layer are cleaner than paper scans,
so the numbers are an upper bound for the scanned PDFs OCR actually reads.
The result goes to `sources/ocr-calibration.json`; PDF bytes are not kept.
"""

import argparse
import difflib
import http.client
import json
import re
import statistics
import sys
import urllib.error
import urllib.parse
import urllib.robotparser
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from . import ocr, pdftext
from .http import PoliteClient

USER_AGENT = "lagar-collector/0.1 (+https://github.com/jacksonmafra-umain/lagar)"
DEFAULT_OUT = "sources/ocr-calibration.json"
NETWORK_ERRORS = (urllib.error.URLError, TimeoutError, ConnectionError, http.client.HTTPException)
MAX_PAGES = 4
MAX_CHARS = 20000  # characters compared for the similarity ratio
_WORD = re.compile(r"\w+|§")  # the section sign counts: OCR often misreads it


def candidates(root, per_source):
    """(source, url, sha256) of text-layer PDFs from the manifests, the lowest hashes first per source."""
    root = Path(root)
    found = {"agency": [], "region": [], "treaty": []}
    agency = json.loads((root / "sources/agency-pdf-manifest.json").read_text(encoding="utf-8"))
    for entry in agency["entries"]:
        first = (entry.get("files") or [{}])[0]
        if first.get("sha256") and not first.get("note"):
            found["agency"].append((first["url"], first["sha256"]))
    county = json.loads((root / "sources/county-pdf-manifest.json").read_text(encoding="utf-8"))
    for entry in county["entries"]:
        for f in entry.get("files", []):
            if f.get("text") == "extracted" and f.get("sha256"):
                found["region"].append((f["url"], f["sha256"]))
    so = json.loads((root / "sources/so-pdf-manifest.json").read_text(encoding="utf-8"))
    for entry in so["entries"]:
        for f in entry.get("pdfs", []):
            if f.get("text") == "extracted" and f.get("pages", 99) <= MAX_PAGES:
                found["treaty"].append((f["url"], f["sha256"]))
    out = []
    for source, files in found.items():
        for url, sha in sorted(set(files), key=lambda f: f[1])[:per_source]:
            out.append((source, url, sha))
    return out


def words(text):
    return Counter(w.lower() for w in _WORD.findall(text))


def compare(layer_text, ocr_text):
    """(word recall, word precision, character similarity) of OCR text against the text layer."""
    reference, read = words(layer_text), words(ocr_text)
    common = sum((reference & read).values())
    recall = common / sum(reference.values()) if reference else 0.0
    precision = common / sum(read.values()) if read else 0.0
    a = "".join(c for c in layer_text.lower() if c.isalnum() or c == "§")[:MAX_CHARS]
    b = "".join(c for c in ocr_text.lower() if c.isalnum() or c == "§")[:MAX_CHARS]
    similarity = difflib.SequenceMatcher(None, a, b, autojunk=False).ratio() if a or b else 0.0
    return round(recall, 4), round(precision, 4), round(similarity, 4)


class _Robots:
    def __init__(self, client):
        self.client, self.parsers = client, {}

    def allows(self, url):
        parts = urllib.parse.urlsplit(url)
        host = f"{parts.scheme}://{parts.netloc}"
        if host not in self.parsers:
            parser = urllib.robotparser.RobotFileParser()
            try:
                parser.parse(self.client.get(host + "/robots.txt").decode("utf-8", "replace").splitlines())
            except NETWORK_ERRORS:
                parser.parse([])
            self.parsers[host] = parser
        return self.parsers[host].can_fetch(USER_AGENT, url)


def summary(results):
    def stat(key):
        values = [r[key] for r in results]
        return {"mean": round(statistics.fmean(values), 4), "median": round(statistics.median(values), 4),
                "min": min(values)} if values else None
    return {"word_recall": stat("word_recall"), "word_precision": stat("word_precision"),
            "character_similarity": stat("character_similarity")}


def run(client, files, log=print):
    robots = _Robots(client)
    results, skipped = [], Counter()
    for source, url, sha in files:
        if not robots.allows(url):
            skipped["robots.txt"] += 1
            continue
        try:
            data = client.get(url)
        except NETWORK_ERRORS:
            skipped["download failed"] += 1
            continue
        layer = pdftext.extract(data)
        if not layer.usable or layer.pages > MAX_PAGES:
            skipped["not a short text-layer PDF"] += 1
            continue
        try:
            read = ocr.extract(data)
        except ocr.OcrError:
            skipped["OCR failed"] += 1
            continue
        recall, precision, similarity = compare(layer.text, read.text)
        results.append({"source": source, "url": url, "sha256": sha, "pages": layer.pages,
                        "word_recall": recall, "word_precision": precision, "character_similarity": similarity})
        log(f"{source} {recall:.3f} {precision:.3f} {similarity:.3f} {url}")
    return results, skipped


def main(argv, client=None):
    parser = argparse.ArgumentParser(prog="ocr_calibration.py", description="Measure OCR accuracy.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--per-source", type=int, default=20, help="PDFs per source (agency, county, SÖ)")
    parser.add_argument("--rate", type=float, default=1.0)
    parser.add_argument("--out", default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    if not ocr.available():
        print("error: OCR needs pdftoppm and tesseract with the Swedish model", file=sys.stderr)
        return 1
    client = client or PoliteClient(USER_AGENT, min_interval=max(args.rate, 1.0))
    results, skipped = run(client, candidates(args.root, args.per_source))
    report = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "method": "text-layer PDFs read again by OCR (pdftoppm 300 dpi, tesseract -l swe); "
                  "words compared as multisets, characters with difflib",
        "pdfs": len(results),
        "skipped": dict(skipped),
        **summary(results),
        "by_source": {s: summary([r for r in results if r["source"] == s]) for s in sorted({r["source"] for r in results})},
        "results": results,
    }
    Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(results)} PDFs measured; skipped {dict(skipped)}")
    return 0
