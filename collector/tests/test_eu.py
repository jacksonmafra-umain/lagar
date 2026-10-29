import hashlib
import io
import json
import tempfile
import unittest
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

from lagar import eu, frontmatter, schema
from lagar.http import Blocked

FIXTURES = Path(__file__).resolve().parent / "fixtures"
SPARQL = (FIXTURES / "eu-32016r0679-sparql.json").read_bytes()
XHTML = (FIXTURES / "eu-32016r0679.xhtml").read_bytes()
OLD_HTML = (FIXTURES / "eu-32004r0261.html").read_bytes()
CONSOLIDATED = (FIXTURES / "eu-02016r0679-20160504.xhtml").read_bytes()
GDPR = "32016R0679"
GDPR_CONS = "02016R0679-20160504"
MANIFESTATION = "https://publications.europa.eu/resource/cellar/3e485e15-11bd-11e6-ba9a-01aa75ed71a1.0024.03/DOC_1"
CONS_MANIFESTATION = "https://publications.europa.eu/resource/cellar/5f2552c2-cc45-11e6-ad7c-01aa75ed71a1.0019.03/DOC_2"
ROBOTS = b"User-agent: *\nAllow: /\nDisallow: /webdav/*\n"


def bindings(fields):
    rows = [
        {"field": {"type": "literal", "value": name}, "value": {"type": "literal", "value": value}}
        for name, values in fields.items()
        for value in values
    ]
    return json.dumps({"head": {"vars": ["field", "value"]}, "results": {"bindings": rows}}).encode()


def gdpr_fields():
    return eu.parse_metadata(GDPR, SPARQL).fields


def consolidated_sparql(**extra):
    fields = {
        "date_document": ["2016-05-04"],
        "eli": ["http://data.europa.eu/eli/reg/2016/679/2016-05-04"],
        "entry_into_force": ["2016-05-04"],
        "title_sv": [gdpr_fields()["title_sv"][0]],
        "manifestation_sv": ["fmx4", "xhtml", "pdfa2a"],
        "base_date_document": ["2016-04-27"],
    }
    fields.update(extra)
    return bindings(fields)


def http_error(url, code):
    return urllib.error.HTTPError(url, code, "err", {}, io.BytesIO(b""))


class FakeClient:
    """Routes: URL -> bytes, (bytes, content_type, final_url) or an exception."""

    def __init__(self, routes, robots=ROBOTS):
        self.routes = dict(routes)
        self.routes.setdefault(eu.ROBOTS_URL, robots)
        self.calls = []

    def fetch_final(self, url, headers=None):
        self.calls.append((url, dict(headers or {})))
        value = self.routes.get(url)
        if value is None:
            raise http_error(url, 404)
        if isinstance(value, Exception):
            raise value
        if isinstance(value, tuple):
            return value
        return value, None, url

    def get(self, url, headers=None):
        return self.fetch_final(url, headers)[0]

    @property
    def urls(self):
        return [url for url, _ in self.calls]


def gdpr_routes(sparql=SPARQL):
    return {
        eu.metadata_url(GDPR): sparql,
        eu.CELEX_URL.format(celex=GDPR): (XHTML, "application/xhtml+xml", MANIFESTATION.replace("https:", "http:")),
    }


