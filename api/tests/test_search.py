import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "api" / "build.py"
CORPUS = ROOT / "api" / "tests" / "fixtures" / "corpus"
BUILT_AT = "2026-10-27T10:30:00Z"
sys.path.insert(0, str(ROOT / "api"))
sys.path.insert(0, str(ROOT / "collector"))
import build  # noqa: E402
import searchindex as si  # noqa: E402


def lookup(out, query, prefix=False):
    """Reference client: ids of documents matching every query term, best field first.

    A document's rank is the lowest field bit it matched over all terms (title, then number,
    then body); ties keep document-table order. With `prefix`, a term matches every indexed
    term that starts with it.
    """
    out = Path(out) / "search"
    manifest = json.loads((out / "index.json").read_text(encoding="utf-8"))
    keys = {s["key"] for s in manifest["shards"]}
    table = json.loads((out / "docs.json").read_text(encoding="utf-8"))["docs"]
    matched = None
    for term in si.tokenize(query):
        key = si.shard_key(term)
        hits = {}
        if key in keys:
            terms = json.loads((out / "shards" / f"{key}.json").read_text(encoding="utf-8"))["terms"]
            for t, flat in terms.items():
                if t == term or (prefix and t.startswith(term)):
                    doc = 0
                    for i in range(0, len(flat), 2):
                        doc += flat[i]
                        hits[doc] = hits.get(doc, 0) | flat[i + 1]
        if matched is None:
            matched = hits
        else:
            matched = {d: matched[d] | b for d, b in hits.items() if d in matched}
    if not matched:
        return []

    def best(bits):
        return bits & -bits

    return [table[d][0] for d in sorted(matched, key=lambda d: (best(matched[d]), d))]


class TokenizeTest(unittest.TestCase):
    def test_normalize_matches_app(self):
        self.assertEqual(si.normalize("Åre ÄÖ Écija Łódź"), "are ao ecija lodz")
        self.assertEqual(len(si.ACCENTED), len(si.PLAIN))

    def test_app_fold_table_in_sync(self):
        kotlin = (ROOT / "app/shared/src/commonMain/kotlin/app/lagar/domain/Search.kt").read_text(encoding="utf-8")
        self.assertIn(f'ACCENTED = "{si.ACCENTED}"', kotlin)
        self.assertIn(f'PLAIN = "{si.PLAIN}"', kotlin)

    def test_sfs_numbers_stay_whole(self):
        self.assertEqual(si.tokenize("Lag (1962:700) om ändring"), ["lag", "1962:700", "andring"])
        self.assertEqual(si.tokenize("N2026:1"), ["n2026:1"])

    def test_words_split_on_punctuation(self):
        self.assertEqual(si.tokenize("Åre-kommunens skatter, 2 kap."), ["are", "kommunens", "skatter", "2", "kap"])

    def test_stop_words_and_single_letters_dropped(self):
        self.assertEqual(si.tokenize("Lagen om att x och 5 § i Sverige"), ["lagen", "5", "sverige"])

    def test_query_and_index_use_same_rules(self):
        self.assertEqual(si.tokenize("ÅRE"), si.tokenize("are"))


class ShardKeyTest(unittest.TestCase):
    def test_first_two_characters(self):
        self.assertEqual(si.shard_key("skollag"), "sk")
        self.assertEqual(si.shard_key("1962:700"), "19")
        self.assertEqual(si.shard_key("5"), "5")

    def test_other_characters_become_underscore(self):
        self.assertEqual(si.shard_key("über"), "_b")
        self.assertEqual(si.shard_key("æø"), "__")


def docs(*rows):
    return [({"id": i, "title": t, "number": n, "type": "act", "issued": None, "repealed": None}, b)
            for i, t, n, b in rows]


