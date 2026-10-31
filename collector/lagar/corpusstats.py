"""Corpus statistics: what the corpus holds, where it comes from and how its text was obtained.

Reads the corpus, the committed source manifests and the generated audit report,
and writes `STATISTICS.md` (a dated, documentary summary) and
`collector/data/statistics.json` (the same numbers for tools). Nothing is
fetched: every number comes from files in the repository.

- Documents: per layer and type, with the number of sections (`N §` opening a
  paragraph) and words in the bodies.
- Issuers: the distinct ministries, agencies, county boards, kommuner, courts and
  EU institutions behind the documents; counties and kommuner covered.
- Origins: the host of each document's `source`.
- Text: how each document's text was obtained (web page or API, a PDF's text
  layer, OCR) or why it has none, and per issuer how many documents rely on
  PDFs and how many needed or still need OCR.
- Quality: the audit report, the SFS text checked against the official PDFs
  (`sources/sfs-pdf-verification.json`) and, when present, the OCR accuracy
  measured on PDFs that also have a text layer (`sources/ocr-calibration.json`).
"""

import argparse
import json
import re
import urllib.parse
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from . import frontmatter
from .riksdagen import PRINT_ONLY_NOTE
from .vocabulary import LAYERS, TYPES

DEFAULT_MD = "STATISTICS.md"
DEFAULT_JSON = "collector/data/statistics.json"

# How a document's text was obtained.
WEB = "web"  # an HTML page or an API
PDF = "pdf"  # a PDF's text layer
OCR = "ocr"  # optical character recognition of a scanned PDF
NONE = "none"  # metadata and links only
ORIGINS = (WEB, PDF, OCR, NONE)
ORIGIN_LABELS = {WEB: "web page or API", PDF: "PDF text layer", OCR: "OCR of a scan", NONE: "no text (metadata and link)"}

# Body phrases that say a document has no text of its own.
_NO_TEXT = (
    PRINT_ONLY_NOTE,
    "saknar textlager",
    "inskannad pdf utan textlager",
    "kan inte läsas maskinellt",
    "textlager går inte att läsa",
    "publicerar texten endast som pdf",
    "Författningen publiceras bara som pdf.",
    "Dokumentet har inte hämtats",
)
_PDF_TEXT = ("Texten är hämtad ur pdf", "Texten är hämtad ur kommunens pdf")
_WEB_TEXT = ("Texten är hämtad från kommunens webbsida",)
_SECTION = re.compile(r"^(?:\*\*)?\d+\s?[a-z]?\s?§", re.M)
_WORD = re.compile(r"\w+")
_COUNTY_TEXT = {"extracted": PDF, "ocr": OCR}
_MUNICIPAL_TEXT = {"pdf": PDF, "ocr": OCR}
_SO_TEXT = {"extracted": PDF, "ocr": OCR}
# Manifest `text` values that are a scan or an unreadable text layer: documents that need OCR.
_OCR_GAPS = ("no text layer", "text layer is not readable", "OCR confidence too low", "no text found by OCR")


def _load_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _host(url):
    return urllib.parse.urlsplit(url or "").netloc.lower().removeprefix("www.") or "(none)"


def _issuer(meta):
    return meta.get("issuer") or meta.get("ministry") or meta.get("court") or "(not stated)"


def _manifest_texts(root):
    """Per document key, the manifest `text` values of its files: {("region", number): [...], ...}."""
    texts = {}
    county = _load_json(root / "sources/county-pdf-manifest.json", {}).get("entries", [])
    for entry in county:
        texts[("region", entry["number"])] = [f.get("text") for f in entry.get("files", [])]
    municipal = _load_json(root / "sources/municipal-manifest.json", {}).get("documents", [])
    for doc in municipal:
        texts[("municipality", doc["id"])] = [doc.get("text")]
    so = _load_json(root / "sources/so-pdf-manifest.json", {}).get("entries", [])
    for entry in so:
        texts[("treaty", entry["number"])] = [f.get("text") for f in entry.get("pdfs", [])]
    return texts


