import contextlib
import html
import io
import json
import tempfile
import unittest
from pathlib import Path

from lagar import agency, agency_generic, frontmatter, schema
from tests.test_agency import FakeClient, fixture

MIGRFS = agency.ADAPTERS["MIGRFS"]
KAMFS = agency.ADAPTERS["KAMFS"]
MDFFS = agency.ADAPTERS["MDFFS"]
NFS = agency.ADAPTERS["NFS"]
KIFS = agency.ADAPTERS["KIFS"]
ELSAK = agency.ADAPTERS["ELSÄK-FS"]
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


class DetailPageTest(unittest.TestCase):
    def test_slug_numbers_and_quoted_queries(self):
        self.assertEqual(NFS.slug_number("https://www.naturvardsverket.se/x/2026/nfs-20269/"), "NFS 2026:9")
        self.assertEqual(NFS.slug_number("https://www.naturvardsverket.se/x/2026/nfs-20267-upphavande-av-y/"),
                         "NFS 2026:7")
        self.assertIsNone(NFS.slug_number("https://www.naturvardsverket.se/x/2026/"))
        entries = ELSAK.parse_listing(
            '<main><a href="/lag-och-ratt/foreskrifter/foreskrift?id=ELSÄK-FS 2022:3&lang=sv">ELSÄK-FS 2022:3</a></main>',
            ELSAK.listing_url)
        self.assertEqual(entries[0].url, "https://elsakerhetsverket.se/lag-och-ratt/foreskrifter/"
                                         "foreskrift?id=ELS%C3%84K-FS%202022:3&lang=sv")

    def test_listing_links_to_pages(self):
        listing = """<main>
          <a href="/om-oss/forfattningssamling/a-mdffs-20251/grundforfattning-mdffs-20251">Grundförfattning (MDFFS 2025:1)</a>
          <a href="/om-oss/forfattningssamling/a-mdffs-20251/andringsforfattning-mdffs-20263">Ändringsförfattning (MDFFS 2026:3)</a>
          <a href="/download/1/mdffs-2025-1.pdf">MDFFS 2025:1 (pdf)</a>
        </main>"""
        entries = MDFFS.parse_listing(listing, MDFFS.listing_url)
        self.assertEqual([(e.number, e.base) for e in entries], [("MDFFS 2025:1", True), ("MDFFS 2026:3", False)])
        self.assertTrue(entries[0].url.endswith("/grundforfattning-mdffs-20251"))

    def test_detail_with_html_text(self):
        entry = agency.Entry(number="MDFFS 2025:1", title="Grundförfattning", url=MDFFS.listing_url + "/x")
        regulation = MDFFS.parse_detail(fixture("agency-mdffs-detail.html"), entry)
        self.assertTrue(regulation.title.startswith("Föreskrifter om krav på leverantörers ansökan"))
        self.assertNotIn("MDFFS 2025:1", regulation.title)
        self.assertEqual(regulation.issued, "2025-04-15")
        self.assertIn("### Föreskriftens innehåll", regulation.text)
        self.assertIn("1 § Denna föreskrift", regulation.text)
        self.assertNotIn("Start", regulation.text)

    def test_detail_pdfs_title_prefix_and_amending(self):
        page = """<main><h1>KIFS 2017:7 om kemiska produkter</h1>
          <a href="/download/1/KIFS-2017-7-konsoliderad.pdf">KIFS 2017:7 konsoliderad (PDF 582 kB) pdf, 582 kB.</a>
          <a href="/download/2/KIFS-2026-3.pdf">KIFS 2026:3 pdf, 98.2 kB.</a>
          <a href="/download/3/pm-konsekvensutredning-KIFS-2026-3.pdf">PM om konsekvensutredning pdf, 9 kB.</a>
        </main>"""
        entry = agency.Entry(number="KIFS 2017:7", title="Gå till", url=KIFS.listing_url + "/kifs-20177")
        regulation = KIFS.parse_detail(page, entry)
        self.assertEqual(regulation.title, "Kemikalieinspektionens föreskrifter om kemiska produkter")
        self.assertEqual([label for label, _ in regulation.pdfs], ["KIFS 2017:7 konsoliderad", "KIFS 2026:3"])
        with self.assertRaises(ValueError):
            KIFS.parse_detail(page.replace("2017:7", "2017:9"), entry)
        nfs = agency.Entry(number="NFS 2014:29", title="NFS 2014:29", url="https://www.naturvardsverket.se/x/")
        with self.assertRaises(agency.NotBase):
            NFS.parse_detail("<main>ÄndringNaturvårdsverkets förteckning (NFS 2014:29)<h1>Förteckning</h1></main>", nfs)

    def test_sitemap_listing(self):
        sitemap = """<urlset>
          <url><loc>https://www.naturvardsverket.se/lagar-och-regler/foreskrifter-och-allmanna-rad/2026/nfs-20269/</loc></url>
          <url><loc>https://www.naturvardsverket.se/lagar-och-regler/foreskrifter-och-allmanna-rad/2014/nfs-201429/</loc></url>
          <url><loc>https://www.naturvardsverket.se/lagar-och-regler/foreskrifter-och-allmanna-rad/2014/nfs-201429/bilaga/</loc></url>
          <url><loc>https://www.naturvardsverket.se/amnesomraden/nfs-20101/</loc></url>
        </urlset>"""
        entries = NFS.parse_listing(sitemap, NFS.listing_url)
        self.assertEqual([e.number for e in entries], ["NFS 2026:9", "NFS 2014:29"])
        page = """<main>GrundföreskriftFöreskrifter om förpackningar (Upphävd: 2023-12-31)<h1>Föreskrifter om förpackningar</h1>
          <a href="/4ac54c/globalassets/nfs/2020/nfs-2020-8.pdf">Ladda ner (719,75 KB)</a></main>"""
        regulation = NFS.parse_detail(page, agency.Entry(number="NFS 2020:8", title="NFS 2020:8", url="u"))
        self.assertEqual((regulation.title, regulation.repealed), ("Föreskrifter om förpackningar", "2023-12-31"))
        with self.assertRaises(ValueError):
            NFS.parse_detail(page, agency.Entry(number="NFS 2020:9", title="NFS 2020:9", url="u"))
        self.assertEqual(agency_generic.issued_date("beslutade den 1 januari 2027."), "2027-01-01")


