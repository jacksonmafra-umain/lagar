import io
import json
import tempfile
import unittest
import urllib.error
from email.message import Message
from pathlib import Path

from lagar import frontmatter, schema, services
from lagar.http import Blocked, Response

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def fixture(name):
    return (FIXTURES / f"service-{name}.html").read_bytes()


FK = "https://www.forsakringskassan.se"
FK_PAGE = FK + "/privatperson/familj-och-barn/foraldrapenning"
FK_NAV = FK + "/privatperson/familj-och-barn/barnbidrag-och-flerbarnstillagg"
POLISEN_PAGE = "https://polisen.se/tjanster-tillstand/pass-och-nationellt-id-kort/"
ALLOW_ALL = b"User-agent: *\nDisallow: /mina-sidor/\n"


def http_error(url, code, location=None):
    headers = Message()
    if location:
        headers["Location"] = location
    return urllib.error.HTTPError(url, code, "status", headers, io.BytesIO(b""))


class FakeClient:
    """Routes: URL -> bytes, (bytes, {header: value}) or an exception; anything else is a 404."""

    def __init__(self, routes):
        self.routes = dict(routes)
        self.calls = []
        self.intervals = []
        self.min_interval = 1.0

    def fetch_response(self, url, headers=None, data=None):
        self.calls.append(url)
        self.intervals.append(self.min_interval)
        value = self.routes.get(url)
        if value is None:
            raise http_error(url, 404)
        if isinstance(value, Exception):
            raise value
        body, extra = value if isinstance(value, tuple) else (value, {})
        message = Message()
        for key, header in extra.items():
            message[key] = header
        return Response(body, "text/html", url, message)


def entry(slug="foraldrapenning", source=FK_PAGE, **extra):
    base = {
        "slug": slug,
        "title": "Föräldrapenning",
        "issuer": "Försäkringskassan",
        "source": source,
        "service_url": None,
        "audience": ["private"],
        "topics": ["family"],
        "scope": "national",
        "based_on": ["sfs-2010-110"],
    }
    base.update(extra)
    return base


