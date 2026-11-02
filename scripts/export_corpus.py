"""Export the corpus for language models and notebook tools.

    python3 -I scripts/export_corpus.py --target dataset --out build/export/dataset [paths ...]
    python3 -I scripts/export_corpus.py --target notebooklm --tier free --out build/export/notebook [paths ...]
    python3 -I scripts/export_corpus.py --target files --out build/export/files [paths ...]

Paths are corpus folders or files (default `corpus`). `--layers sfs,eu` keeps only those
layers and `--only-in-force` leaves out repealed documents.

- `dataset` writes `documents.jsonl` (one record per norm) and `sections.jsonl` (one
  record per § for statutes, other documents chunked by heading and paragraph).
- `notebooklm` packs documents into `bundle-NNN.md` sources of at most `--cap` words
  (400,000, under NotebookLM's 500,000 per source) and writes `manifest.json`; documents
  over the cap are split at chapter, then §, then paragraph boundaries. It fails without
  writing anything when the selection needs more sources than the `--tier` plan allows.
- `files` writes one Markdown file per norm, `<layer>/<id>.md`, with a readable header.
"""

import argparse
import datetime
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "collector"))

from lagar import frontmatter  # noqa: E402
from lagar.vocabulary import LAYERS  # noqa: E402

CAP_WORDS = 400_000
CHUNK_WORDS = 500
# Sources per notebook on each NotebookLM plan (docs/guides/notebooks.md).
TIERS = {"free": 50, "plus": 100, "pro": 300, "ultra": 500}

DOCUMENT_KEYS = (
    "id", "layer", "type", "number", "title", "issued", "in_force", "repealed",
    "amended_by", "amended_through", "issuer", "court", "ecli", "celex",
    "region_code", "municipality_code", "source", "source_sha256", "fetched_at",
    "text_source",
)

_PARAGRAPH_BREAK = re.compile(r"\n[ \t]*\n")
_SECTION = re.compile(r"^\*\*(\d+) ?([a-z])? ?§\*\*")
_CHAPTER = re.compile(r"^(#+ )?(\d+) ?([a-z])? kap\.(?:\s|$)")
_TRANSITIONAL = re.compile(r"^(#+ )?[\w ,-]*(?:övergångs|ikraftträdande)bestämmelser(na)?$", re.IGNORECASE)
_MARKER = re.compile(r"/(Träder i kraft I|Upphör att gälla U):([^/\n]*)/")
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
_SFS_TITLE = re.compile(r"^(\S+) (\([^)]*\d{4}:\d+[^)]*\).*)$")


class Document:
    def __init__(self, path, meta, body):
        self.path = path
        self.meta = meta
        self.body = body.strip()
        first, _, rest = self.body.partition("\n")
        if first.startswith("# "):
            self.heading, self.rest = first, rest.strip()
        else:
            self.heading, self.rest = f"# {meta.get('title') or meta['id']}", self.body

    @property
    def id(self):
        return self.meta["id"]


def words(text):
    return len(text.split())


def paragraphs(text):
    return [p.strip() for p in _PARAGRAPH_BREAK.split(text) if p.strip()]


def corpus_files(paths):
    found = set()
    for path in paths:
        if path.is_dir():
            found.update(path.rglob("*.md"))
        elif path.is_file():
            found.add(path)
        else:
            raise FileNotFoundError(f"no such file or folder: {path}")
    return sorted(found, key=lambda p: p.as_posix())


def is_current(meta, as_of):
    repealed = meta.get("repealed")
    return not repealed or repealed > as_of


def documents(paths, layers=None, only_in_force=False, as_of=None):
    """Documents under `paths` in path order, filtered by layer and repeal date."""
    as_of = as_of or datetime.date.today().isoformat()
    for path in corpus_files(paths):
        text = path.read_text(encoding="utf-8")
        if not text.startswith("---\n"):
            continue  # README and other files without frontmatter
        meta, body = frontmatter.load(text)
        if layers and meta.get("layer") not in layers:
            continue
        if only_in_force and not is_current(meta, as_of):
            continue
        yield Document(path, meta, body)


# Statute structure


def chapter_of(paragraph):
    """The chapter label ("3", "2 a") when the paragraph is a chapter heading."""
    if "\n" in paragraph:
        return None
    match = _CHAPTER.match(paragraph)
    if not match:
        return None
    if not match.group(1) and ("§" in paragraph or words(paragraph) > 12):
        return None  # a sentence that starts with a reference, not a heading
    return " ".join(filter(None, match.group(2, 3)))


