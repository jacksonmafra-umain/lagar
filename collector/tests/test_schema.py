import copy
import json
import unittest
from pathlib import Path

from lagar import schema, vocabulary

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "docs" / "api" / "examples" / "docs" / "sfs-1999-175.json"


def example_meta():
    return copy.deepcopy(json.loads(EXAMPLE.read_text(encoding="utf-8"))["meta"])


def amendment():
    return {
        "number": "1965:280",
        "title": None,
        "scope": "\u00e4ndr. 20 kap 4 \u00a7",
        "preparatory_works": None,
        "celex": None,
        "in_force": "1965-07-01",
        "in_force_raw": "1965-07-01 \u00f6verg.best.",
    }


class SchemaTest(unittest.TestCase):
    def test_valid_example_passes(self):
        self.assertEqual(schema.validate(example_meta()), [])

    def test_n_series_accepted(self):
        meta = example_meta()
        meta.update(id="sfs-n2026-1", number="N2026:1", source="https://data.riksdagen.se/dokument/sfs-N2026-1")
        self.assertEqual(schema.validate(meta), [])

    def test_n_series_amendment_lists(self):
        meta = example_meta()
        meta.update(amended_by=["N2026:1"], amended_through="N2026:1", reprinted_by=["N2026:1"])
        self.assertEqual(schema.validate(meta), [])

    def test_unknown_type_rejected(self):
        meta = example_meta()
        meta["type"] = "decree"
        errors = schema.validate(meta)
        self.assertEqual(len(errors), 1)
        self.assertIn("type", errors[0])

    def test_layer_must_match_type(self):
        meta = example_meta()
        meta["type"] = "act"
        meta["layer"] = "fundamental"
        errors = schema.validate(meta)
        self.assertTrue(any("layer" in e for e in errors))

    def test_missing_key_rejected(self):
        meta = example_meta()
        del meta["source_sha256"]
        errors = schema.validate(meta)
        self.assertTrue(any("source_sha256" in e for e in errors))

    def test_bad_amended_by_rejected(self):
        meta = example_meta()
        meta["amended_by"] = ["2010-283"]
        errors = schema.validate(meta)
        self.assertTrue(any("amended_by" in e for e in errors))

    def test_trailing_newline_in_amended_by_rejected(self):
        meta = example_meta()
        meta["amended_by"] = ["2010:283\n"]
        errors = schema.validate(meta)
        self.assertTrue(any("amended_by" in e for e in errors))

    def test_amendments_optional_null_or_list(self):
        meta = example_meta()
        meta.pop("amendments", None)
        self.assertEqual(schema.validate(meta), [])
        for value in (None, [], [amendment()]):
            with self.subTest(value=value):
                meta["amendments"] = value
                self.assertEqual(schema.validate(meta), [])

    def test_bad_amendment_rejected_with_path(self):
        cases = {
            "amendments[0].number": {"number": "1965-280"},
            "amendments[0].in_force": {"in_force": "1 jan 1965"},
            "amendments[0].extra": {"extra": None},
        }
        for where, change in cases.items():
            with self.subTest(where=where):
                meta = example_meta()
                meta["amendments"] = [{**amendment(), **change}]
                errors = schema.validate(meta)
                self.assertTrue(any(e.startswith(where + ":") for e in errors), errors)
        meta = example_meta()
        item = amendment()
        del item["scope"]
        meta["amendments"] = [item]
        self.assertEqual(schema.validate(meta), ["amendments[0].scope: required key is missing"])

    def test_schema_enums_match_vocabulary(self):
        props = schema._load_schema()["properties"]
        self.assertEqual(props["layer"]["enum"], list(vocabulary.LAYERS))
        self.assertEqual(props["type"]["enum"], list(vocabulary.TYPES))
        self.assertEqual(set(vocabulary.TYPES.values()) - set(vocabulary.LAYERS), set())

    def test_non_dict_input_returns_errors(self):
        for bad in (None, [], "text", 3):
            with self.subTest(bad=bad):
                errors = schema.validate(bad)
                self.assertEqual(len(errors), 1)
                self.assertIn("expected object", errors[0])

    def test_uri_format_is_strict(self):
        for good in ("https://data.riksdagen.se/dokument/sfs-1", "urn:lex:se:1999:175", "http://a.b/c?d=e#f"):
            with self.subTest(good=good):
                self.assertTrue(schema._format_ok("uri", good))
        for bad in ("", "no scheme", "1http://x", "https://", "https:///path", "https://a b/", "https://x/\n", "https://x/\t", "/relative/path", "mailto"):
            with self.subTest(bad=bad):
                self.assertFalse(schema._format_ok("uri", bad))

    def test_if_then_else_and_const(self):
        rule = {"if": {"properties": {"a": {"const": 1}}}, "then": {"required": ["b"]}, "else": {"required": ["c"]}}
        self.assertEqual(schema._valid({"a": 1, "b": 0}, rule), True)
        self.assertEqual(schema._valid({"a": 1}, rule), False)
        self.assertEqual(schema._valid({"a": 2, "c": 0}, rule), True)
        self.assertEqual(schema._valid({"a": 2, "b": 0}, rule), False)
        self.assertEqual(schema._valid([1, 2], {"maxItems": 1}), False)
        self.assertEqual(schema._valid({"x": 1}, {"allOf": [{"required": ["x"]}, {"required": ["y"]}]}), False)


if __name__ == "__main__":
    unittest.main()
