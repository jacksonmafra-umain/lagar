"""Per-series progress against targets: PROGRESS.md and progress.svg."""

import argparse
import json
import re
from pathlib import Path
from xml.sax.saxutils import escape

from . import frontmatter, schema
from .vocabulary import TYPES

DEFAULT_TARGETS = "collector/data/targets.json"
DEFAULT_INTEGRITY = "collector/data/pending-integrity.json"
BACKGROUND = "#f8f9fc"
LABEL_X, BAR_X, BAR_W = 16, 240, 260
LABEL_CHAR_PX = 7.5  # estimated average glyph width at 13px
SFS_TYPES = ("act", "ordinance", "other_statute")
_TYPE_NAMES = {"act": "acts", "ordinance": "ordinances", "other_statute": "other statutes"}
# API layer id -> DESIGN.md layer key (docs/api.md, "Display levels").
_DESIGN_KEYS = {"case_law": "case-law", "sfs": "sfs-act"}
_COLOR_LINE = re.compile(
    r"^  ([a-z-]+):\s*\{\s*base:\s*'(#[0-9a-fA-F]{6})',\s*text:\s*'(#[0-9a-fA-F]{6})',\s*dark:\s*'(#[0-9a-fA-F]{6})'\s*\}\s*$"
)
DISCLAIMER = (
    "Volume does not prove completeness: a series at 100% of its target only means "
    "every counted document is present, and a high count says nothing about gaps in "
    "coverage, missing amendments or text quality. See [COVERAGE.md](COVERAGE.md)."
)


def load_colors(design_path):
    """Read the `layers:` block of DESIGN.md frontmatter into {key: {base, text, dark}}."""
    colors, inside = {}, False
    for line in Path(design_path).read_text(encoding="utf-8").splitlines():
        if line == "layers:":
            inside = True
            continue
        if inside:
            match = _COLOR_LINE.match(line)
            if not match:
                break
            colors[match.group(1)] = dict(zip(("base", "text", "dark"), match.groups()[1:]))
    return colors


def design_key(layer):
    return _DESIGN_KEYS.get(layer, layer)


def count_types(corpus):
    """Return {type: count} over documents that load and pass schema validation."""
    counts = {}
    for path in sorted(Path(corpus).rglob("*.md")):
        try:
            meta, _ = frontmatter.load(path.read_text(encoding="utf-8"))
        except (ValueError, UnicodeDecodeError):
            continue
        if schema.validate(meta):
            continue
        counts[meta["type"]] = counts.get(meta["type"], 0) + 1
    return counts


def build_rows(targets, type_counts):
    rows = []
    for entry in targets:
        layer, type_ = entry["layer"], entry["type"]
        breakdown = None
        if type_ is not None:
            collected = type_counts.get(type_, 0)
        elif layer == "sfs":
            breakdown = {t: type_counts.get(t, 0) for t in SFS_TYPES}
            collected = sum(breakdown.values())
        else:
            collected = sum(n for t, n in type_counts.items() if TYPES.get(t) == layer)
        target = entry["target"]
        percent = round(min(collected, target) / target * 100, 1) if target else None
        rows.append({**entry, "collected": collected, "percent": percent, "breakdown": breakdown})
    return rows


def _percent(row):
    return "-" if row["percent"] is None else f"{row['percent']:.1f}%"


def _target(row):
    return "unknown" if row["target"] is None else str(row["target"])