def section_of(paragraph):
    match = _SECTION.match(paragraph)
    return " ".join(filter(None, match.group(1, 2))) if match else None


def is_transitional(paragraph):
    return "\n" not in paragraph and bool(_TRANSITIONAL.match(paragraph))


def is_heading(paragraph):
    """A Markdown heading, or a short line without closing punctuation."""
    if paragraph.startswith("#"):
        return True
    return (
        "\n" not in paragraph
        and words(paragraph) <= 10
        and not paragraph.endswith((".", ":", ";", ",", ")"))
        and section_of(paragraph) is None
    )


def has_sections(paragraphs_):
    return any(section_of(p) for p in paragraphs_)


def statute_parts(paragraphs_):
    """Split a statute body into parts: one per §, plus the text before the first §
    and the transitional provisions. Headings that precede a § or a chapter heading
    travel with it. Each part is {"chapter", "section", "transitional", "paragraphs"}."""
    parts = []
    current = {"chapter": None, "section": None, "transitional": False, "paragraphs": []}
    chapter = None

    def start(section, transitional, paragraph):
        nonlocal current
        paras = current["paragraphs"]
        carry = []
        if not current["transitional"]:
            if current["section"] is None and all(is_heading(p) for p in paras):
                carry, paras = paras, []
            else:
                while len(paras) > 1 and is_heading(paras[-1]):
                    carry.insert(0, paras.pop())
        if paras:
            parts.append(current)
        current = {
            "chapter": chapter,
            "section": section,
            "transitional": transitional,
            "paragraphs": carry + [paragraph],
        }

    for paragraph in paragraphs_:
        label = chapter_of(paragraph)
        if label is not None:
            chapter = label
            start(None, False, paragraph)
        elif is_transitional(paragraph):
            chapter = None
            start(None, True, paragraph)
        elif (section := section_of(paragraph)) is not None:
            start(section, False, paragraph)
        else:
            current["paragraphs"].append(paragraph)
    if current["paragraphs"]:
        parts.append(current)
    return parts


def citation_name(meta):
    """How a statute is cited: "lagen (1982:80) om anställningsskydd", "brottsbalken (1962:700)"."""
    title = meta.get("title") or ""
    match = _SFS_TITLE.match(title)
    if not match:
        return meta.get("number") or title
    word = match.group(1).lower()
    if word.endswith(("ande", "ente")):
        word += "t"
    elif word.endswith(("a", "e")):
        word += "n"
    else:
        word += "en"
    return f"{word} {match.group(2)}"


def citation(name, chapter, section):
    if section is None:
        return name
    if chapter is None:
        return f"{section} § {name}"
    return f"{chapter} kap. {section} § {name}"


def version(text, meta):
    """The version marker of a § and the in_force and repealed dates it implies."""
    match = _MARKER.search(text[:300])
    in_force, repealed = meta.get("in_force"), meta.get("repealed")
    if not match:
        return None, in_force, repealed
    date = _DATE.fullmatch(match.group(2).strip())
    if match.group(1).startswith("Träder"):
        in_force = date.group(0) if date else None
    elif date:
        repealed = date.group(0)
    return match.group(0), in_force, repealed


def pieces(paragraph, limit):
    """Split a paragraph longer than `limit` words at line breaks, then between words."""
    out, current, count = [], [], 0
    for line in paragraph.split("\n"):
        tokens = line.split()
        if len(tokens) > limit:
            if current:
                out.append("\n".join(current))
                current, count = [], 0
            out.extend(" ".join(tokens[i : i + limit]) for i in range(0, len(tokens), limit))
            continue
        if current and count + len(tokens) > limit:
            out.append("\n".join(current))
            current, count = [], 0
        current.append(line)
        count += len(tokens)
    if current:
        out.append("\n".join(current))
    return out


def chunks(paragraphs_, limit, heading=None):
    """Group paragraphs into chunks of at most `limit` words, starting a new chunk at
    every Markdown heading. Yields (heading, text)."""
    current, count = [], 0
    for paragraph in paragraphs_:
        if paragraph.startswith("#"):
            if current and not all(p.startswith("#") for p in current):
                yield heading, "\n\n".join(current)
                current, count = [], 0
            heading = paragraph.lstrip("#").strip()
        for piece in pieces(paragraph, limit):
            size = words(piece)
            if current and count + size > limit:
                yield heading, "\n\n".join(current)
                current, count = [], 0
            current.append(piece)
            count += size
    if current:
        yield heading, "\n\n".join(current)


# Targets


def document_record(doc):
    record = {key: doc.meta.get(key) for key in DOCUMENT_KEYS}
    record["text"] = doc.body
    return record


