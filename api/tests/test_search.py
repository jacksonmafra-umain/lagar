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


def lookup(out, query, prefix=False, layers=None):
    """Reference client: ids of documents matching every query term, best field first.

    Reads the groups of `layers` (all groups when None). A document's rank is the lowest field
    bit it matched over all terms (title, then number, then body); ties keep group order, then
    document-table order. With `prefix`, a term matches every indexed term that starts with it.
    """
    out = Path(out) / "search"
    top = json.loads((out / "index.json").read_text(encoding="utf-8"))
    base = top["posting_bits_base"]
    ranked = []
    for g, group in enumerate(top["groups"]):
        if layers is not None and not set(group["layers"]) & set(layers):
            continue
        gdir = out / group["id"]
        manifest = json.loads((gdir / "index.json").read_text(encoding="utf-8"))
        keys = {s["key"] for s in manifest["shards"]}
        table = json.loads((gdir / "docs.json").read_text(encoding="utf-8"))["docs"]
        matched = None
        for term in si.tokenize(query):
            key = si.shard_key(term)
            hits = {}
            if key in keys:
                terms = json.loads((gdir / "shards" / f"{key}.json").read_text(encoding="utf-8"))["terms"]
                for t, flat in terms.items():
                    if t == term or (prefix and t.startswith(term)):
                        doc = 0
                        for value in flat:
                            doc += value // base
                            hits[doc] = hits.get(doc, 0) | value % base
            if matched is None:
                matched = hits
            else:
                matched = {d: matched[d] | b for d, b in hits.items() if d in matched}
        for d, bits in (matched or {}).items():
            ranked.append((bits & -bits, g, d, table[d][0]))
    return [doc_id for *_, doc_id in sorted(ranked)]


class TokenizeTest(unittest.TestCase):
    def test_normalize_matches_app(self):
        self.assertEqual(si.normalize("Åre ÄÖ Écija Łódź"), "are ao ecija lodz")
        self.assertEqual(len(si.ACCENTED), len(si.PLAIN))

    def test_shared_token_fixture(self):
        # The app tokenizer is tested against the same file (app/shared androidHostTest SearchTokensParityTest).
        cases = json.loads((ROOT / "api/tests/fixtures/search-tokens.json").read_text(encoding="utf-8"))["cases"]
        for case in cases:
            with self.subTest(text=case["text"]):
                self.assertEqual(si.tokenize(case["text"]), case["tokens"])

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
    return [({"id": i, "title": t, "number": n, "type": ty, "issued": None, "repealed": None}, b)
            for i, t, n, ty, b in rows]


