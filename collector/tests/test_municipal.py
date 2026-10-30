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
        self.posts = []

    def fetch_final(self, url, headers=None, data=None):
        self.calls.append(url)
        if data is not None:
            self.posts.append((url, json.loads(data)))
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

    def test_rerun_without_state_skips_documents_in_the_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = Args(tmp, limit=1)
            municipal.run(FakeClient(sthlm_routes()), args)
            Path(args.state).unlink()
            client = FakeClient(sthlm_routes())
            again = municipal.run(client, args)
            self.assertEqual(again.skipped, 1)
            self.assertEqual(again.written, ["0180-kfs-1995-46"])
            self.assertNotIn(STHLM_PDF, client.calls)

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


class RawLinkTest(unittest.TestCase):
    def test_spaces_and_letters_in_links_are_percent_encoded(self):
        listing = (
            '<h2>Reglerande styrdokument</h2><a href="/globalassets/start/kommunal-forfattningssamling/'
            'kfs 2024 Avfallstaxa för Stockholm.pdf">Avfallstaxa KFS 2024:3</a>'
        ).encode()
        entries, problems = municipal.parse_html_index(kommun("0180"), listing, STHLM_URL)
        self.assertEqual(problems, [])
        self.assertEqual(
            entries[0].url,
            "https://start.stockholm/globalassets/start/kommunal-forfattningssamling/"
            "kfs%202024%20Avfallstaxa%20f%C3%B6r%20Stockholm.pdf",
        )
        self.assertEqual(entries[0].number, "KFS 2024:3")

    def test_reference_without_semicolon_stays_literal(self):
        parser = municipal._PageLinks()
        parser.feed(
            '<a href="/rest-api/graph-service/preview?documentId=01B&currentPageId=4.6b&amp;name=Taxa.pdf">'
            "Taxa</a><a href='/x?a=1&#38;b=2'>X</a>"
        )
        parser.close()
        self.assertEqual([href for href, _ in parser.links], [
            "/rest-api/graph-service/preview?documentId=01B&currentPageId=4.6b&name=Taxa.pdf",
            "/x?a=1&b=2",
        ])


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


SV_BASE = "https://www.varmdo.se/kommunochpolitik/styrningmalochvisioner/forfattningssamling.4.3251048d16e2a7e78489c6e.html"
SV_ENTRY = {
    "name": "Värmdö",
    "issuer": "Värmdö kommun",
    "region_code": "01",
    "collection": "Värmdö kommuns författningssamling",
    "preset": "sitevision",
    "resident_filter": True,
    "hosts": ["www.varmdo.se"],
    "listings": [SV_BASE],
}


def sitevision_config(tmp, **overrides):
    path = Path(tmp) / "municipalities.json"
    path.write_text(json.dumps({"kommuner": {"0120": {**SV_ENTRY, **overrides}}}), encoding="utf-8")
    return str(path)


def sitevision_client():
    return FakeClient({
        "https://www.varmdo.se/robots.txt": b"User-agent: *\nDisallow: /*.html.printable\n",
        SV_BASE: (FIXTURES / "municipal-sitevision-listing.html").read_bytes(),
        SV_BASE + "?lp-page=1": (FIXTURES / "municipal-sitevision-listing.html").read_bytes(),
        SV_BASE + "?lp-page=2": (FIXTURES / "municipal-sitevision-page2.html").read_bytes(),
    })


