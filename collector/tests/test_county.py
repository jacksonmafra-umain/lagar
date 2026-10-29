import contextlib
import hashlib
import io
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path

from lagar import county, frontmatter, schema
from lagar.http import Blocked

FIXTURES = Path(__file__).resolve().parent / "fixtures"
LANDING = (FIXTURES / "county-landing.html").read_text(encoding="utf-8")
YEAR = (FIXTURES / "county-year-2026.html").read_text(encoding="utf-8")
DETAIL = (FIXTURES / "county-detail-01fs-2026-01.html").read_text(encoding="utf-8")
DETAIL_LISTS = (FIXTURES / "county-detail-01fs-2026-02.html").read_text(encoding="utf-8")

ROBOTS = county.ROBOTS_URL
SITE = county.BASE + "/stockholm/om-oss/om-lansstyrelsen-stockholm/lanets-forfattningssamling"
LANDING_URL = SITE + ".html"
YEAR_URL = SITE + "/forfattningar-{}.html"
DETAIL_URL = SITE + "/forfattningar-2026/forfattningar-2026/2026-02-13-01fs-2026{:02d}.html"
PDF_URL = county.BASE + "/download/18.4d207a9019c47c545ea20c10/1770974690947/01FS%202026-01.pdf"
PDF = b"%PDF-1.7\nfake\n"


def http_error(url, code):
    return urllib.error.HTTPError(url, code, "err", {}, io.BytesIO(b""))


def detail_for(n):
    """The fixture detail page renumbered as 01FS 2026:n with its own PDF."""
    if n == 1:
        return DETAIL
    if n == 2:
        return DETAIL_LISTS
    return (
        DETAIL.replace("01FS 2026:01", f"01FS 2026:{n:02d}")
        .replace("01FS%202026-01.pdf", f"01FS%202026-{n:02d}.pdf")
    )


def pdf_only(page):
    """A detail page whose text portlet holds nothing but the PDF link."""
    start = page.index('<p class="normal">Beslutat')
    end = page.index('<p class="sv-font-brodtext-med-bla-lankning">')
    return page[:start] + page[end:]


class FakeClient:
    def __init__(self, pages=None, robots=b"User-agent: *\nDisallow: /*.html.printable\n"):
        self.pages = {
            LANDING_URL: LANDING,
            YEAR_URL.format(2026): YEAR,
            **{DETAIL_URL.format(n): detail_for(n) for n in (1, 2, 3)},
        }
        self.pages.update(pages or {})
        self.robots = robots
        self.calls = []

    def fetch(self, url):
        self.calls.append(url)
        if url == ROBOTS:
            if self.robots is None:
                raise http_error(url, 404)
            return self.robots, "text/plain"
        if url.endswith(".pdf"):
            return PDF, "application/pdf"
        page = self.pages.get(url)
        if page is None:
            raise http_error(url, 404)
        if isinstance(page, Exception):
            raise page
        return page.encode("utf-8"), "text/html"

    def get(self, url):
        return self.fetch(url)[0]


