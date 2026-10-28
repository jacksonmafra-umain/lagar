import copy
import json
import unittest
from pathlib import Path

from lagar import schema, vocabulary

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "docs" / "api" / "examples" / "docs" / "sfs-1999-175.json"


def example_meta():
    return copy.deepcopy(json.loads(EXAMPLE.read_text(encoding="utf-8"))["meta"])


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


if __name__ == "__main__":
    unittest.main()