class IndexTest(unittest.TestCase):
    DOCS = docs(
        ("sfs-2010-800", "Skollag (2010:800)", "2010:800", "act", "**1 §** Bestämmelser om utbildning."),
        ("sfs-1999-100", "Förordning om skolor", "1999:100", "ordinance", "Skolor i Åre."),
        ("nja-2019-2", "Skadestånd för skolor", "NJA 2019 s. 2", "case_report", "Domstolen prövade utbildning."),
    )

    def group(self, files, layer):
        return json.loads(files[f"search/{layer}/index.json"])

    def test_deterministic_and_order_independent(self):
        a = si.build_index(self.DOCS, BUILT_AT)
        b = si.build_index(list(reversed(self.DOCS)), BUILT_AT)
        self.assertEqual(a, b)

    def test_one_group_per_layer_with_documents(self):
        files = si.build_index(self.DOCS, BUILT_AT)
        top = json.loads(files["search/index.json"])
        self.assertEqual(top["search_version"], 2)
        self.assertEqual([g["id"] for g in top["groups"]], ["sfs", "case_law"])
        self.assertEqual(top["doc_count"], 3)
        sfs = top["groups"][0]
        self.assertEqual((sfs["layers"], sfs["doc_count"], sfs["fields"]), (["sfs"], 2, ["title", "number", "body"]))
        self.assertEqual(sfs["bytes"], sum(len(t.encode("utf-8")) for f, t in files.items() if f.startswith("search/sfs/")))
        self.assertEqual(sfs["budget"], si.DEFAULT_BUDGET_BYTES)
        self.assertEqual(top["groups"][1]["budget"], si.DEFAULT_BUDGET_BYTES)
        self.assertEqual(top["term_count"], sum(self.group(files, g["id"])["term_count"] for g in top["groups"]))
        self.assertFalse(any(f.startswith("search/fundamental/") for f in files))

    def test_shards_hold_only_their_terms(self):
        files = si.build_index(self.DOCS, BUILT_AT)
        manifest = self.group(files, "sfs")
        self.assertEqual(manifest["doc_count"], 2)
        listed = [s["key"] for s in manifest["shards"]]
        self.assertEqual(listed, sorted(listed))
        self.assertEqual(sorted(f"search/sfs/shards/{k}.json" for k in listed),
                         sorted(f for f in files if f.startswith("search/sfs/shards/")))
        for shard in manifest["shards"]:
            text = files[f"search/sfs/shards/{shard['key']}.json"]
            self.assertEqual(shard["bytes"], len(text.encode("utf-8")))
            terms = json.loads(text)["terms"]
            self.assertEqual(shard["terms"], len(terms))
            self.assertEqual(list(terms), sorted(terms))
            self.assertTrue(all(si.shard_key(t) == shard["key"] for t in terms))

    def test_postings_pack_gaps_and_field_bits(self):
        files = si.build_index(self.DOCS, BUILT_AT)
        table = json.loads(files["search/sfs/docs.json"])
        self.assertEqual([d[0] for d in table["docs"]], ["sfs-1999-100", "sfs-2010-800"])
        # Columns that are null in every row of the group are left out.
        self.assertEqual(table["fields"], ["id", "title", "number", "type"])
        terms = json.loads(files["search/sfs/shards/sk.json"])["terms"]
        # sfs-1999-100 (doc 0): title and body; sfs-2010-800 (doc 1): title only.
        self.assertEqual(terms["skolor"], [0 * 8 + (si.FIELD_TITLE | si.FIELD_BODY)])
        self.assertEqual(terms["skollag"], [1 * 8 + si.FIELD_TITLE])
        numbers = json.loads(files["search/sfs/shards/20.json"])["terms"]
        self.assertEqual(numbers["2010:800"], [1 * 8 + (si.FIELD_TITLE | si.FIELD_NUMBER)])
        # Document numbers are per group: the case is document 0 of its own group.
        cases = json.loads(files["search/case_law/shards/sk.json"])["terms"]
        self.assertEqual(cases["skolor"], [0 * 8 + si.FIELD_TITLE])

    def test_gaps_accumulate(self):
        rows = docs(*((f"sfs-2000-{n}", "Lag", f"2000:{n}", "act", "") for n in range(1, 4)))
        files = si.build_index(rows, BUILT_AT)
        self.assertEqual(json.loads(files["search/sfs/shards/la.json"])["terms"]["lag"], [1, 9, 9])

    def test_locality_columns_kept_where_set(self):
        rows = [({"id": "0180-1", "title": "Ordning", "number": "1", "type": "municipal_regulation",
                  "issued": None, "repealed": None, "region_code": "01", "municipality_code": "0180"}, "")]
        table = json.loads(si.build_index(rows, BUILT_AT)["search/municipality/docs.json"])
        self.assertEqual(table["fields"], ["id", "title", "number", "type", "region_code", "municipality_code"])
        self.assertEqual(table["docs"], [["0180-1", "Ordning", "1", "municipal_regulation", "01", "0180"]])

    def test_body_dropped_per_group_over_budget(self):
        files = si.build_index(self.DOCS, BUILT_AT, budgets={"case_law": 1})
        top = json.loads(files["search/index.json"])
        self.assertEqual({g["id"]: g["fields"] for g in top["groups"]},
                         {"sfs": ["title", "number", "body"], "case_law": ["title", "number"]})
        self.assertEqual(self.group(files, "case_law")["fields"], ["title", "number"])
        # "Domstolen" is only in the case's body.
        self.assertNotIn("search/case_law/shards/do.json", files)
        self.assertIn("search/sfs/shards/be.json", files)

    def test_case_law_body_indexed_up_to_referat(self):
        body = "Domstol: Högsta domstolen\n\n## Nyckelord\n\n- Hyra\n\n## Referat\n\nParterna tvistade."
        rows = docs(("nja-2020-1", "Fråga om ränta", "NJA 2020 s. 1", "case_report", body))
        files = si.build_index(rows, BUILT_AT)
        self.assertEqual(self.group(files, "case_law")["fields"], ["title", "number", "body"])
        self.assertEqual(json.loads(files["search/case_law/shards/hy.json"])["terms"]["hyra"], [si.FIELD_BODY])
        self.assertNotIn("search/case_law/shards/pa.json", files)

    def test_indexed_body(self):
        self.assertEqual(si.indexed_body("case_law", "Huvud\n## Referat\nText"), "Huvud")
        self.assertEqual(si.indexed_body("case_law", "## Referat\nText"), "")
        self.assertEqual(si.indexed_body("case_law", "Notis utan referat"), "Notis utan referat")
        self.assertEqual(si.indexed_body("case_law", "Se ## Referat\nText"), "Se ## Referat\nText")
        self.assertEqual(si.indexed_body("sfs", "Huvud\n## Referat\nText"), "Huvud\n## Referat\nText")


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
        self.assertEqual((manifest["search_version"], manifest["built_at"], manifest["doc_count"]), (2, BUILT_AT, 3))
        self.assertEqual(manifest["normalization"]["fold_from"], si.ACCENTED)
        self.assertEqual([g["id"] for g in manifest["groups"]], ["fundamental", "sfs"])

    def test_only_the_requested_layers_are_read(self):
        self.assertEqual(lookup(self.out, "utgar", layers=["sfs"]), [])
        self.assertEqual(lookup(self.out, "utgar", layers=["fundamental"]), ["sfs-1974-152"])

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
