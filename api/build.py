"""Generate the static JSON API (docs/api.md) from the corpus.

Usage: python3 -I api/build.py --corpus corpus --out build/api/v1 [--built-at <UTC>]
"""

import argparse
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "collector"))

from lagar import frontmatter, schema  # noqa: E402
from lagar.vocabulary import LAYERS, TYPES  # noqa: E402

API_VERSION = 1
PAGE_SIZE = 50
BUILT_AT_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
ITEM_FIELDS = ("id", "title", "number", "type", "issued", "repealed")


class BuildError(Exception):
    pass


def _number_key(number):
    """(year, ordinal, is_plain); the N-series letter only breaks ties (plain listed first)."""
    year, _, ordinal = number.partition(":")
    n_series = year[:1] in ("N", "n")
    try:
        return (int(year[1:] if n_series else year), int(ordinal), not n_series)
    except ValueError:
        raise BuildError(f"unsortable number: {number!r}")


def _sorted(items):
    """issued descending (null last), then number descending by (year, ordinal)."""
    items = sorted(items, key=lambda i: (_number_key(i["number"]), i["id"]), reverse=True)
    dated = sorted((i for i in items if i["issued"]), key=lambda i: i["issued"], reverse=True)
    return dated + [i for i in items if not i["issued"]]


def load_corpus(corpus):
    docs = []
    for path in sorted(Path(corpus).rglob("*.md")):
        try:
            meta, body = frontmatter.load(path.read_text(encoding="utf-8"))
        except (ValueError, OSError) as exc:
            raise BuildError(f"{path}: {exc}")
        errors = schema.validate(meta)
        if errors:
            raise BuildError("\n".join(f"{path}: {e}" for e in errors))
        docs.append((meta, body))
    ids = [m["id"] for m, _ in docs]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        raise BuildError(f"duplicate document ids: {', '.join(dupes)}")
    return docs


def _write(out, rel, data, written):
    path = out / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n"
    path.write_text(text, encoding="utf-8", newline="")
    written.append(rel)


def _pages(out, rel_dir, layer, type_, items, written):
    items = _sorted(items)
    count = max(1, -(-len(items) // PAGE_SIZE))
    for page in range(1, count + 1):
        chunk = items[(page - 1) * PAGE_SIZE : page * PAGE_SIZE]
        _write(out, f"{rel_dir}index-{page}.json", {
            "layer": layer, "type": type_, "page": page, "page_count": count,
            "total": len(items), "items": chunk,
        }, written)


def build(docs, out, built_at):
    out = Path(out)
    written = []
    items = [{k: meta[k] for k in ITEM_FIELDS} for meta, _ in docs]
    layers = []
    for layer in LAYERS:
        in_layer = [i for i in items if TYPES[i["type"]] == layer]
        series = []
        for type_, type_layer in TYPES.items():
            if type_layer != layer:
                continue
            of_type = [i for i in in_layer if i["type"] == type_]
            if of_type:
                series.append({"id": type_, "count": len(of_type)})
                _pages(out, f"{layer}/{type_}/", layer, type_, of_type, written)
        _pages(out, f"{layer}/", layer, None, in_layer, written)
        layers.append({"id": layer, "count": len(in_layer), "series": series})
    for meta, body in sorted(docs, key=lambda d: d[0]["id"]):
        _write(out, f"docs/{meta['id']}.json", {"meta": meta, "body": body}, written)
    _write(out, "index.json", {"api_version": API_VERSION, "built_at": built_at, "layers": layers}, written)
    return len(layers), len(written)


def _check_no_symlinks(out):
    """Reject --out when it or any parent is a symlink (checked before resolving).

    Root-owned links such as macOS /var -> /private/var are system layout, not
    something a typo can introduce, so they are tolerated.
    """
    path = Path(os.path.abspath(out))
    for candidate in (path, *path.parents):
        if candidate.is_symlink() and candidate.lstat().st_uid != 0:
            raise BuildError(f"--out must not be or sit under a symlink: {candidate}")


def _check_out(out, corpus):
    out, corpus = out.resolve(), corpus.resolve()
    if (
        out == corpus
        or out == REPO_ROOT
        or out == Path(out.anchor)
        or out in corpus.parents
        or out in REPO_ROOT.parents
        or corpus in out.parents
    ):
        raise BuildError(f"refusing to use {out} as the output directory")


def _check_built_at(value):
    try:
        if not BUILT_AT_RE.fullmatch(value):
            raise ValueError(value)
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        raise BuildError(f"--built-at must be a UTC timestamp like 2026-10-27T10:30:00Z, got {value!r}")


def main(argv):
    parser = argparse.ArgumentParser(description="Generate the static JSON API from the corpus.")
    parser.add_argument("--corpus", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--built-at", default=None)
    args = parser.parse_args(argv)
    built_at = args.built_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    corpus, out = Path(args.corpus), Path(args.out)
    try:
        _check_built_at(built_at)
        if not corpus.is_dir():
            raise BuildError(f"corpus directory not found: {corpus}")
        if out.is_symlink() or (out.exists() and not out.is_dir()):
            raise BuildError(f"--out must be a directory, not a file or symlink: {out}")
        _check_no_symlinks(out)
        _check_out(out, corpus)
        docs = load_corpus(corpus)  # fail before clearing anything
        if out.exists():
            if any(out.iterdir()) and not (out / "index.json").is_file():
                raise BuildError(f"refusing to clear {out}: it is not empty and has no index.json (not a previous build)")
            shutil.rmtree(out)
        layers, files = build(docs, out, built_at)
    except (BuildError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"built {len(docs)} documents, {layers} layers, {files} files -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
