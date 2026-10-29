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

    def test_series_target_counts_numbers_with_that_prefix(self):
        for number in ("AFS 2023:1", "AFS 2023:2", "FFFS 2024:21"):
            year, num = number.split(" ")[1].split(":")
            series = number.split(" ")[0].lower()
            writer.write(meta(number, type_="agency_regulation", id=f"{series}-{year}-{num}",
                              layer="agency", issuer="Myndigheten",
                              source=f"https://example.se/{series}-{year}-{num}"), LONG, self.root)
        writer.write(meta("2026:1"), LONG, self.root)
        self.assertEqual(progress.count_series(self.root), {("agency", "AFS"): 2, ("agency", "FFFS"): 1})
        afs = {"layer": "agency", "type": None, "series": "AFS", "label": "AFS", "target": 4,
               "kind": "counted", "source": "s", "as_of": "2026-10-29"}
        rows = progress.build_rows(TARGETS + [afs], progress.count_types(self.root),
                                   progress.count_series(self.root))
        self.assertEqual((rows[-1]["collected"], rows[-1]["percent"]), (2, 50.0))
        self.assertEqual(next(r for r in rows if r["label"] == "Agency regulations")["collected"], 3)

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

    def test_layer_summary_sums_series_and_needs_every_target(self):
        rows = [
            {"layer": "agency", "collected": 3, "target": 2},
            {"layer": "agency", "collected": 1, "target": 2},
            {"layer": "municipality", "collected": 5, "target": None},
            {"layer": "eu", "collected": 1, "target": 4},
            {"layer": "eu", "collected": 1, "target": None},
        ]
        agency, municipality, eu = progress.summarize_layers(rows)
        self.assertEqual((agency["series"], agency["collected"], agency["target"], agency["percent"]), (2, 4, 4, 75.0))
        self.assertEqual((municipality["target"], municipality["percent"]), (None, None))
        self.assertEqual((eu["collected"], eu["target"], eu["percent"]), (2, None, None))

    def test_readme_block_replaced_between_markers(self):
        block = progress.render_readme_block(self.rows())
        self.assertTrue(block.startswith(progress.README_START))
        self.assertTrue(block.endswith(progress.README_END))
        self.assertIn("| Fundamental laws | 0 | 4 | 0.0% |", block)
        self.assertIn("| Agency regulations | 0 | unknown | - |", block)
        self.assertIn("[PROGRESS.md](PROGRESS.md)", block)
        self.assertIn("[COVERAGE.md](COVERAGE.md)", block)
        text = f"# Title\n\n{progress.README_START}\nold\n{progress.README_END}\n\nRest\n"
        updated = progress.update_readme(text, block)
        self.assertEqual(updated, f"# Title\n\n{block}\n\nRest\n")
        self.assertEqual(progress.update_readme(updated, block), updated)
        self.assertIsNone(progress.update_readme("# No markers\n", block))

    def test_main_writes_files(self):
        writer.write(meta(), LONG, self.root)
        targets = Path(self.tmp.name) / "targets.json"
        targets.write_text(json.dumps(TARGETS), encoding="utf-8")
        out = Path(self.tmp.name) / "out"
        out.mkdir()
        (out / "README.md").write_text(f"# t\n{progress.README_START}\n{progress.README_END}\n", encoding="utf-8")
        code = progress.main(["--corpus", str(self.root), "--targets", str(targets),
                              "--integrity", str(out / "none.json"), "--design", str(DESIGN),
                              "--out-dir", str(out)])
        self.assertEqual(code, 0)
        self.assertTrue((out / "PROGRESS.md").exists())
        self.assertTrue((out / "progress.svg").exists())
        self.assertIn("| SFS (statutes and ordinances) | 1 | 2 | 50.0% |", (out / "README.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
