import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

import serve_local


class ServeLocalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.web, self.api = root / "web", root / "api" / "v1"
        (self.web / "composeResources").mkdir(parents=True)
        (self.api / "docs").mkdir(parents=True)
        (self.web / "index.html").write_text("<html>app</html>", encoding="utf-8")
        (self.web / "app.wasm").write_bytes(b"\0asm")
        (self.api / "index.json").write_text('{"api_version": 1}', encoding="utf-8")
        (self.api / "docs" / "sfs-1962-700.json").write_text("{}", encoding="utf-8")
        (root / "secret.txt").write_text("no", encoding="utf-8")

    def test_resolve_maps_api_prefix_and_web_root(self):
        resolve = serve_local.resolve
        self.assertEqual(resolve("/api/v1/index.json", self.web, self.api), (self.api / "index.json").resolve())
        self.assertEqual(resolve("/api/v1/docs/sfs-1962-700.json?x=1", self.web, self.api),
                         (self.api / "docs" / "sfs-1962-700.json").resolve())
        self.assertEqual(resolve("/", self.web, self.api), self.web.resolve() / "index.html")
        self.assertEqual(resolve("/?doc=sfs-1962-700", self.web, self.api), self.web.resolve() / "index.html")
        self.assertEqual(resolve("/app.wasm", self.web, self.api), (self.web / "app.wasm").resolve())

    def test_resolve_refuses_paths_outside_both_folders(self):
        for path in ("/api/v1/../../secret.txt", "/../secret.txt", "/%2e%2e/secret.txt"):
            target = serve_local.resolve(path, self.web, self.api)
            self.assertTrue(target is None or self.web.resolve() in target.parents, path)

    def test_server_answers_app_api_and_wasm_type(self):
        server = serve_local.make_server("127.0.0.1", 0, self.web, self.api)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        base = f"http://127.0.0.1:{server.server_address[1]}"
        with urllib.request.urlopen(base + "/") as response:
            self.assertEqual(response.read(), b"<html>app</html>")
        with urllib.request.urlopen(base + "/api/v1/index.json") as response:
            self.assertEqual(response.headers["Content-Type"], "application/json")
            self.assertEqual(response.headers["Cache-Control"], "no-store")
        (self.api / "docs" / "x.json.gz").write_bytes(b"\x1f\x8b")
        with urllib.request.urlopen(base + "/api/v1/docs/x.json.gz") as response:
            # Served as is: the client decompresses gzip documents itself (docs/api.md).
            self.assertEqual(response.headers["Content-Type"], "application/gzip")
            self.assertIsNone(response.headers["Content-Encoding"])
            self.assertEqual(response.read(), b"\x1f\x8b")
        with urllib.request.urlopen(base + "/app.wasm") as response:
            self.assertEqual(response.headers["Content-Type"], "application/wasm")
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(base + "/api/v1/missing.json")
        self.assertEqual(caught.exception.code, 404)

    def test_ensure_builds_only_what_is_missing(self):
        calls = []
        run_api, run_web = (lambda d: calls.append("api")), (lambda: calls.append("web"))
        self.assertEqual(serve_local.ensure_builds("missing", self.api, self.web, self.web, run_api, run_web), [])
        self.assertEqual(calls, [])
        self.assertEqual(serve_local.ensure_builds("always", self.api, self.web, self.web, run_api, run_web), [])
        self.assertEqual(calls, ["api", "web"])
        (self.api / "index.json").unlink()
        problems = serve_local.ensure_builds("never", self.api, self.web, self.web, run_api, run_web)
        self.assertEqual(len(problems), 1)
        self.assertIn("no API", problems[0])
        other = Path(self.tmp.name) / "other"
        problems = serve_local.ensure_builds("missing", self.api, other, self.web, run_api, run_web)
        self.assertIn("not the Gradle output", problems[0])


if __name__ == "__main__":
    unittest.main()
