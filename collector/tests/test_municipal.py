import gzip
import hashlib
import io
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path

from lagar import frontmatter, municipal, schema
from lagar.http import Blocked

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CONFIG = Path(__file__).resolve().parents[1] / "data" / "municipalities.json"
STHLM_LISTING = (FIXTURES / "municipal-0180-listing.html").read_bytes()
MALMO_LISTING = (FIXTURES / "municipal-1280-listing.html").read_bytes()
GBG_VIEW = (FIXTURES / "municipal-1480-view.xml").read_bytes()
GBG_DETAIL = (FIXTURES / "municipal-1480-detail.html").read_bytes()
PDF = b"%PDF-1.7\n% trimmed test document\n%%EOF\n"

STHLM_URL = (
    "https://start.stockholm/om-stockholms-stad/politik-och-demokrati/styrdokument/"
    "kommunal-forfattningssamling/"
)
STHLM_PDF = (
    "https://start.stockholm/globalassets/start/om-stockholms-stad/politik-och-demokrati/"
    "styrdokument/kommunal-forfattningssamling/"
    "kfs-2026-12-foreskrifter-for-avfallshantering-for-stockholms-stad.pdf"
)
MALMO_URL = (
    "https://malmo.se/Om-Malmo-stad/Demokrati-och-politik/Sa-styrs-Malmo/Forfattningssamling/"
    "Bestammelser-som-riktar-sig-till-dig-som-medborgare.html"
)
MALMO_TAXOR = (
    "https://malmo.se/Om-Malmo-stad/Demokrati-och-politik/Sa-styrs-Malmo/Forfattningssamling/"
    "Taxor-och-avgifter.html"
)
GBG_DB = "https://www4.goteborg.se/prod/Stadsledningskontoret/LIS/Verksamhetshandbok/Forfattn.nsf"
GBG_VIEW_URL = GBG_DB + "/vyHandBok?ReadViewEntries&ExpandView&Count=2000"
GBG_UNID = "94053E04792CC8EBC125828200346E1E"
GBG_DETAIL_URL = f"{GBG_DB}/0/{GBG_UNID}?OpenDocument"
GBG_PDF = f"{GBG_DB}//{GBG_UNID}/$File/C12574360024D6C7WEBVDTC22F.pdf?OpenElement"
MALMO_ROBOTS = (
    b"User-agent: *\nDisallow: /*.html.printable\n\nSitemap: https://malmo.se/sitemapindex.xml\n"
    b"Disallow: /download/*\n"
)


def http_error(url, code):
    return urllib.error.HTTPError(url, code, "err", {}, io.BytesIO(b""))


class FakeClient:
    """Routes: URL -> bytes, (bytes, content_type, final_url) or an exception."""

    def __init__(self, routes):
        self.routes = {
            "https://start.stockholm/robots.txt": b"User-agent: *\nSitemap: http://start.stockholm/sitemap.xml",
            "https://malmo.se/robots.txt": MALMO_ROBOTS,
            "https://www4.goteborg.se/robots.txt": b"User-agent: *\nDisallow: /prod/halmstad/\n",
            **routes,
        }
        self.calls = []

    def fetch_final(self, url, headers=None):
        self.calls.append(url)
        value = self.routes.get(url)
        if value is None:
            raise http_error(url, 404)
        if isinstance(value, Exception):
            raise value
        if isinstance(value, tuple):
            return value
        content_type = "application/pdf" if value.startswith(b"%PDF") else "text/html"
        return value, content_type, url


def sthlm_routes():
    routes = {STHLM_URL: STHLM_LISTING}
    for entry in municipal.parse_html_index(kommun("0180"), STHLM_LISTING, STHLM_URL)[0]:
        routes[entry.url] = PDF + entry.number.encode()
    return routes


def kommun(code):
    return municipal.load_config(CONFIG)[code]


