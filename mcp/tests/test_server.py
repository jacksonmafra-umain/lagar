import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from lagarmcp import server
from lagarmcp.store import ApiStore, NotFound

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "api" / "tests" / "fixtures"
TMP = None
API = None


def setUpModule():
    global TMP, API
    TMP = tempfile.TemporaryDirectory()
    corpus = Path(TMP.name) / "corpus"
    shutil.copytree(FIXTURES / "corpus", corpus)
    shutil.copytree(FIXTURES / "corpus-layers", corpus, dirs_exist_ok=True)
    API = Path(TMP.name) / "api" / "v1"
    subprocess.run([sys.executable, "-I", str(ROOT / "api" / "build.py"), "--corpus", str(corpus), "--out", str(API)],
                   check=True, capture_output=True)


def tearDownModule():
    TMP.cleanup()


def rpc(srv, method, params=None, id=1):
    message = {"jsonrpc": "2.0", "id": id, "method": method}
    if params is not None:
        message["params"] = params
    return srv.handle(message)


def call(srv, tool, **arguments):
    result = rpc(srv, "tools/call", {"name": tool, "arguments": arguments})["result"]
    return result, (None if result["isError"] else json.loads(result["content"][0]["text"]))


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.repo = Path(TMP.name) / "repo"
        self.repo.mkdir(exist_ok=True)
        (self.repo / "COVERAGE.md").write_text("# Coverage\n\nIntro.\n\n## Known gaps\n\n- a gap\n\n### Sub\n\n"
                                               "detail\n\n## Failures\n\nnone\n", encoding="utf-8")
        self.srv = server.LagarServer(ApiStore(API), self.repo)

    def test_initialize_negotiates_version_and_lists_tools(self):
        init = rpc(self.srv, "initialize", {"protocolVersion": "2024-11-05"})["result"]
        self.assertEqual(init["protocolVersion"], "2024-11-05")
        self.assertIn("tools", init["capabilities"])
        unknown = rpc(self.srv, "initialize", {"protocolVersion": "1999-01-01"})["result"]
        self.assertEqual(unknown["protocolVersion"], server.PROTOCOL_VERSIONS[0])
        names = [t["name"] for t in rpc(self.srv, "tools/list")["result"]["tools"]]
        self.assertEqual(names, ["search_laws", "get_document", "list_layers", "list_documents", "get_report"])
        self.assertIsNone(self.srv.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}))
        self.assertEqual(rpc(self.srv, "nope")["error"]["code"], -32601)

    def test_search_folds_accents_ranks_title_first_and_filters(self):
        _, found = call(self.srv, "search_laws", query="Arbetsmiljöverkets")
        self.assertEqual([r["id"] for r in found["results"]], ["afs-2023-1"])
        self.assertEqual(found["results"][0]["layer"], "agency")
        self.assertEqual(found["terms"], ["arbetsmiljoverkets"])
        _, number = call(self.srv, "search_laws", query="2010:800")
        self.assertEqual(number["results"][0]["id"], "sfs-2010-800")
        self.assertIn("number", number["results"][0]["matched_in"])
        _, filtered = call(self.srv, "search_laws", query="2010:800", layers=["case_law"])
        self.assertTrue(all(r["layer"] == "case_law" for r in filtered["results"]))
        _, typed = call(self.srv, "search_laws", query="dataskydd", types=["eu_directive"], prefix=True)
        self.assertEqual([r["id"] for r in typed["results"]], ["eu-31995l0046"])
        _, exact = call(self.srv, "search_laws", query="dataskydd")
        self.assertEqual(exact["total"], 0)
        _, limited = call(self.srv, "search_laws", query="dataskydd", prefix=True, limit=1)
        self.assertEqual((len(limited["results"]), limited["total"]), (1, 2))

    def test_search_errors_are_tool_errors(self):
        result, _ = call(self.srv, "search_laws", query="  ")
        self.assertTrue(result["isError"])
        result, _ = call(self.srv, "search_laws")
        self.assertTrue(result["isError"])

    def test_get_document_truncates_and_rejects_bad_ids(self):
        _, doc = call(self.srv, "get_document", id="SFS-2010-800", max_chars=10)
        self.assertEqual(doc["meta"]["title"], "Skollag (2010:800)")
        self.assertEqual(len(doc["body"]), 10)
        self.assertTrue(doc["truncated"])
        for bad in ("sfs-0000-0", "../index"):
            result, _ = call(self.srv, "get_document", id=bad)
            self.assertTrue(result["isError"], bad)

    def test_get_document_reads_gzip_documents(self):
        packed = Path(TMP.name) / "packed" / "v1"
        if not packed.exists():
            corpus = Path(TMP.name) / "corpus"
            subprocess.run([sys.executable, "-I", str(ROOT / "api" / "build.py"), "--corpus", str(corpus),
                            "--out", str(packed), "--docs-encoding", "gzip"], check=True, capture_output=True)
        self.assertFalse((packed / "docs" / "sfs-2010-800.json").exists())
        srv = server.LagarServer(ApiStore(packed), self.repo)
        _, doc = call(srv, "get_document", id="sfs-2010-800")
        self.assertEqual(doc["meta"]["title"], "Skollag (2010:800)")

    def test_layers_and_listing(self):
        _, layers = call(self.srv, "list_layers")
        self.assertEqual(layers["layers"][0]["id"], "fundamental")
        _, page = call(self.srv, "list_documents", layer="sfs", type="act")
        self.assertEqual([i["id"] for i in page["items"]], ["sfs-2010-800"])
        for args in ({"layer": "sfs", "page": 9}, {"layer": "../x"}):
            result, _ = call(self.srv, "list_documents", **args)
            self.assertTrue(result["isError"], args)

    def test_report_whole_section_and_missing(self):
        _, whole = call(self.srv, "get_report", name="coverage")
        self.assertTrue(whole["text"].startswith("# Coverage"))
        _, part = call(self.srv, "get_report", name="coverage", section="known gaps")
        self.assertEqual(part["text"], "## Known gaps\n\n- a gap\n\n### Sub\n\ndetail\n\n")
        for args in ({"name": "progress"}, {"name": "coverage", "section": "nothing"}, {"name": "secrets"}):
            result, _ = call(self.srv, "get_report", **args)
            self.assertTrue(result["isError"], args)

    def test_serve_reads_lines_and_answers_parse_errors(self):
        stdin = io.StringIO('{"jsonrpc":"2.0","id":7,"method":"ping"}\n\nnot json\n'
                            '{"jsonrpc":"2.0","method":"notifications/initialized"}\n')
        stdout = io.StringIO()
        self.srv.serve(stdin, stdout)
        lines = [json.loads(line) for line in stdout.getvalue().splitlines()]
        self.assertEqual(lines[0], {"jsonrpc": "2.0", "id": 7, "result": {}})
        self.assertEqual(lines[1]["error"]["code"], -32700)
        self.assertEqual(len(lines), 2)


class StoreTests(unittest.TestCase):
    def test_missing_file_is_not_found(self):
        with self.assertRaises(NotFound):
            ApiStore(API).read("nothing.json")

    def test_remote_base_gets_trailing_slash(self):
        self.assertEqual(ApiStore("https://example.org/api/v1").base, "https://example.org/api/v1/")


if __name__ == "__main__":
    unittest.main()
