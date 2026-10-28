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
        # A statute without register data serves amendments: null, never a missing key.
        self.assertNotIn("amendments", meta)
        self.assertEqual(doc["meta"], {**meta, "amendments": None})
        self.assertEqual(list(doc["meta"]), [*meta, "amendments"])
        self.assertEqual(doc["body"], body)

    def test_doc_file_with_register_data(self):
        text = (CORPUS / "fundamental-laws" / "1974-152.md").read_text(encoding="utf-8")
        meta, _ = frontmatter.load(text)
        doc = read(self.out, "docs/sfs-1974-152.json")
        self.assertEqual(doc["meta"], meta)
        self.assertEqual(list(doc["meta"])[-1], "amendments")
        self.assertEqual(doc["meta"]["in_force"], "1975-01-01")
        self.assertEqual([a["number"] for a in doc["meta"]["amendments"]], ["1976:871", "1979:933"])
        self.assertEqual(doc["meta"]["amendments"][0]["in_force_raw"], "1977-01-01 överg.best.")
        self.assertEqual(doc["meta"]["amendments"][1]["in_force"], None)

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
        for rel in ("index.json", "sfs/index-1.json", "docs/sfs-2010-800.json"):
            obj = read(self.out, rel)
            expected = json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n"
            self.assertEqual((self.out / rel).read_bytes(), expected.encode("utf-8"), rel)

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

    def _corpus_with(self, tmp, **overrides):
        from lagar import writer
        meta, body = frontmatter.load((CORPUS / "sfs" / "acts" / "2010-800.md").read_text(encoding="utf-8"))
        corpus = Path(tmp) / "corpus"
        writer.write(meta, body, corpus)
        path = corpus / "sfs" / "acts" / "2010-800.md"
        meta = {k: v for k, v in dict(meta, **overrides).items() if v is not ...}
        path.write_text("---\n" + frontmatter.dump(meta) + "---\n" + body, encoding="utf-8")
        return corpus, path

    def test_layer_type_mismatch_fails_with_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            corpus, path = self._corpus_with(tmp, layer="eu")
            result = run_build(Path(tmp) / "out", corpus=corpus)
            self.assertEqual(result.returncode, 1)
            self.assertIn(str(path), result.stderr)
            self.assertNotIn("Traceback", result.stderr)

    def test_missing_title_fails_cleanly(self):
        with tempfile.TemporaryDirectory() as tmp:
            corpus, path = self._corpus_with(tmp, title=...)
            result = run_build(Path(tmp) / "out", corpus=corpus)
            self.assertEqual(result.returncode, 1)
            self.assertIn(str(path), result.stderr)
            self.assertNotIn("Traceback", result.stderr)

    def test_unsafe_id_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            corpus, _ = self._corpus_with(tmp, id="sfs-../x")
            result = run_build(Path(tmp) / "out", corpus=corpus)
            self.assertEqual(result.returncode, 1)
            self.assertNotIn("Traceback", result.stderr)

    def test_out_file_or_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "afile"
            f.write_text("x")
            self.assertEqual(run_build(f).returncode, 1)
            self.assertEqual(f.read_text(), "x")
            target = Path(tmp) / "target"
            target.mkdir()
            (target / "keep").write_text("k")
            link = Path(tmp) / "link"
            link.symlink_to(target)
            result = run_build(link)
            self.assertEqual(result.returncode, 1)
            self.assertNotIn("Traceback", result.stderr)
            self.assertTrue((target / "keep").exists())

    def test_out_ancestor_or_inside_corpus_rejected(self):
        self.assertEqual(run_build(ROOT.parent).returncode, 1)
        self.assertEqual(run_build(CORPUS / "sfs").returncode, 1)
        self.assertEqual(run_build(CORPUS / "newout").returncode, 1)
        self.assertFalse((CORPUS / "newout").exists())

    def test_page_boundaries(self):
        from lagar import writer
        meta, body = frontmatter.load((CORPUS / "sfs" / "acts" / "2010-800.md").read_text(encoding="utf-8"))
        for total, pages in ((50, 1), (51, 2)):
            with tempfile.TemporaryDirectory() as tmp:
                corpus = Path(tmp) / "corpus"
                for n in range(1, total + 1):
                    writer.write(dict(meta, id=f"sfs-2000-{n}", number=f"2000:{n}"), body, corpus)
                out = Path(tmp) / "out"
                self.assertEqual(run_build(out, corpus=corpus).returncode, 0)
                p1 = read(out, "sfs/index-1.json")
                self.assertEqual((p1["page_count"], p1["total"]), (pages, total))
                self.assertEqual(len(p1["items"]), 50)
                self.assertEqual((out / "sfs" / "index-2.json").exists(), pages == 2)

    def test_numeric_number_sort(self):
        from lagar import writer
        meta, body = frontmatter.load((CORPUS / "sfs" / "acts" / "2010-800.md").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            corpus = Path(tmp) / "corpus"
            for n in (99, 175):
                writer.write(dict(meta, id=f"sfs-1999-{n}", number=f"1999:{n}", issued="1999-03-25"), body, corpus)
            out = Path(tmp) / "out"
            self.assertEqual(run_build(out, corpus=corpus).returncode, 0)
            self.assertEqual([i["number"] for i in read(out, "sfs/index-1.json")["items"]], ["1999:175", "1999:99"])

    def test_n_series_number_sort(self):
        from lagar import writer
        meta, body = frontmatter.load((CORPUS / "sfs" / "acts" / "2010-800.md").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            corpus = Path(tmp) / "corpus"
            for id_, number in (("sfs-2026-5", "2026:5"), ("sfs-n2026-1", "N2026:1"), ("sfs-n2026-5", "N2026:5")):
                writer.write(dict(meta, id=id_, number=number, issued="2026-02-01"), body, corpus)
            out = Path(tmp) / "out"
            self.assertEqual(run_build(out, corpus=corpus).returncode, 0)
            self.assertEqual([i["number"] for i in read(out, "sfs/index-1.json")["items"]],
                             ["2026:5", "N2026:5", "N2026:1"])

    def test_irregular_old_print_number_sort(self):
        from lagar import writer
        meta, body = frontmatter.load((CORPUS / "sfs" / "acts" / "2010-800.md").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            corpus = Path(tmp) / "corpus"
            for id_, number in (("sfs-1736-0123-1", "1736:0123 1"), ("sfs-1736-0123-2", "1736:0123 2"),
                                ("sfs-1827-60-s-1007", "1827:60 s.1007"), ("sfs-1899-bih-25", "1899:bih. 25"),
                                ("sfs-rfs1968-8", "RFS1968:8")):
                writer.write(dict(meta, id=id_, number=number, issued=None), body, corpus)
            out = Path(tmp) / "out"
            self.assertEqual(run_build(out, corpus=corpus).returncode, 0)
            self.assertEqual([i["number"] for i in read(out, "sfs/index-1.json")["items"]],
                             ["RFS1968:8", "1899:bih. 25", "1827:60 s.1007", "1736:0123 2", "1736:0123 1"])



class OutSafetyTest(unittest.TestCase):
    def test_symlinked_parent_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            real = Path(tmp) / "real"
            real.mkdir()
            (Path(tmp) / "link").symlink_to(real)
            result = run_build(Path(tmp) / "link" / "v1")
            self.assertEqual(result.returncode, 1)
            self.assertIn("symlink", result.stderr)
            self.assertFalse((real / "v1").exists())


class OutNonEmptyTest(unittest.TestCase):
    def test_non_empty_out_without_index_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out"
            out.mkdir()
            (out / "keep.txt").write_text("k")
            result = run_build(out)
            self.assertEqual(result.returncode, 1)
            self.assertIn("index.json", result.stderr)
            self.assertTrue((out / "keep.txt").exists())

    def test_previous_build_and_empty_dir_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out"
            out.mkdir()
            self.assertEqual(run_build(out).returncode, 0)
            self.assertEqual(run_build(out).returncode, 0)


class BuiltAtTest(unittest.TestCase):
    def test_invalid_built_at_rejected(self):
        for bad in ("yesterday", "2026-10-27", "2026-10-27T10:30:00", "2026-13-45T10:30:00Z", "2026-10-27T10:30:00+00:00"):
            with tempfile.TemporaryDirectory() as tmp:
                result = run_build(Path(tmp) / "out", built_at=bad)
                self.assertEqual(result.returncode, 1, bad)
                self.assertIn("--built-at", result.stderr)
                self.assertNotIn("Traceback", result.stderr)


class SchemaErrorsTest(unittest.TestCase):
    def test_one_line_per_error_with_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            corpus = Path(tmp) / "corpus"
            corpus.mkdir()
            meta, body = frontmatter.load((CORPUS / "sfs" / "acts" / "2010-800.md").read_text(encoding="utf-8"))
            meta = {k: v for k, v in meta.items() if k not in ("title", "number")}
            path = corpus / "x.md"
            path.write_text("---\n" + frontmatter.dump(meta) + "---\n" + body, encoding="utf-8")
            result = run_build(Path(tmp) / "out", corpus=corpus)
            lines = [line for line in result.stderr.splitlines() if line.startswith("error:") or str(path) in line]
            self.assertGreaterEqual(len(lines), 2, result.stderr)
            for line in lines:
                self.assertIn(str(path), line)
                self.assertNotIn("['", line)


if __name__ == "__main__":
    unittest.main()
