import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "api" / "build.py"
CORPUS = ROOT / "api" / "tests" / "fixtures" / "corpus"
BUILT_AT = "2026-10-27T10:30:00Z"
sys.path.insert(0, str(ROOT / "collector"))
from lagar import frontmatter  # noqa: E402


def run_build(out, corpus=CORPUS, built_at=BUILT_AT):
    return subprocess.run(
        [sys.executable, "-I", str(BUILD), "--corpus", str(corpus), "--out", str(out), "--built-at", built_at],
        capture_output=True, text=True,
    )


def read(out, rel):
    return json.loads((Path(out) / rel).read_text(encoding="utf-8"))


class BuildTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls._tmp.name) / "v1"
        cls.result = run_build(cls.out)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_build_succeeds(self):
        self.assertEqual(self.result.returncode, 0, self.result.stderr)

    def test_index_lists_all_layers(self):
        index = read(self.out, "index.json")
        self.assertEqual(index["api_version"], 1)
        self.assertEqual(index["built_at"], BUILT_AT)
        self.assertEqual(
            [layer["id"] for layer in index["layers"]],
            ["fundamental", "sfs", "agency", "case_law", "eu", "region", "municipality", "service"],
        )
        self.assertEqual([layer["count"] for layer in index["layers"]], [1, 2, 0, 0, 0, 0, 0, 0])
        self.assertEqual(index["layers"][1]["series"], [{"id": "act", "count": 1}, {"id": "ordinance", "count": 1}])
        self.assertEqual(index["layers"][2]["series"], [])

    def test_listing_sort_and_paging(self):
        page = read(self.out, "sfs/index-1.json")
        self.assertEqual((page["layer"], page["type"], page["page"], page["page_count"], page["total"]),
                         ("sfs", None, 1, 1, 2))
        self.assertEqual([i["id"] for i in page["items"]], ["sfs-2010-800", "sfs-1999-100"])
        self.assertEqual(list(page["items"][0]), ["id", "title", "number", "type", "issued", "repealed"])

    def test_series_listing(self):
        page = read(self.out, "sfs/act/index-1.json")
        self.assertEqual(page["type"], "act")
        self.assertEqual(len(page["items"]), 1)
        self.assertFalse((self.out / "sfs" / "other_statute").exists())

    def test_empty_layer_page(self):
        page = read(self.out, "eu/index-1.json")
        self.assertEqual((page["items"], page["page_count"], page["total"]), ([], 1, 0))

    def test_doc_file(self):
        text = (CORPUS / "sfs" / "acts" / "2010-800.md").read_text(encoding="utf-8")
        meta, body = frontmatter.load(text)
        doc = read(self.out, "docs/sfs-2010-800.json")
        self.assertEqual(list(doc), ["meta", "body"])
        self.assertEqual(doc["meta"], meta)
        self.assertEqual(list(doc["meta"]), list(meta))
        self.assertEqual(doc["body"], body)

    def test_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp) / "a", Path(tmp) / "b"
            self.assertEqual(run_build(a).returncode, 0)
            self.assertEqual(run_build(b).returncode, 0)
            files_a = sorted(p.relative_to(a) for p in a.rglob("*") if p.is_file())
            files_b = sorted(p.relative_to(b) for p in b.rglob("*") if p.is_file())
            self.assertEqual(files_a, files_b)
            for rel in files_a:
                self.assertEqual((a / rel).read_bytes(), (b / rel).read_bytes(), rel)
        raw = (self.out / "index.json").read_bytes()
        self.assertTrue(raw.endswith(b"}\n"))
        self.assertNotIn(b" ", raw.replace("Rättsinformation".encode(), b""))

    def test_paging_and_numeric_sort(self):
        with tempfile.TemporaryDirectory() as tmp:
            corpus = Path(tmp) / "corpus"
            d = corpus / "sfs" / "acts"
            d.mkdir(parents=True)
            template = (CORPUS / "sfs" / "acts" / "2010-800.md").read_text(encoding="utf-8")
            meta, body = frontmatter.load(template)
            from lagar import writer
            for n in range(1, 56):
                m = dict(meta, id=f"sfs-2000-{n}", number=f"2000:{n}", title=f"Lag {n}", issued="2000-01-01")
                writer.write(m, body, corpus)
            m = dict(meta, id="sfs-2001-1", number="2001:1", title="Undated", issued=None)
            writer.write(m, body, corpus)
            out = Path(tmp) / "out"
            self.assertEqual(run_build(out, corpus=corpus).returncode, 0)
            p1, p2 = read(out, "sfs/index-1.json"), read(out, "sfs/index-2.json")
            self.assertEqual((p1["page_count"], p1["total"], len(p1["items"]), len(p2["items"])), (2, 56, 50, 6))
            self.assertEqual(p1["items"][0]["number"], "2000:55")
            self.assertEqual(p1["items"][1]["number"], "2000:54")
            self.assertEqual(p2["items"][-1]["id"], "sfs-2001-1")

    def test_refuses_dangerous_out(self):
        for out in (CORPUS, ROOT, "/"):
            result = run_build(out)
            self.assertEqual(result.returncode, 1, out)
        self.assertTrue(CORPUS.exists())

    def test_bad_file_fails_with_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            corpus = Path(tmp) / "corpus"
            corpus.mkdir()
            (corpus / "broken.md").write_text("no frontmatter\n", encoding="utf-8")
            result = run_build(Path(tmp) / "out", corpus=corpus)
            self.assertEqual(result.returncode, 1)
            self.assertIn("broken.md", result.stderr)


if __name__ == "__main__":
    unittest.main()
