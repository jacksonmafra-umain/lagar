import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "api" / "tests" / "fixtures" / "corpus"
sys.path.insert(0, str(ROOT / "api"))
sys.path.insert(0, str(ROOT / "collector"))
import build  # noqa: E402
from lagar import frontmatter, writer  # noqa: E402

BUILT_AT = "2026-10-27T10:30:00Z"


def run_build(out, corpus):
    return subprocess.run(
        [sys.executable, "-I", str(ROOT / "api" / "build.py"), "--corpus", str(corpus), "--out", str(out),
         "--built-at", BUILT_AT],
        capture_output=True, text=True,
    )


def read(out, rel):
    return json.loads((Path(out) / rel).read_text(encoding="utf-8"))


class MinistryNameTest(unittest.TestCase):
    def test_unit_suffix_dropped(self):
        self.assertEqual(build.ministry_name("Justitiedepartementet L2"), "Justitiedepartementet")
        self.assertEqual(build.ministry_name("Finansdepartementet FMA B"), "Finansdepartementet")
        self.assertEqual(
            build.ministry_name("Landsbygds- och infrastrukturdepartementet RSIB TM"),
            "Landsbygds- och infrastrukturdepartementet",
        )

    def test_other_bodies_kept(self):
        self.assertEqual(build.ministry_name("Riksbanken"), "Riksbanken")
        self.assertEqual(build.ministry_name("Statistiska centralbyrån"), "Statistiska centralbyrån")
        self.assertEqual(build.ministry_name("  Socialdepartementet  "), "Socialdepartementet")

    def test_blank_is_none(self):
        self.assertIsNone(build.ministry_name(None))
        self.assertIsNone(build.ministry_name("   "))


class MinistrySlugTest(unittest.TestCase):
    def test_folds_and_hyphenates(self):
        self.assertEqual(build.ministry_slug("Näringsdepartementet"), "naringsdepartementet")
        self.assertEqual(build.ministry_slug("Statistiska centralbyrån"), "statistiska-centralbyran")
        self.assertEqual(build.ministry_slug("Miljö- och energidepartementet"), "miljo-och-energidepartementet")
        self.assertEqual(build.ministry_slug("H.M. Konungen"), "h-m-konungen")


class ByMinistryBuildTest(unittest.TestCase):
    def _corpus(self, tmp, rows):
        meta, body = frontmatter.load((CORPUS / "sfs" / "acts" / "2010-800.md").read_text(encoding="utf-8"))
        corpus = Path(tmp) / "corpus"
        for n, (type_, ministry) in enumerate(rows, start=1):
            layer_meta = dict(meta, id=f"sfs-2000-{n}", number=f"2000:{n}", issued="2000-01-01",
                              type=type_, ministry=ministry)
            writer.write(layer_meta, body, corpus)
        return corpus

    def test_index_and_pages_per_series(self):
        rows = [("act", "Justitiedepartementet L2")] * 52 + [("act", "Justitiedepartementet L4")] \
            + [("act", "Riksbanken")] * 2 + [("act", None)] + [("ordinance", "Socialdepartementet")]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out"
            result = run_build(out, corpus=self._corpus(tmp, rows))
            self.assertEqual(result.returncode, 0, result.stderr)
            index = read(out, "sfs/act/by-ministry/index.json")
            self.assertEqual(list(index), ["layer", "type", "total", "unassigned", "ministries"])
            self.assertEqual((index["layer"], index["type"], index["total"], index["unassigned"]), ("sfs", "act", 56, 1))
            self.assertEqual(index["ministries"], [
                {"id": "justitiedepartementet", "name": "Justitiedepartementet", "count": 53},
                {"id": "riksbanken", "name": "Riksbanken", "count": 2},
            ])
            p1 = read(out, "sfs/act/by-ministry/justitiedepartementet/index-1.json")
            p2 = read(out, "sfs/act/by-ministry/justitiedepartementet/index-2.json")
            self.assertEqual(
                list(p1), ["layer", "type", "ministry_id", "ministry", "page", "page_count", "total", "items"])
            self.assertEqual((p1["ministry_id"], p1["ministry"], p1["page_count"], p1["total"]),
                             ("justitiedepartementet", "Justitiedepartementet", 2, 53))
            self.assertEqual((len(p1["items"]), len(p2["items"])), (50, 3))
            # Items keep the ministry as written, unit included, and the listing order.
            self.assertEqual(p1["items"][0]["number"], "2000:53")
            self.assertEqual(p1["items"][0]["ministry"], "Justitiedepartementet L4")
            ordinances = read(out, "sfs/ordinance/by-ministry/index.json")
            self.assertEqual(ordinances["ministries"], [
                {"id": "socialdepartementet", "name": "Socialdepartementet", "count": 1}])

    def test_ties_sorted_by_name(self):
        rows = [("act", "Utrikesdepartementet"), ("act", "Arbetsmarknadsdepartementet")]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out"
            self.assertEqual(run_build(out, corpus=self._corpus(tmp, rows)).returncode, 0)
            ids = [m["id"] for m in read(out, "sfs/act/by-ministry/index.json")["ministries"]]
            self.assertEqual(ids, ["arbetsmarknadsdepartementet", "utrikesdepartementet"])

    def test_only_sfs_series_with_documents(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out"
            self.assertEqual(run_build(out, corpus=CORPUS).returncode, 0)
            self.assertTrue((out / "sfs" / "act" / "by-ministry" / "index.json").is_file())
            self.assertFalse((out / "sfs" / "other_statute").exists())
            self.assertFalse((out / "fundamental" / "fundamental_law" / "by-ministry").exists())
            self.assertFalse((out / "sfs" / "by-ministry").exists())

    def test_slug_collision_fails(self):
        rows = [("act", "Statens provningsanstalt"), ("act", "Statens Provningsanstalt")]
        with tempfile.TemporaryDirectory() as tmp:
            result = run_build(Path(tmp) / "out", corpus=self._corpus(tmp, rows))
            self.assertEqual(result.returncode, 1)
            self.assertIn("statens-provningsanstalt", result.stderr)
            self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
