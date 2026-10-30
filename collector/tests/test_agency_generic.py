import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from lagar import agency, agency_generic, frontmatter, schema
from tests.test_agency import FakeClient, fixture

MIGRFS = agency.ADAPTERS["MIGRFS"]
KAMFS = agency.ADAPTERS["KAMFS"]
MIGRFS_PDF = "https://www.migrationsverket.se/download/18.{}/MIGRFS_{}.pdf"
MIGRFS_14 = MIGRFS_PDF.format("58abfa671a11163de737ef/1792410229158", "2026_14")
MIGRFS_8 = MIGRFS_PDF.format("7e7ff7f619e5ace55a73704/1781244264058", "2026_8")
MIGRFS_2022_1 = MIGRFS_PDF.format("2cd2e409193b84c506a32871/1738586324886", "2022_1")


class NumberTest(unittest.TestCase):
    def test_series_pattern_spellings(self):
        pattern = agency_generic._series_pattern("MIGRFS")
        for text in ("MIGRFS 2026:14", "MIGRFS_2026_14.pdf", "migrfs-2026-14", "fondMIGRFS 2026:14"):
            self.assertEqual(pattern.search(text).groups(), ("2026", "14"), text)
        self.assertIsNone(agency_generic._series_pattern("KFS").search("KKFS 2020:1"))
        self.assertIsNone(pattern.search("MIGRFS 2026:1400"))
        self.assertEqual(agency_generic._series_pattern("ELSÄK-FS").search("ELSÄK-FS 2022:3").groups(),
                         ("2022", "3"))

    def test_item_number_prefers_the_ends_then_the_file_name(self):
        self.assertEqual(KAMFS.item_number("KAMFS 2020:1 Föreskrifter om ändring (KAMFS 2019:1)", []),
                         "KAMFS 2020:1")
        self.assertEqual(KAMFS.item_number("Ändring i föreskrifterna (KAMFS 2003:4) om avgifter (KAMFS 2004:2)"
                                           " pdf, 12 kB.", []), "KAMFS 2004:2")
        self.assertEqual(KAMFS.item_number("Ändring i föreskrifterna (KAMFS 2003:4) om avgifter",
                                           ["/download/1/kamfs-2005-1.pdf"]), "KAMFS 2005:1")
        self.assertEqual(KAMFS.item_number("Ändring i föreskrifterna (KAMFS 2003:4) om avgifter", []),
                         "KAMFS 2003:4")

    def test_titles_and_amending(self):
        self.assertEqual(MIGRFS.clean_title(
            "MIGRFS 2026:14 pdf, 51.5 kB, öppnas i nytt fönster. Migrationsverkets föreskrifter om x",
            "MIGRFS 2026:14"), "Migrationsverkets föreskrifter om x")
        self.assertEqual(KAMFS.clean_title("Trafikanalys föreskrifter om y (KAMFS 2012:1, TRAFAFS 2012:1)",
                                           "KAMFS 2012:1"), "Trafikanalys föreskrifter om y (TRAFAFS 2012:1)")
        self.assertEqual(KAMFS.clean_title("KAMFS 2012:1 (pdf, 3 MB)", "KAMFS 2012:1"), "KAMFS 2012:1")
        self.assertTrue(agency_generic.is_amending("Föreskrifter om upphävande av föreskrifterna"))
        self.assertTrue(agency_generic.is_amending("Ändring i föreskrifterna om register"))
        self.assertFalse(agency_generic.is_amending("Föreskrifter om försörjningskravet"))