def section_records(doc, chunk_words=CHUNK_WORDS):
    """One record per § for statutes; other text in chunks of about `chunk_words` words."""
    meta = doc.meta
    base = {"doc_id": doc.id, "layer": meta.get("layer")}
    paras = paragraphs(doc.rest)
    name = citation_name(meta) if has_sections(paras) else meta.get("title") or doc.id
    if has_sections(paras):
        parts = statute_parts(paras)
    else:
        parts = [{"chapter": None, "section": None, "transitional": False, "paragraphs": paras}]
    seq = 0
    for part in parts:
        if part["section"] is not None:
            text = "\n\n".join(part["paragraphs"])
            first = next(i for i, p in enumerate(part["paragraphs"]) if section_of(p))
            marker, in_force, repealed = version(part["paragraphs"][first], meta)
            headings = [p.lstrip("#").strip() for p in part["paragraphs"][:first]]
            pieces_ = [(" / ".join(headings) or None, text)]
        else:
            marker, in_force, repealed = None, meta.get("in_force"), meta.get("repealed")
            heading = part["paragraphs"][0].lstrip("#").strip() if part["transitional"] else None
            pieces_ = list(chunks(part["paragraphs"], chunk_words, heading))
        for heading, text in pieces_:
            seq += 1
            yield {
                **base,
                "seq": seq,
                "chapter": part["chapter"],
                "section": part["section"],
                "heading": heading,
                "citation": citation(name, part["chapter"], part["section"]),
                "version": marker,
                "in_force": in_force,
                "repealed": repealed,
                "source": meta.get("source"),
                "text": text,
            }


def export_dataset(docs, out, chunk_words=CHUNK_WORDS):
    out.mkdir(parents=True, exist_ok=True)
    counts = {"documents": 0, "sections": 0}
    with open(out / "documents.jsonl", "w", encoding="utf-8") as documents_file, open(
        out / "sections.jsonl", "w", encoding="utf-8"
    ) as sections_file:
        for doc in docs:
            documents_file.write(json.dumps(document_record(doc), ensure_ascii=False) + "\n")
            counts["documents"] += 1
            for record in section_records(doc, chunk_words):
                sections_file.write(json.dumps(record, ensure_ascii=False) + "\n")
                counts["sections"] += 1
    return counts


def source_line(meta):
    return f"Source: {meta.get('source')} | In force: {meta.get('in_force')}"


def _split(paras, budget, level):
    """Groups of consecutive paragraphs of at most `budget` words each, cut at chapter
    headings first, then at §, then between paragraphs, then inside a paragraph."""
    if level == 3:
        return [[piece] for p in paras for piece in pieces(p, budget)]
    starts = (chapter_of, section_of, lambda p: True)[level]
    groups = []
    for paragraph in paras:
        if not groups or starts(paragraph):
            groups.append([])
        groups[-1].append(paragraph)
    out = []
    for group in groups:
        if sum(words(p) for p in group) > budget:
            out.extend(_split(group, budget, level + 1))
        else:
            out.append(group)
    return out


def notebook_units(doc, cap):
    """The texts one document contributes to bundles: the whole document, or parts of
    at most `cap` words each when it is longer. Yields (part, total, text)."""
    head = f"{doc.heading}\n\n{source_line(doc.meta)}"
    whole = f"{head}\n\n{doc.rest}" if doc.rest else head
    if words(whole) <= cap:
        yield None, None, whole
        return
    budget = cap - words(head) - words("(part 1/1)")
    if budget <= 0:
        raise ValueError(f"--cap {cap} is smaller than the header of {doc.id}")
    parts, current, count = [], [], 0
    for group in _split(paragraphs(doc.rest), budget, 0):
        size = sum(words(p) for p in group)
        if current and count + size > budget:
            parts.append(current)
            current, count = [], 0
        current.extend(group)
        count += size
    if current:
        parts.append(current)
    for number, paras in enumerate(parts, 1):
        part_head = f"{doc.heading} (part {number}/{len(parts)})\n\n{source_line(doc.meta)}"
        yield number, len(parts), part_head + "\n\n" + "\n\n".join(paras)


def plan_bundles(units, cap):
    """Greedy packing in order: a unit goes into the current bundle while it fits."""
    bundles = []
    for unit in units:
        if not bundles or bundles[-1]["words"] + unit["words"] > cap:
            bundles.append({"words": 0, "documents": []})
        bundles[-1]["words"] += unit["words"]
        bundles[-1]["documents"].append(unit)
    return bundles


class TierError(Exception):
    pass