class Args:
    def __init__(self, tmp, **kw):
        self.config = str(CONFIG)
        self.kommun = kw.pop("kommun", ["0180"])
        self.all = False
        self.limit = None
        self.refresh = False
        self.report = None
        self.state = str(Path(tmp) / "state.json")
        self.manifest = str(Path(tmp) / "manifest.json")
        self.corpus = str(Path(tmp) / "corpus")
        for key, value in kw.items():
            setattr(self, key, value)


class ConfigTest(unittest.TestCase):
    def test_pilot_config_loads(self):
        config = municipal.load_config(CONFIG)
        self.assertLessEqual({"0180", "1280", "1480"}, set(config))
        self.assertEqual(config["1480"].strategy, "domino_view")

    def write(self, tmp, kommuner):
        path = Path(tmp) / "config.json"
        path.write_text(json.dumps({"kommuner": kommuner}), encoding="utf-8")
        return path

    def test_kommun_must_be_in_its_region(self):
        entry = json.loads(CONFIG.read_text(encoding="utf-8"))["kommuner"]["0180"]
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(tmp, {"0180": {**entry, "region_code": "03"}})
            with self.assertRaisesRegex(municipal.ConfigError, "not in region"):
                municipal.load_config(path)

    def test_listing_must_be_on_a_configured_host(self):
        entry = json.loads(CONFIG.read_text(encoding="utf-8"))["kommuner"]["0180"]
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(tmp, {"0180": {**entry, "hosts": ["example.org"]}})
            with self.assertRaisesRegex(municipal.ConfigError, "configured host"):
                municipal.load_config(path)

    def test_unknown_strategy(self):
        entry = json.loads(CONFIG.read_text(encoding="utf-8"))["kommuner"]["0180"]
        with tempfile.TemporaryDirectory() as tmp:
            path = self.write(tmp, {"0180": {**entry, "strategy": "magic"}})
            with self.assertRaisesRegex(municipal.ConfigError, "unknown strategy"):
                municipal.load_config(path)


class RobotsTest(unittest.TestCase):
    def test_wildcards_and_rules_after_sitemap(self):
        robots = municipal.Robots(MALMO_ROBOTS.decode())
        self.assertFalse(robots.allows("https://malmo.se/download/18.1a/123/x.pdf"))
        self.assertFalse(robots.allows("https://malmo.se/a/b.html.printable"))
        self.assertTrue(robots.allows(MALMO_URL))

    def test_longest_match_and_allow_wins_ties(self):
        robots = municipal.Robots("User-agent: *\nDisallow: /a\nAllow: /a/b\nAllow: /c\nDisallow: /c\n")
        self.assertTrue(robots.allows("https://x.se/a/b/c"))
        self.assertFalse(robots.allows("https://x.se/a/x"))
        self.assertTrue(robots.allows("https://x.se/c"))

    def test_dollar_anchor(self):
        robots = municipal.Robots("User-agent: *\nDisallow: /*.pdf$\n")
        self.assertFalse(robots.allows("https://x.se/f.pdf"))
        self.assertTrue(robots.allows("https://x.se/f.pdf?x=1"))

    def test_own_group_wins_over_star(self):
        robots = municipal.Robots(
            "User-agent: *\nDisallow: /\n\nUser-agent: lagar-collector\nDisallow: /private/\n"
        )
        self.assertTrue(robots.allows("https://x.se/public"))
        self.assertFalse(robots.allows("https://x.se/private/x"))

    def test_other_agents_are_ignored(self):
        robots = municipal.Robots("User-agent: JoobleBot\nDisallow: /\nUser-agent: *\nDisallow: /x/\n")
        self.assertTrue(robots.allows("https://x.se/y"))
        self.assertFalse(robots.allows("https://x.se/x/1"))