def _props(data):
    return html.escape(json.dumps(data, ensure_ascii=False), quote=True)


class FkfsTest(unittest.TestCase):
    FKFS = agency.ADAPTERS["FKFS"]

    def test_register_and_document(self):
        register = {"incrementBy": "10", "viewUrl": "/foreskrifter/dokument", "documents": [
            {"nummer": "2026:9", "titel": "Försäkringskassans föreskrifter om krav", "id": "18.a",
             "isChangeDocument": False, "upphavdDatum": None, "forfattningssamling": "FKFS"},
            {"nummer": "2025:3", "titel": "Förordning om upphävande av Försäkringskassans föreskrifter (FKFS 2014:3)",
             "id": "18.b", "isChangeDocument": False, "upphavdDatum": None, "forfattningssamling": "FKFS"},
            {"nummer": "2004:1", "titel": "Riksförsäkringsverkets föreskrifter", "id": "18.c",
             "isChangeDocument": False, "upphavdDatum": None, "forfattningssamling": "RFFS"},
        ]}
        entries = self.FKFS.parse_listing(f'<div data-props="{_props(register)}"></div>', self.FKFS.listing_url)
        self.assertEqual([(e.number, e.base) for e in entries], [("FKFS 2026:9", True), ("FKFS 2025:3", False)])
        self.assertEqual(entries[0].url, "https://lagrummet.forsakringskassan.se/foreskrifter/dokument?id=18.a")

        def meta(**values):
            return {k: {"value": v} for k, v in values.items()}

        document = {
            "baseDocument": {"url": "/download/18.a/1/GFKFS2609.pdf", "headline": "x", "metadata": meta(
                titel="Försäkringskassans föreskrifter om krav", dokument_nr="2026:9", beslutsdatum="2026-10-05",
                ikrafttradande="2026-11-02", tryckdatum="2026-10-08", upphavd_datum="")},
            "currentDocument": {"url": "/download/18.k/1/KFKFS2609.pdf"},
            "changeDocuments": [{"url": "/download/18.d/1/AFKFS2701.pdf", "metadata": meta(
                dokument_nr="2027:1", forfattningssamling="FKFS", ikrafttradande="2027-02-01")}],
        }
        regulation = self.FKFS.parse_detail(f'<div data-props="{_props(document)}"></div>', entries[0])
        self.assertEqual((regulation.issued, regulation.in_force, regulation.published, regulation.repealed),
                         ("2026-10-05", "2026-11-02", "2026-10-08", None))
        self.assertEqual(regulation.amended_by, ["FKFS 2027:1"])
        self.assertEqual([label for label, _ in regulation.pdfs],
                         ["FKFS 2026:9", "FKFS 2026:9 (konsoliderad version)", "FKFS 2027:1"])
        with self.assertRaises(ValueError):
            self.FKFS.parse_detail(f'<div data-props="{_props(document)}"></div>', entries[1])


