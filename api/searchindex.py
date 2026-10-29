"""Static full-text search index for the API (docs/api.md, `search/`).

The index is an inverted index split into shards by the first two characters of
each term, so a client fetches only the shards its query needs. Text is
normalised exactly like the app's `normalize()` (lowercase, then fold the
diacritics listed below), so "Åre" and "are" are the same term.
"""

import gzip
import json
import re
from array import array

SEARCH_VERSION = 1
# Whole index (manifest, document table and shards) must stay within this many bytes, uncompressed,
# for body text to be indexed; otherwise only titles and numbers are.
BODY_BUDGET_BYTES = 100_000_000

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
# Columns of docs.json; the locality codes were added within v1, after the original ones.
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
    """Flat [gap, bits, gap, bits, ...]; the first gap is the doc number itself."""
    out, prev = [], 0
    for i in range(0, len(entry), 2):
        out.append(entry[i] - prev)
        out.append(entry[i + 1])
        prev = entry[i]
    return out


def _dumps(data):
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n"


def build_files(docs, built_at, with_body):
    """Every file of the index as {relative path: text}. `docs` must be sorted by id."""
    postings = _postings(docs, with_body)
    shards = {}
    for term in sorted(postings):
        shards.setdefault(shard_key(term), {})[term] = _encode(postings[term])
    files = {
        "search/docs.json": _dumps({
            "fields": list(DOC_FIELDS),
            "docs": [[meta.get(k) for k in DOC_FIELDS] for meta, _ in docs],
        }),
    }
    shard_list = []
    for key in sorted(shards):
        text = _dumps({"key": key, "terms": shards[key]})
        files[f"search/shards/{key}.json"] = text
        shard_list.append({"key": key, "terms": len(shards[key]), "bytes": len(text.encode("utf-8"))})
    fields = ["title", "number"] + (["body"] if with_body else [])
    files["search/index.json"] = _dumps({
        "search_version": SEARCH_VERSION,
        "built_at": built_at,
        "doc_count": len(docs),
        "term_count": len(postings),
        "fields": fields,
        "field_bits": {f: FIELDS[f] for f in fields},
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
        "shards": shard_list,
    })
    return files


def total_bytes(files):
    return sum(len(text.encode("utf-8")) for text in files.values())


def gzip_bytes(files):
    return sum(len(gzip.compress(text.encode("utf-8"), mtime=0)) for text in files.values())


def build_index(docs, built_at, budget=BODY_BUDGET_BYTES):
    """Index with body text when it fits the budget, else titles and numbers only."""
    docs = sorted(docs, key=lambda d: d[0]["id"])
    files = build_files(docs, built_at, with_body=True)
    if total_bytes(files) <= budget:
        return files
    return build_files(docs, built_at, with_body=False)
