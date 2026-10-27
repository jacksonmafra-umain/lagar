import copy
import json
import unittest
from pathlib import Path

from lagar import schema

ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "docs" / "api" / "examples" / "docs" / "sfs-1999-175.json"


def example_meta():
    return copy.deepcopy(json.loads(EXAMPLE.read_text(encoding="utf-8"))["meta"])


class SchemaTest(unittest.TestCase):
    def test_valid_example_passes(self):
        self.assertEqual(schema.validate(example_meta()), [])

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


if __name__ == "__main__":
    unittest.main()
