"""Corpus audit: schema, duplicates, paths, text quality and cross-references."""

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from . import frontmatter, schema, writer
from .riksdagen import PRINT_ONLY_NOTE

MIN_BODY_CHARS = 200
SAMPLE_SIZE = 10
DEFAULT_OUT = "collector/data/pending-integrity.json"
_REFERENCE_FIELDS = ("amended_by", "amended_through", "reprinted_by")


def _rel(path, root):
    return Path(path).relative_to(root).as_posix()


def _text_flags(body):
    flags = []
    stripped = body.strip()
    if not stripped:
        flags.append("empty_body")
        return flags
    if PRINT_ONLY_NOTE in stripped:
        flags.append("print_only")
    if "�" in body:
        flags.append("replacement_character")
    if len(stripped) < MIN_BODY_CHARS:
        flags.append("short_body")
    return flags


def _references(meta):
    refs = {}
    for field in _REFERENCE_FIELDS:
        value = meta.get(field)
        if isinstance(value, str):
            refs[field] = [value]
        elif isinstance(value, list):
            refs[field] = [v for v in value if isinstance(v, str)]
        else:
            refs[field] = []
    return refs


def audit(corpus, generated_at=None, fsck=None):
    """Return the audit report for `corpus`; `fsck` is an optional callable returning an exit status."""
    root = Path(corpus)
    files = sorted(root.rglob("*.md"))
    schema_errors, path_mismatches, text_quality = [], [], []
    ids = {}
    numbers = set()
    parsed = []
    for path in files:
        rel = _rel(path, root)
        try:
            meta, body = frontmatter.load(path.read_text(encoding="utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            schema_errors.append({"path": rel, "errors": [f"unreadable: {exc}"]})
            continue
        errors = schema.validate(meta)
        if errors:
            schema_errors.append({"path": rel, "errors": errors})
            continue
        ids.setdefault(meta["id"], []).append(rel)
        numbers.add(meta["number"])
        if meta.get("celex"):
            numbers.add(meta["celex"])  # EU references are CELEX numbers
        expected = _rel(writer.path_for(meta, root), root)
        if expected != rel:
            path_mismatches.append({"path": rel, "expected": expected})
        for flag in _text_flags(body):
            text_quality.append({"id": meta["id"], "path": rel, "flag": flag})
        parsed.append(meta)

    cross = {field: {"total": 0, "unknown": 0, "sample": set()} for field in _REFERENCE_FIELDS}
    for meta in parsed:
        for field, values in _references(meta).items():
            for value in values:
                cross[field]["total"] += 1
                if value not in numbers:
                    cross[field]["unknown"] += 1
                    cross[field]["sample"].add(value)
    for stats in cross.values():
        stats["sample"] = sorted(stats["sample"])[:SAMPLE_SIZE]

    return {
        "generated_at": generated_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "documents": len(files),
        "schema_errors": sorted(schema_errors, key=lambda e: e["path"]),
        "duplicate_ids": [
            {"id": i, "paths": sorted(p)} for i, p in sorted(ids.items()) if len(p) > 1
        ],
        "path_mismatches": sorted(path_mismatches, key=lambda e: e["path"]),
        "text_quality": sorted(text_quality, key=lambda e: (e["id"], e["flag"], e["path"])),
        "cross_references": cross,
        "fsck": {"exit_status": fsck()} if fsck else None,
    }


def exit_code(report):
    failed = report["schema_errors"] or report["duplicate_ids"] or report["path_mismatches"]
    return 1 if failed else 0


def render(report):
    return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def summary(report):
    refs = report["cross_references"]
    unknown = sum(s["unknown"] for s in refs.values())
    line = (
        f"{report['documents']} documents: {len(report['schema_errors'])} schema errors, "
        f"{len(report['duplicate_ids'])} duplicate ids, {len(report['path_mismatches'])} path mismatches, "
        f"{len(report['text_quality'])} text-quality flags, {unknown} unresolved cross-references"
    )
    if report["fsck"] is not None:
        line += f", fsck exit {report['fsck']['exit_status']}"
    return line


def _run_fsck():
    return subprocess.run(["git", "fsck", "--strict"], capture_output=True, check=False).returncode


def main(argv):
    parser = argparse.ArgumentParser(prog="audit.py", description="Audit the corpus.")
    parser.add_argument("--corpus", default="corpus")
    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument("--fsck", action="store_true", help="also run git fsck --strict")
    parser.add_argument("--generated-at", default=None, help="timestamp for the report (default: now)")
    args = parser.parse_args(argv)
    report = audit(args.corpus, generated_at=args.generated_at, fsck=_run_fsck if args.fsck else None)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(report), encoding="utf-8")
    print(summary(report))
    return exit_code(report)