class CountyParsingTests(unittest.TestCase):
    def test_numbers_are_normalised_and_checked_against_the_series(self):
        self.assertEqual(county.normalise_number("01FS 2026:01"), "01FS 2026:1")
        self.assertEqual(county.normalise_number(" 01 FS 2024 : 003 ", "01"), "01FS 2024:3")
        self.assertEqual(county.corpus_id("01FS 2026:1"), "01fs-2026-1")
        with self.assertRaises(ValueError):
            county.normalise_number("03FS 2026:1", "01")
        with self.assertRaises(ValueError):
            county.normalise_number("SFS 2026:1")

    def test_landing_page_links_every_year(self):
        years = county.parse_landing(LANDING, LANDING_URL)
        self.assertEqual(sorted(years), list(range(2020, 2027)))
        self.assertEqual(years[2026], YEAR_URL.format(2026))

    def test_year_index_entries(self):
        items = county.parse_year(YEAR, YEAR_URL.format(2026), "01")
        self.assertEqual([i.number for i in items], ["01FS 2026:1", "01FS 2026:2", "01FS 2026:3"])
        self.assertEqual(items[0].url, DETAIL_URL.format(1))
        self.assertEqual(items[0].published, "2026-02-16")
        self.assertTrue(items[1].title.startswith("Länsstyrelsen i Stockholms läns beslut om avgränsning"))

    def test_detail_page_maps_to_valid_frontmatter_and_body(self):
        item = county.parse_year(YEAR, YEAR_URL.format(2026), "01")[0]
        detail = county.parse_detail(DETAIL, item.url, "01")
        self.assertEqual(detail.number, "01FS 2026:1")
        self.assertEqual((detail.published, detail.decided), ("2026-02-16", "2025-11-10"))
        self.assertEqual(detail.pdfs, [(PDF_URL, "Länsstyrelsen i Stockholms läns beslut om att "
                                                 "upphäva naturreservatet Bullerö, Värmdö kommun")])
        meta = county.build_meta(detail, item, "01", "2026-10-29T00:00:00Z")
        self.assertEqual(schema.validate(meta), [])
        self.assertEqual(meta["id"], "01fs-2026-1")
        self.assertEqual(meta["layer"], "region")
        self.assertEqual(meta["issued"], "2025-11-10")
        self.assertEqual(meta["issuer"], "Länsstyrelsen i Stockholms län")
        self.assertEqual(meta["region_code"], "01")
        self.assertFalse(meta["title"].endswith("."))
        self.assertEqual(meta["source"], DETAIL_URL.format(1))
        body = county.to_markdown(meta, detail)
        self.assertIn("med stöd av 7 kap. 7 § första stycket miljöbalken", body)
        self.assertIn("## Tryckt version", body)
        self.assertIn(f"]({PDF_URL})", body)
        self.assertNotIn("kB", body)

    def test_lists_are_kept_and_inline_pdf_links_are_not_attachments(self):
        detail = county.parse_detail(DETAIL_LISTS, DETAIL_URL.format(2), "01")
        self.assertEqual(len(detail.pdfs), 1)
        self.assertTrue(detail.pdfs[0][0].endswith("/01FS%202026-02.pdf"))
        item = county.ListingItem("01FS 2026:2", DETAIL_URL.format(2), "2026-02-16", None)
        meta = county.build_meta(detail, item, "01", "2026-10-29T00:00:00Z")
        self.assertEqual(schema.validate(meta), [])
        body = county.to_markdown(meta, detail)
        self.assertIn("1. skada havs- eller sjöbotten", body)
        self.assertIn("   1. använder okopplad hund", body)
        self.assertIn("tidigare beslut (01FS 1984:005, 01FS 1996:243, 01FS 2004:85 och 01FS 2007:227) upphör", body)
        self.assertNotIn("kB", body)
        self.assertNotIn("01FS%201984", body)

    def test_page_nonces_do_not_change_the_hash(self):
        a = county.parse_detail(DETAIL, DETAIL_URL.format(1), "01")
        b = county.parse_detail(DETAIL.replace('nonce="x"', 'nonce="y"'), DETAIL_URL.format(1), "01")
        self.assertEqual(a.canonical, b.canonical)

    def test_pdf_only_regulation_gets_a_note(self):
        detail = county.parse_detail(pdf_only(DETAIL), DETAIL_URL.format(1), "01")
        item = county.ListingItem("01FS 2026:1", DETAIL_URL.format(1), "2026-02-16", None)
        meta = county.build_meta(detail, item, "01", "2026-10-29T00:00:00Z")
        self.assertEqual(meta["issued"], "2026-02-16")
        body = county.to_markdown(meta, detail)
        self.assertIn("Författningen publiceras bara som pdf.", body)
        self.assertIn(PDF_URL, body)

    def test_in_force_is_read_only_when_unambiguous(self):
        self.assertEqual(county._in_force("Denna författning träder i kraft den 1 mars 2026."), "2026-03-01")
        self.assertIsNone(county._in_force("träder i kraft den 1 mars 2026 ... träder i kraft den 2 maj 2026"))
        self.assertIsNone(county._in_force("Inget datum."))

    def test_arguments(self):
        args = county.parse_args(["--region", "1", "--from-year", "2026"])
        self.assertEqual((args.county, args.from_year, args.rate, args.pdf), ("01", 2026, 1.0, True))
        self.assertEqual(county.parse_args(["--county", "01FS"]).county, "01")
        with contextlib.redirect_stderr(io.StringIO()):
            for bad in (["--county", "02"], [], ["--county", "01", "--rate", "0.5"],
                        ["--county", "01", "--from-year", "2026", "--to-year", "2025"]):
                with self.assertRaises(SystemExit, msg=bad):
                    county.parse_args(bad)


class CountyRunTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.corpus = root / "corpus"
        self.state = root / "state.json"
        self.manifest = root / "manifest.json"
        self.report = root / "report.json"

    def tearDown(self):
        self.tmp.cleanup()

    def run_main(self, client, *extra):
        argv = ["county", "--county", "01", "--corpus", str(self.corpus), "--state", str(self.state),
                "--manifest", str(self.manifest), "--report", str(self.report), *extra]
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            code = county.main(argv, client=client)
        report = json.loads(self.report.read_text(encoding="utf-8")) if self.report.exists() else None
        return code, report

    def files(self):
        return sorted(p.relative_to(self.corpus).as_posix() for p in self.corpus.rglob("*.md"))

    def test_run_writes_regulations_and_the_pdf_manifest(self):
        client = FakeClient()
        code, report = self.run_main(client, "--from-year", "2026")
        self.assertEqual(code, 0)
        self.assertEqual(report["written"], ["01FS 2026:1", "01FS 2026:2", "01FS 2026:3"])
        self.assertEqual(self.files(), [f"region/county-regulations/01fs-2026-{n}.md" for n in (1, 2, 3)])
        self.assertEqual(client.calls[0], ROBOTS)
        self.assertNotIn(YEAR_URL.format(2025), client.calls)
        for path in self.corpus.rglob("*.md"):
            meta, _ = frontmatter.load(path.read_text(encoding="utf-8"))
            self.assertEqual(schema.validate(meta), [])
        manifest = json.loads(self.manifest.read_text(encoding="utf-8"))
        entry = manifest["entries"][0]
        self.assertEqual(entry["number"], "01FS 2026:1")
        self.assertEqual(entry["files"][0]["url"], PDF_URL)
        self.assertEqual(entry["files"][0]["sha256"], hashlib.sha256(PDF).hexdigest())
        self.assertEqual(entry["files"][0]["bytes"], len(PDF))

    def test_limit_and_no_pdf(self):
        client = FakeClient()
        _, report = self.run_main(client, "--from-year", "2026", "--limit", "1", "--no-pdf")
        self.assertEqual(report["written"], ["01FS 2026:1"])
        self.assertFalse(any(c.endswith(".pdf") for c in client.calls))
        entry = json.loads(self.manifest.read_text(encoding="utf-8"))["entries"][0]
        self.assertIsNone(entry["files"][0]["sha256"])

    def test_rerun_skips_done_items_and_never_churns_files(self):
        self.run_main(FakeClient(), "--from-year", "2026")
        before = {p: p.read_bytes() for p in self.corpus.rglob("*.md")}
        manifest = self.manifest.read_bytes()
        client = FakeClient()
        _, report = self.run_main(client, "--from-year", "2026")
        self.assertEqual((report["written"], report["skipped"]), ([], 3))
        self.assertFalse(any("01fs-2026" in c for c in client.calls))
        self.state.unlink()
        client = FakeClient()
        _, report = self.run_main(client, "--from-year", "2026")
        self.assertEqual((report["written"], report["unchanged"]), ([], 3))
        self.assertFalse(any(c.endswith(".pdf") for c in client.calls))  # hashes already recorded
        self.assertEqual({p: p.read_bytes() for p in self.corpus.rglob("*.md")}, before)
        self.assertEqual(self.manifest.read_bytes(), manifest)

    def test_bad_detail_page_is_recorded_as_failed(self):
        client = FakeClient({DETAIL_URL.format(2): detail_for(3)})  # wrong number
        code, report = self.run_main(client, "--from-year", "2026")
        self.assertEqual(code, 0)
        self.assertEqual(report["failed"], ["01FS 2026:2"])
        state = json.loads(self.state.read_text(encoding="utf-8"))
        self.assertIn("expected 01FS 2026:2", state["failed"]["01FS 2026:2"])

    def test_robots_disallow_and_403_block_the_run(self):
        robots = b"User-agent: *\nDisallow: /stockholm/\n"
        code, report = self.run_main(FakeClient(robots=robots), "--from-year", "2026")
        self.assertEqual(code, 2)
        self.assertTrue(report["blocked"])
        self.assertEqual(self.files(), [])
        client = FakeClient({DETAIL_URL.format(2): Blocked("403 Forbidden")})
        code, report = self.run_main(client, "--from-year", "2026")
        self.assertEqual((code, report["written"]), (2, ["01FS 2026:1"]))
        self.assertIn("403", json.loads(self.state.read_text(encoding="utf-8"))["blocked"])

    def test_missing_landing_page_and_corrupt_state_exit_1(self):
        client = FakeClient()
        del client.pages[LANDING_URL]
        self.assertEqual(self.run_main(client)[0], 1)
        self.state.write_text("{not json", encoding="utf-8")
        self.assertEqual(self.run_main(FakeClient())[0], 1)


if __name__ == "__main__":
    unittest.main()