class DecodingTest(unittest.TestCase):
    def test_gzip_and_identity(self):
        self.assertEqual(municipal._decode_body(gzip.compress(b"abc"), "gzip"), b"abc")
        self.assertEqual(municipal._decode_body(b"abc", None), b"abc")

    def test_stored_brotli_is_decoded(self):
        text = b"User-agent: *\r\nSitemap: http://start.stockholm/sitemap.xml"
        stream = b"\x8b\x1c\x80" + text + b"\x03"  # as start.stockholm sends robots.txt
        self.assertEqual(municipal._decode_body(stream, "br"), text)

    def test_compressed_or_truncated_brotli_is_refused(self):
        with self.assertRaises(municipal.UnsupportedEncoding):
            municipal._decode_body(b"\x0b\x02\x00\x41\x03", "br")  # compressed meta-block
        with self.assertRaises(municipal.UnsupportedEncoding):
            municipal._decode_body(b"\x8b\x1c\x80User", "br")
        with self.assertRaises(municipal.UnsupportedEncoding):
            municipal._decode_body(b"x", "zstd")

    def test_fetcher_retries_an_unsupported_encoding(self):
        class Flaky(FakeClient):
            def fetch_final(self, url, headers=None):
                if not self.calls:
                    self.calls.append(url)
                    raise municipal.UnsupportedEncoding("br")
                return super().fetch_final(url, headers)

        fetcher = municipal.Fetcher(Flaky({}))
        self.assertTrue(fetcher.allows(STHLM_URL))


class StockholmTest(unittest.TestCase):
    def test_listing_keeps_only_regulating_section_pdfs(self):
        entries, problems = municipal.parse_html_index(kommun("0180"), STHLM_LISTING, STHLM_URL)
        self.assertEqual(problems, [])
        self.assertEqual(
            [(e.number, e.title) for e in entries],
            [
                ("KFS 2026:12", "Föreskrifter för avfallshantering för Stockholms stad"),
                ("KFS 1995:46", "Hamnordning för Stockholms hamn"),
                ("KFS 2026:14", "Lokala ordningsföreskrifter för torghandeln i Stockholms stad"),
                ("KFS 2026:09", "Taxa för avfall under kommunalt ansvar för 2026"),
            ],
        )
        self.assertEqual(entries[0].url, STHLM_PDF)
        self.assertEqual(entries[0].listing_sha256, hashlib.sha256(STHLM_LISTING).hexdigest())

    def test_run_writes_valid_documents_and_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = Args(tmp, limit=2)
            summary = municipal.run(FakeClient(sthlm_routes()), args)
            self.assertEqual(summary.written, ["0180-kfs-2026-12", "0180-kfs-1995-46"])
            path = Path(args.corpus) / "municipality" / "regulations" / "0180-kfs-2026-12.md"
            meta, body = frontmatter.load(path.read_text(encoding="utf-8"))
            self.assertEqual(schema.validate(meta), [])
            self.assertEqual(meta["number"], "KFS 2026:12")
            self.assertEqual(meta["municipality_code"], "0180")
            self.assertEqual(meta["region_code"], "01")
            self.assertEqual(meta["issuer"], "Stockholms stad")
            self.assertEqual(meta["source"], STHLM_PDF)
            self.assertEqual(meta["source_sha256"], hashlib.sha256(PDF + b"KFS 2026:12").hexdigest())
            self.assertIn(f"- [Föreskrifter för avfallshantering för Stockholms stad](<{STHLM_PDF}>)", body)
            self.assertNotIn("inte hämtats", body)
            manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
            self.assertEqual([d["id"] for d in manifest["documents"]], ["0180-kfs-1995-46", "0180-kfs-2026-12"])
            self.assertEqual(manifest["gaps"], [])

    def test_rerun_skips_and_refresh_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = Args(tmp, limit=1)
            municipal.run(FakeClient(sthlm_routes()), args)
            path = Path(args.corpus) / "municipality" / "regulations" / "0180-kfs-2026-12.md"
            before = path.read_text(encoding="utf-8")
            again = municipal.run(FakeClient(sthlm_routes()), args)
            self.assertEqual(again.skipped, 1)
            self.assertEqual(again.written, ["0180-kfs-1995-46"])
            args.refresh, args.limit = True, None
            refreshed = municipal.run(FakeClient(sthlm_routes()), args)
            self.assertEqual(refreshed.written, ["0180-kfs-2026-14", "0180-kfs-2026-09"])
            self.assertEqual(sorted(refreshed.unchanged), ["0180-kfs-1995-46", "0180-kfs-2026-12"])
            self.assertEqual(path.read_text(encoding="utf-8"), before)

    def test_failed_document_is_recorded_and_run_continues(self):
        routes = sthlm_routes()
        routes[STHLM_PDF] = b"<html>not a pdf</html>"
        with tempfile.TemporaryDirectory() as tmp:
            args = Args(tmp, limit=1)
            summary = municipal.run(FakeClient(routes), args)
            self.assertEqual(summary.failed, ["0180-kfs-2026-12"])
            self.assertEqual(summary.written, ["0180-kfs-1995-46"])
            state = json.loads(Path(args.state).read_text(encoding="utf-8"))
            self.assertIn("expected a PDF", state["failed"]["0180-kfs-2026-12"])

    def test_403_blocks_the_kommun(self):
        routes = sthlm_routes()
        routes[STHLM_PDF] = Blocked("403 Forbidden")
        with tempfile.TemporaryDirectory() as tmp:
            args = Args(tmp, report=str(Path(tmp) / "report.json"))
            summary = municipal.run(FakeClient(routes), args)
            self.assertEqual(summary.written, [])
            self.assertIn("0180", summary.blocked)
            report = json.loads(Path(args.report).read_text(encoding="utf-8"))
            self.assertEqual(list(report["blocked"]), ["0180"])

    def test_listing_disallowed_by_robots_is_never_fetched(self):
        client = FakeClient({"https://start.stockholm/robots.txt": b"User-agent: *\nDisallow: /\n"})
        with tempfile.TemporaryDirectory() as tmp:
            summary = municipal.run(client, Args(tmp))
            self.assertIn("robots.txt disallows", summary.blocked["0180"])
            self.assertEqual(client.calls, ["https://start.stockholm/robots.txt"])

    def test_unreadable_robots_skips_the_kommun(self):
        client = FakeClient({"https://start.stockholm/robots.txt": http_error("x", 500)})
        with tempfile.TemporaryDirectory() as tmp:
            summary = municipal.run(client, Args(tmp))
            self.assertIn("robots.txt", summary.blocked["0180"])
            self.assertEqual(len(client.calls), 1)

    def test_redirect_off_the_configured_hosts_fails_the_document(self):
        routes = sthlm_routes()
        routes[STHLM_PDF] = (PDF, "application/pdf", "https://elsewhere.example/x.pdf")
        with tempfile.TemporaryDirectory() as tmp:
            summary = municipal.run(FakeClient(routes), Args(tmp, limit=1))
            self.assertEqual(summary.failed, ["0180-kfs-2026-12"])


