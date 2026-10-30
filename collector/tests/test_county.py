import contextlib
import hashlib
import io
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

from lagar import county, frontmatter, pdftext, schema
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

    def test_title_falls_back_to_the_pdf_label(self):
        detail = county.parse_detail(DETAIL.replace("Länsstyrelsen i Stockholms läns beslut om att upphäva "
                                                    "naturreservatet Bullerö, Värmdö kommun.", ""),
                                     DETAIL_URL.format(1), "01")
        detail.pdfs = [(PDF_URL, "01FS 2026:1 Beslut om Bullerö")]
        item = county.ListingItem("01FS 2026:1", DETAIL_URL.format(1))
        meta = county.build_meta(detail, item, "01", "2026-10-29T00:00:00Z")
        self.assertEqual(meta["title"], "Beslut om Bullerö")

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


FILESHARE = (FIXTURES / "county-fileshare-landing.html").read_text(encoding="utf-8")
LINKS = (FIXTURES / "county-links-landing.html").read_text(encoding="utf-8")
FOLDERS = (FIXTURES / "county-folders-landing.html").read_text(encoding="utf-8")
FOLDER_2026 = (FIXTURES / "county-folder-2026.json").read_text(encoding="utf-8")
CONFIG = county.load_config(county.DEFAULT_CONFIG)
FOLDER_URL = (county.BASE + "/appresource/4.11a2cbf716d6c8f9f742a271/12.30198b32199c8d3aec4374c1/files?"
              "folderId=19.{}")


