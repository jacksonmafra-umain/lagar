import contextlib
import copy
import hashlib
import io
import json
import tempfile
import unittest
import urllib.error
import urllib.parse
from pathlib import Path

from lagar import caselaw, frontmatter, schema
from lagar.http import Blocked

FIXTURES = Path(__file__).resolve().parent / "fixtures"
SAMPLE = json.loads((FIXTURES / "caselaw-listing.json").read_text(encoding="utf-8"))
ROBOTS = "https://rattspraxis.etjanst.domstol.se/robots.txt"
NJA, HFD_REF, HFD_NOT = SAMPLE


def http_error(url, code):
    return urllib.error.HTTPError(url, code, "err", {}, io.BytesIO(b""))


def excluded_items():
    """A full ruling with an attachment and a leave-to-appeal item: never stored."""
    ruling = copy.deepcopy(HFD_REF)
    ruling.update(
        id="00000000-0000-0000-0000-00000000dom1",
        publiceringsform="DOM_ELLER_BESLUT",
        typ="EJ_VAGLEDANDE",
        referatNummerLista=[],
        bilagaLista=[{"fillagringId": "bilaga-1", "filnamn": "dom.pdf"}],
    )
    leave = copy.deepcopy(HFD_REF)
    leave.update(id="00000000-0000-0000-0000-00000000pt01", publiceringsform=None,
                 typ="PROVNINGSTILLSTAND", referatNummerLista=[])
    return [ruling, leave]


class FakeClient:
    """Serves listing pages by page number; any other URL is a 404."""

    def __init__(self, items, robots=None, error=None):
        self.items = items
        self.robots = robots
        self.error = error
        self.calls = []

    def get(self, url):
        self.calls.append(url)
        if url == ROBOTS:
            if self.robots is None:
                raise http_error(url, 404)
            return self.robots
        parsed = urllib.parse.urlparse(url)
        if parsed.path != "/api/v1/publiceringar":
            raise http_error(url, 404)
        if self.error is not None:
            raise self.error
        query = dict(urllib.parse.parse_qsl(parsed.query))
        page, size = int(query["page"]), int(query["pagesize"])
        items = [
            i for i in self.items
            if "domstolkod" not in query or i["domstol"]["domstolKod"] == query["domstolkod"]
        ]
        items.sort(key=lambda i: i["avgorandedatum"], reverse=True)
        return json.dumps(items[page * size:(page + 1) * size], ensure_ascii=False).encode()

    def listing_calls(self):
        return [c for c in self.calls if c != ROBOTS]


