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

    def test_regulation_from_the_listing(self):
        entry = MIGRFS.parse_listing(fixture("agency-migrfs-listing.html"), MIGRFS.listing_url)[0]
        self.assertFalse(MIGRFS.detail)
        regulation = MIGRFS.regulation(entry)
        self.assertEqual((regulation.number, regulation.title, regulation.pdfs), (entry.number, entry.title, entry.pdfs))


class SectionedListTest(unittest.TestCase):
    def test_table_rows_with_consolidated_column(self):
        bfnar = agency.ADAPTERS["BFNAR"]
        listing = """<table><tr><td>Allmänna råd</td><td>Grundtext</td><th>Konsoliderad version</th></tr>
          <tr><td>BFNAR 2026:2</td><td><a href="/u/bfnar-2026-2.pdf">Ändringar i Bokföringsnämndens allmänna råd
            (BFNAR 2006:11) om gränsvärden</a></td><th></th></tr>
          <tr><td>BFNAR 2006:11</td><td><a href="/u/bfnar06-11-grund.pdf">Gränsvärden</a></td>
            <th><a href="/u/bfnar06-11-kons3.pdf">konsoliderad version</a></th></tr></table>"""
        entries = bfnar.parse_listing(listing, bfnar.listing_url)
        self.assertEqual([(e.number, e.base) for e in entries], [("BFNAR 2026:2", False), ("BFNAR 2006:11", True)])
        base = entries[1]
        self.assertEqual((base.title, base.amended_by), ("Gränsvärden", ["BFNAR 2026:2"]))
        self.assertEqual(base.url, "https://www.bfn.se/u/bfnar06-11-grund.pdf")
        self.assertEqual([label for label, _ in base.pdfs], ["BFNAR 2006:11", "BFNAR 2006:11 (konsoliderad version)"])

    def test_items_under_consolidated_and_printed_headings(self):
        csnfs = agency.ADAPTERS["CSNFS"]
        listing = """<main><h3>Studiehjälp</h3>
          <h3><a href="#">Fulltext - studiehjälp</a></h3>
          <ul><li><a href="/download/1/2001-6-2023-4.pdf">2001:6 Centrala studiestödsnämndens föreskrifter och
            allmänna råd om studiehjälp Pdf, 417 kB.</a> · 417 kB</li></ul>
          <h3><a href="#">Tryckt version - studiehjälp</a></h3>
          <ul><li><a href="/download/2/2001:6%20CSN.pdf">2001:6 Centrala studiestödsnämndens föreskrifter och
            allmänna råd om studiehjälp Pdf, 112 kB.</a> · 112 kB</li>
          <li><a href="/download/3/2001:6%20R%C3%A4ttelseblad.pdf">2001:6 Rättelseblad Pdf, 466 kB.</a></li>
          <li><a href="/download/4/2023:4%20%C3%84ndring.pdf">2023:4 Ändring Pdf, 176 kB.</a></li></ul></main>"""
        entries = csnfs.parse_listing(listing, csnfs.listing_url)
        self.assertEqual([(e.number, e.base) for e in entries], [("CSNFS 2001:6", True), ("CSNFS 2023:4", False)])
        base = entries[0]
        self.assertEqual(base.title, "Centrala studiestödsnämndens föreskrifter och allmänna råd om studiehjälp")
        self.assertEqual(base.url, "https://www.csn.se/download/2/2001:6%20CSN.pdf")  # as issued, not consolidated
        self.assertEqual(base.pdfs, [("CSNFS 2001:6 (konsoliderad version)", "https://www.csn.se/download/1/2001-6-2023-4.pdf"),
                                     ("CSNFS 2001:6", "https://www.csn.se/download/2/2001:6%20CSN.pdf")])

    def test_heading_groups_skip_repealed_and_link_bare_references(self):
        lmfs = agency.ADAPTERS["LMFS"]
        listing = """<main><h2>Gällande föreskrifter</h2>
          <h3>LMFS 2026:3</h3><p>Lantmäteriets föreskrifter om ändringar i Lantmäteriets föreskrifter (2022:4) om
            avgifter.</p><p><a href="/f/andringsforeskrift-lmfs-2026-3.pdf">LMFS 2026:3 (pdf, nytt fönster)</a></p>
          <h3>LMFS 2022:4</h3><p>Lantmäteriets föreskrifter om avgifter.</p>
            <p><a href="/f/lmfs-2022-4.pdf">LMFS 2022:4 (pdf, nytt fönster)</a></p>
          <h2>Upphävda föreskrifter</h2>
          <h3>LMFS 2015:1</h3><p>Lantmäteriets föreskrifter om avgifter.</p>
            <p><a href="/f/lmfs_151.pdf">LMFS 2015:1 (pdf, nytt fönster)</a></p></main>"""
        entries = lmfs.parse_listing(listing, lmfs.listing_url)
        self.assertEqual([(e.number, e.base) for e in entries], [("LMFS 2026:3", False), ("LMFS 2022:4", True)])
        self.assertEqual(entries[1].title, "Lantmäteriets föreskrifter om avgifter")
        self.assertEqual(entries[1].amended_by, ["LMFS 2026:3"])

    def test_link_groups_take_the_title_after_the_link(self):
        imyfs = agency.ADAPTERS["IMYFS"]
        listing = """<main><h2>Föreskrifter</h2>
          <p><a href="/link/1.aspx">IMYFS 2024:1 (pdf, 3 MB)</a>Föreskrifter om behandling av personuppgifter.</p>
          <p><a href="/link/2.aspx">Vägledning – föreskrifter (IMYFS 2024:1) (pdf, 441 kB)</a></p>
          <h3>Upphävande av tidigare gällande föreskrifter</h3>
          <p><a href="/link/3.aspx">IMYFS 2023:1 (pdf, 26 kB)</a>Föreskrifter om upphävande av Datainspektionens
            föreskrifter (DIFS 1989:1)</p>
          <p><a href="/link/4.aspx">DIFS 2018:1 (pdf, 63 kB)</a>Föreskrifter om upphävande.</p></main>"""
        entries = imyfs.parse_listing(listing, imyfs.listing_url)
        self.assertEqual([(e.number, e.base) for e in entries], [("IMYFS 2024:1", True), ("IMYFS 2023:1", False)])
        self.assertEqual(entries[0].title, "Föreskrifter om behandling av personuppgifter")
        self.assertEqual(entries[0].pdfs, [("IMYFS 2024:1", "https://www.imy.se/link/1.aspx")])


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