class CountyFilesLayoutTests(unittest.TestCase):
    def test_config_covers_every_county(self):
        self.assertEqual(sorted(CONFIG), sorted(county.COUNTIES))
        self.assertEqual(CONFIG["01"]["landing"], LANDING_URL)
        self.assertEqual({c for c, e in CONFIG.items() if e["layout"] == "pages"}, {"01", "13", "21"})

    def test_bad_config_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "counties.json"
            for bad in ({}, {"counties": {"02": {}}},
                        {"counties": {"01": {"landing": "https://example.org/x.html", "layout": "pages"}}},
                        {"counties": {"01": {"landing": LANDING_URL, "layout": "other"}}},
                        {"counties": {"01": {"landing": LANDING_URL, "layout": "files",
                                             "number_patterns": ["(?P<year>\\d{4})"]}}}):
                path.write_text(json.dumps(bad), encoding="utf-8")
                with self.assertRaises(county.ConfigError, msg=bad):
                    county.load_config(path)

    def test_numbers_from_link_text_or_file_name(self):
        default = CONFIG["22"]["number_patterns"]
        cases = [
            ("22 FS 2026-1 Länsstyrelsen i Västernorrlands läns föreskrifter.pdf", "22", default, "22FS 2026:1"),
            ("18FS2025 1 Lunnedets naturreservat.pdf", "18", default, "18FS 2025:1"),
            ("25 FS 2026 6 A 5 Säkerhetsföreskrifter.pdf", "25", default, "25FS 2026:6"),
            ("FS 2026-01  Naturreservat - Warragården - Osby kommun.pdf", "12", default, "12FS 2026:1"),
            ("17 FS 2024_21 Ändring i föreskrifter 14FS 2021_43.pdf", "17", default, "17FS 2024:21"),
            ("UPPHÄVD 2026_2 Föreskrifter om eldningsförbud.pdf", "07", CONFIG["07"]["number_patterns"],
             "07FS 2026:2"),
            ("2026-23 Naturreservat Marstrands skärgård Kungälv", "14", CONFIG["14"]["number_patterns"],
             "14FS 2026:23"),
            ("202603 Sjötrafikföreskrifter om förbud mot ankring.pdf", "08", CONFIG["08"]["number_patterns"],
             "08FS 2026:3"),
            ("Föreskrifter om upphävande av (05FS 2026.18) om eldningsförbud 2026.25.pdf", "05",
             CONFIG["05"]["number_patterns"], "05FS 2026:25"),
            ("Sjötrafikföreskrifter om fartbegränsningar i Ettersundet, 05FS 2025-4 ny .pdf", "05",
             CONFIG["05"]["number_patterns"], "05FS 2025:4"),
        ]
        for text, code, patterns, number in cases:
            found = county.file_number(text, county.BASE + "/download/18.1/1/x.pdf", code, patterns)
            self.assertEqual(found and found[0], number, msg=text)
        # A foreign series is skipped; the file name is the fallback for a bare title.
        self.assertIsNone(county.file_number("14FS 2021:43 Ändring", "/x.pdf", "17", default))
        found = county.file_number("Föreskrifter för Lövbergets naturreservat",
                                   county.BASE + "/download/18.1/1/17FS2025_6%20L%C3%B6vberget.pdf", "17", default)
        self.assertEqual(found[0], "17FS 2025:6")
        self.assertIsNone(county.file_number("Regelförteckning 2026", "/x.pdf", "12", default))

    def test_titles_drop_the_number_suffix_and_repeal_mark(self):
        def title(text, code):
            found = county.file_number(text, "/x.pdf", code, CONFIG[code]["number_patterns"])
            return county.file_title(text, found[1], found[2], CONFIG[code]["title_strip"])
        self.assertEqual(title("UPPHÄVD 2026_2 Föreskrifter om eldningsförbud.pdf", "07"),
                         "Föreskrifter om eldningsförbud")
        self.assertEqual(title("2026_3_Länsstyrelsen_i_Kronobergs_läns_föreskrifter.pdf", "07"),
                         "Länsstyrelsen i Kronobergs läns föreskrifter")
        self.assertEqual(title("Sammanställning över allmänna vägar Östergötlands län 2026.5.pdf", "05"),
                         "Sammanställning över allmänna vägar Östergötlands län")
        self.assertEqual(title("25FS 2026_2A1 Föreskrifter om Björknäs naturreservat.pdf", "25"),
                         "Föreskrifter om Björknäs naturreservat")
        self.assertEqual(title("24FS 2026-1.pdf", "24"), "")

    def test_fileshare_landing_lists_the_module_files(self):
        links, folders = county.parse_files_landing(FILESHARE, CONFIG["22"]["landing"])
        self.assertEqual(folders, {})
        self.assertEqual(len(links), 6)
        self.assertTrue(all(u.startswith(county.BASE + "/download/") and n is None for u, _, n in links))
        self.assertTrue(links[0][1].startswith("22 FS 2026-1 Länsstyrelsen"))
        items, loose = county.group_files(links, "22", CONFIG["22"], CONFIG["22"]["landing"])
        self.assertEqual(sorted(i.number for i in items),
                         ["22FS 2025:1", "22FS 2025:3", "22FS 2025:4", "22FS 2026:1", "22FS 2026:2", "22FS 2026:3"])
        self.assertEqual(loose, [])

    def test_plain_links_take_title_and_decision_from_the_next_paragraph(self):
        links, folders = county.parse_files_landing(LINKS, CONFIG["20"]["landing"])
        self.assertEqual(folders, {})
        self.assertEqual([t for _, t, _ in links], ["20 FS 2026:1", "20 FS 2026:2", "20 FS 2026:3"])
        self.assertNotIn("footer", " ".join(u for u, _, _ in links))
        items, _ = county.group_files(links, "20", CONFIG["20"], CONFIG["20"]["landing"])
        first = items[0]
        self.assertEqual(first.title, "Länsstyrelsen i Dalarnas läns föreskrifter om Hästflotens naturreservat "
                                      "i Mora och Orsa kommuner.")
        self.assertEqual(first.decided, "2025-10-13")
        meta = county.build_file_meta(first, "20", first.files[0][0], "0" * 64, "2026-10-29T00:00:00Z")
        self.assertEqual(schema.validate(meta), [])
        self.assertEqual((meta["issued"], meta["title"][-8:]), ("2025-10-13", "kommuner"))
        body = county.file_markdown(meta, first)
        self.assertIn("Beslutad: 2025-10-13", body)
        self.assertIn("Författningen publiceras bara som pdf.", body)
        self.assertIn(f"- [20 FS 2026:1]({first.files[0][0]})", body)

    def test_year_folders_are_read_from_the_module_endpoint(self):
        links, folders = county.parse_files_landing(FOLDERS, CONFIG["24"]["landing"])
        self.assertEqual(links, [])
        self.assertEqual(sorted(folders), [2024, 2025, 2026])
        self.assertEqual(folders[2026], [FOLDER_URL.format("69ced119d24e4b4ca5062b")])
        found = county.parse_folder(FOLDER_2026, folders[2026][0])
        self.assertEqual([t for _, t, _ in found], ["24FS 2026-1.pdf", "24FS 2026-2.pdf", "24FS 2026-3.pdf"])
        with self.assertRaises(ValueError):
            county.parse_folder('{"nothing": []}', folders[2026][0])