class PdfListTest(unittest.TestCase):
    def test_migrfs_listing(self):
        entries = MIGRFS.parse_listing(fixture("agency-migrfs-listing.html"), MIGRFS.listing_url)
        self.assertEqual([(e.number, e.base) for e in entries],
                         [("MIGRFS 2026:14", True), ("MIGRFS 2026:8", False), ("MIGRFS 2022:1", True)])
        first = entries[0]
        self.assertEqual(first.title, "Migrationsverkets föreskrifter om försörjningskravet för studier "
                                      "inom högre utbildning")
        self.assertEqual(first.url, MIGRFS_14)
        self.assertEqual(first.pdfs, [("MIGRFS 2026:14", MIGRFS_14)])

    def test_amendments_are_linked_to_their_base(self):
        listing = """<main>
          <a href="/d/kamfs-2019-1.pdf">Föreskrifter om åtgärder mot penningtvätt (KAMFS 2019:1) pdf, 1 MB.</a>
          <a href="/d/kamfs-2020-1.pdf">Ändring i föreskrifterna (KAMFS 2019:1) om åtgärder mot penningtvätt</a>
          <a href="/d/kamfs-2019-1-k.pdf">KAMFS 2019:1 konsoliderad pdf, 1 MB.</a>
          <a href="/om-oss/">Om oss</a>
        </main>"""
        entries = KAMFS.parse_listing(listing, KAMFS.listing_url)
        self.assertEqual([(e.number, e.base) for e in entries], [("KAMFS 2019:1", True), ("KAMFS 2020:1", False)])
        self.assertEqual(entries[0].amended_by, ["KAMFS 2020:1"])
        self.assertEqual([u for _, u in entries[0].pdfs], [
            "https://www.kammarkollegiet.se/d/kamfs-2019-1.pdf", "https://www.kammarkollegiet.se/d/kamfs-2019-1-k.pdf"])

    def test_listing_without_regulations_fails(self):
        with self.assertRaises(ValueError):
            MIGRFS.parse_listing("<main><a href='/x.pdf'>Om oss</a></main>", MIGRFS.listing_url)

    def test_detail_must_be_a_pdf(self):
        entry = MIGRFS.parse_listing(fixture("agency-migrfs-listing.html"), MIGRFS.listing_url)[0]
        with self.assertRaises(ValueError):
            MIGRFS.parse_detail(b"<html>", entry)
        regulation = MIGRFS.parse_detail(b"%PDF-1.7", entry)
        self.assertEqual((regulation.number, regulation.pdfs), (entry.number, entry.pdfs))


class RunTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.corpus = self.root / "corpus"

    def main(self, client, *args):
        argv = ["--corpus", str(self.corpus), "--state", str(self.root / "state.json"),
                "--manifest", str(self.root / "manifest.json"), "--report", str(self.root / "report.json"),
                *args]
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return agency.main(argv, client=client)

    def test_migrfs_run_downloads_each_pdf_once(self):
        client = FakeClient({
            MIGRFS.listing_url: fixture("agency-migrfs-listing.html").encode(),
            MIGRFS_14: b"%PDF-1.7 fourteen",
            MIGRFS_2022_1: b"%PDF-1.7 one",
        })
        self.assertEqual(self.main(client, "--series", "MIGRFS"), 0)
        report = json.loads((self.root / "report.json").read_text(encoding="utf-8"))
        self.assertEqual((report["written"], report["excluded"]), (["MIGRFS 2026:14", "MIGRFS 2022:1"], 1))
        self.assertNotIn(MIGRFS_8, client.calls)
        self.assertEqual(client.calls.count(MIGRFS_14), 1)
        meta, body = frontmatter.load(
            (self.corpus / "agency" / "regulations" / "migrfs-2026-14.md").read_text(encoding="utf-8"))
        self.assertEqual(schema.validate(meta), [])
        self.assertEqual((meta["issuer"], meta["source"]), ("Migrationsverket", MIGRFS_14))
        self.assertIn("## Dokument", body)
        manifest = json.loads((self.root / "manifest.json").read_text(encoding="utf-8"))
        files = {e["number"]: e["files"] for e in manifest["entries"]}
        self.assertEqual(files["MIGRFS 2026:14"][0]["bytes"], len(b"%PDF-1.7 fourteen"))


if __name__ == "__main__":
    unittest.main()