def export_notebooklm(select, out, tier="free", cap=CAP_WORDS):
    """`select` returns a fresh iterator of documents; it is read twice, once to plan
    and once to write, so the whole selection never has to be held in memory."""
    units = []
    for doc in select():
        for part, total, text in notebook_units(doc, cap):
            units.append({
                "id": doc.id,
                "path": doc.path.as_posix(),
                "part": f"{part}/{total}" if part else None,
                "words": words(text),
            })
    bundles = plan_bundles(units, cap)
    limit = TIERS[tier]
    if len(bundles) > limit:
        raise TierError(
            f"the selection needs {len(bundles)} sources; the {tier} plan allows {limit}. "
            "Choose fewer documents or a larger --tier."
        )
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("bundle-*.md"):
        old.unlink()
    for number, bundle in enumerate(bundles, 1):
        bundle["file"] = f"bundle-{number:03}.md"

    owner = [bundle["file"] for bundle in bundles for _ in bundle["documents"]]
    handle, current, index = None, None, 0
    try:
        for doc in select():
            for _, _, text in notebook_units(doc, cap):
                if owner[index] != current:
                    if handle:
                        handle.close()
                    current = owner[index]
                    handle = open(out / current, "w", encoding="utf-8")
                else:
                    handle.write("\n\n")
                handle.write(text)
                index += 1
    finally:
        if handle:
            handle.close()

    manifest = {
        "tier": tier,
        "max_sources": limit,
        "cap_words": cap,
        "sources": len(bundles),
        "documents": len({unit["id"] for unit in units}),
        "words": sum(unit["words"] for unit in units),
        "bundles": [
            {"file": b["file"], "words": b["words"], "documents": b["documents"]} for b in bundles
        ],
    }
    (out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def file_header(meta):
    labels = (
        ("number", "Number"), ("type", "Type"), ("issuer", "Issuer"), ("court", "Court"),
        ("ecli", "ECLI"), ("celex", "CELEX"), ("issued", "Issued"), ("in_force", "In force"),
        ("repealed", "Repealed"), ("amended_through", "Amended through"), ("source", "Source"),
        ("fetched_at", "Read from source"),
    )
    lines = [f"- {label}: {meta[key]}" for key, label in labels if meta.get(key)]
    if meta.get("text_source") == "ocr":
        lines.append("- Text: read by OCR from a scanned PDF; it can contain recognition errors")
    return "\n".join(lines)


def export_files(docs, out):
    count = 0
    for doc in docs:
        path = out / doc.meta.get("layer", "other") / f"{doc.id}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        text = f"{doc.heading}\n\n{file_header(doc.meta)}\n"
        if doc.rest:
            text += f"\n{doc.rest}\n"
        path.write_text(text, encoding="utf-8")
        count += 1
    return {"files": count}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--target", required=True, choices=("dataset", "notebooklm", "files"))
    parser.add_argument("--out", required=True, type=Path, help="output folder")
    parser.add_argument("paths", nargs="*", type=Path, help="corpus folders or files (default: corpus)")
    parser.add_argument("--layers", help=f"comma-separated layers to keep ({', '.join(LAYERS)})")
    parser.add_argument("--only-in-force", action="store_true", help="leave out repealed documents")
    parser.add_argument("--as-of", help="date for --only-in-force (default: today, YYYY-MM-DD)")
    parser.add_argument("--tier", choices=TIERS, default="free", help="NotebookLM plan (default: free)")
    parser.add_argument("--cap", type=int, default=CAP_WORDS, help=f"words per bundle (default: {CAP_WORDS})")
    parser.add_argument(
        "--chunk-words", type=int, default=CHUNK_WORDS,
        help=f"words per chunk for text outside § (default: {CHUNK_WORDS})",
    )
    args = parser.parse_args(argv)

    layers = None
    if args.layers:
        layers = {layer.strip() for layer in args.layers.split(",") if layer.strip()}
        unknown = sorted(layers - set(LAYERS))
        if unknown:
            parser.error(f"unknown layers: {', '.join(unknown)}")
    paths = args.paths or [Path("corpus")]

    def select():
        return documents(paths, layers, args.only_in_force, args.as_of)

    try:
        if args.target == "dataset":
            result = export_dataset(select(), args.out, args.chunk_words)
        elif args.target == "notebooklm":
            manifest = export_notebooklm(select, args.out, args.tier, args.cap)
            result = {key: manifest[key] for key in ("sources", "documents", "words")}
        else:
            result = export_files(select(), args.out)
    except (TierError, FileNotFoundError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(", ".join(f"{value} {key}" for key, value in result.items()) + f" in {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
