import json
import tempfile
import unittest
from pathlib import Path

from lagar import eu, eucaselaw, frontmatter, schema
from lagar.http import Blocked

from tests.test_eu import FakeClient, bindings, http_error

FIXTURES = Path(__file__).resolve().parent / "fixtures"
XHTML = (FIXTURES / "eu-62014cj0362.xhtml").read_bytes()
SCHREMS = "62014CJ0362"
DIGITAL_RIGHTS = "62012CJ0293"
MANIFESTATION = "https://publications.europa.eu/resource/cellar/cdf1b143-6c15-11e5-9317-01aa75ed71a1.0024.01/DOC_2"
TITLE = ("Domstolens dom (stora avdelningen) av den 6 oktober 2015.#Maximillian Schrems mot Data Protection "
         "Commissioner.#Begäran om förhandsavgörande från High Court (Irland).#Personuppgifter")


def schrems_fields(**extra):
    fields = {
        "date_document": ["2015-10-06"],
        "ecli": ["ECLI:EU:C:2015:650"],
        "procedure_language": ["http://publications.europa.eu/resource/authority/language/ENG"],
        "interprets": ["31995L0046"],
        "title_sv": [TITLE],
        "manifestation_sv": ["pdfa1a", "xhtml", "fmx4"],
    }
    fields.update(extra)
    return fields


def listing(*rows):
    out = [{"celex": {"type": "literal", "value": c}, "modified": {"type": "literal", "value": m}} for c, m in rows]
    return json.dumps({"head": {"vars": ["celex", "modified"]}, "results": {"bindings": out}}).encode()


def routes(sparql=None):
    return {
        eucaselaw.metadata_url(SCHREMS): sparql or bindings(schrems_fields()),
        eu.CELEX_URL.format(celex=SCHREMS): (XHTML, "application/xhtml+xml", MANIFESTATION.replace("https:", "http:")),
    }


class NumbersTest(unittest.TestCase):
    def test_case_numbers_follow_the_court_and_year(self):
        self.assertEqual(eucaselaw.case_number("62012CJ0293"), "C-293/12")
        self.assertEqual(eucaselaw.case_number("62019TJ0012"), "T-12/19")
        self.assertEqual(eucaselaw.case_number("61962CJ0026"), "26/62")
        self.assertEqual(eucaselaw.case_number("61989CJ0106"), "C-106/89")
        self.assertEqual(eucaselaw.corpus_id("62012CJ0293"), "eu-62012cj0293")

    def test_only_judgments_are_accepted(self):
        for bad in ("62012CO0293", "62012CC0293", "32016R0679"):
            with self.assertRaises(ValueError):
                eucaselaw.metadata_url(bad)
        with self.assertRaises(ValueError):
            eucaselaw.list_url(["62012CJ0293"])

    def test_list_url_filters_on_the_acts_and_the_moment(self):
        url = eucaselaw.list_url(["32016R0679"], "2026-10-29")
        self.assertTrue(url.startswith(eucaselaw.SPARQL_URL))
        self.assertIn("32016R0679", url)
        self.assertIn("2026-10-29T00%3A00%3A00.000Z", url)
        self.assertNotIn("FILTER%28%3Fm", eucaselaw.list_url(["32016R0679"]))

    def test_parse_list_keeps_judgments_and_their_newest_change(self):
        raw = listing((SCHREMS, "2025-01-01T10:00:00Z"), (SCHREMS, "2025-02-01T10:00:00Z"),
                      ("62014CO0001", "2025-03-01T10:00:00Z"))
        self.assertEqual(eucaselaw.parse_list(raw), {SCHREMS: "2025-02-01T10:00:00.000Z"})


