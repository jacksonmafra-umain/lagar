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


def new_layer_meta(type_):
    """A valid document of one of the non-SFS types, built on the SFS example."""
    meta = example_meta()
    meta.pop("amendments", None)
    meta.update(amended_by=[], amended_through=None, reprinted_by=[], ministry=None)
    meta.update(NEW_TYPES[type_])
    meta["type"] = type_
    meta["layer"] = vocabulary.TYPES[type_]
    return meta


NEW_TYPES = {
    "agency_regulation": {
        "id": "afs-2023-1", "number": "AFS 2023:1", "issuer": "Arbetsmilj\u00f6verket",
        "amended_by": ["AFS 2024:2"], "amended_through": "AFS 2024:2",
    },
    "case_report": {
        "id": "nja-2019-2", "number": "NJA 2019 s. 2", "court": "HDO", "issuer": "H\u00f6gsta domstolen",
        "ecli": "ECLI:SE:HDO:2019:2",
    },
    "case_notice": {"id": "hfd-2020-not-3", "number": "HFD 2020 not. 3", "court": "HFD"},
    "eu_regulation": {
        "id": "eu-32016r0679", "number": "(EU) 2016/679", "celex": "32016R0679",
        "amended_by": ["32016R0679R(02)"], "amended_through": "32016R0679R(02)",
        "eli": "http://data.europa.eu/eli/reg/2016/679/oj",
    },
    "eu_directive": {"id": "eu-31995l0046", "number": "95/46/EG", "celex": "31995L0046"},
    "eu_decision": {"id": "eu-32019d0001", "number": "(EU) 2019/1", "celex": "32019D0001"},
    "county_regulation": {
        "id": "01fs-2024-3", "number": "01FS 2024:3", "region_code": "01",
        "issuer": "L\u00e4nsstyrelsen i Stockholms l\u00e4n", "amended_by": ["01FS 2025:1"],
    },
    "municipal_regulation": {
        "id": "0180-2024-12", "number": "SKFS 2024:12", "municipality_code": "0180", "region_code": "01",
        "issuer": "Stockholms kommun",
    },
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

    def test_every_type_has_a_valid_fixture(self):
        self.assertEqual(set(NEW_TYPES) | set(vocabulary.SFS_TYPES), set(vocabulary.TYPES))
        for type_ in NEW_TYPES:
            with self.subTest(type_=type_):
                self.assertEqual(schema.validate(new_layer_meta(type_)), [])

    def test_new_fields_optional_and_nullable(self):
        fields = ("issuer", "court", "ecli", "celex", "region_code", "municipality_code")
        meta = example_meta()
        self.assertEqual(schema.validate(meta), [])
        for field in fields:
            with self.subTest(field=field):
                self.assertEqual(schema.validate({**meta, field: None}), [])
        meta = new_layer_meta("agency_regulation")
        for field in fields:
            meta.setdefault(field, None)
        self.assertEqual(schema.validate(meta), [])

    def test_new_field_patterns(self):
        cases = {
            "court": ("county_regulation", "hdo"),
            "ecli": ("case_report", "ECLI:SE:HDO:2019"),
            "celex": ("eu_regulation", "2016R679"),
            "region_code": ("county_regulation", "02"),
            "municipality_code": ("municipal_regulation", "180"),
            "issuer": ("agency_regulation", " Arbetsmilj\u00f6verket"),
        }
        for field, (type_, bad) in cases.items():
            with self.subTest(field=field):
                errors = schema.validate({**new_layer_meta(type_), field: bad})
                self.assertTrue(any(e.startswith(field + ":") for e in errors), errors)

    def test_sfs_keeps_strict_reference_patterns(self):
        for field, value in (
            ("amended_by", ["AFS 2023:1"]),
            ("amended_through", "AFS 2023:1"),
            ("reprinted_by", ["32016R0679"]),
            ("amended_through", "01FS 2024:3"),
        ):
            with self.subTest(field=field, value=value):
                errors = schema.validate({**example_meta(), field: value})
                self.assertTrue(any(e.startswith(field) for e in errors), errors)

    def test_sfs_rejects_other_layer_fields(self):
        for field, value in (("issuer", "Riksdagen"), ("court", "HDO"), ("ecli", "ECLI:SE:HDO:2019:2"),
                             ("celex", "32016R0679"), ("region_code", "01"), ("municipality_code", "0180")):
            with self.subTest(field=field):
                errors = schema.validate({**example_meta(), field: value})
                self.assertTrue(any(e.startswith(field + ":") for e in errors), errors)

    def test_new_type_numbers(self):
        good = {
            "agency_regulation": ["AFS 2023:1", "FFFS 2014:1", "HSLF-FS 2016:40", "ELS\u00c4K-FS 2022:1", "TSFS 2009:131"],
            "case_report": ["NJA 2019 s. 2", "HFD 2020 ref. 5", "MIG 2026:10", "AD 2020 nr 45", "R\u00c5 2008 ref. 1",
                            "PM\u00d6D 2020:1"],
            "case_notice": ["HFD 2020 not. 3", "NJA 2004 N 23"],
            "eu_regulation": ["(EU) 2016/679", "(EG) nr 1907/2006", "(EEG) nr 1408/71", "(EU, Euratom) 2018/1046"],
            "eu_directive": ["95/46/EG", "2004/18/EG", "(EU) 2022/2555", "2013/59/Euratom"],
            "eu_decision": ["(EU) 2019/1", "(Gusp) 2019/797"],
            "county_regulation": ["01FS 2024:3", "25FS 2020:004"],
            "municipal_regulation": ["SKFS 2024:12", "Kf 2019-03-11 \u00a7 45", "1.7.3"],
        }
        bad = {
            "agency_regulation": ["2023:1", "afs 2023:1", "AFS 2023-1", "AFS2023:1"],
            "case_report": ["2019:2", "NJA 2019 2", "nja 2019 s. 2", "NJA 2019 s.2"],
            "case_notice": ["HFD 2020 not 3"],
            "eu_regulation": ["2016/679", "EU 2016/679", "32016R0679"],
            "eu_directive": ["95/46", "95/46/XX"],
            "eu_decision": ["(EU)2019/1"],
            "county_regulation": ["02FS 2024:3", "01 FS 2024:3", "1FS 2024:3", "AFS 2024:3"],
            "municipal_regulation": ["", " SKFS 2024:12", "SKFS 2024:12\n"],
        }
        for type_, numbers in good.items():
            for number in numbers:
                with self.subTest(type_=type_, number=number):
                    meta = {**new_layer_meta(type_), "number": number}
                    if type_ == "county_regulation":
                        meta["region_code"] = number[:2]
                    self.assertEqual(schema.validate(meta), [])
        for type_, numbers in bad.items():
            for number in numbers:
                with self.subTest(type_=type_, number=number):
                    errors = schema.validate({**new_layer_meta(type_), "number": number})
                    self.assertTrue(any(e.startswith("number:") for e in errors), errors)

    def test_new_type_reference_patterns(self):
        cases = {
            "agency_regulation": ("AFS 2024:2", "2024:2"),
            "eu_regulation": ("32019R1020", "(EU) 2019/1020"),
            "county_regulation": ("01FS 2025:1", "AFS 2025:1"),
            "municipal_regulation": ("SKFS 2025:1", " "),
        }
        for type_, (good, bad) in cases.items():
            with self.subTest(type_=type_):
                meta = new_layer_meta(type_)
                if type_ == "eu_regulation":
                    meta["reprinted_by"] = []
                else:
                    meta["reprinted_by"] = [good]
                self.assertEqual(schema.validate({**meta, "amended_by": [good], "amended_through": good}), [])
                for field, value in (("amended_by", [bad]), ("amended_through", bad)):
                    errors = schema.validate({**meta, field: value})
                    self.assertTrue(any(e.startswith(field) for e in errors), (field, errors))

    def test_case_law_is_never_amended(self):
        for field, value in (("amended_by", ["NJA 2020 s. 1"]), ("amended_through", "NJA 2020 s. 1"),
                             ("reprinted_by", ["NJA 2020 s. 1"])):
            with self.subTest(field=field):
                errors = schema.validate({**new_layer_meta("case_report"), field: value})
                self.assertTrue(any(e.startswith(field + ":") for e in errors), errors)

    def test_eu_has_no_reprints(self):
        errors = schema.validate({**new_layer_meta("eu_directive"), "reprinted_by": ["32016R0679"]})
        self.assertTrue(any(e.startswith("reprinted_by:") for e in errors), errors)

    def test_required_fields_per_type(self):
        for type_, field in (("case_report", "court"), ("case_notice", "court"), ("eu_regulation", "celex"),
                             ("eu_directive", "celex"), ("eu_decision", "celex"),
                             ("county_regulation", "region_code"), ("municipal_regulation", "municipality_code")):
            with self.subTest(type_=type_):
                meta = new_layer_meta(type_)
                del meta[field]
                self.assertIn(f"{field}: required key is missing", schema.validate(meta))
                meta[field] = None
                self.assertTrue(any(e.startswith(field + ":") for e in schema.validate(meta)))

    def test_fields_of_other_layers_rejected(self):
        for type_, field, value in (("agency_regulation", "court", "HDO"), ("case_report", "celex", "32016R0679"),
                                    ("eu_regulation", "ecli", "ECLI:EU:C:2014:317"),
                                    ("county_regulation", "municipality_code", "0180"),
                                    ("municipal_regulation", "court", "HDO")):
            with self.subTest(type_=type_, field=field):
                errors = schema.validate({**new_layer_meta(type_), field: value})
                self.assertTrue(any(e.startswith(field + ":") for e in errors), errors)

    def test_region_code_matches_county_series(self):
        errors = schema.validate({**new_layer_meta("county_regulation"), "region_code": "03"})
        self.assertTrue(any(e.startswith("region_code:") for e in errors), errors)

    def test_municipality_lies_in_region(self):
        errors = schema.validate({**new_layer_meta("municipal_regulation"), "region_code": "14"})
        self.assertTrue(any(e.startswith("municipality_code:") for e in errors), errors)
        meta = new_layer_meta("municipal_regulation")
        meta["region_code"] = None
        self.assertEqual(schema.validate(meta), [])

    def test_sfs_types_match_schema(self):
        branch = schema._load_schema()["allOf"][0]["if"]["properties"]["type"]["enum"]
        self.assertEqual(branch, list(vocabulary.SFS_TYPES))

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