class MalmoTest(unittest.TestCase):
    def test_listing_keeps_kommun_pdfs_in_citizen_sections(self):
        entries, problems = municipal.parse_html_index(kommun("1280"), MALMO_LISTING, MALMO_URL)
        self.assertEqual(problems, [])
        titles = [e.title for e in entries]
        self.assertIn("Lokala ordningsföreskrifter för Malmö kommun", titles)
        self.assertIn("Torghandelsstadga för Malmö kommun", titles)
        self.assertNotIn("Kontaktuppgifter", titles)  # under "Kontakta oss"
        self.assertTrue(all(e.url.startswith("https://malmo.se/download/") for e in entries))
        self.assertEqual(len(entries), 9)
        first = entries[0]
        self.assertEqual(first.number, "18.50574bcf196ed960a5523b7d")
        self.assertEqual(first.title, "Lokala föreskrifter för renhållning av gångbana")

    def test_robots_disallowed_pdfs_become_gaps_pointing_at_the_listing(self):
        client = FakeClient({MALMO_URL: MALMO_LISTING, MALMO_TAXOR: b"<html><h1>Taxor och avgifter</h1></html>"})
        with tempfile.TemporaryDirectory() as tmp:
            args = Args(tmp, kommun=["1280"], limit=2)
            summary = municipal.run(client, args)
            self.assertEqual(summary.written, ["1280-18-50574bcf196ed960a5523b7d", "1280-18-7413819a18bf1f2a7976451"])
            self.assertEqual(summary.gaps, summary.written)
            self.assertFalse(any("/download/" in url for url in client.calls))
            path = Path(args.corpus) / "municipality" / "regulations" / "1280-18-50574bcf196ed960a5523b7d.md"
            meta, body = frontmatter.load(path.read_text(encoding="utf-8"))
            self.assertEqual(schema.validate(meta), [])
            self.assertEqual(meta["source"], MALMO_URL)
            self.assertEqual(meta["source_sha256"], hashlib.sha256(MALMO_LISTING).hexdigest())
            self.assertIn("Dokumentet har inte hämtats: robots.txt disallows the document URL.", body)
            manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
            self.assertEqual(manifest["documents"], [])
            self.assertEqual(len(manifest["gaps"]), 2)


