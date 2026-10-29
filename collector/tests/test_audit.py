import json
import shutil
import tempfile
import unittest
from pathlib import Path

from lagar import audit, riksdagen, writer

LONG = "# Title\n\n" + "Text of the provision. " * 20 + "\n"


def meta(number="2026:1", type_="act", **extra):
    year, num = number.split(":")
    base = {
        "id": f"sfs-{year}-{num}",
        "title": "Lag om test",
        "type": type_,
        "layer": "sfs",
        "number": number,
        "issued": "2026-01-01",
        "in_force": None,
        "repealed": None,
        "amended_by": [],
        "amended_through": None,
        "reprinted_by": [],
        "ministry": None,
        "eli": None,
        "language": "sv",
        "authoritative": False,
        "source": f"https://data.riksdagen.se/dokument/sfs-{year}-{num}",
        "source_sha256": "a" * 64,
        "fetched_at": "2026-10-27T10:00:00Z",
    }
    base.update(extra)
    return base


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "corpus"

    def run_audit(self):
        return audit.audit(self.root, generated_at="2026-10-28T00:00:00Z")

    def test_clean_corpus(self):
        writer.write(meta(), LONG, self.root)
        report = self.run_audit()
        self.assertEqual(report["documents"], 1)
        self.assertEqual(report["schema_errors"], [])
        self.assertEqual(report["duplicate_ids"], [])
        self.assertEqual(report["path_mismatches"], [])
        self.assertEqual(audit.exit_code(report), 0)

    def test_schema_error_detected(self):
        path = writer.write(meta(), LONG, self.root)
        path.write_text(path.read_text(encoding="utf-8").replace('"act"', '"bogus"', 1), encoding="utf-8")
        report = self.run_audit()
        self.assertEqual(len(report["schema_errors"]), 1)
        self.assertEqual(audit.exit_code(report), 1)

    def test_unreadable_frontmatter_is_a_schema_error(self):
        path = self.root / "sfs" / "acts" / "2026-9.md"
        path.parent.mkdir(parents=True)
        path.write_text("no frontmatter\n", encoding="utf-8")
        report = self.run_audit()
        self.assertEqual(len(report["schema_errors"]), 1)

    def test_duplicate_id_detected(self):
        path = writer.write(meta(), LONG, self.root)
        copy = self.root / "sfs" / "ordinances" / path.name
        copy.parent.mkdir(parents=True)
        shutil.copy(path, copy)
        report = self.run_audit()
        self.assertEqual(len(report["duplicate_ids"]), 1)
        self.assertEqual(report["duplicate_ids"][0]["id"], "sfs-2026-1")
        self.assertEqual(len(report["duplicate_ids"][0]["paths"]), 2)
        self.assertEqual(audit.exit_code(report), 1)

    def test_path_mismatch_detected(self):
        path = writer.write(meta(), LONG, self.root)
        moved = self.root / "sfs" / "ordinances" / path.name
        moved.parent.mkdir(parents=True)
        path.rename(moved)
        report = self.run_audit()
        self.assertEqual(len(report["path_mismatches"]), 1)
        self.assertIn("ordinances", report["path_mismatches"][0]["path"])
        self.assertIn("acts", report["path_mismatches"][0]["expected"])
        self.assertEqual(audit.exit_code(report), 1)

    def test_print_only_body_flagged(self):
        writer.write(meta(), "# Title\n\n" + riksdagen.PRINT_ONLY_NOTE + "\n", self.root)
        flags = self.run_audit()["text_quality"]
        self.assertEqual([f["flag"] for f in flags if f["id"] == "sfs-2026-1"].count("print_only"), 1)
        self.assertEqual(audit.exit_code(self.run_audit()), 0)

    def test_other_text_flags(self):
        writer.write(meta("2026:2"), "", self.root)
        writer.write(meta("2026:3"), LONG + "bad � char\n", self.root)
        writer.write(meta("2026:4"), "# T\n\nshort\n", self.root)
        by_id = {}
        for f in self.run_audit()["text_quality"]:
            by_id.setdefault(f["id"], []).append(f["flag"])
        self.assertIn("empty_body", by_id["sfs-2026-2"])
        self.assertEqual(by_id["sfs-2026-3"], ["replacement_character"])
        self.assertEqual(by_id["sfs-2026-4"], ["short_body"])

    def test_unknown_amendment_numbers_counted(self):
        writer.write(
            meta(amended_by=["2026:2", "2026:99"], amended_through="2026:99", reprinted_by=["2026:98"]),
            LONG,
            self.root,
        )
        writer.write(meta("2026:2"), LONG, self.root)
        refs = self.run_audit()["cross_references"]
        self.assertEqual(refs["amended_by"]["unknown"], 1)
        self.assertEqual(refs["amended_by"]["total"], 2)
        self.assertEqual(refs["amended_by"]["sample"], ["2026:99"])
        self.assertEqual(refs["amended_through"]["unknown"], 1)
        self.assertEqual(refs["reprinted_by"]["unknown"], 1)

    def test_eu_references_resolve_by_celex(self):
        def eu_meta(celex, number, **extra):
            base = meta("2026:1", "eu_regulation", id="eu-" + celex.lower(), layer="eu", celex=celex,
                        source="https://publications.europa.eu/resource/celex/" + celex, **extra)
            return {**base, "number": number}

        writer.write(eu_meta("32016R0679", "(EU) 2016/679", amended_by=["32018R1725", "32099R0001"]),
                     LONG, self.root)
        writer.write(eu_meta("32018R1725", "(EU) 2018/1725"), LONG, self.root)
        refs = self.run_audit()["cross_references"]["amended_by"]
        self.assertEqual((refs["total"], refs["unknown"], refs["sample"]), (2, 1, ["32099R0001"]))

    def test_report_is_deterministic_and_sorted(self):
        writer.write(meta("2026:2"), "", self.root)
        writer.write(meta("2026:1"), "", self.root)
        first = audit.render(self.run_audit())
        second = audit.render(self.run_audit())
        self.assertEqual(first, second)
        ids = [f["id"] for f in json.loads(first)["text_quality"]]
        self.assertEqual(ids, sorted(ids))

    def test_summary_line(self):
        writer.write(meta(), LONG, self.root)
        line = audit.summary(self.run_audit())
        self.assertIn("1 documents", line)
        self.assertNotIn("\n", line)

    def test_fsck_status_recorded(self):
        writer.write(meta(), LONG, self.root)
        report = audit.audit(self.root, generated_at="x", fsck=lambda: 0)
        self.assertEqual(report["fsck"], {"exit_status": 0})
        self.assertIsNone(self.run_audit()["fsck"])


if __name__ == "__main__":
    unittest.main()
