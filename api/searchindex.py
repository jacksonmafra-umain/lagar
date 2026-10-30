"""Static full-text search index for the API (docs/api.md, `search/`).

The index is split by layer: each layer with documents has its own group under
`search/<layer>/` (manifest, document table and shards), so a client reads only
the layers it searches and each layer has its own size budget. Within a group,
an inverted index is split into shards by the first two characters of each
term, so a client fetches only the shards its query needs. Text is normalised
exactly like the app's `normalize()` (lowercase, then fold the diacritics
listed below), so "Åre" and "are" are the same term.
"""

import gzip
import json
import re
from array import array

from lagar.vocabulary import LAYERS, TYPES

SEARCH_VERSION = 2
# Each group (manifest, document table and shards) must stay within its budget, in bytes,
# uncompressed, for body text to be indexed; otherwise only its titles and numbers are.
DEFAULT_BUDGET_BYTES = 40_000_000
BUDGET_BYTES = {}
# A layer's body text is indexed only up to the first line starting with this heading. A case-law
# referat runs to tens of KB; the decision header before it (court, dates, case numbers, summary,
# cited provisions, keywords) is what people search for, at a fifth of the index size.
BODY_END = {"case_law": "## Referat"}

# Same table as the app (app/shared/.../domain/Search.kt); keep the two in sync.
ACCENTED = "åäöàáâãāăąçćčďđèéêëēėęěìíîïīįłñńňòóôõøōőŕřśšşťùúûūůűųýÿźżž"
PLAIN = "aaoaaaaaaacccddeeeeeeeeiiiiiilnnnooooooorrssstuuuuuuuyyzzz"
_FOLD = str.maketrans(ACCENTED, PLAIN)

# An SFS-style number ("1962:700", "n2026:1") is one token; otherwise runs of letters and digits.
TOKEN_RE = re.compile(r"[a-z]*\d{4}:\d+|[^\W_]+")

# Very common Swedish function words, normalised. Kept short on purpose: words such as "lag",
# "kap" or "inte" stay searchable.
STOP_WORDS = frozenset("""
    att av de dem den denna deras dess dessa det detta din du eller en ett for fran har hon i
    jag man med mot nar och om pa sa sin sig ska skall som till under var vi vid vara
""".split())

FIELD_TITLE = 1
FIELD_NUMBER = 2
FIELD_BODY = 4
FIELDS = {"title": FIELD_TITLE, "number": FIELD_NUMBER, "body": FIELD_BODY}
# A posting is one integer: gap * BITS_BASE + field bits.
BITS_BASE = 8
# Columns of docs.json, in this order; a column that is null in every row of a group is left out.
DOC_FIELDS = ("id", "title", "number", "type", "issued", "repealed", "region_code", "municipality_code")
_KEY_CHARS = frozenset("abcdefghijklmnopqrstuvwxyz0123456789")


def normalize(text):
    """Lowercase and fold diacritics, as the app does; å/ä/ö become a/a/o."""
    return text.lower().translate(_FOLD)


def tokenize(text):
    """Normalised terms in order of appearance: drops stop words and single letters, keeps single digits."""
    return [
        t for t in TOKEN_RE.findall(normalize(text))
        if t not in STOP_WORDS and (len(t) > 1 or t.isdigit())
    ]


def shard_key(term):
    """First two characters of a term; anything outside a-z and 0-9 becomes `_`."""
    return "".join(c if c in _KEY_CHARS else "_" for c in term[:2])


def indexed_body(group, body):
    """The part of `body` that group `group` indexes: all of it, or the text before its BODY_END heading."""
    heading = BODY_END.get(group)
    if heading is None:
        return body
    if body.startswith(heading + "\n"):
        return ""
    end = body.find("\n" + heading + "\n")
    return body if end < 0 else body[:end]


def _postings(docs, with_body):
    """term -> array of (doc number, field bits) pairs, doc numbers ascending."""
    postings = {}
    for n, (meta, body) in enumerate(docs):
        fields = {}
        for field, text in (("title", meta["title"]), ("number", meta["number"])) + (
            (("body", body),) if with_body else ()
        ):
            bit = FIELDS[field]
            for term in tokenize(text):
                fields[term] = fields.get(term, 0) | bit
        for term, bits in fields.items():
            entry = postings.get(term)
            if entry is None:
                entry = postings[term] = array("i")
            entry.append(n)
            entry.append(bits)
    return postings