class SitevisionPresetTest(unittest.TestCase):
    def test_preset_follows_pages_and_keeps_rules_for_residents(self):
        with tempfile.TemporaryDirectory() as tmp:
            kommun = municipal.load_config(sitevision_config(tmp))["0120"]
            client = sitevision_client()
            entries, problems = municipal.list_entries(municipal.Fetcher(client), kommun)
        self.assertEqual(problems, [])
        self.assertEqual(
            [(municipal.corpus_id("0120", e.number), e.title) for e in entries],
            [
                ("0120-18-3a91f79168a7ed2a564f420",
                 "Allmänna bestämmelser för användande av Värmdö kommuns allmänna vatten- och "
                 "avloppsanläggning (ABVA)"),
                ("0120-18-22e4ee451639ed6e2d8af1d4", "Avfallsföreskrifter"),
                ("0120-18-eece1c7193dec9019b60b8", "Avfallstaxa"),
                ("0120-18-22e4ee451639ed6e2d8af1d8", "Lokala ordningsföreskrifter för Värmdö kommun"),
                ("0120-18-4cdf0adf19b2bcf6e2a1676", "Taxa för livsmedelskontroll"),
            ],
        )
        self.assertFalse(any("printable" in url for url in client.calls))

    def test_own_keys_override_the_preset(self):
        with tempfile.TemporaryDirectory() as tmp:
            kommun = municipal.load_config(
                sitevision_config(tmp, follow="", title_include=["avfall"], title_exclude=["plan"])
            )["0120"]
            entries, _ = municipal.list_entries(municipal.Fetcher(sitevision_client()), kommun)
        self.assertEqual([e.title for e in entries], ["Avfallsföreskrifter", "Avfallstaxa"])

    def test_files_in_embedded_module_state_are_listed_under_their_heading(self):
        olofstrom = "https://olofstrom.se/kommun-och-politik/kommunfakta/styrande-dokument"
        with tempfile.TemporaryDirectory() as tmp:
            config = sitevision_config(
                tmp, hosts=["olofstrom.se"], listings=[olofstrom], resident_filter=False,
                sections=["Föreskrifter"],
            )
            kommun = municipal.load_config(config)["0120"]
        raw = (FIXTURES / "municipal-sitevision-state.html").read_bytes()
        entries, problems = municipal.parse_html_index(kommun, raw, olofstrom)
        self.assertEqual(problems, [])
        self.assertEqual(
            [(e.number, e.title) for e in entries],
            [
                ("18.506734c51817fe18b912cee", "Föreskrift för avfallshantering"),
                ("18.30eb2ed016f19a67e6c2ca27", "lokala-ordningsforeskrifter-for-torghandel"),
            ],
        )
        kommun.embedded_json = False
        self.assertEqual(municipal.parse_html_index(kommun, raw, olofstrom)[0], [])

    def test_non_ascii_links_are_percent_encoded(self):
        self.assertEqual(
            municipal._uri("https://www.vetlanda.se/styrdokument?letter=Ö&x=%C3%A5"),
            "https://www.vetlanda.se/styrdokument?letter=%C3%96&x=%C3%A5",
        )
        self.assertEqual(municipal._uri("https://a.se/b%20c.pdf"), "https://a.se/b%20c.pdf")

    def test_resident_filter_matches_compound_taxa(self):
        with tempfile.TemporaryDirectory() as tmp:
            kommun = municipal.load_config(sitevision_config(tmp))["0120"]
        self.assertTrue(municipal.binds_residents(kommun, "Plan- och byggtaxa 2025"))
        self.assertTrue(municipal.binds_residents(kommun, "Livsmedelstaxa"))
        self.assertFalse(municipal.binds_residents(kommun, "Taxonomi för arkivet"))

    def test_decomposed_titles_are_normalised_before_filtering(self):
        with tempfile.TemporaryDirectory() as tmp:
            kommun = municipal.load_config(sitevision_config(tmp))["0120"]
        decomposed = "A\u0308gardirektiv fo\u0308r bolaget.pdf"
        self.assertEqual(municipal._title(kommun, decomposed), "Ägardirektiv för bolaget")
        self.assertFalse(municipal.binds_residents(kommun, municipal._title(kommun, decomposed)))
        self.assertTrue(municipal.binds_residents(kommun, municipal._title(kommun, "Avfallsfo\u0308reskrifter")))

    def test_unknown_preset_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(municipal.ConfigError):
                municipal.load_config(sitevision_config(tmp, preset="episerver"))

    def test_dry_run_lists_without_fetching_documents(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = Args(tmp, kommun=["0120"], config=sitevision_config(tmp))
            client, out = sitevision_client(), io.StringIO()
            self.assertEqual(municipal.dry_run(client, args, out), 0)
            self.assertFalse(Path(args.corpus).exists())
        self.assertFalse(any("/download/" in url for url in client.calls))
        self.assertIn("0120-18-22e4ee451639ed6e2d8af1d4\tAvfallsföreskrifter\t", out.getvalue())


PAGES_BASE = "https://www.oskarshamn.se/mer-om-kommunen/forfattningssamling/"
PAGES_ENTRY = {
    "name": "Oskarshamn",
    "issuer": "Oskarshamns kommun",
    "region_code": "08",
    "collection": "Författningssamling och styrande dokument",
    "strategy": "html_pages",
    "resident_filter": True,
    "hosts": ["www.oskarshamn.se"],
    "listings": [PAGES_BASE],
    "sections": ["Kommunala taxor och avgifter", "Andra taxor och avgifter"],
    "link_pattern": "^https://www\\.oskarshamn\\.se/mer-om-kommunen/forfattningssamling/[^#?]+/$",
    "number": [{"from": "href", "pattern": "/([^/]+)/$"}],
    "document_pattern": "\\.pdf$",
}
PAGES_PDF = (
    "https://www.oskarshamn.se/download/18.4f1e2/1700000000000/Lokala%20ordningsf%C3%B6reskrifter.pdf"
)


def pages_client():
    rule = (FIXTURES / "municipal-pages-rule.html").read_bytes()
    return FakeClient({
        PAGES_BASE: (FIXTURES / "municipal-pages-listing.html").read_bytes(),
        PAGES_BASE + "taxor-och-avgifter/avgifter-ekonomi/": rule,
        PAGES_BASE + "taxor-och-avgifter/va-taxa/": b"<html><main><h1>VA-taxa</h1><p>Se taxan.</p></main></html>",
        PAGES_BASE + "lokala-ordningsforeskrifter/": (FIXTURES / "municipal-pages-pdf.html").read_bytes(),
        PAGES_PDF: PDF,
    })


class HtmlPagesTest(unittest.TestCase):
    def config(self, tmp, **overrides):
        path = Path(tmp) / "municipalities.json"
        path.write_text(json.dumps({"kommuner": {"0882": {**PAGES_ENTRY, **overrides}}}), encoding="utf-8")
        return str(path)

    def test_listing_keeps_rule_pages_in_resident_sections(self):
        with tempfile.TemporaryDirectory() as tmp:
            kommun = municipal.load_config(self.config(tmp))["0882"]
        raw = (FIXTURES / "municipal-pages-listing.html").read_bytes()
        entries, problems = municipal.parse_html_index(kommun, raw, PAGES_BASE)
        self.assertEqual(problems, [])
        self.assertEqual([(e.number, e.title) for e in entries], [
            ("avgifter-ekonomi", "Avgifter Ekonomi"),
            ("va-taxa", "VA-taxa"),
            ("lokala-ordningsforeskrifter", "Lokala ordningsföreskrifter"),
        ])

    def test_page_text_and_linked_documents(self):
        with tempfile.TemporaryDirectory() as tmp:
            kommun = municipal.load_config(self.config(tmp, content_id="content"))["0882"]
        page = municipal.parse_page(kommun, (FIXTURES / "municipal-pages-pdf.html").read_bytes(),
                                    PAGES_BASE + "lokala-ordningsforeskrifter/")
        self.assertEqual(page.attachments, [(PAGES_PDF, "Lokala ordningsföreskrifter (pdf)")])
        self.assertIn("antog de lokala ordningsföreskrifterna", page.note)
        rule = municipal.parse_page(kommun, (FIXTURES / "municipal-pages-rule.html").read_bytes(), PAGES_BASE)
        self.assertTrue(rule.note.startswith("### Avgifter Ekonomi"))
        self.assertIn("- Aviseringsavgift – 60 kronor", rule.note)
        for noise in ("Start", "Skriv ut", "Senast granskad", "572 80"):
            self.assertNotIn(noise, rule.note)

    def test_run_writes_page_text_or_pdf_and_skips_empty_pages(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = Args(tmp, kommun=["0882"], config=self.config(tmp))
            summary = municipal.run(pages_client(), args)
            self.assertEqual(summary.written, ["0882-avgifter-ekonomi", "0882-lokala-ordningsforeskrifter"])
            self.assertEqual(summary.failed, ["0882-va-taxa"])
            folder = Path(args.corpus) / "municipality" / "regulations"
            meta, body = frontmatter.load((folder / "0882-avgifter-ekonomi.md").read_text(encoding="utf-8"))
            self.assertEqual(schema.validate(meta), [])
            self.assertEqual(meta["source"], PAGES_BASE + "taxor-och-avgifter/avgifter-ekonomi/")
            self.assertIn("## Text", body)
            self.assertNotIn("## Dokument", body)
            text = body.split("Texten är hämtad från kommunens webbsida.\n\n", 1)[1].rstrip("\n")
            self.assertEqual(meta["source_sha256"], hashlib.sha256(text.encode()).hexdigest())
            meta, body = frontmatter.load((folder / "0882-lokala-ordningsforeskrifter.md").read_text(encoding="utf-8"))
            self.assertEqual(meta["source"], PAGES_PDF)
            self.assertIn("## Uppgifter från kommunen", body)
            self.assertIn(f"(<{PAGES_PDF}>)", body)
            manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
            kinds = {d["id"]: d["content_type"] for d in manifest["documents"]}
            self.assertEqual(kinds, {"0882-avgifter-ekonomi": "text/markdown",
                                     "0882-lokala-ordningsforeskrifter": "application/pdf"})

    def test_html_pages_needs_link_pattern_and_number(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(municipal.ConfigError):
                municipal.load_config(self.config(tmp, number=[]))


DOCWEB = "https://dokument.example.se"
DOCWEB_FOLDER = DOCWEB + "/api/folders/64fda324"
DOCWEB_ENTRY = {
    "name": "Exempla", "issuer": "Exempla kommun", "region_code": "19",
    "collection": "Exempla kommuns taxor och föreskrifter", "strategy": "json_list",
    "hosts": ["dokument.example.se"], "listings": [DOCWEB_FOLDER], "resident_filter": True,
    "items": "documents", "title_field": "name", "number_field": "id",
    "url_template": "/api/download/{id}/{folderId}",
}
DOCWEB_LIST = json.dumps({"id": "64fda324", "folders": [], "documents": [
    {"id": "e3b7", "folderId": "64fda324", "name": "Lokala ordningsfo\u0308reskrifter 2024", "extension": ".pdf"},
    {"id": "a1c2", "folderId": "64fda324", "name": "Avfallstaxa 2026", "extension": ".pdf"},
    {"id": "b9d0", "folderId": "64fda324", "name": "Policy för föreningsbidrag", "extension": ".pdf"},
    {"id": "", "folderId": "64fda324", "name": "Taxa utan id", "extension": ".pdf"},
]}).encode()
WPFD_ENTRY = {
    **DOCWEB_ENTRY, "hosts": ["example.se"],
    "listings": ["https://example.se/wp-admin/admin-ajax.php?action=wpfd&task=files.display&id=190"],
    "items": "files", "title_field": "post_title", "number_field": "ID", "url_template": "{linkdownload}",
}
WPFD_LIST = json.dumps({"files": [
    {"ID": 18192, "post_title": "Renhållningstaxa 2025", "ext": "pdf",
     "linkdownload": "https://example.se/laddaner/190/taxor/18192/renhallningstaxa-2025.pdf"},
    {"ID": 18193, "post_title": "Avgift för bygglov", "ext": "pdf"},
]}).encode()


class JsonListTest(unittest.TestCase):
    def config(self, tmp, entry):
        path = Path(tmp) / "municipalities.json"
        path.write_text(json.dumps({"kommuner": {"1961": entry}}), encoding="utf-8")
        return str(path)

    def test_document_list_builds_links_from_item_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            kommun = municipal.load_config(self.config(tmp, DOCWEB_ENTRY))["1961"]
        entries, problems = municipal.parse_json_list(kommun, DOCWEB_LIST, DOCWEB_FOLDER)
        self.assertEqual([(e.number, e.title, e.url) for e in entries], [
            ("e3b7", "Lokala ordningsföreskrifter 2024", DOCWEB + "/api/download/e3b7/64fda324"),
            ("a1c2", "Avfallstaxa 2026", DOCWEB + "/api/download/a1c2/64fda324"),
        ])
        self.assertEqual(problems, [DOCWEB + "/api/download//64fda324"])

    def test_item_without_a_template_field_is_a_problem(self):
        with tempfile.TemporaryDirectory() as tmp:
            kommun = municipal.load_config(self.config(tmp, WPFD_ENTRY))["1961"]
        entries, problems = municipal.parse_json_list(kommun, WPFD_LIST, WPFD_ENTRY["listings"][0])
        self.assertEqual([(e.number, e.url) for e in entries],
                         [("18192", "https://example.se/laddaner/190/taxor/18192/renhallningstaxa-2025.pdf")])
        self.assertEqual(problems, ["Avgift för bygglov"])

    def test_run_writes_the_pdfs(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = Args(tmp, kommun=["1961"], config=self.config(tmp, DOCWEB_ENTRY))
            client = FakeClient({
                DOCWEB_FOLDER: (DOCWEB_LIST, "application/json", DOCWEB_FOLDER),
                DOCWEB + "/api/download/e3b7/64fda324": PDF + b"1",
                DOCWEB + "/api/download/a1c2/64fda324": PDF + b"2",
            })
            summary = municipal.run(client, args)
            self.assertEqual(sorted(summary.written), ["1961-a1c2", "1961-e3b7"])
            folder = Path(args.corpus) / "municipality" / "regulations"
            meta, _ = frontmatter.load((folder / "1961-e3b7.md").read_text(encoding="utf-8"))
            self.assertEqual(schema.validate(meta), [])
            self.assertEqual(meta["source"], DOCWEB + "/api/download/e3b7/64fda324")

    def test_list_in_a_next_js_page(self):
        entry = {**DOCWEB_ENTRY, "hosts": ["www.example.se", "static.example.se"],
                 "listings": ["https://www.example.se/forfattningssamling/"], "embedded": "next",
                 "items": "ordinancePages", "title_field": "Heading", "number_field": "Id",
                 "number_pattern": "^([0-9a-f-]{36})", "url_template": "{FileUrl}"}
        pages = [
            {"Heading": "Avfallsföreskrifter", "FileUrl": "https://static.example.se/avfallsforeskrifter.pdf",
             "Id": "0f1e2d3c-4b5a-6978-8091-a2b3c4d5e6f7_sv_Published"},
            {"Heading": "Riktlinje för donationer", "FileUrl": "https://static.example.se/riktlinje.pdf",
             "Id": "11111111-2222-3333-4444-555555555555_sv_Published"},
        ]
        flight = '3c:["$","main",null,{"children":[["$","$L3f",null,{"ordinancePages":' + json.dumps(pages) + "}]]}]"
        half = len(flight) // 2  # the data arrives in several pushes
        html = "".join(f"<script>self.__next_f.push([1,{json.dumps(part)}])</script>"
                       for part in (flight[:half], flight[half:])).encode()
        with tempfile.TemporaryDirectory() as tmp:
            kommun = municipal.load_config(self.config(tmp, entry))["1961"]
            with self.assertRaises(municipal.ConfigError):
                municipal.load_config(self.config(tmp, {**entry, "embedded": "nuxt"}))
        entries, problems = municipal.parse_json_list(kommun, html, entry["listings"][0])
        self.assertEqual([(e.number, e.title, e.url) for e in entries], [
            ("0f1e2d3c-4b5a-6978-8091-a2b3c4d5e6f7", "Avfallsföreskrifter",
             "https://static.example.se/avfallsforeskrifter.pdf")])
        self.assertEqual(problems, [])

    def test_a_listing_with_its_own_settings(self):
        page = "https://www.example.se/taxor/"
        lst = "https://www.example.se/forfattningssamling/"
        entry = {"name": "Exempla", "issuer": "Exempla kommun", "region_code": "19", "collection": "Exempla",
                 "strategy": "html_index", "hosts": ["www.example.se", "static.example.se"],
                 "link_pattern": "^https://static\\.example\\.se/.+\\.pdf$",
                 "number": [{"from": "href", "pattern": "/([^/]+)\\.pdf$"}],
                 "listings": [page, {"url": lst, "strategy": "json_list", "embedded": "next",
                                     "items": "ordinancePages", "title_field": "Heading", "number_field": "Id",
                                     "url_template": "{FileUrl}"}]}
        with tempfile.TemporaryDirectory() as tmp:
            kommun = municipal.load_config(self.config(tmp, entry))["1961"]
            bad = {**entry, "listings": [page, {"url": lst, "strategy": "domino_view"}]}
            with self.assertRaises(municipal.ConfigError):
                municipal.load_config(self.config(tmp, bad))
        self.assertEqual(kommun.listings, [page, lst])
        self.assertEqual(kommun.strategy, "html_index")
        self.assertEqual(kommun.listing_settings[lst].strategy, "json_list")
        items = [{"Heading": "Avfallsföreskrifter", "FileUrl": "https://static.example.se/avfall.pdf", "Id": "a1"}]
        flight = json.dumps('x:{"ordinancePages":' + json.dumps(items) + "}")
        pages = {page: b'<h2>Taxor</h2><a href="https://static.example.se/va-taxa.pdf">VA-taxa</a>',
                 lst: f"<script>self.__next_f.push([1,{flight}])</script>".encode()}

        class Pages:
            def fetch_final(self, url, headers=None):
                if url not in pages:
                    raise urllib.error.HTTPError(url, 404, "missing", {}, io.BytesIO(b""))
                return pages[url], "text/html", url

        entries, problems = municipal.list_entries(municipal.Fetcher(Pages()), kommun)
        self.assertEqual(sorted((e.number, e.title) for e in entries),
                         [("a1", "Avfallsföreskrifter"), ("va-taxa", "VA-taxa")])
        self.assertEqual(problems, [])

    def test_json_list_needs_its_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(municipal.ConfigError):
                municipal.load_config(self.config(tmp, {**DOCWEB_ENTRY, "url_template": ""}))


def _config(tmp, code, entry):
    path = Path(tmp) / "municipalities.json"
    path.write_text(json.dumps({"kommuner": {code: entry}}), encoding="utf-8")
    return municipal.load_config(str(path))[code]


TORSAS = {
    "name": "Torsås", "issuer": "Torsås kommun", "region_code": "08", "collection": "Samlade styrdokument",
    "strategy": "html_index", "resident_filter": True, "row_titles": True, "hosts": ["www.torsas.se"],
    "listings": ["https://www.torsas.se/styrdokument/"],
    "link_pattern": "/wp-content/uploads/.+\\.pdf$",
    "number": [{"from": "href", "pattern": "/([^/]+)\\.pdf$"}],
}
UPPSALA = {
    "name": "Uppsala", "issuer": "Uppsala kommun", "region_code": "03", "collection": "Styrdokument",
    "strategy": "html_pages", "resident_filter": True, "page_titles": True, "hosts": ["www.uppsala.se"],
    "listings": ["https://www.uppsala.se/sitemaps.xml"], "follow": "/sitemap\\d+\\.xml$",
    "link_pattern": "^https://www\\.uppsala\\.se/kommun-och-politik/publikationer/styrdokument/[^/]+/$",
    "number": [{"from": "href", "pattern": "/styrdokument/([^/]+)/$"}],
    "document_pattern": "/contentassets/.+\\.pdf$",
}
UPPSALA_PAGE = (
    "<html><body><main><nav><a href='/'>Start</a> Kommun och politik</nav>"
    "<h1>Lokala ordningsföreskrifter för Uppsala kommun</h1><p>Föreskrifterna gäller från 1 juli 2026.</p>"
    "<a href='/contentassets/d4f7/lokala-ordningsforeskrifter.pdf'>Lokala ordningsföreskrifter (pdf)</a>"
    "</main></body></html>"
).encode()
UPPSALA_ARCHIVE = (
    "<html><body><main><h1>Arkivreglemente för Uppsala kommun</h1><p>Reglementet styr arkivvården.</p>"
    "<a href='/contentassets/aa/arkivreglemente.pdf'>Arkivreglemente (pdf)</a></main></body></html>"
).encode()


class ListingOptionsTest(unittest.TestCase):
    def test_row_titles_come_from_the_other_cells(self):
        with tempfile.TemporaryDirectory() as tmp:
            kommun = _config(tmp, "0834", TORSAS)
        raw = (FIXTURES / "municipal-rows-listing.html").read_bytes()
        entries, problems = municipal.parse_html_index(kommun, raw, TORSAS["listings"][0])
        self.assertEqual(problems, [])
        self.assertEqual([(e.number, e.title) for e in entries], [
            ("Lokala-ordningsforeskrifter", "Lokala ordningsföreskrifter för Torsås kommun KF 2025-12-15"),
            ("Avfallstaxa-2026", "Avfallstaxa 2026"),
        ])

    def test_sitemap_listing_with_titles_and_filter_from_the_rule_page(self):
        base = "https://www.uppsala.se/kommun-och-politik/publikationer/styrdokument/"
        client = FakeClient({
            "https://www.uppsala.se/robots.txt": b"User-agent: *\nDisallow: /search/\n",
            "https://www.uppsala.se/sitemaps.xml": (FIXTURES / "municipal-sitemap-index.xml").read_bytes(),
            "https://www.uppsala.se/sitemap1.xml": (FIXTURES / "municipal-sitemap.xml").read_bytes(),
            base + "lokala-ordningsforeskrifter/": UPPSALA_PAGE,
            base + "arkivreglemente/": UPPSALA_ARCHIVE,
            "https://www.uppsala.se/contentassets/d4f7/lokala-ordningsforeskrifter.pdf": PDF,
        })
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "m.json"
            path.write_text(json.dumps({"kommuner": {"0380": UPPSALA}}), encoding="utf-8")
            args = Args(tmp, kommun=["0380"], config=str(path))
            summary = municipal.run(client, args)
            self.assertEqual(summary.written, ["0380-lokala-ordningsforeskrifter"])
            self.assertEqual(summary.skipped, 1)
            self.assertNotIn("https://www.uppsala.se/sitemap-news.xml", client.calls)
            meta, body = frontmatter.load(next((Path(args.corpus) / "municipality" / "regulations").glob("*.md"))
                                          .read_text(encoding="utf-8"))
            self.assertEqual(meta["title"], "Lokala ordningsföreskrifter för Uppsala kommun")
            self.assertEqual(meta["source"], "https://www.uppsala.se/contentassets/d4f7/lokala-ordningsforeskrifter.pdf")
            self.assertNotIn("Start", body)

    def test_html_pages_accepts_a_pdf_linked_from_the_listing(self):
        entry = {**PAGES_ENTRY, "link_pattern": "^https://www\\.oskarshamn\\.se/(mer-om-kommunen/forfattningssamling/[^#?]+/|download/.+\\.pdf)$",
                 "number": [{"from": "href", "pattern": "/([^/]+?)(\\.pdf)?/?$"}]}
        listing = (b"<html><body><h2>Andra taxor och avgifter</h2>"
                   b"<a href='/download/18.4f1e2/1700000000000/Lokala%20ordningsf%C3%B6reskrifter.pdf'>"
                   b"Lokala ordningsf\xc3\xb6reskrifter</a></body></html>")
        client = FakeClient({PAGES_BASE: listing, PAGES_PDF: PDF})
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "m.json"
            path.write_text(json.dumps({"kommuner": {"0882": entry}}), encoding="utf-8")
            args = Args(tmp, kommun=["0882"], config=str(path))
            summary = municipal.run(client, args)
            self.assertEqual(len(summary.written), 1)
            meta, body = frontmatter.load(next((Path(args.corpus) / "municipality" / "regulations").glob("*.md"))
                                          .read_text(encoding="utf-8"))
            self.assertEqual(meta["source"], PAGES_PDF)
            self.assertNotIn("Uppgifter från kommunen", body)


DOCWEB_TREE = {
    "id": "root", "name": "Regler och styrande dokument", "documents": [],
    "folders": [
        {"id": "f1", "name": "Taxor och avgifter", "folders": [], "documents": [
            {"id": "d1", "folderId": "f1", "name": "Avfallstaxa 2026"},
            {"id": "d2", "folderId": "f1", "name": "Delegationsordning för taxor"}]},
        {"id": "f2", "name": "Policyer", "folders": [
            {"id": "f3", "name": "Föreskrifter", "folders": [], "documents": [
                {"id": "d3", "folderId": "f3", "name": "Lokala ordningsföreskrifter"}]}],
         "documents": [{"id": "d4", "folderId": "f2", "name": "Taxa för internt bruk"}]},
    ],
}
NETPUB = "https://docs.netpublicator.com/api/public/r1/read?hash=a-root&isr=false"
NETPUB_ROOT = {"history": [], "items": [
    {"id": "c1", "text": "Avgifter och taxor", "type": "channel"},
    {"id": "d1", "text": "Lokala ordningsf&#246;reskrifter", "type": "document"}]}
NETPUB_CHILD = {"history": [], "items": [{"id": "d2", "text": "Avfallstaxa", "type": "document"}]}


class PlatformOptionsTest(unittest.TestCase):
    def test_javascript_hrefs_and_file_name_titles(self):
        entry = {"name": "Aneby", "issuer": "Aneby kommun", "region_code": "06", "collection": "Taxor",
                 "preset": "sitevision", "href_titles": True, "hosts": ["www.aneby.se"],
                 "listings": ["https://www.aneby.se/taxor.html"]}
        listing = (b"<html><body><a href=\"javascript:void(window.open('/download/18.5a2/1700/Taxa%20milj%C3%B6.pdf',"
                   b"'_blank'))\">Taxa milj\xc3\xb6balken (213 kB)</a>"
                   b"<a href='/download/18.6b3/1701/Avfallstaxa_2026.pdf'><img src='x.png'></a></body></html>")
        with tempfile.TemporaryDirectory() as tmp:
            kommun = _config(tmp, "0604", entry)
        entries, problems = municipal.parse_html_index(kommun, listing, entry["listings"][0])
        self.assertEqual(problems, [])
        self.assertEqual([(e.url, e.title) for e in entries], [
            ("https://www.aneby.se/download/18.5a2/1700/Taxa%20milj%C3%B6.pdf", "Taxa miljöbalken (213 kB)"),
            ("https://www.aneby.se/download/18.6b3/1701/Avfallstaxa_2026.pdf", "Avfallstaxa 2026"),
        ])

    def test_gzipped_sitemaps_are_read(self):
        urlset = (FIXTURES / "municipal-sitemap.xml").read_bytes()
        self.assertEqual(len(municipal._sitemap_locs(gzip.compress(urlset))), 3)
        self.assertIsNone(municipal._sitemap_locs(b"\x1f\x8bnot gzip"))

    def json_kommun(self, tmp, **extra):
        entry = {"name": "Västervik", "issuer": "Västerviks kommun", "region_code": "08", "collection": "Regler",
                 "strategy": "json_list", "resident_filter": True, "hosts": ["document.vastervik.se"],
                 "listings": ["https://document.vastervik.se/api/folders/root"], "items": "documents",
                 "title_field": "name", "number_field": "id", "url_template": "/api/download/{id}/{folderId}",
                 **extra}
        return _config(tmp, "0883", entry)

    def test_recursive_json_folders_with_sections(self):
        raw = json.dumps(DOCWEB_TREE).encode()
        with tempfile.TemporaryDirectory() as tmp:
            every = self.json_kommun(tmp, recursive=True)
            some = self.json_kommun(tmp, recursive=True, sections=["Taxor och avgifter", "Föreskrifter"])
        url = "https://document.vastervik.se/api/folders/root"
        self.assertEqual([e.number for e in municipal.parse_json_list(every, raw, url)[0]], ["d1", "d4", "d3"])
        entries, _ = municipal.parse_json_list(some, raw, url)
        self.assertEqual([(e.number, e.url) for e in entries], [
            ("d1", "https://document.vastervik.se/api/download/d1/f1"),
            ("d3", "https://document.vastervik.se/api/download/d3/f3"),
        ])

    def test_json_channels_are_followed_with_the_listing_query(self):
        entry = {"name": "Sigtuna", "issuer": "Sigtuna kommun", "region_code": "01", "collection": "KFS",
                 "strategy": "json_list", "resident_filter": True, "hosts": ["docs.netpublicator.com"],
                 "listings": [NETPUB], "items": "items", "title_field": "text", "number_field": "id",
                 "url_template": "document/{id}?hash={_hash}",
                 "follow_items": {"field": "type", "value": "channel", "url_template": "read?hash={_hash}-{id}&isr=false"}}
        child = "https://docs.netpublicator.com/api/public/r1/read?hash=a-root-c1&isr=false"
        client = FakeClient({NETPUB: json.dumps(NETPUB_ROOT).encode(), child: json.dumps(NETPUB_CHILD).encode()})
        with tempfile.TemporaryDirectory() as tmp:
            kommun = _config(tmp, "0191", entry)
            entries, problems = municipal.list_entries(municipal.Fetcher(client), kommun)
        self.assertEqual(problems, [])
        self.assertEqual([(e.number, e.title, e.url) for e in entries], [
            ("d1", "Lokala ordningsföreskrifter", "https://docs.netpublicator.com/api/public/r1/document/d1?hash=a-root"),
            ("d2", "Avfallstaxa", "https://docs.netpublicator.com/api/public/r1/document/d2?hash=a-root-c1"),
        ])


MF = "https://shareapi.mediaflow.com"
MF_TOKEN = MF + "/1/oauth2/token?grant_type=refresh_token&refresh_token=3KATTCX4I1"
MF_PAGE = "https://www.example.se/regler/foreskrifter.html"
MF_ENTRY = {
    "name": "Exempla", "issuer": "Exempla kommun", "region_code": "21",
    "collection": "Exempla kommuns föreskrifter och taxor", "strategy": "mediaflow",
    "hosts": ["www.example.se", "shareapi.mediaflow.com", "files.mediaflow.com"],
    "listings": [MF_TOKEN], "page": MF_PAGE, "resident_filter": True,
}
MF_FILES = json.dumps([
    {"id": 3143522, "nr": "17DFVQAWHJ", "type": "document", "name": "Lokala föreskrifter om VA"},
    {"id": 3143523, "nr": "17DFVQAWHK", "type": "document", "name": "Policy för möten"},
    {"id": 3143524, "nr": "", "type": "document", "name": "Avfallstaxa 2026"},
]).encode()
MF_SIGNED = "https://files.mediaflow.com/dn/17DFVQAWHJ/0?t=1&ch=abc"


def mediaflow_client():
    token = (b'{"access_token": "tok", "expires_in": 7200}', "application/json", MF_TOKEN)
    downloads = json.dumps([
        {"format": "custom", "filetype": "*", "downloadURL": "https://files.mediaflow.com/dn/x/custom"},
        {"format": "original", "filetype": "pdf", "downloadURL": MF_SIGNED},
    ]).encode()
    return FakeClient({
        MF_TOKEN: token,
        MF + "/1/files?access_token=tok": (MF_FILES, "application/json", MF + "/1/files?access_token=tok"),
        MF + "/1/file/3143522/downloads?access_token=tok": (downloads, "application/json", ""),
        MF_SIGNED: PDF,
    })


class MediaflowTest(unittest.TestCase):
    def config(self, tmp, entry=MF_ENTRY):
        path = Path(tmp) / "municipalities.json"
        path.write_text(json.dumps({"kommuner": {"2180": entry}}), encoding="utf-8")
        return str(path)

    def test_share_files_become_entries_numbered_by_media_number(self):
        with tempfile.TemporaryDirectory() as tmp:
            kommun = municipal.load_config(self.config(tmp))["2180"]
        entries, problems = municipal.list_entries(municipal.Fetcher(mediaflow_client()), kommun)
        self.assertEqual([(e.number, e.title, e.url, e.listing) for e in entries], [
            ("17DFVQAWHJ", "Lokala föreskrifter om VA", MF + "/1/file/3143522/downloads?share=3KATTCX4I1", MF_PAGE),
        ])
        self.assertEqual(problems, ["Avfallstaxa 2026"])

    def test_run_fetches_the_original_pdf_through_a_signed_link(self):
        with tempfile.TemporaryDirectory() as tmp:
            client = mediaflow_client()
            args = Args(tmp, kommun=["2180"], config=self.config(tmp))
            summary = municipal.run(client, args)
            self.assertEqual(summary.written, ["2180-17dfvqawhj"])
            self.assertEqual(client.posts, [(MF + "/1/file/3143522/downloads?access_token=tok", {"ids": [3143522]})])
            folder = Path(args.corpus) / "municipality" / "regulations"
            meta, body = frontmatter.load((folder / "2180-17dfvqawhj.md").read_text(encoding="utf-8"))
            self.assertEqual(schema.validate(meta), [])
            self.assertEqual(meta["source"], MF_PAGE)
            self.assertEqual(meta["source_sha256"], hashlib.sha256(PDF).hexdigest())
            self.assertNotIn("files.mediaflow.com", body)
            manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
            self.assertEqual([d["url"] for d in manifest["documents"]],
                             [MF + "/1/file/3143522/downloads?share=3KATTCX4I1"])

    def test_mediaflow_needs_the_page_on_a_configured_host(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(municipal.ConfigError):
                municipal.load_config(self.config(tmp, {**MF_ENTRY, "page": "https://elsewhere.se/x"}))


class MainTest(unittest.TestCase):
    def test_bad_code_is_rejected(self):
        with self.assertRaises(SystemExit):
            municipal.parse_args(["--kommun", "9999"])

    def test_unknown_kommun_returns_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = Args(tmp)
            code = municipal.main(
                ["municipal", "--kommun", "0114", "--config", sitevision_config(tmp), "--state", args.state,
                 "--manifest", args.manifest, "--corpus", args.corpus],
                client=FakeClient({}),
            )
            self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
