import json
import tempfile
import unittest
from pathlib import Path

from lagar import progress, writer
from tests.test_audit import LONG, meta

DESIGN = Path(__file__).resolve().parents[2] / "DESIGN.md"

TARGETS = [
    {"layer": "fundamental", "type": "fundamental_law", "label": "Fundamental laws", "target": 4,
     "kind": "counted", "source": "s", "as_of": "2026-10-27"},
    {"layer": "sfs", "type": None, "label": "SFS", "target": 2, "kind": "counted",
     "source": "s", "as_of": "2026-10-27"},
    {"layer": "agency", "type": None, "label": "Agency regulations", "target": None,
     "kind": "unknown", "source": None, "as_of": None},
]


class ProgressTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "corpus"
        self.colors = progress.load_colors(DESIGN)

    def rows(self):
        return progress.build_rows(TARGETS, progress.count_types(self.root))

    def test_other_layers_count_all_their_types(self):
        counts = {"eu_regulation": 3, "eu_directive": 2, "act": 7}
        targets = [{"layer": "eu", "type": None, "label": "EU", "target": 10, "kind": "curated",
                    "source": "s", "as_of": "2026-10-29"}]
        [row] = progress.build_rows(targets, counts)
        self.assertEqual((row["collected"], row["percent"]), (5, 50.0))

    def test_design_colors_parsed(self):
        self.assertEqual(self.colors["sfs-act"], {"base": "#005b99", "text": "#005b99", "dark": "#9ecaff"})
        self.assertEqual(self.colors["case-law"]["base"], "#7a2e4d")

    def test_progress_capped_at_target(self):
        for n in (1, 2, 3):
            writer.write(meta(f"2026:{n}"), LONG, self.root)
        row = next(r for r in self.rows() if r["layer"] == "sfs")
        self.assertEqual(row["collected"], 3)
        self.assertEqual(row["percent"], 100.0)

    def test_sfs_row_sums_types_with_breakdown(self):
        writer.write(meta("2026:1"), LONG, self.root)
        writer.write(meta("2026:2", type_="ordinance"), LONG, self.root)
        row = next(r for r in self.rows() if r["layer"] == "sfs")
        self.assertEqual(row["collected"], 2)
        self.assertEqual(row["breakdown"], {"act": 1, "ordinance": 1, "other_statute": 0})
        self.assertIn("1 acts, 1 ordinances, 0 other statutes", progress.render_markdown(self.rows(), None))

    def test_other_layers_sum_their_types(self):
        counts = {"act": 4, "case_report": 2, "case_notice": 1}
        case_law = {"layer": "case_law", "type": None, "label": "Case law", "target": 10,
                    "kind": "counted", "source": "s", "as_of": "2026-10-29"}
        rows = progress.build_rows(TARGETS + [case_law], counts)
        row = next(r for r in rows if r["layer"] == "case_law")
        self.assertEqual((row["collected"], row["breakdown"]), (3, None))

    def test_unknown_target_has_no_percent(self):
        row = next(r for r in self.rows() if r["layer"] == "agency")
        self.assertIsNone(row["percent"])
        self.assertEqual(row["collected"], 0)

    def test_svg_deterministic_with_layer_base_colors(self):
        writer.write(meta(), LONG, self.root)
        first = progress.render_svg(self.rows(), self.colors)
        self.assertEqual(first, progress.render_svg(self.rows(), self.colors))
        for key in ("fundamental", "sfs-act", "agency"):
            self.assertIn(self.colors[key]["base"], first)
            self.assertIn(self.colors[key]["text"], first)
        self.assertIn("#f8f9fc", first)
        self.assertTrue(first.startswith("<svg"))

    def test_labels_end_before_bars(self):
        for entry in json.loads((Path(__file__).resolve().parents[1] / "data" / "targets.json").read_text(encoding="utf-8")):
            end = progress.LABEL_X + len(entry["label"]) * progress.LABEL_CHAR_PX
            self.assertLess(end, progress.BAR_X, entry["label"])

    def test_invalid_documents_not_counted(self):
        path = writer.write(meta("2026:1"), LONG, self.root)
        writer.write(meta("2026:2"), LONG, self.root)
        path.write_text(path.read_text(encoding="utf-8").replace('"act"', '"bogus"', 1), encoding="utf-8")
        self.assertEqual(progress.count_types(self.root), {"act": 1})

    def test_markdown_has_disclaimer_table_and_integrity(self):
        integrity = {"generated_at": "2026-10-28T00:00:00Z", "documents": 0, "schema_errors": [],
                     "duplicate_ids": [], "path_mismatches": [], "text_quality": [],
                     "cross_references": {"amended_by": {"total": 3, "unknown": 2, "sample": []}}}
        text = progress.render_markdown(self.rows(), integrity)
        self.assertIn("Volume does not prove completeness", text)
        self.assertIn("| layer | series | collected | target | kind | % |", text)
        self.assertIn("## Integrity", text)
        self.assertIn("![", text)
        self.assertNotIn("## Integrity", progress.render_markdown(self.rows(), None))

    def test_main_writes_files(self):
        writer.write(meta(), LONG, self.root)
        targets = Path(self.tmp.name) / "targets.json"
        targets.write_text(json.dumps(TARGETS), encoding="utf-8")
        out = Path(self.tmp.name) / "out"
        out.mkdir()
        code = progress.main(["--corpus", str(self.root), "--targets", str(targets),
                              "--integrity", str(out / "none.json"), "--design", str(DESIGN),
                              "--out-dir", str(out)])
        self.assertEqual(code, 0)
        self.assertTrue((out / "PROGRESS.md").exists())
        self.assertTrue((out / "progress.svg").exists())


if __name__ == "__main__":
    unittest.main()