class DvfsEifsKbvfsFfsTest(unittest.TestCase):
    DVFS = agency.ADAPTERS["DVFS"]
    EIFS = agency.ADAPTERS["EIFS"]
    KBVFS = agency.ADAPTERS["KBVFS"]
    FFS = agency.ADAPTERS["FFS"]

    def test_dvfs_base_pages_from_the_sitemap(self):
        prefix = "https://www.domstol.se" + self.DVFS.path_prefix
        sitemap = f"""<urlset><url><loc>{prefix}2020/dvfs-20202/</loc></url>
          <url><loc>{prefix}2006/dvfs-20069/dvfs-20212/</loc></url>
          <url><loc>{prefix}2021/dvfs-202112/dvfs-202112/</loc></url>
          <url><loc>{prefix}</loc></url></urlset>"""
        entries = self.DVFS.parse_listing(sitemap, self.DVFS.listing_url)
        self.assertEqual([e.number for e in entries], ["DVFS 2020:2"])
        page = """<main><h1>DVFS 2020:2</h1><h2>Grundförfattning</h2><p>Domstolsverkets föreskrifter om
          kvällsberedskap</p><a href="/globalassets/dvfs/2020/dvfs_2020-2.pdf">DVFS 2020:2<span>pdf</span>165 kB</a>
          <h2>Ändringsföreskrifter</h2><a href="/globalassets/dvfs/2026/dvfs-2026-2.pdf">DVFS 2026:2pdf121 kB</a></main>"""
        regulation = self.DVFS.parse_detail(page, entries[0])
        self.assertEqual(regulation.title, "DVFS 2020:2")  # the title comes from the PDF
        self.assertEqual([label for label, _ in regulation.pdfs], ["DVFS 2020:2", "DVFS 2026:2"])

    def test_eifs_rows_link_to_pages_without_the_print_pdf(self):
        listing = """<table><tr><th>Publiceringsår</th><th>Föreskrift</th></tr><tr><td>2026</td><td>
          <a href="/om-oss/publikationer/publikationer/foreskrifter-el/2026/foreskrift-eifs-20268">EIFS 2026:8</a>
          Energimarknadsinspektionens föreskrifter om information</td></tr></table>"""
        entries = self.EIFS.parse_listing(listing, self.EIFS.listing_url)
        self.assertEqual([e.number for e in entries], ["EIFS 2026:8"])
        page = """<main><h1>Föreskrift</h1><p>EIFS 2026:8</p>
          <a href="/download/18.1/1/EIFS-2026-8-om-information.pdf">Energimarknadsinspektionens föreskrifter
            EIFS 2026:8</a><a href="/4.19e22.pdf?properties=12.5b0e">Skriv ut som PDF</a></main>"""
        regulation = self.EIFS.parse_detail(page, entries[0])
        self.assertEqual(regulation.title, "EIFS 2026:8")
        self.assertEqual([url.rsplit("/", 1)[-1] for _, url in regulation.pdfs], ["EIFS-2026-8-om-information.pdf"])

    def test_kbvfs_clickable_rows(self):
        listing = """<table><tr><th>Titel</th></tr>
          <tr class="js-documentRow" data-href="/globalassets/kbvfs-2021-3-rapportering.pdf"><td>
            <p class="ml-6 md:ml-4">KBVFS 2021:3 Kustbevakningens föreskrifter om rapportering till havs utanför EU.pdf</p>
            Beslutad den 5 maj 2021.</td><td>140 kb</td></tr></table>"""
        entries = self.KBVFS.parse_listing(listing, self.KBVFS.listing_url)
        self.assertEqual([(e.number, e.base) for e in entries], [("KBVFS 2021:3", True)])
        self.assertEqual(entries[0].title, "Kustbevakningens föreskrifter om rapportering till havs utanför EU")
        self.assertEqual(entries[0].url, "https://www.kustbevakningen.se/globalassets/kbvfs-2021-3-rapportering.pdf")

    def test_ffs_content_api_list(self):
        def pdf(name, url):
            return {"contentLink": {"expanded": {"name": name, "url": "https://www.forsvarsmakten.se/globalassets/" + url}}}

        listing = json.dumps({"pdfFilesArea": [
            pdf("FFS 2026.3 a\u0308ndring av FFS 1996.16 om fo\u0308rma\u030aner.pdf", "ffs-2026.3-andring.pdf"),
            pdf("ffs-2013.1_andring-fm-skyddsforeskrifter-ffs-2010.5.pdf", "ffs-2013.1_andring.pdf"),
            pdf("ffs--2017-5.pdf", "ffs--2017-5.pdf"),
            {"contentLink": {"expanded": None}}]})
        entries = self.FFS.parse_listing(listing, self.FFS.listings[-1])
        self.assertEqual([(e.number, e.base) for e in entries],
                         [("FFS 2026:3", False), ("FFS 2013:1", False), ("FFS 2017:5", True)])
        self.assertEqual(entries[2].title, "FFS 2017:5")  # the title comes from the PDF