def text_origin(meta, body, manifest_texts=None):
    """How the document's text was obtained: WEB, PDF, OCR or NONE."""
    if meta.get("text_source") == "ocr":
        return OCR
    if any(phrase in body for phrase in _NO_TEXT) or not body.strip():
        return NONE
    if any(phrase in body for phrase in _PDF_TEXT):
        return PDF
    if any(phrase in body for phrase in _WEB_TEXT):
        return WEB
    mapping = {"region": _COUNTY_TEXT, "municipality": _MUNICIPAL_TEXT}.get(meta.get("layer"))
    if meta.get("type") == "treaty":
        mapping = _SO_TEXT
    if mapping is not None and manifest_texts:
        found = {mapping.get(t) for t in manifest_texts if t}
        if OCR in found:
            return OCR
        if PDF in found:
            return PDF
        if meta.get("type") == "treaty" or meta.get("layer") == "municipality":
            return NONE
    if meta.get("layer") == "agency" and "## Författningstext" not in body and "§" not in body:
        return NONE
    return WEB


def _needs_ocr(texts):
    return any(t and t.startswith(_OCR_GAPS) for t in texts)


def collect(root, corpus="corpus"):
    root = Path(root)
    manifests = _manifest_texts(root)
    agency_pdfs = {e["number"] for e in _load_json(root / "sources/agency-pdf-manifest.json", {}).get("entries", [])}
    types = Counter()
    sections, words = Counter(), Counter()
    origins = defaultdict(Counter)
    hosts = defaultdict(Counter)
    issuers = defaultdict(set)
    pdf_issuers = defaultdict(Counter)
    counties, kommuner = set(), set()
    for path in sorted((root / corpus).rglob("*.md")):
        try:
            meta, body = frontmatter.load(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        layer, type_ = meta.get("layer"), meta.get("type")
        types[type_] += 1
        sections[type_] += len(_SECTION.findall(body))
        words[type_] += len(_WORD.findall(body))
        key = ("treaty", meta.get("number")) if type_ == "treaty" else (
            ("municipality", meta.get("id")) if layer == "municipality" else (layer, meta.get("number")))
        texts = manifests.get(key)
        origin = text_origin(meta, body, texts)
        origins[layer][origin] += 1
        hosts[layer][_host(meta.get("source"))] += 1
        issuer = _issuer(meta)
        issuers[layer].add(issuer)
        if meta.get("region_code"):
            counties.add(meta["region_code"])
        if meta.get("municipality_code"):
            kommuner.add(meta["municipality_code"])
        uses_pdf = (origin in (PDF, OCR) or str(meta.get("source", "")).lower().endswith(".pdf")
                    or meta.get("number") in agency_pdfs or bool(texts))
        if uses_pdf:
            row = pdf_issuers[(layer, issuer)]
            row["documents"] += 1
            row[origin] += 1
            if origin == OCR or (origin == NONE and (texts is None or _needs_ocr(texts))
                                 and ("inskannad" in body or "textlager" in body or _needs_ocr(texts or []))):
                row["scanned"] += 1
    return {
        "types": types, "sections": sections, "words": words, "origins": origins, "hosts": hosts,
        "issuers": issuers, "pdf_issuers": pdf_issuers, "counties": counties, "kommuner": kommuner,
        "audit": _load_json(root / "collector/data/pending-integrity.json"),
        "verification": _load_json(root / "sources/sfs-pdf-verification.json"),
        "calibration": _load_json(root / "sources/ocr-calibration.json"),
        "county_total": len(_load_json(root / "collector/data/counties.json", {}).get("counties", {})),
        "kommun_total": len(_load_json(root / "collector/data/kommuner.json", {}).get("websites", {})),
    }


def summarise(data, generated_at):
    """The JSON report: plain dicts and numbers."""
    types, origins = data["types"], data["origins"]
    layers = {}
    for layer in LAYERS:
        layer_types = [t for t, owner in TYPES.items() if owner == layer and types[t]]
        if not layer_types:
            continue
        layers[layer] = {
            "documents": sum(types[t] for t in layer_types),
            "types": {t: {"documents": types[t], "sections": data["sections"][t], "words": data["words"][t]}
                      for t in layer_types},
            "issuers": len(data["issuers"][layer]),
            "text": {o: origins[layer][o] for o in ORIGINS},
            "hosts": dict(data["hosts"][layer].most_common()),
        }
    pdf = defaultdict(lambda: {"issuers": 0, "documents": 0, "issuers_with_scans": 0, "scanned": 0,
                               "ocr": 0, "still_without_text": 0})
    for (layer, _issuer_name), row in data["pdf_issuers"].items():
        s = pdf[layer]
        s["issuers"] += 1
        s["documents"] += row["documents"]
        s["scanned"] += row["scanned"]
        s["ocr"] += row[OCR]
        s["still_without_text"] += row["scanned"] - row[OCR]
        s["issuers_with_scans"] += 1 if row["scanned"] else 0
    audit = data["audit"] or {}
    verification = data["verification"] or {}
    statuses = Counter(e.get("status") for e in verification.get("entries", []))
    checked = statuses["match"] + statuses["differs"]
    quality = {
        "audit": {
            "documents": audit.get("documents"),
            "schema_errors": len(audit.get("schema_errors", [])),
            "duplicate_ids": len(audit.get("duplicate_ids", [])),
            "path_mismatches": len(audit.get("path_mismatches", [])),
            "text_quality_flags": dict(Counter(f["flag"] for f in audit.get("text_quality", []))),
            "unresolved_references": sum(r.get("unknown", 0) for r in (audit.get("cross_references") or {}).values()),
            "references": sum(r.get("total", 0) for r in (audit.get("cross_references") or {}).values()),
        } if audit else None,
        "sfs_pdf_verification": {
            "statuses": dict(statuses),
            "checked": checked,
            "match_rate": round(statuses["match"] / checked, 4) if checked else None,
            "threshold": verification.get("threshold"),
        } if verification else None,
        "ocr_calibration": data["calibration"],
    }
    total = sum(types.values())
    return {
        "generated_at": generated_at,
        "documents": total,
        "layers": layers,
        "text": {o: sum(row[o] for row in origins.values()) for o in ORIGINS},
        "issuers": {layer: len(names) for layer, names in data["issuers"].items()},
        "geography": {"counties": len(data["counties"]), "county_total": data["county_total"],
                      "kommuner": len(data["kommuner"]), "kommun_total": data["kommun_total"]},
        "pdf": dict(pdf),
        "pdf_issuers": {f"{layer}: {name}": dict(row) for (layer, name), row in sorted(data["pdf_issuers"].items())
                        if row["scanned"]},
        "quality": quality,
    }


def _n(value):
    return f"{value:,}" if isinstance(value, int) else ("–" if value is None else str(value))


def _pct(part, whole):
    return f"{100 * part / whole:.1f} %" if whole else "–"


def render(report):
    """STATISTICS.md from the JSON report."""
    lines = ["# Corpus statistics", "",
             f"Generated {report['generated_at']} by `collector/stats.py` from the corpus, the source "
             "manifests and the audit report. Every number is computed from files in this repository.", ""]
    total = report["documents"]
    lines += ["## Documents", "",
              f"The corpus holds {_n(total)} documents in {len(report['layers'])} layers.", "",
              "| layer | type | documents | sections (§) | words |", "| --- | --- | ---: | ---: | ---: |"]
    for layer, row in report["layers"].items():
        for type_, t in row["types"].items():
            lines.append(f"| {layer} | {type_} | {_n(t['documents'])} | {_n(t['sections'])} | {_n(t['words'])} |")
    lines += ["", "Sections count paragraphs that open with a section number (`1 §`, `2 a §`); "
              "case law and EU documents have none.", ""]
    geo = report["geography"]
    lines += ["## Issuers and places", "",
              "| layer | distinct issuers |", "| --- | ---: |"]
    lines += [f"| {layer} | {_n(n)} |" for layer, n in report["issuers"].items()]
    lines += ["", f"County regulations cover {geo['counties']} of {geo['county_total']} counties; "
              f"municipal regulations cover {geo['kommuner']} of {geo['kommun_total']} kommuner.", ""]
    lines += ["## Origins", "", "Documents per host of their `source`, per layer (the ten largest).", ""]
    for layer, row in report["layers"].items():
        lines += [f"### {layer}", "", "| host | documents |", "| --- | ---: |"]
        lines += [f"| {host} | {_n(n)} |" for host, n in list(row["hosts"].items())[:10]]
        if len(row["hosts"]) > 10:
            lines.append(f"| {len(row['hosts']) - 10} other hosts | "
                         f"{_n(sum(list(row['hosts'].values())[10:]))} |")
        lines.append("")
    text = report["text"]
    lines += ["## How the text was obtained", "",
              "| layer | " + " | ".join(ORIGIN_LABELS[o] for o in ORIGINS) + " |",
              "| --- |" + " ---: |" * len(ORIGINS)]
    for layer, row in report["layers"].items():
        lines.append(f"| {layer} | " + " | ".join(_n(row["text"][o]) for o in ORIGINS) + " |")
    lines.append("| **all** | " + " | ".join(f"**{_n(text[o])}** ({_pct(text[o], total)})" for o in ORIGINS) + " |")
    lines += ["", "OCR text is marked `text_source: ocr` in the frontmatter and may contain misread characters; "
              "the PDF stays the authoritative source.", ""]
    lines += ["## PDFs and OCR", "",
              "Issuers whose documents rely on a PDF (the text comes from it, or only a PDF is linked), and "
              "how many of those PDFs are scans without a readable text layer.", "",
              "| layer | issuers using PDF | documents | issuers with scans | scanned | read by OCR "
              "| still without text |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for layer, row in report["pdf"].items():
        lines.append(f"| {layer} | {_n(row['issuers'])} | {_n(row['documents'])} | {_n(row['issuers_with_scans'])} "
                     f"| {_n(row['scanned'])} | {_n(row['ocr'])} | {_n(row['still_without_text'])} |")
    lines += ["", "### Issuers with scanned PDFs", "", "| issuer | documents | scanned | read by OCR |",
              "| --- | ---: | ---: | ---: |"]
    for name, row in report["pdf_issuers"].items():
        lines.append(f"| {name} | {_n(row['documents'])} | {_n(row['scanned'])} | {_n(row.get(OCR, 0))} |")
    quality = report["quality"]
    lines += ["", "## Quality and accuracy", ""]
    audit = quality["audit"]
    if audit:
        flags = ", ".join(f"{k} {v}" for k, v in sorted(audit["text_quality_flags"].items())) or "none"
        lines += ["### Corpus audit", "",
                  f"- Documents checked: {_n(audit['documents'])}",
                  f"- Schema errors: {_n(audit['schema_errors'])}; duplicate ids: {_n(audit['duplicate_ids'])}; "
                  f"path mismatches: {_n(audit['path_mismatches'])}",
                  f"- Text-quality flags: {flags}",
                  f"- Amendment references (`amended_by`, `amended_through`, `reprinted_by`) to documents not in "
                  f"the corpus: {_n(audit['unresolved_references'])} of {_n(audit['references'])} (mostly older "
                  "amending acts, which are not collected as documents of their own)", ""]
    verification = quality["sfs_pdf_verification"]
    if verification:
        statuses = ", ".join(f"{k} {_n(v)}" for k, v in sorted(verification["statuses"].items()))
        rate = verification["match_rate"]
        lines += ["### SFS text against the official PDF", "",
                  "Riksdagen's text of each statute is compared word by word with the printed SFS PDF "
                  "(`sources/sfs-pdf-verification.json`).", "",
                  f"- Statuses: {statuses}",
                  f"- Of {_n(verification['checked'])} statutes printed in their current wording, "
                  f"{'–' if rate is None else f'{100 * rate:.1f} %'} match the print "
                  f"(word coverage at least {verification['threshold']}).", ""]
    calibration = quality["ocr_calibration"]
    lines += ["### OCR accuracy", ""]
    if calibration:
        lines += [f"Measured on {_n(calibration.get('pdfs'))} official PDFs that have a text layer, read a second "
                  f"time by OCR and compared with the text layer (`sources/ocr-calibration.json`, "
                  f"{calibration.get('generated_at', '')}). Pages rendered from a text layer are cleaner than "
                  "paper scans, so these numbers are an upper bound for the scanned PDFs read by OCR.", "",
                  "| measure | mean | median | lowest |", "| --- | ---: | ---: | ---: |"]
        for key, label in (("word_recall", "word recall (text-layer words OCR found)"),
                           ("word_precision", "word precision (OCR words in the text layer)"),
                           ("character_similarity", "character similarity")):
            row = calibration.get(key) or {}
            lines.append(f"| {label} | {_pct(row.get('mean', 0), 1)} | {_pct(row.get('median', 0), 1)} "
                         f"| {_pct(row.get('min', 0), 1)} |")
        lines.append("")
    else:
        lines += ["Not measured yet: run `python3 -I collector/ocr_calibration.py`.", ""]
    return "\n".join(lines) + "\n"


def main(argv):
    parser = argparse.ArgumentParser(prog="stats.py", description="Write corpus statistics.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--corpus", default="corpus")
    parser.add_argument("--markdown", default=DEFAULT_MD)
    parser.add_argument("--json", default=DEFAULT_JSON)
    parser.add_argument("--generated-at", help="timestamp to record (default: now, UTC)")
    args = parser.parse_args(argv)
    generated_at = args.generated_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    report = summarise(collect(args.root, args.corpus), generated_at)
    Path(args.json).write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    Path(args.markdown).write_text(render(report), encoding="utf-8")
    print(f"{report['documents']} documents; text: "
          + ", ".join(f"{o} {report['text'][o]}" for o in ORIGINS), flush=True)
    return 0