class FilesClient(FakeClient):
    def __init__(self, pages=None):
        super().__init__({
            CONFIG["24"]["landing"]: FOLDERS,
            FOLDER_URL.format("69ced119d24e4b4ca5062b"): FOLDER_2026,
            CONFIG["22"]["landing"]: FILESHARE.replace("22FS 2025-1 Länsstyrelsen", "Karta 2025 Länsstyrelsen")
            .replace("22FS%202025-1%20L", "Karta%202025%20L"),
            **(pages or {}),
        })


class CountyFilesRunTests(unittest.TestCase):
    setUp = CountyRunTests.setUp
    tearDown = CountyRunTests.tearDown

    def run_files(self, client, code, *extra):
        argv = ["county", "--county", code, "--corpus", str(self.corpus), "--state", str(self.state),
                "--manifest", str(self.manifest), "--report", str(self.report), *extra]
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            code = county.main(argv, client=client)
        report = json.loads(self.report.read_text(encoding="utf-8")) if self.report.exists() else None
        return code, report

    def test_folder_county_reads_only_the_requested_years(self):
        client = FilesClient()
        code, report = self.run_files(client, "24", "--from-year", "2026")
        self.assertEqual(code, 0)
        self.assertEqual(report["written"], ["24FS 2026:1", "24FS 2026:2", "24FS 2026:3"])
        self.assertEqual([c for c in client.calls if "appresource" in c],
                         [FOLDER_URL.format("69ced119d24e4b4ca5062b")])
        for path in self.corpus.rglob("*.md"):
            meta, _ = frontmatter.load(path.read_text(encoding="utf-8"))
            self.assertEqual(schema.validate(meta), [])
            self.assertTrue(meta["source"].endswith(".pdf"))
            self.assertEqual(meta["source_sha256"], hashlib.sha256(PDF).hexdigest())
            self.assertEqual(meta["title"], meta["number"])
        entry = json.loads(self.manifest.read_text(encoding="utf-8"))["entries"][0]
        self.assertEqual((entry["detail_url"], entry["files"][0]["bytes"]), (CONFIG["24"]["landing"], len(PDF)))
        client = FilesClient()
        _, report = self.run_files(client, "24", "--from-year", "2026")
        self.assertEqual((report["written"], report["skipped"]), ([], 3))
        self.assertFalse(any(c.endswith(".pdf") for c in client.calls))

    def test_unnumbered_files_are_reported_and_not_collected(self):
        code, report = self.run_files(FilesClient(), "22", "--from-year", "2025", "--no-pdf")
        self.assertEqual(code, 0)
        self.assertEqual(report["written"], ["22FS 2025:3", "22FS 2025:4", "22FS 2026:1", "22FS 2026:2",
                                             "22FS 2026:3"])
        self.assertEqual(len(report["unnumbered"]), 1)
        self.assertTrue(report["unnumbered"][0].startswith("Karta 2025"))
        meta, _ = frontmatter.load((self.corpus / "region/county-regulations/22fs-2026-1.md")
                                   .read_text(encoding="utf-8"))
        self.assertEqual(schema.validate(meta), [])

    def test_landing_without_pdfs_exits_1(self):
        client = FilesClient({CONFIG["22"]["landing"]: "<html><main></main></html>"})
        self.assertEqual(self.run_files(client, "22")[0], 1)


PDF_TEXT = (
    "Västerbottens läns författningssamling\n\n24FS 2026:1\n"
    "Länsstyrelsen i Västerbottens läns föreskrifter\nom eldningsförbud;\n\n"
    "beslutade den 3 juni 2026.\n"
    "Länsstyrelsen föreskriver med stöd av 2 kap. 7 § förordningen (2003:789) om skydd mot olyckor följande.\n"
    "1 § Det är förbjudet att elda utomhus i länet. Förbudet gäller också grillning på\n"
    "allmän plats.\n"
    "___________\n"
    "Dessa föreskrifter träder i kraft den 5 juni 2026.\n\n1\n\f"
)


def fake_extract(text=PDF_TEXT, gap=None):
    return mock.patch.object(
        county.pdftext, "extract",
        return_value=pdftext.PdfText(text=text, pages=1, text_pages=0 if gap else 1, gap=gap),
    )