class LeadTest(unittest.TestCase):
    def page(self, name, url):
        return services.extract(fixture(name).decode("utf-8"), url)

    def test_forsakringskassan_uses_the_ingress_not_the_cookie_banner(self):
        page = self.page("forsakringskassan", FK_PAGE)
        self.assertEqual(page.lead, "Föräldrapenning är ersättning till dig som tar hand om ditt eller någon annans barn.")
        self.assertEqual(page.lead_source, "ingress")
        self.assertEqual(page.title, "Föräldrapenning - Försäkringskassan")

    def test_a_question_as_ingress_falls_back_to_the_meta_description(self):
        page = self.page("forsakringskassan-navigation", FK_NAV)
        self.assertEqual(page.lead, "Barnbidrag och flerbarnstillägg är ekonomiskt stöd till barnfamiljer. "
                                    "Läs vem som kan få ersättning och hur reglerna fungerar.")
        self.assertEqual(page.lead_source, "meta")

    def test_skatteverket_ingress(self):
        page = self.page("skatteverket", "https://www.skatteverket.se/privat/folkbokforing/namn/bytaefternamn.html")
        self.assertTrue(page.lead.startswith("Du kan både ändra, lägga till och ta bort efternamn."))
        self.assertTrue(page.lead.endswith("Du ansöker på någon av våra blanketter."))
        self.assertEqual(page.title, "Byta efternamn | Skatteverket")

    def test_polisen_preamble_with_entities(self):
        page = self.page("polisen", POLISEN_PAGE)
        self.assertEqual(page.lead, "Här hittar du information om pass, nationellt id-kort, id-kort för folkbokförda "
                                    "utan svensk medborgarskap och den statliga e-legitimationen SverigeID.")

    def test_transportstyrelsen_lead_block_not_the_truncated_meta(self):
        page = self.page("transportstyrelsen", "https://www.transportstyrelsen.se/sv/vagtrafik/korkort/")
        self.assertTrue(page.lead.startswith("Du behöver ett giltigt körkortstillstånd"))
        self.assertTrue(page.lead.endswith("ny körkortsbehörighet."))
        self.assertEqual(page.title, "Körkortstillstånd - Transportstyrelsen")

    def test_migrationsverket_intro(self):
        page = self.page("migrationsverket", "https://www.migrationsverket.se/du-vill-ansoka/arbeta.html")
        self.assertEqual(page.lead, "Du vill ansöka om arbetstillstånd eller uppehållstillstånd för att arbeta i "
                                    "Sverige, eller som medföljande familj till någon som arbetar.")

    def test_csn_ingress_as_published(self):
        page = self.page("csn", "https://www.csn.se/bidrag-och-lan/studiemedel.html")
        self.assertTrue(page.lead.startswith("Studiemedel består av två delar - ett bidrag som du får"))
        # Kept as published, the double full stop included.
        self.assertTrue(page.lead.endswith("från och med hösten det år du fyller 20.."))

    def test_arbetsformedlingen_ingress(self):
        page = self.page("arbetsformedlingen", "https://arbetsformedlingen.se/for-arbetsgivare/anmal-varsel")
        self.assertTrue(page.lead.startswith("Här anmäler du som arbetsgivare eller konkursbo varsel"))

    def test_lead_keeps_at_most_three_sentences(self):
        raw = ('<html><head><title>T</title></head><body><p class="ingress">Ett. Två är bra. Tre! '
               'Fyra? Fem.</p></body></html>')
        page = services.extract(raw, "https://www.skatteverket.se/x")
        self.assertEqual(page.lead, "Ett. Två är bra. Tre!")

    def test_unknown_host_reads_the_meta_description(self):
        raw = '<html><head><meta name="description" content="Kort &amp; tydligt."></head><body></body></html>'
        page = services.extract(raw, "https://example.se/x")
        self.assertEqual((page.lead, page.lead_source), ("Kort & tydligt.", "meta"))

    def test_a_page_without_a_lead_is_an_error(self):
        raw = '<html><head><meta name="description" content="Avkortad text..."></head><body></body></html>'
        with self.assertRaises(services.NoLead):
            services.extract(raw, "https://example.se/x")


class DocumentTest(unittest.TestCase):
    def test_meta_is_a_valid_public_service(self):
        page = services.extract(fixture("forsakringskassan").decode("utf-8"), FK_PAGE)
        meta = services.build_meta(entry(), page, "2026-11-13T10:00:00Z")
        self.assertEqual(schema.validate(meta), [])
        self.assertEqual((meta["id"], meta["number"], meta["type"], meta["layer"]),
                         ("service-foraldrapenning", "foraldrapenning", "public_service", "service"))
        self.assertEqual(meta["source"], FK_PAGE)
        self.assertEqual(meta["title"], "Föräldrapenning")
        self.assertEqual(meta["issuer"], "Försäkringskassan")
        self.assertEqual((meta["channels"], meta["issuer_org_number"], meta["template"]), ([], None, False))

    def test_body_is_heading_lead_and_link(self):
        page = services.extract(fixture("forsakringskassan").decode("utf-8"), FK_PAGE)
        body = services.to_markdown(entry(), page)
        self.assertEqual(body, "# Föräldrapenning\n\n"
                               "Föräldrapenning är ersättning till dig som tar hand om ditt eller någon annans barn.\n\n"
                               f"Källa: [Försäkringskassan]({FK_PAGE})\n")


class ListTest(unittest.TestCase):
    def write(self, data):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "services.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def test_loads_the_curated_list(self):
        path = Path(__file__).resolve().parents[1] / "data" / "services.json"
        entries = services.load_list(path)
        self.assertGreaterEqual(len(entries), 50)
        self.assertEqual(len({e["slug"] for e in entries}), len(entries))

    def test_rejects_duplicate_slugs_and_missing_fields(self):
        for data in ([entry(), entry()], [{k: v for k, v in entry().items() if k != "source"}],
                     [entry(slug="Bad Slug")], [entry(source="http://insecure.se/x")], {"slug": "x"}):
            with self.subTest(data=data), self.assertRaises(services.ListError):
                services.load_list(self.write(data))


class RunTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.list_path = self.root / "services.json"
        self.entries = [entry(), entry(slug="pass", title="Pass", issuer="Polismyndigheten", source=POLISEN_PAGE,
                                       based_on=["sfs-1978-302"])]
        self.list_path.write_text(json.dumps(self.entries), encoding="utf-8")

    def routes(self, **extra):
        routes = {
            FK + "/robots.txt": ALLOW_ALL,
            "https://polisen.se/robots.txt": b"User-agent: *\nDisallow:\n",
            FK_PAGE: (fixture("forsakringskassan"), {"Last-Modified": "Wed, 11 Nov 2026 08:00:00 GMT"}),
            POLISEN_PAGE: fixture("polisen"),
        }
        routes.update(extra)
        return routes

    def run_collector(self, client, *argv):
        report = self.root / "report.json"
        args = services.parse_args([
            "--list", str(self.list_path), "--state", str(self.root / "state.json"),
            "--manifest", str(self.root / "manifest.json"), "--corpus", str(self.root / "corpus"),
            "--report", str(report), *argv,
        ])
        summary = services.run(client, args)
        return summary, json.loads(report.read_text(encoding="utf-8"))

    def manifest(self):
        data = json.loads((self.root / "manifest.json").read_text(encoding="utf-8"))
        return {e["slug"]: e for e in data["entries"]}

    def corpus_file(self, slug):
        return self.root / "corpus" / "services" / f"service-{slug}.md"

    def test_writes_documents_manifest_and_state(self):
        summary, report = self.run_collector(FakeClient(self.routes()))
        self.assertEqual(summary.written, ["foraldrapenning", "pass"])
        self.assertEqual(report["written"], ["foraldrapenning", "pass"])
        meta, body = frontmatter.load(self.corpus_file("foraldrapenning").read_text(encoding="utf-8"))
        self.assertEqual(schema.validate(meta), [])
        self.assertIn("Föräldrapenning är ersättning", body)
        record = self.manifest()["foraldrapenning"]
        self.assertEqual((record["result"], record["status"], record["final_url"]), ("ok", 200, FK_PAGE))
        self.assertEqual(record["last_modified"], "Wed, 11 Nov 2026 08:00:00 GMT")
        self.assertEqual(record["sha256"], services.hashlib.sha256(fixture("forsakringskassan")).hexdigest())
        self.assertEqual(record["title"], "Föräldrapenning - Försäkringskassan")
        self.assertEqual(record["lead_source"], "ingress")
        self.assertIsNone(self.manifest()["pass"]["last_modified"])
        state = json.loads((self.root / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["done"], {"foraldrapenning": "ok", "pass": "ok"})

    def test_reads_robots_once_per_host_and_honours_crawl_delay(self):
        self.entries.append(entry(slug="vab", source=FK + "/privatperson/vab"))
        self.list_path.write_text(json.dumps(self.entries), encoding="utf-8")
        routes = self.routes(**{FK + "/privatperson/vab": fixture("forsakringskassan")})
        routes["https://polisen.se/robots.txt"] = b"User-agent: *\nCrawl-delay: 10\nDisallow:\n"
        client = FakeClient(routes)
        self.run_collector(client)
        self.assertEqual(client.calls.count(FK + "/robots.txt"), 1)
        self.assertEqual(client.intervals[client.calls.index(POLISEN_PAGE)], 10.0)
        self.assertEqual(client.intervals[client.calls.index(FK_PAGE)], 1.0)

    def test_unchanged_page_leaves_file_and_manifest_untouched(self):
        self.run_collector(FakeClient(self.routes()))
        path = self.corpus_file("foraldrapenning")
        before = path.read_bytes()
        manifest_before = (self.root / "manifest.json").read_bytes()
        mtime = path.stat().st_mtime_ns
        summary, _ = self.run_collector(FakeClient(self.routes()))
        self.assertEqual(summary.unchanged, ["foraldrapenning", "pass"])
        self.assertEqual(summary.written, [])
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(path.stat().st_mtime_ns, mtime)
        self.assertEqual((self.root / "manifest.json").read_bytes(), manifest_before)

    def test_changed_lead_rewrites_the_file(self):
        self.run_collector(FakeClient(self.routes()))
        changed = fixture("forsakringskassan").replace("någon annans barn".encode(), "ett annat barn".encode())
        summary, _ = self.run_collector(FakeClient(self.routes(**{FK_PAGE: changed})))
        self.assertEqual(summary.written, ["foraldrapenning"])
        self.assertIn("ett annat barn", self.corpus_file("foraldrapenning").read_text(encoding="utf-8"))

    def test_not_found_keeps_the_previous_file(self):
        self.run_collector(FakeClient(self.routes()))
        before = self.corpus_file("foraldrapenning").read_bytes()
        routes = self.routes()
        del routes[FK_PAGE]
        summary, report = self.run_collector(FakeClient(routes))
        self.assertEqual(self.corpus_file("foraldrapenning").read_bytes(), before)
        self.assertEqual([f["slug"] for f in report["failed"]], ["foraldrapenning"])
        self.assertEqual(report["failed"][0]["result"], "not_found")
        record = self.manifest()["foraldrapenning"]
        self.assertEqual((record["result"], record["status"]), ("not_found", 404))
        state = json.loads((self.root / "state.json").read_text(encoding="utf-8"))
        self.assertIn("foraldrapenning", state["failed"])

    def test_not_found_on_a_first_run_writes_nothing(self):
        routes = self.routes()
        routes[FK_PAGE] = http_error(FK_PAGE, 410)
        summary, _ = self.run_collector(FakeClient(routes))
        self.assertFalse(self.corpus_file("foraldrapenning").exists())
        self.assertEqual(summary.written, ["pass"])
        self.assertEqual(self.manifest()["foraldrapenning"]["status"], 410)

    def test_cross_host_redirect_is_not_followed_nor_stored(self):
        self.run_collector(FakeClient(self.routes()))
        before = self.corpus_file("foraldrapenning").read_bytes()
        elsewhere = "https://www.example.com/foraldrapenning"
        client = FakeClient(self.routes(**{FK_PAGE: http_error(FK_PAGE, 301, elsewhere)}))
        summary, report = self.run_collector(client)
        self.assertNotIn(elsewhere, client.calls)
        self.assertEqual(self.corpus_file("foraldrapenning").read_bytes(), before)
        meta, _ = frontmatter.load(before.decode("utf-8"))
        self.assertEqual(meta["source"], FK_PAGE)
        record = self.manifest()["foraldrapenning"]
        self.assertEqual((record["result"], record["status"], record["final_url"]), ("redirected", 301, elsewhere))
        self.assertEqual(report["failed"][0]["final_url"], elsewhere)

    def test_same_host_redirect_is_followed_and_reported_as_moved(self):
        moved = FK + "/privatperson/foraldrapenning-ny"
        routes = self.routes(**{FK_PAGE: http_error(FK_PAGE, 301, "/privatperson/foraldrapenning-ny"),
                                moved: fixture("forsakringskassan")})
        summary, report = self.run_collector(FakeClient(routes))
        self.assertIn("foraldrapenning", summary.written)
        meta, _ = frontmatter.load(self.corpus_file("foraldrapenning").read_text(encoding="utf-8"))
        self.assertEqual(meta["source"], FK_PAGE)
        self.assertEqual(self.manifest()["foraldrapenning"]["final_url"], moved)
        self.assertEqual(report["moved"], [{"slug": "foraldrapenning", "final_url": moved}])

    def test_same_host_redirect_into_a_disallowed_path_is_not_fetched(self):
        target = FK + "/mina-sidor/foraldrapenning"
        client = FakeClient(self.routes(**{FK_PAGE: http_error(FK_PAGE, 302, target)}))
        self.run_collector(client)
        self.assertNotIn(target, client.calls)
        self.assertEqual(self.manifest()["foraldrapenning"]["result"], "robots")

    def test_robots_forbidden_page_is_never_fetched(self):
        self.run_collector(FakeClient(self.routes()))
        before = self.corpus_file("foraldrapenning").read_bytes()
        routes = self.routes(**{FK + "/robots.txt": b"User-agent: *\nDisallow: /privatperson/\n"})
        client = FakeClient(routes)
        summary, report = self.run_collector(client)
        self.assertNotIn(FK_PAGE, client.calls)
        self.assertEqual(self.corpus_file("foraldrapenning").read_bytes(), before)
        self.assertEqual(self.manifest()["foraldrapenning"]["result"], "robots")
        self.assertEqual(report["failed"][0]["result"], "robots")

    def test_robots_redirect_on_the_same_host_is_followed(self):
        download = FK + "/download/robots.txt"
        routes = self.routes(**{FK + "/robots.txt": http_error(FK + "/robots.txt", 301, download),
                                download: b"User-agent: *\nDisallow: /privatperson/\n"})
        client = FakeClient(routes)
        self.run_collector(client)
        self.assertNotIn(FK_PAGE, client.calls)

    def test_blocked_host_is_recorded_and_left_alone(self):
        self.entries.append(entry(slug="vab", source=FK + "/privatperson/vab"))
        self.list_path.write_text(json.dumps(self.entries), encoding="utf-8")
        client = FakeClient(self.routes(**{FK_PAGE: Blocked("403 Forbidden")}))
        summary, report = self.run_collector(client)
        self.assertNotIn(FK + "/privatperson/vab", client.calls)
        self.assertEqual(summary.written, ["pass"])
        self.assertEqual(report["blocked_hosts"], ["www.forsakringskassan.se"])
        self.assertEqual({f["slug"]: f["result"] for f in report["failed"]},
                         {"foraldrapenning": "blocked", "vab": "blocked"})

    def test_network_error_is_a_failure_not_a_crash(self):
        routes = self.routes(**{FK_PAGE: urllib.error.URLError("timed out")})
        summary, report = self.run_collector(FakeClient(routes))
        self.assertEqual(report["failed"][0]["result"], "error")
        self.assertEqual(summary.written, ["pass"])

    def test_slug_and_limit_select_entries(self):
        client = FakeClient(self.routes())
        summary, _ = self.run_collector(client, "--slug", "pass")
        self.assertEqual(summary.written, ["pass"])
        self.assertNotIn(FK_PAGE, client.calls)
        summary, _ = self.run_collector(FakeClient(self.routes()), "--limit", "1")
        self.assertEqual(summary.written + summary.unchanged, ["foraldrapenning"])

    def test_unknown_slug_is_an_error(self):
        with self.assertRaises(services.ListError):
            self.run_collector(FakeClient(self.routes()), "--slug", "nope")

    def test_partial_run_keeps_other_manifest_entries(self):
        self.run_collector(FakeClient(self.routes()))
        self.run_collector(FakeClient(self.routes()), "--slug", "pass")
        self.assertEqual(sorted(self.manifest()), ["foraldrapenning", "pass"])

    def test_main_returns_2_when_a_host_blocks(self):
        client = FakeClient(self.routes(**{FK_PAGE: Blocked("403 Forbidden")}))
        code = services.main([
            "services", "--list", str(self.list_path), "--state", str(self.root / "state.json"),
            "--manifest", str(self.root / "manifest.json"), "--corpus", str(self.root / "corpus"),
        ], client=client)
        self.assertEqual(code, 2)


class RedirectOpenerTest(unittest.TestCase):
    def test_the_page_opener_does_not_follow_redirects(self):
        handler = services._NoRedirect()
        self.assertIsNone(handler.redirect_request(None, None, 301, "Moved", Message(), "https://elsewhere/"))


if __name__ == "__main__":
    unittest.main()