class GoteborgTest(unittest.TestCase):
    def test_view_keeps_regulations_and_fees_once(self):
        entries, _ = municipal.parse_domino_view(kommun("1480"), GBG_VIEW, GBG_VIEW_URL)
        self.assertEqual(
            [(e.number, e.title) for e in entries],
            [
                ("N010G00723", "Avgifter för undantag från föreskrifter för breda, långa och tunga fordon"),
                ("N010G00547", "Göteborgs Stads föreskrifter för avfallshantering"),
                ("N010G00545", "Lokala ordningsföreskrifter för Göteborgs Stad"),
            ],
        )
        self.assertEqual(entries[2].url, GBG_DETAIL_URL)

    def test_view_with_doctype_is_refused(self):
        with self.assertRaises(ValueError):
            municipal.parse_domino_view(kommun("1480"), b"<!DOCTYPE x [<!ENTITY a 'b'>]><x/>", GBG_VIEW_URL)

    def test_detail_page(self):
        detail = municipal.parse_detail(GBG_DETAIL, GBG_DETAIL_URL)
        self.assertEqual(detail.fields["serial"], "N010G00545")
        self.assertEqual(detail.fields["version"], "12")
        self.assertEqual(detail.fields["valid"], "2026-04-21")
        self.assertEqual(detail.fields["adopted_by"], "Kommunfullmäktige")
        self.assertEqual([url for url, _ in detail.attachments], [GBG_PDF])
        self.assertIn("Länsstyrelsen", detail.note)
        self.assertIn("- 16 §: Camping får inte ske på offentlig plats.", detail.note)

    def test_run_writes_document_from_detail_and_pdf(self):
        routes = {
            GBG_VIEW_URL: (GBG_VIEW, "text/xml", GBG_VIEW_URL),
            GBG_DETAIL_URL: GBG_DETAIL,
            GBG_PDF: PDF,
        }
        client = FakeClient(routes)
        with tempfile.TemporaryDirectory() as tmp:
            args = Args(tmp, kommun=["1480"])
            summary = municipal.run(client, args)
            self.assertEqual(summary.written, ["1480-n010g00545"])
            self.assertEqual(len(summary.failed), 2)  # the other detail pages answer 404 here
            path = Path(args.corpus) / "municipality" / "regulations" / "1480-n010g00545.md"
            meta, body = frontmatter.load(path.read_text(encoding="utf-8"))
            self.assertEqual(schema.validate(meta), [])
            self.assertEqual(meta["source"], GBG_PDF)
            self.assertEqual(meta["region_code"], "14")
            self.assertIn("Fastställd av: Kommunfullmäktige", body)
            self.assertIn("Gällande från: 2026-04-21", body)
            self.assertIn("## Uppgifter från kommunen", body)
            self.assertIn(f"Kommunens sida: <{GBG_DETAIL_URL}>", body)


class MainTest(unittest.TestCase):
    def test_bad_code_is_rejected(self):
        with self.assertRaises(SystemExit):
            municipal.parse_args(["--kommun", "9999"])

    def test_unknown_kommun_returns_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = Args(tmp)
            code = municipal.main(
                ["municipal", "--kommun", "0114", "--config", args.config, "--state", args.state,
                 "--manifest", args.manifest, "--corpus", args.corpus],
                client=FakeClient({}),
            )
            self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
