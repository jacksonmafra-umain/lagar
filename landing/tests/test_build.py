"""Checks scripts/build-site.sh and the Vercel config."""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "build-site.sh"


def run_build(out):
    env = dict(os.environ, LAGAR_SITE_OUT=str(out))
    return subprocess.run(["bash", str(SCRIPT)], env=env, capture_output=True, text=True, check=True)


class BuildTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        tmp = Path(cls.tmp.name)
        cls.out = tmp / "out"
        cls.out.mkdir()
        (cls.out / "stale.txt").write_text("left over from an earlier build")
        cls.result = run_build(cls.out)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_output_layout(self):
        for path in [
            "index.html",
            "favicon.svg",
            "css/tokens.css",
            "css/site.css",
            "js/lang.js",
            "i18n/sv.json",
            "i18n/en.json",
            "fonts/inter_regular.ttf",
            "fonts/source_serif_4_bold.ttf",
            "data/sources.json",
            "data/statistics.json",
            "vercel.json",
        ]:
            self.assertTrue((self.out / path).is_file(), path)

    def test_tests_app_and_api_not_shipped(self):
        self.assertFalse((self.out / "tests").exists())
        self.assertFalse((self.out / "app").exists())
        self.assertFalse((self.out / "api").exists())

    def test_rebuild_is_clean(self):
        self.assertFalse((self.out / "stale.txt").exists())

    def test_prints_output_path(self):
        self.assertIn(str(self.out), self.result.stdout)

    def test_refuses_dangerous_output(self):
        env = dict(os.environ, LAGAR_SITE_OUT="/")
        result = subprocess.run(["bash", str(SCRIPT)], env=env, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("refusing", result.stderr)


class VercelConfigTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = json.loads((ROOT / "landing" / "vercel.json").read_text(encoding="utf-8"))

    def test_old_app_links_go_home(self):
        redirects = {(r["source"], r["destination"]) for r in self.config.get("redirects", [])}
        self.assertIn(("/app", "/"), redirects)
        self.assertIn(("/app/:path*", "/"), redirects)

    def test_no_api_proxy(self):
        self.assertNotIn("rewrites", self.config)

if __name__ == "__main__":
    unittest.main()
