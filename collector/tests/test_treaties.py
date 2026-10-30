import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from lagar import frontmatter, pdftext, schema, treaties
from lagar.http import Blocked

from tests.test_eu import FakeClient

FIXTURES = Path(__file__).resolve().parent / "fixtures"
PAGE = (FIXTURES / "so-2023-3.html").read_bytes()
DECLARATION = (FIXTURES / "so-declaration.html").read_bytes()
SECTION = treaties.BASE + treaties.SECTION
PAGE_URL = SECTION + "2023/06/so-20233/"
OLD_URL = SECTION + "1994/01/so-197576/"
DECLARATION_URL = SECTION + "2025/08/avsiktsforklaring-om-gemensam-produktion/"
PDF_URL = treaties.BASE + "/contentassets/0f83c54d121c4a17b047cf49cda6a5c6/avtal-so-20233.pdf"
PDF = b"%PDF-1.4 fixture"
ROBOTS = b"User-agent: *\nDisallow: /episerver/\nDisallow: /utils/\n"
TEXT = ("Sveriges internationella överenskommelser\n\nSÖ 2023:3\n\n"
        "Artikel 1\n\nParterna ska skydda säkerhetsskyddsklassificerade uppgifter.\n")


def sitemap(*urls):
    rows = "".join(f"<url><loc>{u}</loc><lastmod>2025-07-09T16:20:17+02:00</lastmod></url>" for u in urls)
    return f'<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{rows}</urlset>'.encode()


def old_page():
    raw = PAGE.decode()
    raw = raw.replace("S&#xD6; 2023:3", "S&#xD6; 1975:76").replace("Vilnius den 12 juli 2023", "")
    return raw.replace("avtal-so-20233.pdf", "konvention-so-197576/").encode()


def client(**extra):
    routes = {treaties.ROBOTS_URL: ROBOTS, treaties.SITEMAP_URL: sitemap(PAGE_URL, DECLARATION_URL, OLD_URL),
              PAGE_URL: PAGE, DECLARATION_URL: DECLARATION, OLD_URL: old_page(), PDF_URL: PDF}
    routes.update(extra)
    fake = FakeClient(routes, robots=ROBOTS)
    fake.routes[treaties.ROBOTS_URL] = routes[treaties.ROBOTS_URL]
    return fake


def extracted(text=TEXT, gap=None):
    return pdftext.PdfText(text=text, pages=2, text_pages=2 if gap is None else 0, gap=gap)


class ParseTest(unittest.TestCase):
    def test_page_fields(self):
        page = treaties.parse_page(PAGE.decode(), PAGE_URL)
        self.assertEqual(page.title, "Avtal mellan Sveriges regering och Ukrainas regering om utbyte och ömsesidigt "
                                     "skydd av säkerhetsskyddsklassificerade uppgifter")
        self.assertEqual(page.number, "SÖ 2023:3")
        self.assertEqual((page.signed, page.place_date), ("2023-07-12", "Vilnius den 12 juli 2023"))
        self.assertEqual(page.ministry, "Utrikesdepartementet")
        self.assertEqual(treaties.in_force(page.note), "2023-12-13")
        self.assertEqual([url for url, _ in page.pdfs], [PDF_URL])

    def test_a_page_without_an_so_number_has_none(self):
        page = treaties.parse_page(DECLARATION.decode(), DECLARATION_URL)
        self.assertIsNone(page.number)
        self.assertEqual(page.ministry, "Försvarsdepartementet")

    def test_sitemap_keeps_only_so_pages(self):
        raw = sitemap(PAGE_URL, SECTION, treaties.BASE + "/rattsliga-dokument/proposition/2015/09/prop/")
        self.assertEqual(list(treaties.parse_sitemap(raw)), [PAGE_URL])

    def test_numbers_dates_and_ids(self):
        self.assertEqual(treaties.corpus_id("SÖ 2023:3"), "so-2023-3")
        self.assertEqual(treaties.slug_year(PAGE_URL), 2023)
        self.assertIsNone(treaties.slug_year(DECLARATION_URL))
        self.assertEqual(treaties.swedish_date("Ramsar den 2 februari 1971"), "1971-02-02")
        self.assertEqual(treaties.in_force("Avtalet trädde i kraft för Sveriges del den 1 maj 2024."), "2024-05-01")
        self.assertIsNone(treaties.in_force("Regeringen beslutade den 29 juni 2023 att underteckna avtalet."))


class RunTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.corpus, self.state, self.manifest = root / "corpus", root / "state.json", root / "manifest.json"

    def args(self, *extra):
        return treaties.parse_args([*extra, "--corpus", str(self.corpus), "--state", str(self.state),
                                    "--manifest", str(self.manifest)])

    def load(self, number):
        path = self.corpus / "sfs" / "treaties" / (treaties.corpus_id(number) + ".md")
        return frontmatter.load(path.read_text(encoding="utf-8"))

    def test_collects_text_for_recent_treaties_and_metadata_for_old_ones(self):
        with mock.patch.object(treaties.pdftext, "extract", return_value=extracted()) as extract:
            summary = treaties.run(client(), self.args())
        self.assertEqual(extract.call_count, 1)  # only the 2023 treaty's PDF
        self.assertEqual(sorted(summary.written), ["SÖ 1975:76", "SÖ 2023:3"])
        self.assertEqual(summary.excluded, [DECLARATION_URL])
        meta, body = self.load("SÖ 2023:3")
        self.assertEqual(schema.validate(meta), [])
        self.assertEqual((meta["type"], meta["layer"], meta["issued"], meta["in_force"]),
                         ("treaty", "sfs", "2023-07-12", "2023-12-13"))
        self.assertIn("Undertecknad: Vilnius den 12 juli 2023  \nSÖ 2023:3", body)
        self.assertIn("Parterna ska skydda säkerhetsskyddsklassificerade uppgifter.", body)
        old, old_body = self.load("SÖ 1975:76")
        self.assertEqual(schema.validate(old), [])
        self.assertNotIn("Artikel 1", old_body)
        entries = json.loads(self.manifest.read_text())["entries"]
        self.assertEqual([e["number"] for e in entries], ["SÖ 2023:3"])
        self.assertEqual(entries[0]["pdfs"][0]["bytes"], len(PDF))
        self.assertEqual(entries[0]["pdfs"][0]["text"], "extracted")

    def test_second_run_skips_and_refresh_is_unchanged(self):
        with mock.patch.object(treaties.pdftext, "extract", return_value=extracted()):
            treaties.run(client(), self.args())
            self.assertEqual(treaties.run(client(), self.args()).skipped, 3)
            self.assertEqual(sorted(treaties.run(client(), self.args("--refresh")).unchanged),
                             ["SÖ 1975:76", "SÖ 2023:3"])

    def test_a_second_page_with_the_same_number_is_a_duplicate(self):
        copy = SECTION + "2012/12/so-20233/"
        fake = client(**{treaties.SITEMAP_URL: sitemap(PAGE_URL, copy), copy: PAGE})
        with mock.patch.object(treaties.pdftext, "extract", return_value=extracted()):
            summary = treaties.run(fake, self.args())
        self.assertEqual((summary.written, summary.duplicates, summary.failed), (["SÖ 2023:3"], [PAGE_URL], []))
        meta, _ = self.load("SÖ 2023:3")
        self.assertEqual(meta["source"], copy)
        self.assertEqual(json.loads(self.state.read_text())["done"][PAGE_URL],
                         f"duplicate: SÖ 2023:3 from {copy}")

    def test_scanned_pdf_is_a_text_gap(self):
        with mock.patch.object(treaties.pdftext, "extract", return_value=extracted("", pdftext.NO_TEXT_LAYER)):
            summary = treaties.run(client(), self.args("--url", PAGE_URL))
        self.assertEqual(summary.text_gaps, ["SÖ 2023:3"])
        entry = json.loads(self.manifest.read_text())["entries"][0]
        self.assertEqual(entry["pdfs"][0]["text"], pdftext.NO_TEXT_LAYER)
        _, body = self.load("SÖ 2023:3")
        self.assertIn(PDF_URL, body)

    def test_year_range_and_text_year(self):
        with mock.patch.object(treaties.pdftext, "extract", return_value=extracted()) as extract:
            summary = treaties.run(client(), self.args("--from-year", "2000", "--text-from-year", "2024"))
        self.assertEqual(summary.written, ["SÖ 2023:3"])
        extract.assert_not_called()

    def test_changed_since_reads_only_recently_modified_pages(self):
        old = sitemap(OLD_URL).replace(b"2025-07-09", b"2015-04-02")
        fake = client(**{treaties.SITEMAP_URL: sitemap(PAGE_URL)[:-9] + old[old.index(b"<url>"):]})
        with mock.patch.object(treaties.pdftext, "extract", return_value=extracted()):
            summary = treaties.run(fake, self.args("--changed-since", "2025-01-01"))
        self.assertEqual(summary.written, ["SÖ 2023:3"])
        self.assertNotIn(OLD_URL, fake.urls)

    def test_robots_disallow_blocks(self):
        fake = client(**{treaties.ROBOTS_URL: b"User-agent: *\nDisallow: /rattsliga-dokument/\n"})
        summary = treaties.run(fake, self.args())
        self.assertTrue(summary.blocked)
        self.assertNotIn(PAGE_URL, fake.urls)

    def test_blocked_stops_the_run(self):
        fake = client(**{PAGE_URL: Blocked("HTTP 403")})
        summary = treaties.run(fake, self.args("--url", PAGE_URL))
        self.assertTrue(summary.blocked)
        self.assertIn("403", json.loads(self.state.read_text())["blocked"])

    def test_personal_identity_number_fails(self):
        text = TEXT + "\nKontaktperson 811218-9876.\n"
        with mock.patch.object(treaties.pdftext, "extract", return_value=extracted(text)):
            summary = treaties.run(client(), self.args("--url", PAGE_URL))
        self.assertEqual(summary.failed, [PAGE_URL])


if __name__ == "__main__":
    unittest.main()