class CountyTextTests(unittest.TestCase):
    setUp = CountyRunTests.setUp
    tearDown = CountyRunTests.tearDown
    run_files = CountyFilesRunTests.run_files

    def body(self, number):
        path = self.corpus / f"region/county-regulations/{county.corpus_id(number)}.md"
        return frontmatter.load(path.read_text(encoding="utf-8"))

    def test_files_layout_body_is_the_pdf_text(self):
        with fake_extract():
            code, report = self.run_files(FilesClient(), "24", "--from-year", "2026")
        self.assertEqual((code, len(report["written"])), (0, 3))
        meta, body = self.body("24FS 2026:1")
        self.assertEqual(schema.validate(meta), [])
        self.assertEqual((meta["issued"], meta["in_force"]), ("2026-06-03", "2026-06-05"))
        self.assertIn("1 § Det är förbjudet att elda utomhus i länet. Förbudet gäller också grillning på "
                      "allmän plats.\n\nDessa föreskrifter träder i kraft den 5 juni 2026.", body)
        self.assertIn("Ikraftträdande: 2026-06-05", body)
        self.assertNotIn(county.PDF_ONLY, body)
        self.assertIn("## Tryckt version", body)
        entry = json.loads(self.manifest.read_text(encoding="utf-8"))["entries"][0]
        self.assertEqual(entry["files"][0]["text"], county.TEXT_EXTRACTED)

    def test_scanned_pdf_is_a_gap(self):
        with fake_extract("\f\f", pdftext.NO_TEXT_LAYER):
            self.run_files(FilesClient(), "24", "--from-year", "2026")
        _, body = self.body("24FS 2026:2")
        self.assertIn(county.NO_TEXT, body)
        entry = json.loads(self.manifest.read_text(encoding="utf-8"))["entries"][1]
        self.assertEqual(entry["files"][0]["text"], pdftext.NO_TEXT_LAYER)

    def test_rerun_does_not_download_read_pdfs_again(self):
        with fake_extract():
            self.run_files(FilesClient(), "24", "--from-year", "2026")
        before = {p: p.read_bytes() for p in self.corpus.rglob("*.md")}
        self.state.unlink()
        client = FilesClient()
        with fake_extract() as extract:
            _, report = self.run_files(client, "24", "--from-year", "2026")
        self.assertEqual((report["written"], report["unchanged"]), ([], 3))
        self.assertFalse(any(c.endswith(".pdf") for c in client.calls))
        extract.assert_not_called()
        self.assertEqual({p: p.read_bytes() for p in self.corpus.rglob("*.md")}, before)
        self.state.unlink()
        client = FilesClient()
        with fake_extract():
            self.run_files(client, "24", "--from-year", "2026", "--refresh-pdf")
        self.assertEqual(sum(c.endswith(".pdf") for c in client.calls), 3)

    def test_pages_layout_without_html_text_reads_the_pdf(self):
        client = FakeClient({DETAIL_URL.format(1): pdf_only(DETAIL)})
        with fake_extract(PDF_TEXT.replace("24FS", "01FS")):
            code, _ = self.run_main(client, "--from-year", "2026")
        self.assertEqual(code, 0)
        meta, body = self.body("01FS 2026:1")
        self.assertIn("1 § Det är förbjudet att elda utomhus i länet.", body)
        self.assertEqual(meta["in_force"], "2026-06-05")
        _, body = self.body("01FS 2026:2")
        self.assertNotIn("Det är förbjudet att elda", body)  # HTML text wins

    run_main = CountyRunTests.run_main

    def test_unnumbered_link_takes_the_number_printed_in_the_pdf(self):
        text = PDF_TEXT.replace("24FS 2026:1", "22FS 2025:1")
        with fake_extract(text):
            code, report = self.run_files(FilesClient(), "22", "--from-year", "2025")
        self.assertEqual(code, 0)
        self.assertEqual(report["unnumbered"], [])
        self.assertIn("22FS 2025:1", report["written"])
        meta, body = self.body("22FS 2025:1")
        self.assertEqual(schema.validate(meta), [])
        self.assertIn("Karta%202025", meta["source"])
        self.assertIn("1 § Det är förbjudet att elda utomhus", body)
        self.assertEqual(county.number_in_text(["Ändring i 14FS 2021:43", "22FS 2025:01"], "22"), "22FS 2025:1")
        self.assertIsNone(county.number_in_text(["Informationsblad 2017"], "22"))
        client = FilesClient()
        with fake_extract(text) as extract:
            self.run_files(client, "22", "--from-year", "2025")
        extract.assert_not_called()  # known from the manifest, nothing downloaded

    def test_missing_pdftotext_exits_1_unless_no_text(self):
        with mock.patch.object(county.pdftext, "available", return_value=False):
            self.assertEqual(self.run_files(FilesClient(), "24", "--from-year", "2026")[0], 1)
            self.assertEqual(self.run_files(FilesClient(), "24", "--from-year", "2026", "--no-text")[0], 0)


if __name__ == "__main__":
    unittest.main()
