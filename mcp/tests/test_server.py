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
SERVICES = FIXTURES / "corpus-services"
TMP = None
API = None
SERVICE_API = None


def setUpModule():
    global TMP, API, SERVICE_API
    TMP = tempfile.TemporaryDirectory()
    corpus = Path(TMP.name) / "corpus"
    shutil.copytree(FIXTURES / "corpus", corpus)
    shutil.copytree(FIXTURES / "corpus-layers", corpus, dirs_exist_ok=True)
    API = Path(TMP.name) / "api" / "v1"
    subprocess.run([sys.executable, "-I", str(ROOT / "api" / "build.py"), "--corpus", str(corpus), "--out", str(API)],
                   check=True, capture_output=True)
    SERVICE_API = Path(TMP.name) / "service-api" / "v1"
    subprocess.run([sys.executable, "-I", str(ROOT / "api" / "build.py"), "--corpus", str(SERVICES),
                    "--out", str(SERVICE_API)], check=True, capture_output=True)


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


class ServiceTests(unittest.TestCase):
    """Public services (layer `service`) through the same tools as the norms."""

    def setUp(self):
        self.srv = server.LagarServer(ApiStore(SERVICE_API))

    def test_list_layers_counts_services(self):
        _, layers = call(self.srv, "list_layers")
        service = next(layer for layer in layers["layers"] if layer["id"] == "service")
        self.assertEqual((service["count"], service["series"]), (3, [{"id": "public_service", "count": 3}]))

    def test_search_finds_the_service_next_to_the_law(self):
        _, found = call(self.srv, "search_laws", query="förskola")
        rows = {r["id"]: r for r in found["results"]}
        self.assertEqual(rows["service-forskola"]["layer"], "service")
        self.assertEqual(rows["service-forskola"]["type"], "public_service")
        self.assertEqual(rows["service-forskola"]["matched_in"], ["title", "number", "body"])
        _, law = call(self.srv, "search_laws", query="socialförsäkringsbalk")
        self.assertEqual([r["id"] for r in law["results"]], ["sfs-2010-110"])

    def test_search_filters_to_the_service_layer(self):
        _, only = call(self.srv, "search_laws", query="skola", layers=["service"], prefix=True)
        self.assertEqual({r["layer"] for r in only["results"]}, {"service"})
        self.assertIn("service-registerutdrag-skola-forskola", [r["id"] for r in only["results"]])
        _, none = call(self.srv, "search_laws", query="adoptionsbidrag", layers=["sfs"])
        self.assertEqual(none["total"], 0)

    def test_get_document_resolves_based_on(self):
        _, doc = call(self.srv, "get_document", id="service-adoptionsbidrag")
        self.assertEqual(doc["meta"]["based_on"], ["sfs-2010-110"])
        self.assertEqual(doc["based_on"], [{"id": "sfs-2010-110", "title": "Socialförsäkringsbalk (2010:110)",
                                            "type": "act", "layer": "sfs"}])
        self.assertIn("adoptionsbidrag", doc["body"])
        _, law = call(self.srv, "get_document", id="sfs-2010-110", max_chars=0)
        self.assertEqual(law["services"], [{"id": "service-adoptionsbidrag", "title": "Adoptionsbidrag",
                                            "issuer": "Försäkringskassan"}])
        self.assertNotIn("based_on", law)

    def test_get_document_without_service_files(self):
        _, doc = call(server.LagarServer(ApiStore(API)), "get_document", id="sfs-2010-800", max_chars=0)
        self.assertNotIn("services", doc)


class StoreTests(unittest.TestCase):
    def test_missing_file_is_not_found(self):
        with self.assertRaises(NotFound):
            ApiStore(API).read("nothing.json")

    def test_remote_base_gets_trailing_slash(self):
        self.assertEqual(ApiStore("https://example.org/api/v1").base, "https://example.org/api/v1/")


if __name__ == "__main__":
    unittest.main()