def _encode(entry):
    """Flat [gap * 8 + bits, ...]; the first gap is the doc number itself."""
    out, prev = [], 0
    for i in range(0, len(entry), 2):
        out.append((entry[i] - prev) * BITS_BASE + entry[i + 1])
        prev = entry[i]
    return out


def _dumps(data):
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n"


def _size(text):
    return len(text.encode("utf-8"))


def layer_of(meta):
    return meta.get("layer") or TYPES[meta["type"]]


def build_group(group, docs, with_body):
    """Every file of one group as {relative path: text}. `docs` must be sorted by id."""
    prefix = f"search/{group}/"
    postings = _postings([(meta, indexed_body(group, body)) for meta, body in docs], with_body)
    shards = {}
    for term in sorted(postings):
        shards.setdefault(shard_key(term), {})[term] = _encode(postings[term])
    columns = [k for k in DOC_FIELDS if k == "id" or any(meta.get(k) is not None for meta, _ in docs)]
    files = {
        f"{prefix}docs.json": _dumps({
            "fields": columns,
            "docs": [[meta.get(k) for k in columns] for meta, _ in docs],
        }),
    }
    shard_list = []
    for key in sorted(shards):
        text = _dumps({"key": key, "terms": shards[key]})
        files[f"{prefix}shards/{key}.json"] = text
        shard_list.append({"key": key, "terms": len(shards[key]), "bytes": _size(text)})
    files[f"{prefix}index.json"] = _dumps({
        "group": group,
        "layers": [group],
        "doc_count": len(docs),
        "term_count": len(postings),
        "fields": ["title", "number"] + (["body"] if with_body else []),
        "shards": shard_list,
    })
    return files


def total_bytes(files):
    return sum(_size(text) for text in files.values())


def gzip_bytes(files):
    return sum(len(gzip.compress(text.encode("utf-8"), mtime=0)) for text in files.values())


def budget_for(group, budgets=None):
    budgets = BUDGET_BYTES if budgets is None else budgets
    return budgets.get(group, DEFAULT_BUDGET_BYTES)


def build_index(docs, built_at, budgets=None):
    """One group per layer with documents: body text where the group fits its budget, else titles and numbers.

    `budgets` maps a layer to its budget in bytes; layers it leaves out get DEFAULT_BUDGET_BYTES.
    """
    by_layer = {}
    for doc in sorted(docs, key=lambda d: d[0]["id"]):
        by_layer.setdefault(layer_of(doc[0]), []).append(doc)
    files, groups, term_count = {}, [], 0
    for layer in LAYERS:
        if layer not in by_layer:
            continue
        budget = budget_for(layer, budgets)
        group = build_group(layer, by_layer[layer], with_body=True)
        if total_bytes(group) > budget:
            group = build_group(layer, by_layer[layer], with_body=False)
        manifest = json.loads(group[f"search/{layer}/index.json"])
        term_count += manifest["term_count"]
        groups.append({
            "id": layer,
            "layers": manifest["layers"],
            "doc_count": manifest["doc_count"],
            "fields": manifest["fields"],
            "bytes": total_bytes(group),
            "budget": budget,
        })
        files.update(group)
    files["search/index.json"] = _dumps({
        "search_version": SEARCH_VERSION,
        "built_at": built_at,
        "doc_count": sum(g["doc_count"] for g in groups),
        "term_count": term_count,
        "field_bits": dict(FIELDS),
        "posting_bits_base": BITS_BASE,
        "normalization": {
            "lowercase": True,
            "fold_from": ACCENTED,
            "fold_to": PLAIN,
            "token_pattern": TOKEN_RE.pattern,
            "min_length": 2,
            "keep_single_digits": True,
            "stop_words": sorted(STOP_WORDS),
        },
        "shard_key_length": 2,
        "groups": groups,
    })
    return files
