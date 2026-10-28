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
# Fields added after the first release go at the end, so earlier keys keep their position.
ITEM_FIELDS = ("id", "title", "number", "type", "issued", "repealed", "in_force", "amended_through", "ministry")
# Document meta keys, in the schema's order; optional frontmatter keys are served as null.
META_FIELDS = tuple(schema._load_schema()["properties"])


class BuildError(Exception):
    pass


_NUMBER_RE = re.compile(r"([A-Za-z]*)(\d{4}):\D*(\d*)(.*)")
# Series-prefixed numbers: agency (AFS 2023:1) and county (01FS 2024:3) regulations.
_SERIES_RE = re.compile(r"(\S+) (\d{4}):(\d+)")
# Case law: NJA 2019 s. 2, HFD 2020 ref. 5, HFD 2020 not. 3, AD 2020 nr 45, MIG 2026:10.
_CASE_RE = re.compile(r"(\S+) (\d{4})(:| s\. | ref\. | not\. | nr | N )(\d+)")
# EU acts: (EU) 2016/679 is year/number; with "nr", (EG) nr 1907/2006 is number/year;
# 95/46/EG and 2004/18/EG are year/number/institution. Two-digit years are 19xx.
_EU_YEAR_FIRST_RE = re.compile(r"\([^)]+\) (\d{4})/(\d+)")
_EU_NR_RE = re.compile(r"\([^)]+\) nr (\d+)/(\d{2}|\d{4})")
_EU_SLASH_RE = re.compile(r"(\d{2}|\d{4})/(\d+)/\D.*")
_YEAR_RE = re.compile(r"(?<!\d)((?:1[6-9]|20)\d{2})(?!\d)\D*(\d*)")


def _year(text):
    return int(text) + 1900 if len(text) == 2 else int(text)


def _eu_key(number):
    m = _EU_YEAR_FIRST_RE.fullmatch(number)
    if m:
        return (int(m.group(1)), int(m.group(2)))
    m = _EU_NR_RE.fullmatch(number)
    if m:
        return (_year(m.group(2)), int(m.group(1)))
    m = _EU_SLASH_RE.fullmatch(number)
    if m:
        return (_year(m.group(1)), int(m.group(2)))
    return None


def _number_key(number, type_="act"):
    """(year, ordinal, is_plain, rest) for sorting `number` of a document of `type_`.

    SFS: a series prefix (N, RFS) and old-print page suffixes only break ties.
    Agency, county and case law: the series or report name only breaks ties.
    EU: year and number of the act, whatever the citation form.
    Municipal: the first year in the number and the digits after it, else (0, 0).
    """
    if type_ in ("agency_regulation", "county_regulation"):
        m = _SERIES_RE.fullmatch(number)
        if m:
            return (int(m.group(2)), int(m.group(3)), True, m.group(1))
    elif type_ in ("case_report", "case_notice"):
        m = _CASE_RE.fullmatch(number)
        if m:
            return (int(m.group(2)), int(m.group(4)), True, m.group(1) + m.group(3))
    elif type_ in ("eu_regulation", "eu_directive", "eu_decision"):
        key = _eu_key(number)
        if key:
            return (*key, True, number)
    elif type_ == "municipal_regulation":
        m = _YEAR_RE.search(number)
        return (int(m.group(1)), int(m.group(2) or 0), True, number) if m else (0, 0, True, number)
    else:
        m = _NUMBER_RE.fullmatch(number)
        if m:
            prefix, year, ordinal, rest = m.groups()
            return (int(year), int(ordinal or 0), not prefix, rest)
    raise BuildError(f"unsortable number: {number!r}")


def _sorted(items):
    """issued descending (null last), then number descending by (year, ordinal)."""
    return sorted(
        items,
        key=lambda i: (bool(i["issued"]), i["issued"] or "", _number_key(i["number"], i["type"]), i["id"]),
        reverse=True,
    )


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


def doc_meta(meta):
    """Frontmatter as served: every schema key in schema order, null when the file leaves it out.

    `amendments` is null until the register was collected; the other layers' fields
    (`issuer`, `court`, `ecli`, `celex`, `region_code`, `municipality_code`) are null
    where they do not apply.
    """
    return {key: meta.get(key) for key in META_FIELDS}


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
        _write(out, f"docs/{meta['id']}.json", {"meta": doc_meta(meta), "body": body}, written)
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