class McfPredecessorTest(unittest.TestCase):
    PAGE1 = """<main>
      <a href="/sv/regler/gallande-regler/mcffs-20261/">MCFFS 2026:1</a>
      <a href="/sv/regler/gallande-regler/msbfs-202510/">MSBFS 2025:10 upphävande av Statens räddningsverks
        föreskrifter (SRVFS 2004:11) om kontroll av brandposter <span>Status: Gällande</span></a>
      <a href="/sv/regler/gallande-regler/srvfs-20071/">SRVFS 2007:1 allmänna råd och kommentarer om brandvarnare
        i bostäder <span>Status: Gällande</span></a>
      <a href="/sv/regler/gallande-regler/?selectedpage=2">2</a>
      <a href="/sv/regler/gallande-regler/?selectedpage=10">10</a></main>"""
    PAGE10 = """<main>
      <a href="/sv/regler/gallande-regler/msbfs-202510/">MSBFS 2025:10</a>
      <a href="/sv/regler/gallande-regler/srvfs-20043/">SRVFS 2004:3 föreskrifter om tillsyn</a>
      <a href="/sv/regler/gallande-regler/?selectedpage=9">9</a></main>"""

    def test_paged_list_numbered_from_the_slug_and_read_once(self):
        srvfs = type(agency.ADAPTERS["SRVFS"])()
        url = srvfs.listing_url
        first = srvfs.parse_listing(self.PAGE1, url)
        self.assertEqual([(e.number, e.title) for e in first],
                         [("SRVFS 2007:1", "allmänna råd och kommentarer om brandvarnare i bostäder")])
        self.assertEqual(srvfs.more_pages(self.PAGE1, url), [url + "?selectedpage=2", url + "?selectedpage=10"])
        self.assertEqual(srvfs.more_pages(self.PAGE10, url + "?selectedpage=10"), [url + "?selectedpage=9"])
        self.assertEqual([e.number for e in srvfs.parse_listing(self.PAGE10, url + "?selectedpage=10")],
                         ["SRVFS 2004:3"])
        msbfs = type(agency.ADAPTERS["MSBFS"])()
        self.assertEqual([e.number for e in msbfs.parse_listing(self.PAGE1, url)], ["MSBFS 2025:10"])
        self.assertEqual(msbfs.parse_listing(self.PAGE10, url + "?selectedpage=10"), [])  # repeated, read once
        self.assertEqual(type(agency.ADAPTERS["KBMFS"])().parse_listing(self.PAGE1, url), [])