class MetaTest(unittest.TestCase):
    def test_frontmatter_is_valid_and_follows_the_case(self):
        metadata = eucaselaw.parse_metadata(SCHREMS, bindings(schrems_fields()))
        meta = eucaselaw.build_meta(metadata, "0" * 64, MANIFESTATION, "2026-10-30T00:00:00Z")
        self.assertEqual(schema.validate(meta), [])
        self.assertEqual(meta["id"], "eu-62014cj0362")
        self.assertEqual(meta["number"], "C-362/14")
        self.assertEqual(meta["type"], "eu_judgment")
        self.assertEqual(meta["layer"], "eu")
        self.assertEqual(meta["title"], "Domstolens dom (stora avdelningen) av den 6 oktober 2015. "
                                        "Maximillian Schrems mot Data Protection Commissioner.")
        self.assertEqual((meta["court"], meta["ecli"], meta["celex"]), ("CJ", "ECLI:EU:C:2015:650", SCHREMS))
        self.assertFalse(meta["authoritative"])

    def test_a_swedish_case_is_authoritative(self):
        fields = schrems_fields(procedure_language=["http://publications.europa.eu/resource/authority/language/SWE"])
        metadata = eucaselaw.parse_metadata(SCHREMS, bindings(fields))
        self.assertTrue(eucaselaw.build_meta(metadata, "0" * 64, MANIFESTATION, "2026-10-30T00:00:00Z")["authoritative"])

    def test_joined_cases_come_from_case_uris(self):
        fields = schrems_fields(joined=["http://publications.europa.eu/resource/case/celex%3A62012CJ0594",
                                        "http://publications.europa.eu/resource/case/celex%3A62014CJ0362"])
        self.assertEqual(eucaselaw.parse_metadata(SCHREMS, bindings(fields)).joined, ["62012CJ0594"])

    def test_body_lists_the_case_and_the_interpreted_acts(self):
        metadata = eucaselaw.parse_metadata(SCHREMS, bindings(schrems_fields()))
        meta = eucaselaw.build_meta(metadata, "0" * 64, MANIFESTATION, "2026-10-30T00:00:00Z")
        body = eucaselaw.to_body(meta, metadata, XHTML)
        self.assertTrue(body.startswith("# Domstolens dom (stora avdelningen) av den 6 oktober 2015."))
        self.assertIn("Mål: C-362/14  \nECLI: ECLI:EU:C:2015:650  \nTolkar: 95/46/EG\n", body)
        self.assertIn("Beslut 2000/520 är ogiltigt.", body)


class RunTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.corpus = root / "corpus"
        self.state = root / "state.json"
        self.manifest = root / "manifest.json"
        self.acts = root / "acts.json"
        self.acts.write_text(json.dumps([{"celex": "31995L0046", "name": "Data Protection Directive"}]))

    def args(self, *extra):
        return eucaselaw.parse_args([*extra, "--corpus", str(self.corpus), "--state", str(self.state),
                                     "--manifest", str(self.manifest)])

    def test_collects_a_judgment_and_records_its_bytes(self):
        client = FakeClient(routes())
        summary = eucaselaw.run(client, self.args("--celex", SCHREMS))
        self.assertEqual(summary.written, [SCHREMS])
        path = self.corpus / "eu" / "judgments" / "62014cj0362.md"
        meta, body = frontmatter.load(path.read_text(encoding="utf-8"))
        self.assertEqual(meta["source"], MANIFESTATION)
        self.assertEqual(schema.validate(meta), [])
        manifest = json.loads(self.manifest.read_text())
        self.assertEqual([e["celex"] for e in manifest["judgments"]], [SCHREMS])
        self.assertEqual(manifest["judgments"][0]["bytes"], len(XHTML))
        self.assertTrue(all("eur-lex" not in url for url in client.urls))
        # A second run skips it; a refresh finds it unchanged.
        self.assertEqual(eucaselaw.run(FakeClient(routes()), self.args("--celex", SCHREMS)).skipped, 1)
        self.assertEqual(eucaselaw.run(FakeClient(routes()), self.args("--celex", SCHREMS, "--refresh")).unchanged,
                         [SCHREMS])

    def test_no_swedish_text_is_a_gap(self):
        sparql = bindings(schrems_fields(manifestation_sv=["pdfa1a"]))
        summary = eucaselaw.run(FakeClient(routes(sparql)), self.args("--celex", SCHREMS))
        self.assertEqual(summary.gaps, [SCHREMS])
        gaps = json.loads(self.manifest.read_text())["gaps"]
        self.assertEqual(gaps[0]["celex"], SCHREMS)
        self.assertIn("no Swedish XHTML or HTML", gaps[0]["reason"])
        sparql = bindings(schrems_fields(title_sv=[], manifestation_sv=[]))
        self.assertEqual(eucaselaw.run(FakeClient(routes(sparql)), self.args("--celex", SCHREMS)).gaps, [SCHREMS])

    def test_html_is_tried_when_xhtml_is_not_served(self):
        sparql = bindings(schrems_fields(manifestation_sv=["xhtml", "html"]))
        r = routes(sparql)
        r[eu.CELEX_URL.format(celex=SCHREMS)] = (XHTML, "text/html", MANIFESTATION)

        class XhtmlMissing(FakeClient):
            def fetch_final(self, url, headers=None):
                if (headers or {}).get("Accept") == "application/xhtml+xml":
                    self.calls.append((url, dict(headers)))
                    raise http_error(url, 404)
                return super().fetch_final(url, headers)

        summary = eucaselaw.run(XhtmlMissing(r), self.args("--celex", SCHREMS))
        self.assertEqual(summary.written, [SCHREMS])

    def test_several_swedish_documents_are_a_gap(self):
        r = routes()
        r[eu.CELEX_URL.format(celex=SCHREMS)] = http_error(eu.CELEX_URL.format(celex=SCHREMS), 300)
        summary = eucaselaw.run(FakeClient(r), self.args("--celex", SCHREMS))
        self.assertEqual(summary.gaps, [SCHREMS])

    def test_list_collects_the_judgments_interpreting_the_acts(self):
        r = routes()
        r[eucaselaw.list_url(["31995L0046"])] = listing((SCHREMS, "2025-02-01T10:00:00Z"))
        summary = eucaselaw.run(FakeClient(r), self.args("--list", str(self.acts)))
        self.assertEqual(summary.written, [SCHREMS])
        self.assertEqual(summary.latest_modified, "2025-02-01T10:00:00.000Z")
        self.assertIsNone(summary.retry_from)

    def test_a_failure_holds_the_marker_before_the_judgment(self):
        r = routes()
        r[eucaselaw.list_url(["31995L0046"], "2025-01-01")] = listing(
            (SCHREMS, "2025-02-01T10:00:00Z"), (DIGITAL_RIGHTS, "2025-03-01T10:00:00Z"))
        summary = eucaselaw.run(FakeClient(r), self.args("--list", str(self.acts), "--changed-since", "2025-01-01"))
        self.assertEqual(summary.written, [SCHREMS])
        self.assertEqual(summary.failed, [DIGITAL_RIGHTS])
        self.assertEqual(summary.retry_from, "2025-03-01T09:59:59.999Z")

    def test_robots_disallow_blocks_before_any_query(self):
        client = FakeClient(routes(), robots=b"User-agent: *\nDisallow: /webapi/\n")
        summary = eucaselaw.run(client, self.args("--celex", SCHREMS))
        self.assertTrue(summary.blocked)
        self.assertEqual(client.urls, [eu.ROBOTS_URL])

    def test_blocked_mid_run_stops(self):
        r = routes()
        r[eucaselaw.metadata_url(SCHREMS)] = Blocked("HTTP 403")
        summary = eucaselaw.run(FakeClient(r), self.args("--celex", SCHREMS))
        self.assertTrue(summary.blocked)
        self.assertIn("403", json.loads(self.state.read_text())["blocked"])

    def test_changed_since_needs_a_list(self):
        with self.assertRaises(SystemExit):
            eucaselaw.parse_args(["--celex", SCHREMS, "--changed-since", "2025-01-01"])


if __name__ == "__main__":
    unittest.main()
