"""Read access to the static API (docs/api.md): a local folder or an HTTP base URL."""

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

USER_AGENT = "lagar-mcp/0.1 (+https://github.com/jacksonmafra-umain/lagar)"
TIMEOUT_SECONDS = 30
_ID = re.compile(r"^[a-z0-9_]+-[0-9a-z-]+$")
_SEGMENT = re.compile(r"^[a-z0-9_-]+$")


class NotFound(Exception):
    """The API has no file at that path."""


class ApiStore:
    """Reads API files by path relative to `/api/v1/`, caching what it has read."""

    def __init__(self, base):
        self.base = str(base)
        self.remote = self.base.startswith(("http://", "https://"))
        if self.remote and not self.base.endswith("/"):
            self.base += "/"
        self._cache = {}

    def read(self, path):
        if path in self._cache:
            return self._cache[path]
        if self.remote:
            request = urllib.request.Request(urllib.parse.urljoin(self.base, path), headers={"User-Agent": USER_AGENT})
            try:
                with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                    raw = response.read()
            except urllib.error.HTTPError as error:
                if error.code == 404:
                    raise NotFound(path) from error
                raise
        else:
            file = Path(self.base) / path
            if not file.is_file():
                raise NotFound(path)
            raw = file.read_bytes()
        data = json.loads(raw.decode("utf-8"))
        if not path.startswith("docs/"):
            self._cache[path] = data
        return data

    def index(self):
        return self.read("index.json")

    def document(self, doc_id):
        if not _ID.match(doc_id or ""):
            raise ValueError(f"not a document id: {doc_id!r}")
        return self.read(f"docs/{doc_id}.json")

    def listing(self, layer, type_=None, page=1):
        for part in (layer, type_):
            if part is not None and not _SEGMENT.match(part):
                raise ValueError(f"not a layer or type id: {part!r}")
        prefix = f"{layer}/{type_}/" if type_ else f"{layer}/"
        return self.read(f"{prefix}index-{int(page)}.json")


class SearchIndex:
    """Query side of the full-text index (search_version 2, docs/api.md "Querying")."""

    def __init__(self, store):
        self.store = store
        self.manifest = store.read("search/index.json")
        if self.manifest.get("search_version") != 2:
            raise ValueError(f"unsupported search_version {self.manifest.get('search_version')}")
        norm = self.manifest["normalization"]
        self._fold = str.maketrans(norm["fold_from"], norm["fold_to"])
        self._token = re.compile(norm["token_pattern"])
        self._stop = frozenset(norm["stop_words"])
        self._min = norm["min_length"]
        self._digits = norm["keep_single_digits"]
        self._base = self.manifest["posting_bits_base"]
        self._bits = self.manifest["field_bits"]

    def tokenize(self, text):
        folded = text.lower().translate(self._fold) if self.manifest["normalization"]["lowercase"] else text
        return [t for t in self._token.findall(folded)
                if t not in self._stop and (len(t) >= self._min or (self._digits and t.isdigit()))]

    @staticmethod
    def shard_key(term):
        return "".join(c if c in "abcdefghijklmnopqrstuvwxyz0123456789" else "_" for c in term[:2])

    def _decode(self, postings):
        """{doc number: field bits} from the flat `gap * base + bits` array."""
        out, doc = {}, 0
        for value in postings:
            doc += value // self._base
            out[doc] = out.get(doc, 0) | value % self._base
        return out

    def _term_hits(self, group, term, prefix):
        key = self.shard_key(term)
        shards = {s["key"] for s in self.store.read(f"search/{group}/index.json")["shards"]}
        if key not in shards:
            return {}
        terms = self.store.read(f"search/{group}/shards/{key}.json")["terms"]
        if not prefix:
            return self._decode(terms.get(term, []))
        hits = {}
        for candidate, postings in terms.items():
            if candidate.startswith(term):
                for doc, bits in self._decode(postings).items():
                    hits[doc] = hits.get(doc, 0) | bits
        return hits

    def _rank(self, bits):
        """Title matches first, then number, then body only; a title and number match beats a title match."""
        return (not bits & self._bits["title"], not bits & self._bits["number"])

    def search(self, query, layers=None, types=None, limit=20, prefix=False):
        terms = self.tokenize(query)
        if not terms:
            return {"terms": [], "total": 0, "results": []}
        results = []
        for group in self.manifest["groups"]:
            if layers and not set(group["layers"]) & set(layers):
                continue
            matched = None
            for term in terms:
                # A prefix needs two characters: shorter terms would span shards.
                hits = self._term_hits(group["id"], term, prefix and len(term) >= 2)
                matched = hits if matched is None else {d: matched[d] | b for d, b in hits.items() if d in matched}
                if not matched:
                    break
            if not matched:
                continue
            table = self.store.read(f"search/{group['id']}/docs.json")
            columns = table["fields"]
            for doc, bits in matched.items():
                row = dict(zip(columns, table["docs"][doc]))
                if types and row.get("type") not in types:
                    continue
                row = {k: row.get(k) for k in ("id", "title", "number", "type", "issued", "repealed")}
                row["layer"] = group["layers"][0] if len(group["layers"]) == 1 else None
                row["matched_in"] = [f for f in ("title", "number", "body") if bits & self._bits[f]]
                results.append((self._rank(bits), row))
        results.sort(key=lambda item: (item[0], -_date_key(item[1]["issued"]), item[1]["id"]))
        return {"terms": terms, "total": len(results), "results": [row for _, row in results[:limit]]}


def _date_key(value):
    return int(value.replace("-", "")) if value else 0
