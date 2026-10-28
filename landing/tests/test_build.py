"""Checks scripts/build-site.sh against a stub web app build."""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "build-site.sh"
PAGES_API = "https://jacksonmafra-umain.github.io/lagar/api/v1/"


def run_build(out, dist):
    env = dict(os.environ, LAGAR_SITE_OUT=str(out), LAGAR_WASM_DIST=str(dist))
    return subprocess.run(["bash", str(SCRIPT)], env=env, capture_output=True, text=True, check=True)


class BuildTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        tmp = Path(cls.tmp.name)
        cls.dist = tmp / "dist"
        cls.dist.mkdir()
        (cls.dist / "index.html").write_text("<!DOCTYPE html><title>app</title>")
        (cls.dist / "webApp.wasm").write_bytes(b"\0asm")
        cls.out = tmp / "out"
        cls.out.mkdir()
        (cls.out / "stale.txt").write_text("left over from an earlier build")
        cls.result = run_build(cls.out, cls.dist)

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
            "app/index.html",
            "app/webApp.wasm",
            "vercel.json",
        ]:
            self.assertTrue((self.out / path).is_file(), path)

    def test_tests_and_api_not_shipped(self):
        self.assertFalse((self.out / "tests").exists())
        self.assertFalse((self.out / "api").exists())

    def test_rebuild_is_clean(self):
        self.assertFalse((self.out / "stale.txt").exists())

    def test_prints_output_path(self):
        self.assertIn(str(self.out), self.result.stdout)

    def test_refuses_dangerous_output(self):
        env = dict(os.environ, LAGAR_SITE_OUT="/", LAGAR_WASM_DIST=str(self.dist))
        result = subprocess.run(["bash", str(SCRIPT)], env=env, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("refusing", result.stderr)


class VercelConfigTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = json.loads((ROOT / "landing" / "vercel.json").read_text(encoding="utf-8"))

    def test_app_redirects_to_trailing_slash(self):
        redirects = {(r["source"], r["destination"]) for r in self.config.get("redirects", [])}
        self.assertIn(("/app", "/app/"), redirects)

    def test_app_api_proxied_to_pages(self):
        rewrites = {(r["source"], r["destination"]) for r in self.config.get("rewrites", [])}
        self.assertIn(("/app/api/v1/:path*", PAGES_API + ":path*"), rewrites)

    def test_wasm_content_type(self):
        headers = [
            h for rule in self.config.get("headers", []) if rule["source"].endswith(".wasm")
            for h in rule["headers"]
        ]
        self.assertIn({"key": "Content-Type", "value": "application/wasm"}, headers)


if __name__ == "__main__":
    unittest.main()