class CaseLawMappingTests(unittest.TestCase):
    def test_fixture_publications_map_to_valid_frontmatter(self):
        expected = {
            NJA["id"]: ("nja-2026-38", "NJA 2026:38", "case_report", "HDO", "Högsta domstolen"),
            HFD_REF["id"]: ("hfd-2026-ref-43", "HFD 2026 ref. 43", "case_report", "HFD",
                            "Högsta förvaltningsdomstolen"),
            HFD_NOT["id"]: ("hfd-2026-not-24", "HFD 2026 not. 24", "case_notice", "HFD",
                            "Högsta förvaltningsdomstolen"),
        }
        for item in SAMPLE:
            meta = caselaw.build_meta(item, "0" * 64, "2026-10-29T00:00:00Z")
            self.assertEqual(schema.validate(meta), [], item["id"])
            self.assertEqual(
                (meta["id"], meta["number"], meta["type"], meta["court"], meta["issuer"]),
                expected[item["id"]],
            )
            self.assertEqual(meta["layer"], "case_law")
            self.assertEqual(meta["issued"], item["avgorandedatum"])
            self.assertEqual(meta["title"], item["sammanfattning"].strip())
            self.assertEqual(
                meta["source"],
                "https://rattspraxis.etjanst.domstol.se/api/v1/publiceringar/" + item["id"],
            )
            self.assertIsNone(meta["ecli"])
            self.assertEqual((meta["amended_by"], meta["reprinted_by"]), ([], []))

    def test_ecli_is_kept_only_in_the_schema_form(self):
        item = dict(HFD_REF, ecliNummer="ECLI:SE:HFD:2026:43")
        self.assertEqual(caselaw.build_meta(item, "0" * 64, "2026-10-29T00:00:00Z")["ecli"],
                         "ECLI:SE:HFD:2026:43")
        item = dict(HFD_REF, ecliNummer="not an ecli")
        self.assertIsNone(caselaw.build_meta(item, "0" * 64, "2026-10-29T00:00:00Z")["ecli"])

    def test_number_prefers_the_ordinal_form_and_ids_are_ascii(self):
        self.assertEqual(caselaw.report_number({"referatNummerLista": ["NJA 2026 s. 435", "NJA 2026:38"]}),
                         "NJA 2026:38")
        self.assertEqual(caselaw.report_number({"referatNummerLista": ["NJA 2019 s. 2"]}), "NJA 2019 s. 2")
        self.assertEqual(caselaw.report_number({"referatNummerLista": [],
                                                "arbetsdomstolenDomsnummer": "AD 2020 nr 45"}),
                         "AD 2020 nr 45")
        self.assertEqual(caselaw.corpus_id("RÅ 2010 ref. 5".replace(" ", " ")), "ra-2010-ref-5")
        self.assertEqual(caselaw.corpus_id("MÖD 2005:3"), "mod-2005-3")
        with self.assertRaises(ValueError):
            caselaw.report_number({"referatNummerLista": ["B 1234-25"]})

    def test_only_referat_and_notis_are_stored(self):
        self.assertEqual(caselaw.corpus_type(NJA), "case_report")
        self.assertEqual(caselaw.corpus_type(HFD_NOT), "case_notice")
        for item in excluded_items():
            self.assertIsNone(caselaw.corpus_type(item))
        self.assertIsNone(caselaw.corpus_type(dict(NJA, typ="EJ_VAGLEDANDE")))

    def test_canonical_bytes_match_the_api_serialisation(self):
        raw = caselaw.canonical_bytes({"b": "ä", "a": [1, {"d": None, "c": True}]})
        self.assertEqual(raw, '{"a":[1,{"c":true,"d":null}],"b":"ä"}'.encode())

    def test_body_has_sections_and_the_text(self):
        meta = caselaw.build_meta(NJA, "0" * 64, "2026-10-29T00:00:00Z")
        body = caselaw.to_markdown(meta, NJA)
        self.assertTrue(body.startswith("# " + meta["title"] + "\n\nDomstol: Högsta domstolen  \n"))
        self.assertIn("Referat: NJA 2026:38, NJA 2026 s. 435", body)
        self.assertIn("## Lagrum\n\n- 2 kap. 15 § regeringsformen (SFS 1974:152)", body)
        self.assertIn("## Nyckelord\n\n- Ersättning", body)
        self.assertIn("## Referat\n\n### Nacka tingsrätt, mark- och miljödomstolen", body)
        self.assertNotIn("## Sammanfattning", body)  # the summary is the title
        notice = caselaw.build_meta(HFD_NOT, "0" * 64, "2026-10-29T00:00:00Z")
        self.assertIn("## Notis\n\n### Not 24", caselaw.to_markdown(notice, HFD_NOT))

    def test_references_given_as_json_lists_are_joined(self):
        item = copy.deepcopy(HFD_REF)
        item["hanvisadePubliceringarLista"] = [{"fritext": '["NJA 1981 s. 1263","NJA 1981:173"]'},
                                               {"fritext": "[inte json"}]
        meta = caselaw.build_meta(item, "0" * 64, "2026-10-29T00:00:00Z")
        body = caselaw.to_markdown(meta, item)
        self.assertIn("## Hänvisningar\n\n- NJA 1981 s. 1263, NJA 1981:173\n- [inte json\n", body)

    def test_personal_identity_numbers_are_detected(self):
        self.assertEqual(caselaw.personal_numbers("född 811218-9876 i"), ["811218-9876"])
        self.assertEqual(caselaw.personal_numbers("19811218-9876"), ["19811218-9876"])
        # case numbers, organisation numbers and a bad check digit are not personal numbers
        self.assertEqual(caselaw.personal_numbers("mål nr B 10973-25, 556036-0793, 811218-9875"), [])

    def test_listing_url(self):
        url = caselaw.listing_url("HDO", "2026-10-01", 3, 20)
        self.assertEqual(
            url,
            "https://rattspraxis.etjanst.domstol.se/api/v1/publiceringar?publiceringsformer=referat,notis"
            "&domstolkod=HDO&publicerad_fran_och_med=2026-10-01&page=3&pagesize=20",
        )

    def test_arguments(self):
        args = caselaw.parse_args(["--court", "hdo", "--court", "HFD", "--changed-since", "2026-10-01"])
        self.assertEqual((args.court, args.since, args.rate), (["HDO", "HFD"], "2026-10-01", 1.0))
        self.assertEqual(args.state, "collector/data/case-law-state.json")
        with contextlib.redirect_stderr(io.StringIO()):
            for bad in (["--from", "2026-02-01", "--to", "2026-01-01"], ["--since", "2026-13-01"],
                        ["--court", "H"], ["--page-size", "0"]):
                with self.assertRaises(SystemExit):
                    caselaw.parse_args(bad)


class CaseLawRunTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.corpus = self.root / "corpus"
        self.state = self.root / "state.json"
        self.report = self.root / "report.json"

    def run_main(self, client, *extra):
        argv = ["case-law", "--corpus", str(self.corpus), "--state", str(self.state),
                "--report", str(self.report), "--page-size", "2", *extra]
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = caselaw.main(argv, client=client)
        return code, json.loads(self.report.read_text(encoding="utf-8"))

    def files(self):
        return sorted(p.relative_to(self.corpus).as_posix() for p in self.corpus.rglob("*.md"))

    def test_run_writes_reports_and_notices_and_never_requests_attachments(self):
        client = FakeClient(SAMPLE + excluded_items())
        code, report = self.run_main(client)
        self.assertEqual(code, 0)
        self.assertEqual(self.files(), [
            "case-law/notices/hfd-2026-not-24.md",
            "case-law/reports/hfd-2026-ref-43.md",
            "case-law/reports/nja-2026-38.md",
        ])
        self.assertEqual(report["excluded"], 2)
        self.assertEqual(sorted(report["written"]), ["HFD 2026 not. 24", "HFD 2026 ref. 43", "NJA 2026:38"])
        self.assertEqual(report["latest_published"], "2026-10-22T14:55:00")
        for url in client.calls:
            self.assertNotIn("bilag", url)
            self.assertTrue(url == ROBOTS or urllib.parse.urlparse(url).path == "/api/v1/publiceringar")
        self.assertEqual(len(client.listing_calls()), 3)  # 5 items, pages of 2
        for path in self.corpus.rglob("*.md"):
            meta, body = frontmatter.load(path.read_text(encoding="utf-8"))
            self.assertEqual(schema.validate(meta), [])
            self.assertNotIn("dom.pdf", body)
            item = next(i for i in SAMPLE if meta["source"].endswith(i["id"]))
            self.assertEqual(meta["source_sha256"],
                             hashlib.sha256(caselaw.canonical_bytes(item)).hexdigest())

    def test_rerun_skips_done_items_and_never_churns_files(self):
        self.run_main(FakeClient(SAMPLE))
        before = {p: p.read_bytes() for p in self.corpus.rglob("*.md")}
        _, report = self.run_main(FakeClient(SAMPLE))
        self.assertEqual((report["written"], report["skipped"]), ([], 3))
        self.state.unlink()
        _, report = self.run_main(FakeClient(SAMPLE))
        self.assertEqual((report["written"], report["unchanged"]), ([], 3))
        self.assertEqual({p: p.read_bytes() for p in self.corpus.rglob("*.md")}, before)

    def test_a_different_body_is_rewritten_without_a_source_change(self):
        self.run_main(FakeClient(SAMPLE))
        path = self.corpus / "case-law/reports/nja-2026-38.md"
        path.write_text(path.read_text(encoding="utf-8") + "stale\n", encoding="utf-8")
        self.state.unlink()
        _, report = self.run_main(FakeClient(SAMPLE))
        self.assertEqual(report["written"], ["NJA 2026:38"])
        self.assertFalse(path.read_text(encoding="utf-8").endswith("stale\n"))

    def test_changed_publication_is_rewritten(self):
        self.run_main(FakeClient(SAMPLE))
        changed = copy.deepcopy(SAMPLE)
        changed[1]["publiceringstid"] = "2026-10-23T08:00:00"
        changed[1]["nyckelordLista"].append("Nytt nyckelord")
        _, report = self.run_main(FakeClient(changed))
        self.assertEqual(report["written"], ["HFD 2026 ref. 43"])
        text = (self.corpus / "case-law/reports/hfd-2026-ref-43.md").read_text(encoding="utf-8")
        self.assertIn("- Nytt nyckelord", text)

    def test_court_filter_limit_and_dates(self):
        client = FakeClient(SAMPLE)
        _, report = self.run_main(client, "--court", "HDO")
        self.assertEqual(report["written"], ["NJA 2026:38"])
        self.assertTrue(all("domstolkod=HDO" in c for c in client.listing_calls()))

        self.state.unlink()
        _, report = self.run_main(FakeClient(SAMPLE), "--court", "HFD", "--limit", "1",
                                  "--corpus", str(self.root / "other"))
        self.assertEqual(report["written"], ["HFD 2026 ref. 43"])

    def test_from_stops_paging_and_to_filters(self):
        client = FakeClient(SAMPLE)
        _, report = self.run_main(client, "--from", "2026-06-20", "--to", "2026-09-01")
        self.assertEqual(report["written"], ["NJA 2026:38"])
        self.assertEqual(len(client.listing_calls()), 2)  # the item on page 2 is older: stop

    def test_since_is_sent_as_publication_date(self):
        client = FakeClient(SAMPLE)
        self.run_main(client, "--since", "2026-10-01")
        self.assertTrue(all("publicerad_fran_och_med=2026-10-01" in c for c in client.listing_calls()))

    def test_unsorted_listing_is_an_error(self):
        class Unsorted(FakeClient):
            def get(self, url):
                if url == ROBOTS:
                    return super().get(url)
                self.calls.append(url)
                return json.dumps(SAMPLE[::-1]).encode()

        with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
            code = caselaw.main(["--corpus", str(self.corpus), "--state", str(self.state)],
                                client=Unsorted(SAMPLE))
        self.assertEqual(code, 1)

    def test_personal_identity_number_and_duplicate_reference_fail(self):
        leaky = copy.deepcopy(HFD_REF)
        leaky["innehall"] += "<p>Personnummer 811218-9876.</p>"
        twin = copy.deepcopy(HFD_NOT)
        twin["id"] = "ffffffff-0000-0000-0000-000000000000"
        _, report = self.run_main(FakeClient([leaky, HFD_NOT, twin]))
        self.assertEqual(report["written"], ["HFD 2026 not. 24"])
        self.assertEqual(sorted(report["failed"]), sorted([leaky["id"], twin["id"]]))
        state = json.loads(self.state.read_text(encoding="utf-8"))
        self.assertIn("personal identity number", state["failed"][leaky["id"]])
        self.assertIn("already stored", state["failed"][twin["id"]])
        self.assertFalse((self.corpus / "case-law/reports/hfd-2026-ref-43.md").exists())

    def test_blocked_and_robots_disallow(self):
        code, report = self.run_main(FakeClient(SAMPLE, error=Blocked("403 Forbidden")))
        self.assertEqual(code, 2)
        self.assertTrue(report["blocked"])
        self.assertEqual(json.loads(self.state.read_text())["blocked"], "403 Forbidden")

        client = FakeClient(SAMPLE, robots=b"User-agent: *\nDisallow: /api/\n")
        code, report = self.run_main(client)
        self.assertEqual(code, 2)
        self.assertEqual(client.listing_calls(), [])

    def test_listing_error_and_corrupt_state_exit_1(self):
        error = urllib.error.URLError("down")
        with contextlib.redirect_stderr(io.StringIO()):
            code = caselaw.main(["--corpus", str(self.corpus), "--state", str(self.state)],
                                client=FakeClient(SAMPLE, error=error))
        self.assertEqual(code, 1)
        self.state.write_text("{", encoding="utf-8")
        with contextlib.redirect_stderr(io.StringIO()):
            code = caselaw.main(["--corpus", str(self.corpus), "--state", str(self.state)],
                                client=FakeClient(SAMPLE))
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