def render_markdown(rows, integrity):
    lines = [
        "# Progress",
        "",
        DISCLAIMER,
        "",
        "![Progress per series](progress.svg)",
        "",
        "| layer | series | collected | target | kind | % |",
        "| --- | --- | ---: | ---: | --- | ---: |",
    ]
    for row in rows:
        lines.append(
            f"| {row['layer']} | {row['label']} | {row['collected']} | {_target(row)} | {row['kind']} | {_percent(row)} |"
        )
    lines += ["", "Progress is capped at the target; a series without a known target has no percentage."]
    for row in rows:
        if row["breakdown"]:
            parts = ", ".join(f"{row['breakdown'][t]} {_TYPE_NAMES[t]}" for t in SFS_TYPES)
            lines += ["", f"{row['label']} breakdown: {parts}."]
    sources = [r for r in rows if r["source"]]
    if sources:
        lines += ["", "Targets:"]
        lines += [f"- {r['label']}: {r['kind']}, {r['source']}, as of {r['as_of']}" for r in sources]
    if integrity:
        refs = integrity["cross_references"]
        unknown = sum(s["unknown"] for s in refs.values())
        total = sum(s["total"] for s in refs.values())
        lines += [
            "",
            "## Integrity",
            "",
            f"Audit of {integrity['documents']} documents ({integrity['generated_at']}):",
            "",
            f"- schema errors: {len(integrity['schema_errors'])}",
            f"- duplicate ids: {len(integrity['duplicate_ids'])}",
            f"- path mismatches: {len(integrity['path_mismatches'])}",
            f"- text-quality flags: {len(integrity['text_quality'])}",
            f"- cross-references not in the corpus: {unknown} of {total} (informational, the corpus is partial)",
        ]
    return "\n".join(lines) + "\n"


def render_svg(rows, colors):
    width, left, bar_w, row_h, top = 720, LABEL_X, BAR_W, 36, 44
    bar_x = BAR_X
    height = top + row_h * len(rows) + 12
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="Corpus progress per series">',
        f'<rect width="{width}" height="{height}" fill="{BACKGROUND}"/>',
        '<g font-family="Inter, system-ui, sans-serif" font-size="13">',
    ]
    out.append(
        f'<text x="{left}" y="26" font-size="16" font-weight="600" fill="#191c1e">Corpus progress per series</text>'
    )
    for i, row in enumerate(rows):
        c = colors[design_key(row["layer"])]
        y = top + i * row_h
        fill_w = round(bar_w * (row["percent"] or 0) / 100)
        label = escape(row["label"])
        out.append(f'<text x="{left}" y="{y + 15}" fill="{c["text"]}">{label}</text>')
        out.append(f'<rect x="{bar_x}" y="{y + 4}" width="{bar_w}" height="16" rx="8" fill="{c["base"]}" fill-opacity="0.18"/>')
        if fill_w:
            out.append(f'<rect x="{bar_x}" y="{y + 4}" width="{fill_w}" height="16" rx="8" fill="{c["base"]}"/>')
        out.append(
            f'<text x="{width - left}" y="{y + 15}" text-anchor="end" fill="{c["text"]}">'
            f'{row["collected"]} / {escape(_target(row))} ({_percent(row)})</text>'
        )
    out += ["</g>", "</svg>"]
    return "\n".join(out) + "\n"


def main(argv):
    parser = argparse.ArgumentParser(prog="plan.py", description="Write PROGRESS.md and progress.svg.")
    parser.add_argument("--corpus", default="corpus")
    parser.add_argument("--targets", default=DEFAULT_TARGETS)
    parser.add_argument("--integrity", default=DEFAULT_INTEGRITY)
    parser.add_argument("--design", default="DESIGN.md")
    parser.add_argument("--out-dir", default=".")
    args = parser.parse_args(argv)
    targets = json.loads(Path(args.targets).read_text(encoding="utf-8"))
    integrity_path = Path(args.integrity)
    integrity = json.loads(integrity_path.read_text(encoding="utf-8")) if integrity_path.exists() else None
    rows = build_rows(targets, count_types(args.corpus))
    out = Path(args.out_dir)
    (out / "PROGRESS.md").write_text(render_markdown(rows, integrity), encoding="utf-8")
    (out / "progress.svg").write_text(render_svg(rows, load_colors(args.design)), encoding="utf-8")
    for row in rows:
        print(f"{row['label']}: {row['collected']} / {_target(row)} ({_percent(row)})")
    return 0