class AffsTest(unittest.TestCase):
    AFFS = agency.ADAPTERS["AFFS"]

    def test_state_listing_and_html_text(self):
        state = {"returnObject": {"list": [
            {"displayName": "AFFS 2025:1", "URI": "/om-oss/x/gallande-forfattningar/affs-20251",
             "description": "Hur en sökande ska vara anmäld, föreskrifter"},
            {"displayName": "AFFS 2025: 2", "URI": "/om-oss/x/gallande-forfattningar/affs-2025-2",
             "description": "Om ändring i föreskrifterna om statsbidrag, föreskrifter"},
            {"displayName": "AMSFS 1996:7", "URI": "/om-oss/x/amsfs-19967", "description": "Äldre"},
        ]}}
        listing = (f"<script>AppRegistry.registerInitialState('12.3',{json.dumps(state, ensure_ascii=False)});"
                   "</script>")
        entries = self.AFFS.parse_listing(listing, self.AFFS.listing_url)
        self.assertEqual([(e.number, e.base) for e in entries], [("AFFS 2025:1", True), ("AFFS 2025:2", False)])
        page = """<main>
          <div class="sv-text-portlet"><div id="Rubrik"></div><div class="sv-text-portlet-content"><h1>AFFS 2025:1</h1></div></div>
          <div class="sv-text-portlet"><div id="Beskrivning"></div><div class="sv-text-portlet-content">
            <p class="ingress">Arbetsförmedlingens föreskrifter om anmälan, föreskrifter</p></div></div>
          <div class="sv-text-portlet"><div id="Fakta"></div><div class="sv-text-portlet-content"><p>
            <strong>Beslutade:</strong> Den 20 maj 2025<br><strong>Utkom från trycket:</strong> Den 3 juni 2025</p></div></div>
          <div class="sv-text-portlet"><div id="Innehall"></div><div class="sv-text-portlet-content">
            <h2>Inledande bestämmelse</h2><p><strong>1 </strong><strong>§</strong> Dessa föreskrifter gäller.</p></div></div>
          <a href="/download/1/AFFS-2025-1.pdf">AFFS 2025:1, ursprunglig lydelse pdf, 75 kB.</a>
        </main>"""
        regulation = self.AFFS.parse_detail(page, entries[0])
        self.assertEqual(regulation.title, "Arbetsförmedlingens föreskrifter om anmälan")
        self.assertEqual((regulation.issued, regulation.published), ("2025-05-20", "2025-06-03"))
        self.assertEqual(regulation.text, "### Inledande bestämmelse\n\n**1 §** Dessa föreskrifter gäller.")
        self.assertEqual(regulation.pdfs[0][0], "AFFS 2025:1, ursprunglig lydelse")


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