class IndexTest(unittest.TestCase):
    DOCS = docs(
        ("sfs-2010-800", "Skollag (2010:800)", "2010:800", "**1 §** Bestämmelser om utbildning."),
        ("sfs-1999-100", "Förordning om skolor", "1999:100", "Skolor i Åre."),
    )

    def test_deterministic_and_order_independent(self):
        a = si.build_index(self.DOCS, BUILT_AT)
        b = si.build_index(list(reversed(self.DOCS)), BUILT_AT)
        self.assertEqual(a, b)

    def test_shards_hold_only_their_terms(self):
        files = si.build_index(self.DOCS, BUILT_AT)
        manifest = json.loads(files["search/index.json"])
        self.assertEqual(manifest["fields"], ["title", "number", "body"])
        self.assertEqual(manifest["doc_count"], 2)
        listed = [s["key"] for s in manifest["shards"]]
        self.assertEqual(listed, sorted(listed))
        self.assertEqual(sorted(f"search/shards/{k}.json" for k in listed),
                         sorted(f for f in files if f.startswith("search/shards/")))
        for shard in manifest["shards"]:
            text = files[f"search/shards/{shard['key']}.json"]
            self.assertEqual(shard["bytes"], len(text.encode("utf-8")))
            terms = json.loads(text)["terms"]
            self.assertEqual(shard["terms"], len(terms))
            self.assertEqual(list(terms), sorted(terms))
            self.assertTrue(all(si.shard_key(t) == shard["key"] for t in terms))

    def test_postings_are_gaps_and_field_bits(self):
        files = si.build_index(self.DOCS, BUILT_AT)
        table = json.loads(files["search/docs.json"])
        self.assertEqual([d[0] for d in table["docs"]], ["sfs-1999-100", "sfs-2010-800"])
        terms = json.loads(files["search/shards/sk.json"])["terms"]
        # sfs-1999-100 (doc 0): title and body; sfs-2010-800 (doc 1): title only.
        self.assertEqual(terms["skolor"], [0, si.FIELD_TITLE | si.FIELD_BODY])
        self.assertEqual(terms["skollag"], [1, si.FIELD_TITLE])
        numbers = json.loads(files["search/shards/20.json"])["terms"]
        self.assertEqual(numbers["2010:800"], [1, si.FIELD_TITLE | si.FIELD_NUMBER])

    def test_body_dropped_over_budget(self):
        files = si.build_index(self.DOCS, BUILT_AT, budget=1)
        manifest = json.loads(files["search/index.json"])
        self.assertEqual(manifest["fields"], ["title", "number"])
        self.assertNotIn("search/shards/be.json", files)


class FixtureQueryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls._tmp.name) / "v1"
        result = subprocess.run(
            [sys.executable, "-I", str(BUILD), "--corpus", str(CORPUS), "--out", str(cls.out), "--built-at", BUILT_AT],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, result.stderr

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_manifest(self):
        manifest = json.loads((self.out / "search/index.json").read_text(encoding="utf-8"))
        self.assertEqual((manifest["search_version"], manifest["built_at"], manifest["doc_count"]), (1, BUILT_AT, 3))
        self.assertEqual(manifest["normalization"]["fold_from"], si.ACCENTED)

    def test_title_query(self):
        self.assertEqual(lookup(self.out, "skollag"), ["sfs-2010-800"])

    def test_number_query(self):
        self.assertEqual(lookup(self.out, "2010:800"), ["sfs-2010-800"])

    def test_body_query_folds_diacritics(self):
        self.assertEqual(lookup(self.out, "utgar fran folket"), ["sfs-1974-152"])
        self.assertEqual(lookup(self.out, "UTGÅR"), ["sfs-1974-152"])

    def test_prefix_query(self):
        self.assertEqual(lookup(self.out, "regering", prefix=True), ["sfs-1974-152"])
        self.assertEqual(lookup(self.out, "regering"), [])

    def test_all_terms_required(self):
        self.assertEqual(lookup(self.out, "skollag folket"), [])

    def test_unknown_term(self):
        self.assertEqual(lookup(self.out, "zzzz"), [])

    def test_api_build_imports_index(self):
        self.assertIs(build.searchindex, si)
