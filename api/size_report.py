"""Size report for a built API (docs/api.md, "Size report").

The report sums the bytes of every file under --site (the API under --api, plus
the web app when it is there), by top-level folder, by layer and by search
group. It only reports: there is no size limit, since the API is built and
served per machine.

Usage: python3 -I api/size_report.py --api build/api/v1 [--site build] [--summary FILE] [--json FILE]

Exit status: 0, or 2 on bad arguments or a missing API. MB are 1 000 000 bytes.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

MB = 1_000_000
# Meta keys come first in docs/<id>.json, so `layer` is near the start of the file.
_LAYER_RE = re.compile(r'(?<!\\)"layer":"([a-z_]+)"')
_HEAD_BYTES = 8192


def _files(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for name in sorted(filenames):
            path = Path(dirpath) / name
            if path.is_file() and not path.is_symlink():
                yield path


def doc_layer(path):
    """The `meta.layer` of an API document file, or None when it has none."""
    with open(path, "rb") as f:
        head = f.read(_HEAD_BYTES).decode("utf-8", "ignore")
    m = _LAYER_RE.search(head)
    if m:
        return m.group(1)
    try:
        return json.loads(path.read_text(encoding="utf-8"))["meta"]["layer"]
    except (ValueError, KeyError, TypeError):
        return None


def measure(api, site=None):
    """Sizes in bytes: the whole site, its top-level folders, the API by folder and by layer, and the search groups."""
    api = Path(api)
    separate_site = site is not None
    site = Path(site) if separate_site else api
    report = {"total": 0, "files": 0, "site": {} if separate_site else None, "api": {"total": 0, "files": 0, "folders": {}, "layers": {}},
              "search": None}
    api_resolved = api.resolve()
    manifest = api / "search" / "index.json"
    search = json.loads(manifest.read_text(encoding="utf-8")) if manifest.is_file() else None
    groups = {g["id"] for g in (search or {}).get("groups", [])}
    for path in _files(site):
        size = path.stat().st_size
        report["total"] += size
        report["files"] += 1
        if separate_site:
            rel = path.relative_to(site).parts
            top = rel[0] if len(rel) > 1 else "."
            report["site"][top] = report["site"].get(top, 0) + size
        if api_resolved not in path.resolve().parents:
            continue
        parts = path.resolve().relative_to(api_resolved).parts
        folder = parts[0] if len(parts) > 1 else "."
        api_report = report["api"]
        api_report["total"] += size
        api_report["files"] += 1
        api_report["folders"][folder] = api_report["folders"].get(folder, 0) + size
        # A layer's share: its listings, its documents and its search group.
        if folder == "docs":
            layer = doc_layer(path) or "unknown"
        elif folder == "search":
            layer = parts[1] if len(parts) > 2 and parts[1] in groups else None
        elif folder == ".":
            layer = None
        else:
            layer = folder
        if layer is not None:
            api_report["layers"][layer] = api_report["layers"].get(layer, 0) + size
    if search is not None:
        report["search"] = {
            "search_version": search.get("search_version"),
            "bytes": report["api"]["folders"].get("search", 0),
            "groups": [
                {k: g.get(k) for k in ("id", "doc_count", "fields", "bytes", "budget")}
                for g in search.get("groups", [])
            ],
        }
    return report


def _mb(n):
    return f"{n / MB:,.1f} MB" if n >= MB else f"{n / 1000:,.1f} KB"


def _rows(sizes):
    return [f"| `{k}` | {_mb(v)} |" for k, v in sorted(sizes.items(), key=lambda kv: (-kv[1], kv[0]))]


def markdown(report):
    lines = [
        "### Site size",
        "",
        f"**{_mb(report['total'])}** in {report['files']:,} files.",
        "",
    ]
    if report["site"] is not None:
        lines += ["| site folder | size |", "| --- | --- |", *_rows(report["site"]), ""]
    api = report["api"]
    lines += [f"API: {_mb(api['total'])} in {api['files']:,} files.", "",
              "| API folder | size |", "| --- | --- |", *_rows(api["folders"]), "",
              "| layer (listings, documents, search group) | size |", "| --- | --- |", *_rows(api["layers"]), ""]
    search = report["search"]
    if search:
        lines += [f"Search index (version {search['search_version']}): {_mb(search['bytes'])}.", ""]
        if search["groups"]:
            lines += ["| group | documents | fields | size | budget |", "| --- | --- | --- | --- | --- |"]
        for g in search["groups"]:
            fields = ", ".join(g["fields"] or [])
            budget = _mb(g["budget"]) if g.get("budget") is not None else "-"
            size = _mb(g["bytes"]) if g.get("bytes") is not None else "-"
            lines.append(f"| `{g['id']}` | {g['doc_count']} | {fields} | {size} | {budget} |")
        lines.append("")
    return "\n".join(lines)


def main(argv):
    parser = argparse.ArgumentParser(description="Report the size of a built API and site.")
    parser.add_argument("--api", required=True, help="the built API directory (api/v1)")
    parser.add_argument("--site", help="the whole published site, when it holds more than the API")
    parser.add_argument("--summary", help="append the Markdown report to this file (the step summary)")
    parser.add_argument("--json", help="write the report as JSON to this file")
    args = parser.parse_args(argv)
    if not (Path(args.api) / "index.json").is_file():
        print(f"error: no API at {args.api} (index.json missing)", file=sys.stderr)
        return 2
    report = measure(args.api, args.site)
    text = markdown(report)
    print(text)
    if args.summary:
        with open(args.summary, "a", encoding="utf-8") as f:
            f.write(text + "\n")
    if args.json:
        Path(args.json).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