class MetadataTest(unittest.TestCase):
    def test_query_is_for_one_celex_on_the_cellar_endpoint(self):
        url = eu.metadata_url(GDPR)
        self.assertTrue(url.startswith("https://publications.europa.eu/webapi/rdf/sparql?query="))
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)["query"][0]
        self.assertIn('"32016R0679"^^xsd:string', query)
        for bad in ("32016R0679R(02)", '32016R0679" } #', "52025PC0501", "62019CJ0311"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                eu.metadata_url(bad)

    def test_parse_recorded_result(self):
        md = eu.parse_metadata(GDPR, SPARQL)
        self.assertEqual(md.first("date_document"), "2016-04-27")
        self.assertEqual(sorted(md.all("agent")), ["CONSIL", "EP"])
        self.assertEqual(md.manifestations, {"xhtml", "fmx4", "pdfa1a"})
        self.assertEqual(md.consolidated, [GDPR_CONS])
        self.assertTrue(md.title.startswith("Europaparlamentets och rådets förordning (EU) 2016/679 av den 27 april"))

    def test_unknown_celex_is_an_error(self):
        with self.assertRaises(ValueError):
            eu.parse_metadata("32099R9999", bindings({}))

    def test_build_meta_for_gdpr(self):
        md = eu.parse_metadata(GDPR, SPARQL)
        meta = eu.build_meta(md, "a" * 64, MANIFESTATION, "2026-10-29T00:00:00Z")
        self.assertEqual(schema.validate(meta), [])
        expected = {
            "id": "eu-32016r0679",
            "type": "eu_regulation",
            "layer": "eu",
            "number": "(EU) 2016/679",
            "issued": "2016-04-27",
            "in_force": "2016-05-24",
            "repealed": None,
            "amended_by": [],
            "eli": "http://data.europa.eu/eli/reg/2016/679/oj",
            "language": "sv",
            "authoritative": True,
            "ministry": None,
            "issuer": "Europaparlamentet och Europeiska unionens råd",
            "celex": GDPR,
            "source": MANIFESTATION,
        }
        self.assertEqual({k: meta[k] for k in expected}, expected)

    def test_end_of_validity_and_amendments(self):
        fields = gdpr_fields()
        fields["end_of_validity"] = ["2024-01-01"]
        fields["amended_by"] = ["32018R1725", "32016R0679R(02)", "not a celex"]
        meta = eu.build_meta(eu.Metadata(GDPR, fields), "a" * 64, MANIFESTATION, "2026-10-29T00:00:00Z")
        self.assertEqual(meta["repealed"], "2024-01-01")
        self.assertEqual(meta["amended_by"], ["32016R0679R(02)", "32018R1725"])
        self.assertEqual(schema.validate(meta), [])

    def test_consolidated_version_is_not_authoritative(self):
        md = eu.parse_metadata(GDPR_CONS, consolidated_sparql())
        meta = eu.build_meta(md, "b" * 64, CONS_MANIFESTATION, "2026-10-29T00:00:00Z")
        self.assertEqual(schema.validate(meta), [])
        self.assertEqual((meta["id"], meta["number"], meta["issued"], meta["in_force"], meta["authoritative"]),
                         ("eu-02016r0679-20160504", "(EU) 2016/679", "2016-04-27", "2016-05-04", False))

    def test_latest_consolidated_applying_today(self):
        md = eu.Metadata(GDPR, {"consolidated": ["02016R0679-20160504", "02016R0679-20260801",
                                                  "02016R0679-20200101", "bogus"]})
        self.assertEqual(eu.latest_consolidated(md, date(2026, 7, 1)), "02016R0679-20200101")
        self.assertEqual(eu.latest_consolidated(md, date(2026, 8, 1)), "02016R0679-20260801")
        self.assertIsNone(eu.latest_consolidated(eu.Metadata(GDPR, {}), date(2026, 8, 1)))


class NumberTest(unittest.TestCase):
    def test_number_from_the_swedish_title(self):
        cases = {
            ("32016R0679", "Europaparlamentets och rådets förordning (EU) 2016/679 av den 27 april 2016 "
                           "om ... upphävande av direktiv 95/46/EG"): "(EU) 2016/679",
            ("32006R1907", "Europaparlamentets och rådets förordning (EG) nr 1907/2006 av den 18 december 2006"):
                "(EG) nr 1907/2006",
            ("32013R0952", "Europaparlamentets och rådets förordning (EU) nr 952/2013 av den 9 oktober 2013"):
                "(EU) nr 952/2013",
            ("32000L0060", "Europaparlamentets och rådets direktiv 2000/60/EG av den 23 oktober 2000"):
                "2000/60/EG",
            ("31995L0046", "Europaparlamentets och rådets direktiv 95/46/EG av den 24 oktober 1995"): "95/46/EG",
            ("32011D0833", "2011/833/EU: Kommissionens beslut av den 12 december 2011"): "2011/833/EU",
        }
        for (celex, title), number in cases.items():
            with self.subTest(celex=celex):
                self.assertEqual(eu.citation_number(celex, title), number)

    def test_title_disagreeing_with_celex_falls_back_to_derived_number(self):
        # The Swedish title of the whistleblower directive prints 2019/1936.
        title = "Europaparlamentets och rådets direktiv (EU) 2019/1936 av den 23 oktober 2019 om skydd för personer"
        self.assertEqual(eu.citation_number("32019L1937", title), "(EU) 2019/1937")
        self.assertEqual(eu.citation_number("32002L0058", None), "2002/58/EG")

    def test_derived_numbers(self):
        cases = {
            "32024R1689": "(EU) 2024/1689",
            "32022L2555": "(EU) 2022/2555",
            "32004R0261": "(EG) nr 261/2004",
            "32012R1215": "(EU) nr 1215/2012",
            "31991R0295": "(EEG) nr 295/1991",
            "31993L0013": "93/13/EEG",
            "32010L0013": "2010/13/EU",
        }
        for celex, number in cases.items():
            with self.subTest(celex=celex):
                self.assertEqual(eu.derived_number(celex), number)


class MarkdownTest(unittest.TestCase):
    def test_oj_xhtml(self):
        md = eu.to_markdown("Titel", XHTML)
        self.assertTrue(md.startswith("# Titel\n\n"))
        self.assertIn("\n\n## KAPITEL I\n\n**Allmänna bestämmelser**\n\n### Artikel 1\n\n**Syfte**\n\n1. I denna", md)
        self.assertIn("\n\na) utgör ett led i en verksamhet som inte omfattas av unionsrätten,\n\n", md)
        self.assertIn("\n\n(1) Skyddet för fysiska personer", md)
        self.assertIn("### Artikel 2", md)
        self.assertNotIn("L 119/1", md)  # Official Journal page header
        self.assertNotIn("Europeiska unionens officiella tidning", md)
        self.assertNotIn("  ", md)

    def test_old_eurlex_html_keeps_only_the_text(self):
        md = eu.to_markdown("Titel", OLD_HTML)
        self.assertNotIn("32004R0261", md)
        self.assertNotIn("Avis juridique", md)
        self.assertIn("\n\n### Artikel 1\n\nSyfte\n\n1. Denna förordning fastställer", md)
        self.assertIn("\n\n### Artikel 19\n\nIkraftträdande\n\n", md)
        self.assertIn("\n\na) Nekad ombordstigning mot deras vilja.\n\n", md)

    def test_consolidated_xhtml_drops_modification_markers(self):
        md = eu.to_markdown("Titel", CONSOLIDATED)
        self.assertIn("ingen rättslig verkan", md)
        self.assertNotIn("►", md)
        self.assertNotIn("▼", md)
        self.assertNotIn("02016R0679 — SV", md)
        self.assertIn("\n\n### Artikel 1\n\n**Syfte**\n\n1. I denna förordning", md)
        self.assertIn("\n\na) utgör ett led i en verksamhet", md)

    def test_headings_by_text_and_labels(self):
        html = (
            "<body><p>AVDELNING II</p><p>Artikel 3a</p><p>Rubrik</p>"
            "<table><tr><td><p>(i)</p></td><td><p>första</p></td></tr></table>"
            "<p>BILAGA I</p><p>Del 1</p><p>—</p></body>"
        ).encode()
        self.assertEqual(
            eu.to_markdown("T", html),
            "# T\n\n## AVDELNING II\n\n### Artikel 3a\n\nRubrik\n\n(i) första\n\n## BILAGA I\n\n## Del 1\n\n—\n",
        )

    def test_empty_text_is_an_error(self):
        with self.assertRaises(ValueError):
            eu.to_markdown("T", b"<html><head><title>x</title></head><body></body></html>")


class HostGuardTest(unittest.TestCase):
    def test_only_cellar_hosts(self):
        eu.check_host("https://publications.europa.eu/resource/celex/32016R0679")
        eu.check_host("https://op.europa.eu/robots.txt")
        for url in (
            "https://eur-lex.europa.eu/legal-content/SV/TXT/?uri=CELEX:32016R0679",
            "https://eur-lex.europa.eu/robots.txt",
            "https://publications.europa.eu.evil.example/x",
            "ftp://publications.europa.eu/x",
        ):
            with self.subTest(url=url), self.assertRaises(eu.ForbiddenHost):
                eu.check_host(url)

    def test_no_eurlex_url_in_the_module(self):
        for name in ("BASE", "ROBOTS_URL", "SPARQL_URL", "CELEX_URL"):
            self.assertNotIn("eur-lex", getattr(eu, name))

    def _redirect(self, target):
        request = urllib.request.Request("https://publications.europa.eu/resource/celex/32016R0679",
                                         headers={"Accept": "application/xhtml+xml"})
        return eu.CellarRedirects().redirect_request(request, None, 303, "See Other", {}, target)

    def test_redirects_to_eurlex_are_refused(self):
        with self.assertRaises(eu.ForbiddenHost):
            self._redirect("https://eur-lex.europa.eu/legal-content/SV/TXT/HTML/?uri=CELEX:32016R0679")

    def test_redirects_are_upgraded_to_https(self):
        new = self._redirect(MANIFESTATION.replace("https:", "http:"))
        self.assertEqual(new.full_url, MANIFESTATION)
        self.assertEqual(new.get_header("Accept"), "application/xhtml+xml")


class RunTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.corpus = self.tmp / "corpus"
        self.state = self.tmp / "state.json"
        self.manifest = self.tmp / "manifest.json"
        self.path = self.corpus / "eu" / "regulations" / "32016r0679.md"

    def args(self, *extra):
        return eu.parse_args(["--corpus", str(self.corpus), "--state", str(self.state),
                              "--manifest", str(self.manifest), *extra])

    def test_collects_one_act(self):
        client = FakeClient(gdpr_routes())
        report = self.tmp / "report.json"
        summary = eu.run(client, self.args("--celex", GDPR, "--report", str(report)))
        self.assertEqual(summary.written, [GDPR])
        self.assertEqual(client.urls, [eu.ROBOTS_URL, eu.metadata_url(GDPR), eu.CELEX_URL.format(celex=GDPR)])
        self.assertEqual(client.calls[1][1], {"Accept": "application/sparql-results+json"})
        self.assertEqual(client.calls[2][1], {"Accept": "application/xhtml+xml", "Accept-Language": "swe"})
        meta, body = frontmatter.load(self.path.read_text(encoding="utf-8"))
        self.assertEqual(schema.validate(meta), [])
        self.assertEqual(meta["source"], MANIFESTATION)
        self.assertEqual(meta["source_sha256"], hashlib.sha256(XHTML).hexdigest())
        self.assertTrue(body.startswith("# Europaparlamentets och rådets förordning (EU) 2016/679"))
        manifest = json.loads(self.manifest.read_text(encoding="utf-8"))
        [entry] = manifest["acts"]
        self.assertEqual((entry["celex"], entry["url"], entry["bytes"], entry["sha256"], entry["content_type"]),
                         (GDPR, MANIFESTATION, len(XHTML), hashlib.sha256(XHTML).hexdigest(),
                          "application/xhtml+xml"))
        self.assertEqual(json.loads(report.read_text())["written"], [GDPR])

    def test_rerun_skips_and_refresh_leaves_the_file_alone(self):
        eu.run(FakeClient(gdpr_routes()), self.args("--celex", GDPR))
        before = self.path.read_bytes()
        manifest_before = self.manifest.read_bytes()
        client = FakeClient(gdpr_routes())
        summary = eu.run(client, self.args("--celex", GDPR))
        self.assertEqual((summary.skipped, client.urls), (1, [eu.ROBOTS_URL]))
        summary = eu.run(FakeClient(gdpr_routes()), self.args("--celex", GDPR, "--refresh"))
        self.assertEqual(summary.unchanged, [GDPR])
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(self.manifest.read_bytes(), manifest_before)

    def test_pdf_only_act_is_a_gap_without_a_text_request(self):
        fields = gdpr_fields()
        fields["manifestation_sv"] = ["pdf", "print"]
        client = FakeClient(gdpr_routes(bindings(fields)))
        summary = eu.run(client, self.args("--celex", GDPR))
        self.assertEqual(summary.gaps, [GDPR])
        self.assertNotIn(eu.CELEX_URL.format(celex=GDPR), client.urls)
        self.assertFalse(self.path.exists())
        manifest = json.loads(self.manifest.read_text(encoding="utf-8"))
        self.assertEqual(manifest["gaps"], [{"celex": GDPR, "reason": "no Swedish XHTML or HTML manifestation "
                                                                      "(found: pdf, print)"}])
        # A later successful run clears the gap.
        eu.run(FakeClient(gdpr_routes()), self.args("--celex", GDPR))
        manifest = json.loads(self.manifest.read_text(encoding="utf-8"))
        self.assertEqual(manifest["gaps"], [])

    def test_no_swedish_expression_is_a_gap(self):
        fields = gdpr_fields()
        del fields["title_sv"], fields["manifestation_sv"]
        summary = eu.run(FakeClient(gdpr_routes(bindings(fields))), self.args("--celex", GDPR))
        self.assertEqual(summary.gaps, [GDPR])
        self.assertEqual(json.loads(self.state.read_text())["gaps"][GDPR], "no Swedish expression")

    def test_old_html_manifestation(self):
        celex = "32004R0261"
        fields = {"date_document": ["2004-02-11"], "entry_into_force": ["2005-02-17"],
                  "title_sv": ["Europaparlamentets och rådets förordning (EG) nr 261/2004 av den 11 februari 2004"],
                  "manifestation_sv": ["html", "pdf", "print"]}
        url = "https://publications.europa.eu/resource/cellar/439cd3a7-fd3c-4da7-8bf4-b0f60600c1d6.0011.01/DOC_1"
        client = FakeClient({eu.metadata_url(celex): bindings(fields),
                             eu.CELEX_URL.format(celex=celex): (OLD_HTML, "text/html", url)})
        summary = eu.run(client, self.args("--celex", celex))
        self.assertEqual(summary.written, [celex])
        self.assertEqual(client.calls[-1][1]["Accept"], "text/html")
        meta, _ = frontmatter.load((self.corpus / "eu/regulations/32004r0261.md").read_text(encoding="utf-8"))
        self.assertEqual((meta["number"], meta["eli"], meta["issuer"]), ("(EG) nr 261/2004", None, None))

    def test_wrong_content_type_fails_the_act(self):
        routes = gdpr_routes()
        routes[eu.CELEX_URL.format(celex=GDPR)] = (b"%PDF-1.4", "application/pdf", MANIFESTATION)
        summary = eu.run(FakeClient(routes), self.args("--celex", GDPR))
        self.assertEqual(summary.failed, [GDPR])
        self.assertIn("expected xhtml", json.loads(self.state.read_text())["failed"][GDPR])

    def test_text_answered_off_the_cellar_hosts_fails_the_act(self):
        routes = gdpr_routes()
        routes[eu.CELEX_URL.format(celex=GDPR)] = (XHTML, "application/xhtml+xml",
                                                   "https://eur-lex.europa.eu/legal-content/SV/TXT/HTML/")
        summary = eu.run(FakeClient(routes), self.args("--celex", GDPR))
        self.assertEqual(summary.failed, [GDPR])
        self.assertFalse(self.path.exists())

    def test_failures_are_per_act(self):
        routes = gdpr_routes()
        client = FakeClient(routes)
        summary = eu.run(client, self.args("--celex", "32099R0001," + GDPR))
        self.assertEqual((summary.failed, summary.written), (["32099R0001"], [GDPR]))

    def test_consolidated_collects_the_latest_version(self):
        routes = gdpr_routes()
        routes[eu.metadata_url(GDPR_CONS)] = consolidated_sparql()
        routes[eu.CELEX_URL.format(celex=GDPR_CONS)] = (CONSOLIDATED, "application/xhtml+xml", CONS_MANIFESTATION)
        older = self.corpus / "eu" / "regulations" / "02016r0679-20100101.md"
        older.parent.mkdir(parents=True)
        older.write_text("old", encoding="utf-8")
        summary = eu.run(FakeClient(routes), self.args("--celex", GDPR, "--consolidated"), today=date(2026, 10, 29))
        self.assertEqual(summary.written, [GDPR, GDPR_CONS])
        meta, body = frontmatter.load((self.corpus / "eu/regulations/02016r0679-20160504.md").read_text("utf-8"))
        self.assertFalse(meta["authoritative"])
        self.assertIn("ingen rättslig verkan", body)
        self.assertFalse(older.exists())
        # Rerun: the metadata is read again to find the latest version, nothing else.
        client = FakeClient(routes)
        summary = eu.run(client, self.args("--celex", GDPR, "--consolidated"), today=date(2026, 10, 29))
        self.assertEqual(summary.skipped, 2)
        self.assertEqual(client.urls, [eu.ROBOTS_URL, eu.metadata_url(GDPR), eu.metadata_url(GDPR_CONS)])

    def test_list_file(self):
        acts = self.tmp / "acts.json"
        acts.write_text(json.dumps([{"celex": GDPR, "name": "GDPR"}, {"celex": GDPR}]), encoding="utf-8")
        client = FakeClient(gdpr_routes())
        summary = eu.run(client, self.args("--list", str(acts)))
        self.assertEqual(summary.written, [GDPR])
        acts.write_text(json.dumps([{"celex": "not-a-celex"}]), encoding="utf-8")
        with self.assertRaises(eu.ListingError):
            eu.run(FakeClient({}), self.args("--list", str(acts)))

    def test_curated_list_is_valid(self):
        path = Path(__file__).resolve().parents[1] / "data" / "eu-acts.json"
        celexes = eu.load_list(path)
        self.assertEqual(len(celexes), len(set(celexes)))
        self.assertLessEqual(len(celexes), 50)

    def test_limit(self):
        summary = eu.run(FakeClient(gdpr_routes()), self.args("--celex", GDPR, "--limit", "0"))
        self.assertEqual(summary.written, [])

    def test_blocked_stops_and_records(self):
        routes = gdpr_routes()
        routes[eu.metadata_url(GDPR)] = Blocked("403 Forbidden")
        summary = eu.run(FakeClient(routes), self.args("--celex", GDPR + ",32022L2555"))
        self.assertTrue(summary.blocked)
        self.assertIn("403", json.loads(self.state.read_text())["blocked"])
        self.assertEqual(eu.main(["eu", "--celex", GDPR, "--corpus", str(self.corpus), "--state",
                                  str(self.state), "--manifest", str(self.manifest)],
                                 client=FakeClient(routes)), 2)

    def test_robots_disallow_blocks_before_any_query(self):
        client = FakeClient(gdpr_routes(), robots=b"User-agent: *\nDisallow: /webapi/\n")
        summary = eu.run(client, self.args("--celex", GDPR))
        self.assertTrue(summary.blocked)
        self.assertEqual(client.urls, [eu.ROBOTS_URL])

    def test_every_request_stays_on_the_cellar_hosts(self):
        routes = gdpr_routes()
        routes[eu.metadata_url(GDPR_CONS)] = consolidated_sparql()
        routes[eu.CELEX_URL.format(celex=GDPR_CONS)] = (CONSOLIDATED, "application/xhtml+xml", CONS_MANIFESTATION)
        client = FakeClient(routes)
        eu.run(client, self.args("--celex", GDPR, "--consolidated"), today=date(2026, 10, 29))
        for url in client.urls:
            self.assertIn(urllib.parse.urlsplit(url).hostname, eu.ALLOWED_HOSTS)

    def test_rate_below_one_second_is_refused(self):
        with self.assertRaises(SystemExit):
            eu.parse_args(["--celex", GDPR, "--rate", "0.5"])
        with self.assertRaises(SystemExit):
            eu.parse_args(["--celex", "eur-lex"])


if __name__ == "__main__":
    unittest.main()