class HslffsTest(unittest.TestCase):
    HSLF = agency.ADAPTERS["HSLF-FS"]
    FOHM = "https://www.folkhalsomyndigheten.se/publikationsarkiv/f/folkhalsomyndighetens-foreskrifter-hslf-fs-2025-55/"
    TLV = "https://www.tlv.se/om-tlv/regelverk/foreskrifter.html"
    IVO = "https://ivo.se/globalassets/foreskrifter/hslf-fs-2023-7.pdf"

    @classmethod
    def listing(cls):
        def item(designation, heading, authority, url):
            return {"Designation": designation, "Heading": heading, "Authority": authority, "Url": url}

        items = [
            item("HSLF-FS 2025:55", "HSLF-FS 2025:55", "Folkhälsomyndigheten", cls.FOHM),
            item("HSLF-FS 2015:17", "Föreskrifter om ändring i föreskrifterna (HSLF-FS 2015:17) om prissättning",
                 "Tandvårds- och läkemedelsförmånsverket, TLV", cls.TLV),
            item("HSLF-FS 2015:17", "Tandvårds- och läkemedelsförmånsverkets föreskrifter om prissättning",
                 "Tandvårds- och läkemedelsförmånsverket, TLV", cls.TLV),
            item("HSLF-FS 2023:7", "Inspektionen för vård och omsorgs föreskrifter om anmälan",
                 "Inspektionen för vård och omsorg, IVO", cls.IVO),
            item("HSLF-FS 2026:26", "Läkemedelsverkets föreskrifter om tillverkning", "Läkemedelsverket",
                 "https://www.lakemedelsverket.se/sv/lagar-och-regler/foreskrifter/2026-26"),
            item("SOSFS 2015:10", "Basal hygien i vård och omsorg (SOSFS 2015:10)", "Socialstyrelsen",
                 "https://www.socialstyrelsen.se/regler/"),
            item("HSLF-FS 2021:1", "Socialstyrelsens föreskrifter", "Socialstyrelsen,E-hälsomyndigheten",
                 "https://www.socialstyrelsen.se/publikationer/hslf-fs-20211-socialstyrelsens-foreskrifter/"),
            item("HSLF-FS 2016:55", "Socialstyrelsens föreskrifter om hem för vård eller boende", "Socialstyrelsen",
                 cls.HSLF.SOS_INDEX),
        ]
        return "<script>ReactDOM.hydrate(React.createElement(SOS.Components.FilterList, " + json.dumps(
            {"filterItems": items}) + "), document.getElementById('react_1'));</script>"

    def test_listing_from_the_page_json(self):
        entries = self.HSLF.parse_listing(self.listing(), self.HSLF.listing_url)
        self.assertEqual([(e.number, e.base, e.issuer) for e in entries], [
            ("HSLF-FS 2025:55", True, "Folkhälsomyndigheten"),
            ("HSLF-FS 2015:17", True, "Tandvårds- och läkemedelsförmånsverket"),
            ("HSLF-FS 2023:7", True, "Inspektionen för vård och omsorg"),
            ("HSLF-FS 2021:1", True, "Socialstyrelsen och E-hälsomyndigheten")])
        self.assertEqual(entries[0].title, "HSLF-FS 2025:55")  # the title comes from the PDF
        self.assertEqual(entries[1].url, self.TLV)
        # linked to Socialstyrelsen's general page: its own page comes from Socialstyrelsen's index
        index = ('[{"name":"HSLF-FS 2025:33 Föreskrifter om ändring (HSLF-FS 2016:55)","url":"/publikationer/hslf-fs-202533/"},'
                 '{"name":"HSLF-FS 2016:55 Socialstyrelsens föreskrifter","url":"/publikationer/hslf-fs-201655-hem/"}]')
        resolved = self.HSLF.parse_listing(index, self.HSLF.SOS_INDEX)
        self.assertEqual([(e.number, e.url) for e in resolved],
                         [("HSLF-FS 2016:55", "https://www.socialstyrelsen.se/publikationer/hslf-fs-201655-hem/")])

    def test_page_listing_many_keeps_the_pdfs_naming_the_number(self):
        entry = agency.Entry(number="HSLF-FS 2015:17", title="x", url=self.TLV)
        page = """<main><h1>TLV:s föreskrifter</h1>
          <a href="/download/1/HSLF-FS_2015_16.pdf">HSLF-FS 2015:16 pdf, 2 MB.</a>
          <a href="/download/2/HSLF-FS_2015_17.pdf">HSLF-FS 2015:17 pdf, 2 MB.</a>
          <a href="/download/3/hslf_2015_17_konsoliderad.pdf">HSLF-FS 2015:17 pdf, 394 kB.</a>
          <a href="/download/4/HSLF-FS_2014_1.pdf">HSLF-FS 2014:1 pdf, 1 MB.</a></main>"""
        regulation = self.HSLF.parse_detail(page, entry)
        self.assertEqual([url.rsplit("/", 1)[-1] for _, url in regulation.pdfs],
                         ["HSLF-FS_2015_17.pdf", "hslf_2015_17_konsoliderad.pdf"])
        general = "<main><p>HSLF-FS 2015:17 om prissättning</p><a href='/a.pdf'>Broschyr</a><a href='/b.pdf'>Mall</a></main>"
        with self.assertRaises(ValueError):
            self.HSLF.parse_detail(general, entry)
        with self.assertRaises(ValueError):
            self.HSLF.parse_detail("<main><p>HSLF-FS 2015:17</p></main>", entry)

    def test_run_reads_robots_per_host_and_takes_a_listed_pdf_as_the_document(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        fohm_pdf = "https://www.folkhalsomyndigheten.se/contentassets/1/hslf-fs-2025-55.pdf"
        client = FakeClient({
            self.HSLF.listing_url: self.listing().encode(),
            self.FOHM: f'<main><p>HSLF-FS 2025:55</p><a href="{fohm_pdf}">Ladda ner</a></main>'.encode(),
            fohm_pdf: b"%PDF-1.7 fohm",
            self.IVO: b"%PDF-1.7 ivo",
        }, robots={"https://www.tlv.se": b"User-agent: *\nDisallow: /om-tlv/\n"})
        argv = ["--series", "HSLF-FS", "--no-pdf-text", "--corpus", str(root / "corpus"),
                "--state", str(root / "state.json"), "--manifest", str(root / "manifest.json"),
                "--report", str(root / "report.json")]
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            agency.main(argv, client=client)
        self.assertIn("https://www.tlv.se/robots.txt", client.calls)
        self.assertNotIn(self.TLV, client.calls)  # disallowed on its own host
        meta, _ = frontmatter.load((root / "corpus/agency/regulations/hslf-fs-2023-7.md").read_text("utf-8"))
        self.assertEqual((meta["source"], meta["issuer"]), (self.IVO, "Inspektionen för vård och omsorg"))
        meta, body = frontmatter.load((root / "corpus/agency/regulations/hslf-fs-2025-55.md").read_text("utf-8"))
        self.assertEqual((meta["source"], meta["issuer"]), (self.FOHM, "Folkhälsomyndigheten"))
        self.assertIn("Utgivare: Folkhälsomyndigheten", body)


class PredecessorTest(unittest.TestCase):
    def test_predecessors_read_their_own_numbers_from_the_current_listing(self):
        listing = """<main><h2>Gällande föreskrifter</h2>
          <h3>LMFS 2022:4</h3><p>Lantmäteriets föreskrifter om avgifter.</p>
            <p><a href="/f/lmfs-2022-4.pdf">LMFS 2022:4 (pdf)</a></p>
          <h3>LMVFS 2000:2</h3><p>Lantmäteriets föreskrifter om hur fastighetsregistrets allmänna del skall föras.</p>
            <p><a href="/f/lmv002.pdf">LMVFS 2000:2 (pdf)</a></p>
          <h3>LMVFS 2004:1</h3><p>Lantmäteriets föreskrifter om ändring i föreskrifter (LMVFS 2000:2) om hur.</p>
            <p><a href="/f/lmv041.pdf">LMVFS 2004:1 (pdf)</a></p></main>"""
        lmvfs = agency.ADAPTERS["LMVFS"]
        entries = lmvfs.parse_listing(listing, lmvfs.listing_url)
        self.assertEqual([(e.number, e.base, e.amended_by) for e in entries],
                         [("LMVFS 2000:2", True, ["LMVFS 2004:1"]), ("LMVFS 2004:1", False, [])])
        self.assertEqual([e.number for e in agency.ADAPTERS["LMFS"].parse_listing(listing, lmvfs.listing_url)],
                         ["LMFS 2022:4"])
        self.assertEqual((agency.ADAPTERS["FIFS"].issuer, agency.ADAPTERS["RFFS"].issuer),
                         ("Fiskeriverket", "Riksförsäkringsverket"))

    def test_tsfs_predecessors_from_the_year_pages_before_2009(self):
        lfs, jvsfs = agency.ADAPTERS["LFS"], agency.ADAPTERS["JvSFS"]
        index = "".join(f'<a href="/x/ts-foreskrifter-i-nummerordning/{y}/">{y}</a>' for y in (2026, 2009, 2007, 1982))
        self.assertEqual(lfs.parse_index(index), [2007, 1982])

        def item(number, title, badge=""):
            return (f'<li class="tsfs-item"><span>{number}</span><a href="/x/{number[-6:]}">{title}, {number}</a>'
                    f'{badge}</li>')

        year = ("<ul>" + item("LFS 2007:4", "Luftfartsstyrelsens föreskrifter om driftbidrag",
                              '<span class="badge">Upphävd 2026-06-30 genom TSFS 2026:76</span>')
                + item("LFS 2007:9", "Luftfartsstyrelsens föreskrifter om ändring i föreskrifterna (LFS 2007:4)")
                + item("JvSFS 2007:6", "Järnvägsstyrelsens föreskrifter om ansökan om tillstånd") + "</ul>")
        entries = lfs.parse_listing(year, lfs.year_url(2007))
        self.assertEqual([(e.number, e.base, e.repealed, e.issuer) for e in entries],
                         [("LFS 2007:4", True, "2026-06-30", "Luftfartsstyrelsen"), ("LFS 2007:9", False, None, "Luftfartsstyrelsen")])
        self.assertEqual([e.number for e in jvsfs.parse_listing(year, jvsfs.year_url(2007))], ["JvSFS 2007:6"])


if __name__ == "__main__":
    unittest.main()



class HslffsPredecessorTest(unittest.TestCase):
    SOSFS = agency.ADAPTERS["SOSFS"]
    TLVFS = agency.ADAPTERS["TLVFS"]
    FOHMFS = agency.ADAPTERS["FoHMFS"]
    FOHM = "https://www.folkhalsomyndigheten.se/publikationer-och-material/foreskrifter-och-allmanna-rad/"

    def listing(self):
        def item(designation, heading, url):
            return {"Designation": designation, "Heading": heading, "Authority": "x", "Url": url}

        items = [
            item("SOSFS 2011:9", "Ledningssystem för systematiskt kvalitetsarbete (SOSFS 2011:9)", self.SOSFS.SOS_INDEX),
            item("SOSFS 2015:9", "Upphävande av allmänna råden (SOSFS 1989:20) om hälsoundersökning",
                 self.SOSFS.SOS_INDEX),
            item("SOSFS 1997:14", "Delegering av medicinska arbetsuppgifter", self.SOSFS.SOS_INDEX),
            item("HSLF-FS 2025:21", "Socialstyrelsens föreskrifter om ändring i föreskrifterna (SOSFS 2011:9)",
                 "https://www.socialstyrelsen.se/publikationer/hslf-fs-202521-andring-sosfs-20119/"),
            item("TLVFS 2009:3", "Konsoliderad föreskrift Tandvårds- och läkemedelsförmånsverkets föreskrifter "
                 "om handelsmarginal", "https://www.tlv.se/om-tlv/regelverk/foreskrifter.html"),
            item("FoHMFS 2014:7", "Folkhälsomyndighetens föreskrifter om kunskapsprov",
                 self.FOHM + "fohmfs-20147/"),
            item("FoHMFS 2014:9", "Folkhälsomyndighetens föreskrifter om varningstexter",
                 self.FOHM + "upphavda-foreskrifter/"),
        ]
        return "<script>React.createElement(SOS.Components.FilterList, " + json.dumps(
            {"filterItems": items}) + ")</script>"

    def test_sosfs_from_the_shared_list_and_socialstyrelsens_index(self):
        sosfs = type(self.SOSFS)()
        self.assertEqual(sosfs.parse_listing(self.listing(), sosfs.listing_url), [])  # all wait for the index
        index = '[{"name":"SOSFS 2011:9 Ledningssystem","url":"/publikationer/sosfs-20119-ledningssystem/"}]'
        entries = sosfs.parse_listing(index, sosfs.SOS_INDEX)
        # SOSFS 1997:14 has no publication page in the index of regulations in force
        self.assertEqual([(e.number, e.url, e.amended_by) for e in entries], [
            ("SOSFS 2011:9", "https://www.socialstyrelsen.se/publikationer/sosfs-20119-ledningssystem/", [])])

    def test_titles_and_repealed_pages(self):
        tlvfs = type(self.TLVFS)()
        [entry] = tlvfs.parse_listing(self.listing(), tlvfs.listing_url)
        self.assertEqual((entry.number, entry.title),
                         ("TLVFS 2009:3", "Tandvårds- och läkemedelsförmånsverkets föreskrifter om handelsmarginal"))
        fohmfs = type(self.FOHMFS)()
        self.assertEqual([e.number for e in fohmfs.parse_listing(self.listing(), fohmfs.listing_url)],
                         ["FoHMFS 2014:7"])

class KvfsLivsfsMyhfsTest(unittest.TestCase):
    KVFS = agency.ADAPTERS["KVFS"]
    LIVSFS = agency.ADAPTERS["LIVSFS"]
    MYHFS = agency.ADAPTERS["MYHFS"]

    def test_kvfs_sitemap_and_page_title(self):
        prefix = "https://www.kriminalvarden.se" + self.KVFS.path_prefix
        sitemap = f"""<urlset><url><loc>{prefix}fangelse/kvfs-20111--fark-fangelse/</loc></url>
          <url><loc>{prefix}frivard/kvfs-20245--fark-frivard/</loc></url>
          <url><loc>https://www.kriminalvarden.se/om-oss/kvfs-20101/</loc></url></urlset>"""
        entries = self.KVFS.parse_listing(sitemap, self.KVFS.listing_url)
        self.assertEqual([e.number for e in entries], ["KVFS 2024:5", "KVFS 2011:1"])
        page = """<div class="regulationPage col-12"><div class="intro"><h1>KVFS 2011:1 – FARK Fängelse</h1>
          <p>KVFS 2011:1 - Kriminalvårdens föreskrifter och allmänna råd om fängelse.</p></div>
          <a href="/globalassets/dokument/foreskrifter/kvfs-2011-1.pdf">Ladda ner</a></div>"""
        regulation = self.KVFS.parse_detail(page, entries[1])
        self.assertEqual(regulation.title, "Kriminalvårdens föreskrifter och allmänna råd om fängelse")
        self.assertEqual([url.rsplit("/", 1)[-1] for _, url in regulation.pdfs], ["kvfs-2011-1.pdf"])
        amending = page.replace("2011:1", "2024:5").replace("om fängelse", "om ändring i föreskrifterna (KVFS 2011:4)")
        with self.assertRaises(agency.NotBase):
            self.KVFS.parse_detail(amending, entries[0])

    def test_livsfs_year_tables_link_amendments_across_years(self):
        def row(number, status, file, subject="Ämne"):
            return (f'<tr><td><p><a title="{number}" href="/x/{file}.pdf">{number}</a></p></td>'
                    f"<td><p>{status}</p></td><td><p>{subject}</p></td></tr>")

        newer = ("<table><thead><tr><th>LIVSFS</th></tr></thead><tbody>"
                 + row("LIVSFS 2024:3", "Ändrar LIVSFS 2006:12<br />Gällande", "livsfs-2024-3")
                 + row("LIVSFS 2024:2", "Upphäver LIVSFS 2012:6<br />Gällande", "livsfs-2024-2")
                 + row("LIVSFS 2022:4 rättelse", "Rättar LIVSFS 2022:4", "livsfs-2022-4-rattelseblad")
                 + "</tbody></table>")
        older = ("<table><tbody>"
                 + row("LIVSFS 2006:12", "Gällande", "livsfs-2006-12",
                       "Livsmedelsverkets förteckning över gällande föreskrifter")
                 + row("LIVSFS 2006:11", "Upphävd genom LIVSFS 2024:2", "livsfs-2006-11")
                 + row("LIVSFS 2006:2", "Ändrar LIVSFS 2005:20<br />Upphävd genom LIVSFS 2006:12", "livsfs-2006-2")
                 + "</tbody></table>")
        index_url = self.LIVSFS.listing_url
        index = "".join(f'<a href="/om-oss/lagstiftning1/foreskrifter-i-nummerordning/foreskrifter-i-nummerordning-{y}/">'
                        f"{y}</a>" for y in (2004, 2006, 2024, 2017))
        self.assertEqual(self.LIVSFS.parse_listing(index, index_url), [])
        pages = self.LIVSFS.more_pages(index, index_url)
        self.assertEqual([p.rstrip("/")[-4:] for p in pages], ["2024", "2017", "2006", "2004"])  # LIVSFS since 2002
        slvfs = agency.ADAPTERS["SLVFS"]  # every year: later LIVSFS rows amend or replace SLVFS ones
        self.assertEqual([p.rstrip("/")[-4:] for p in slvfs.more_pages(index.replace("2017", "1998"), index_url)],
                         ["2024", "2006", "2004", "1998"])
        slvfs.parse_listing(index, index_url)
        self.assertEqual(slvfs.parse_listing(newer.replace("Ändrar LIVSFS 2006:12", "Ersätter SLVFS 2001:4"),
                                             pages[0]), [])
        old = ('<table><tbody><tr><td><a title="SLVFS 2001:4" href="/x/slvfs-2001-4.pdf">SLVFS 2001:4</a></td>'
               "<td>Ersätter SLVFS 2000:1</td><td>Förteckning</td></tr>"
               '<tr><td><a title="SLVFS 2000:1" href="/x/slvfs-2000-1.pdf">SLVFS 2000:1</a></td>'
               "<td>Ersätter SLVFS 1999:8</td><td>Förteckning</td></tr></tbody></table>")
        self.assertEqual([(e.number, e.base) for e in slvfs.parse_listing(old, pages[-1])],
                         [("SLVFS 2001:4", False), ("SLVFS 2000:1", False)])
        self.assertEqual(self.LIVSFS.more_pages(index, pages[0]), [])
        entries = self.LIVSFS.parse_listing(newer, pages[0])
        self.assertEqual([(e.number, e.base) for e in entries], [("LIVSFS 2024:3", False), ("LIVSFS 2024:2", True)])
        self.assertEqual(entries[1].title, "LIVSFS 2024:2")  # the title comes from the PDF
        entries = self.LIVSFS.parse_listing(older, pages[-1])
        self.assertEqual([(e.number, e.base, e.amended_by) for e in entries],
                         [("LIVSFS 2006:12", True, ["LIVSFS 2024:3"]), ("LIVSFS 2006:11", False, []),
                          ("LIVSFS 2006:2", False, [])])
        self.assertEqual(entries[0].url, "https://www.livsmedelsverket.se/x/livsfs-2006-12.pdf")
        self.assertEqual(entries[0].title, "Livsmedelsverkets förteckning över gällande föreskrifter")

    def test_myhfs_repeal_dates_from_both_lists(self):
        def item(number, title, *facts):
            lines = "".join(f"<p>{f}</p>" for f in (f"MYHFS-nummer: {number}",) + facts)
            return (f'<a href="https://assets.myh.se/docs/lag-ratt/myhfs/myhfs-{number.replace(":", "-")}.pdf">'
                    f'<div class="v-list-item__title">{title} <span>(pdf, 195 kB)</span></div>'
                    f'<div class="link-text">{lines}</div></a>')

        in_force = (item("2026:5", "Föreskrifter om ämnen", "I kraft: 2026-07-01",
                         "Genom föreskrifterna upphävs Myndigheten för yrkeshögskolans föreskrifter (MYHFS 2022:2).")
                    + item("2026:3", "Föreskrifter om upphävande av föreskrifterna (2017:2) om el",
                           "I kraft: 2026-03-01"))
        repealed = (item("2022:2", "Föreskrifter om kurser", "Genom dessa föreskrifter upphävs MYHFS 2018:2.")
                    + item("2022:1", "Föreskrifter om vårdadministratör", "Upphävd: 2026-03-01")
                    + item("2018:2", "Föreskrifter om behörighet")
                    + item("2017:2", "Föreskrifter om elinstallation", "I kraft: 2017-07-01"))
        entries = self.MYHFS.parse_listing(in_force, self.MYHFS.listings[0])
        self.assertEqual([(e.number, e.base, e.in_force, e.repealed) for e in entries],
                         [("MYHFS 2026:5", True, "2026-07-01", None), ("MYHFS 2026:3", False, "2026-03-01", None)])
        self.assertEqual(entries[0].title, "Föreskrifter om ämnen")
        entries = self.MYHFS.parse_listing(repealed, self.MYHFS.listings[1])
        self.assertEqual([(e.number, e.base, e.repealed) for e in entries],
                         [("MYHFS 2022:2", True, "2026-07-01"), ("MYHFS 2022:1", True, "2026-03-01"),
                          ("MYHFS 2018:2", False, None), ("MYHFS 2017:2", True, "2026-03-01")])
