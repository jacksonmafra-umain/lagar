import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "api" / "build.py"
REPORT = ROOT / "api" / "size_report.py"
CORPUS = ROOT / "api" / "tests" / "fixtures" / "corpus"
LAYERS_CORPUS = ROOT / "api" / "tests" / "fixtures" / "corpus-layers"
BUILT_AT = "2026-10-27T10:30:00Z"
sys.path.insert(0, str(ROOT / "api"))
sys.path.insert(0, str(ROOT / "collector"))
import size_report as sr  # noqa: E402


def run_report(*args):
    return subprocess.run([sys.executable, "-I", str(REPORT), *map(str, args)], capture_output=True, text=True)


class SizeReportTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.site = Path(cls._tmp.name) / "site"
        cls.api = cls.site / "api" / "v1"
        corpus = Path(cls._tmp.name) / "corpus"
        # Both fixture corpora together: every layer but `service` has documents.
        for src in (CORPUS, LAYERS_CORPUS):
            for path in src.rglob("*.md"):
                dest = corpus / path.relative_to(src)
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(path.read_bytes())
        result = subprocess.run(
            [sys.executable, "-I", str(BUILD), "--corpus", str(corpus), "--out", str(cls.api), "--built-at", BUILT_AT],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, result.stderr
        # A stand-in for the web app next to the API.
        (cls.site / "index.html").write_text("<!doctype html>\n", encoding="utf-8")
        (cls.site / "assets").mkdir()
        (cls.site / "assets" / "app.wasm").write_bytes(b"\0" * 5000)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def sizes(self, root):
        return {p: p.stat().st_size for p in Path(root).rglob("*") if p.is_file()}

    def test_api_totals_match_the_files(self):
        report = sr.measure(self.api)
        sizes = self.sizes(self.api)
        self.assertEqual(report["total"], sum(sizes.values()))
        self.assertEqual(report["files"], len(sizes))
        self.assertEqual(report["api"]["total"], report["total"])
        self.assertIsNone(report["site"])
        self.assertEqual(sum(report["api"]["folders"].values()), report["total"])
        docs = sum(s for p, s in sizes.items() if p.parent.name == "docs")
        self.assertEqual(report["api"]["folders"]["docs"], docs)

    def test_site_includes_the_web_app(self):
        report = sr.measure(self.api, self.site)
        self.assertEqual(report["total"], sum(self.sizes(self.site).values()))
        self.assertEqual(report["site"]["assets"], 5000)
        self.assertEqual(report["site"]["api"], report["api"]["total"])
        self.assertIn(".", report["site"])

    def test_layers_hold_listings_documents_and_search_group(self):
        report = sr.measure(self.api)
        layers = report["api"]["layers"]
        api = self.api
        for layer in ("sfs", "case_law", "eu", "region", "municipality", "agency", "fundamental"):
            listings = sum(s for p, s in self.sizes(api / layer).items())
            docs = sum(p.stat().st_size for p in (api / "docs").glob("*.json")
                       if json.loads(p.read_text(encoding="utf-8"))["meta"]["layer"] == layer)
            group = sum(self.sizes(api / "search" / layer).values())
            self.assertGreater(docs, 0, layer)
            self.assertGreater(group, 0, layer)
            self.assertEqual(layers[layer], listings + docs + group, layer)
        # Only the top-level search manifest and index.json are outside every layer.
        outside = (api / "index.json").stat().st_size + (api / "search" / "index.json").stat().st_size
        self.assertEqual(sum(layers.values()) + outside, report["total"])

    def test_search_groups_are_reported(self):
        search = sr.measure(self.api)["search"]
        self.assertEqual(search["search_version"], 2)
        self.assertEqual(search["bytes"], sum(self.sizes(self.api / "search").values()))
        by_id = {g["id"]: g for g in search["groups"]}
        self.assertEqual(by_id["case_law"]["fields"], ["title", "number", "body"])
        self.assertEqual(by_id["case_law"]["bytes"], sum(self.sizes(self.api / "search" / "case_law").values()))

    def test_doc_layer_falls_back_to_parsing(self):
        path = Path(self._tmp.name) / "long.json"
        path.write_text(json.dumps({"meta": {"title": "x" * 10000, "layer": "eu"}, "body": ""}), encoding="utf-8")
        self.assertEqual(sr.doc_layer(path), "eu")
        path.write_text(json.dumps({"meta": {"title": 'a "layer":"sfs" b', "layer": "eu"}}, separators=(",", ":")),
                        encoding="utf-8")
        self.assertEqual(sr.doc_layer(path), "eu")

    def test_writes_summary_and_json(self):
        summary = Path(self._tmp.name) / "summary.md"
        summary.write_text("before\n", encoding="utf-8")
        out = Path(self._tmp.name) / "report.json"
        result = run_report("--api", self.api, "--site", self.site, "--summary", summary, "--json", out)
        self.assertEqual(result.returncode, 0, result.stderr)
        text = summary.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("before\n### Site size"))
        self.assertNotIn("budget", text.split("| API folder")[0])
        self.assertIn("| `case_law` |", text)
        self.assertEqual(json.loads(out.read_text(encoding="utf-8"))["total"], sum(self.sizes(self.site).values()))

    def test_reports_without_failing(self):
        result = run_report("--api", self.api)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertIn("### Site size", result.stdout)
        self.assertEqual(run_report("--api", self.api, "--budget-mb", 1).returncode, 2)  # the option is gone

    def test_bad_arguments(self):
        self.assertEqual(run_report("--api", Path(self._tmp.name) / "missing").returncode, 2)


if __name__ == "__main__":
    unittest.main()
