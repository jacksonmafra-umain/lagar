import contextlib
import hashlib
import io
import json
import tempfile
import unittest
import unittest.mock
import urllib.error
from pathlib import Path

from lagar import agency, frontmatter, schema
from lagar.http import Blocked

FIXTURES = Path(__file__).resolve().parent / "fixtures"
AFS, FFFS, TSFS = agency.ADAPTERS["AFS"], agency.ADAPTERS["FFFS"], agency.ADAPTERS["TSFS"]
AFS_1 = "https://www.av.se/arbetsmiljoarbete-och-inspektioner/publikationer/foreskrifter/afs-20231/"
AFS_3 = "https://www.av.se/arbetsmiljoarbete-och-inspektioner/publikationer/foreskrifter/afs-20233/"
AFS_4 = "https://www.av.se/arbetsmiljoarbete-och-inspektioner/publikationer/foreskrifter/afs-20234/"
FFFS_DETAIL = "https://www.fi.se/sv/vara-register/fffs/sok-fffs/2015/20151/"
FFFS_PDFS = (
    "https://www.fi.se/contentassets/56c6ee74bd65465fa3a5bd141fff0f17/fs1501.pdf",
    "https://www.fi.se/contentassets/56c6ee74bd65465fa3a5bd141fff0f17/fs1501k-20250623.pdf",
)
TSFS_2025 = TSFS.year_url(2025)
XFS = agency.ListedAdapter("XFS", "Exempelverket", ["https://www.example.se/forfattningar/"])
XFS_2013_1 = "https://www.example.se/download/18.1/1/XFS+2013_1.pdf"
XFS_2013_1_CONSOLIDATED = "https://www.example.se/globalassets/xfs/konsoliderad-xfs-2013-1.pdf"
AV_ROBOTS = (
    "User-agent: *\n"
    "Disallow: /globalassets/filer/publikationer/foreskrifter/ursprungs/\n"
    "Disallow: /sok/\n"
).encode()


def fixture(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


def http_error(url, code):
    return urllib.error.HTTPError(url, code, "err", {}, io.BytesIO(b""))


class FakeClient:
    """Serves a URL -> bytes map; robots.txt is a 404 unless given; anything else is a 404."""

    def __init__(self, pages, robots=None):
        self.pages = pages
        self.robots = robots or {}
        self.calls = []

    def fetch(self, url):
        self.calls.append(url)
        if url.endswith("/robots.txt"):
            host = url.removesuffix("/robots.txt")
            if host not in self.robots:
                raise http_error(url, 404)
            return self.robots[host], "text/plain"
        page = self.pages.get(url)
        if page is None:
            raise http_error(url, 404)
        if isinstance(page, Exception):
            raise page
        return page, "application/pdf" if url.endswith(".pdf") else "text/html"

    def get(self, url):
        return self.fetch(url)[0]


def afs_pages(detail_1=None):
    return {
        AFS.listing_url: fixture("agency-afs-listing.html").encode(),
        AFS_1: (detail_1 or fixture("agency-afs-detail.html")).encode(),
        AFS_4: fixture("agency-afs-detail-consolidated.html").encode(),
    }


class ParseTest(unittest.TestCase):
    def test_afs_listing(self):
        entries = AFS.parse_listing(fixture("agency-afs-listing.html"), AFS.listing_url)
        self.assertEqual([e.number for e in entries], ["AFS 2023:1", "AFS 2023:3", "AFS 2023:4", "AFS 2005:4"])
        # The repealing regulations under "Gällande ändringsföreskrifter" are not base regulations.
        self.assertEqual([e.base for e in entries], [True, True, True, False])
        self.assertEqual(entries[0].url, AFS_1)
        self.assertEqual(entries[1].amended_by, ["AFS 2024:1"])
        self.assertEqual(entries[2].amended_by, ["AFS 2024:2"])

    def test_afs_base_detail(self):
        entry = AFS.parse_listing(fixture("agency-afs-listing.html"), AFS.listing_url)[0]
        regulation = AFS.parse_detail(fixture("agency-afs-detail.html"), entry)
        self.assertTrue(regulation.title.startswith("Arbetsmiljöverkets föreskrifter och allmänna råd (AFS 2023:1)"))
        self.assertEqual((regulation.issued, regulation.published, regulation.in_force),
                         ("2023-09-15", "2023-11-22", "2025-01-01"))
        self.assertEqual(regulation.version, "Grundförfattning")
        self.assertIsNone(regulation.amended_through)
        text = regulation.text
        self.assertIn("Arbetsmiljöverket föreskriver[1] följande med stöd av 18 §", text)
        self.assertIn("**1 §** Syftet med dessa föreskrifter", text)
        self.assertIn("\n### Varför föreskrifterna finns", "\n" + text)
        self.assertIn("**Allmänna råd**", text)
        self.assertIn("1. Denna författning träder i kraft den 1 januari 2025.", text)
        self.assertIn("- a) valet av andra arbetstagare", text)
        self.assertNotIn("Stöd och verktyg", text)  # guidance link dropped
        self.assertEqual(len(regulation.footnotes), 1)
        self.assertIn("89/391/EEG", regulation.footnotes[0])

    def test_afs_consolidated_detail(self):
        entry = AFS.parse_listing(fixture("agency-afs-listing.html"), AFS.listing_url)[2]
        regulation = AFS.parse_detail(fixture("agency-afs-detail-consolidated.html"), entry)
        self.assertEqual(regulation.version, "Konsoliderad version")
        self.assertEqual(regulation.amended_through, "AFS 2024:2")
        self.assertIsNone(regulation.in_force)
        self.assertIn("a) Maskin | – en sammansatt enhet", regulation.text)
        self.assertNotIn("Visa hela tabellen", regulation.text)
        self.assertIn("**4 §** I dessa föreskrifter", regulation.text)

    def test_afs_detail_for_another_number_fails(self):
        entry = agency.Entry("AFS 2023:9", "x", AFS_1)
        with self.assertRaises(ValueError):
            AFS.parse_detail(fixture("agency-afs-detail.html"), entry)

    def test_fffs_listing_and_detail(self):
        entries = FFFS.parse_listing(fixture("agency-fffs-listing.html"), FFFS.listing_url)
        self.assertEqual([(e.number, e.base) for e in entries],
                         [("FFFS 2026:33", False), ("FFFS 2025:12", False), ("FFFS 2015:1", True)])
        self.assertEqual(entries[2].url, FFFS_DETAIL)
        regulation = FFFS.parse_detail(fixture("agency-fffs-detail.html"), entries[2])
        self.assertEqual(regulation.title, "Föreskrifter och allmänna råd om information om ränta på bostadskrediter")
        self.assertEqual(regulation.in_force, "2015-06-01")
        self.assertEqual([url for _, url in regulation.pdfs], list(FFFS_PDFS))
        self.assertEqual(regulation.amended_by, ["FFFS 2025:12", "FFFS 2026:33"])
        self.assertEqual(regulation.amendments[0].in_force, "2026-11-20")
        self.assertTrue(regulation.summary.startswith("## Sammanfattning"))
        self.assertEqual(regulation.text, "")

    def test_tsfs_index_listing_and_detail(self):
        self.assertEqual(TSFS.parse_index(fixture("agency-tsfs-index.html")), [2026, 2025, 2024])
        entries = TSFS.parse_listing(fixture("agency-tsfs-listing.html"), TSFS_2025)
        self.assertEqual([(e.number, e.base) for e in entries],
                         [("TSFS 2025:1", True), ("TSFS 2025:2", True), ("TSFS 2025:4", False)])
        self.assertEqual(entries[0].title, "Transportstyrelsens föreskrifter om utlämnande av körkort")
        self.assertEqual((entries[0].in_force, entries[0].repealed), ("2025-02-01", "2026-02-01"))
        self.assertTrue(entries[0].url.endswith("/2025/details?RuleNumber=2025:1&ruleprefix=TSFS"))
        entry = agency.Entry("TSFS 2009:19", "x", "https://www.transportstyrelsen.se/d")
        regulation = TSFS.parse_detail(fixture("agency-tsfs-detail.html"), entry)
        self.assertTrue(regulation.title.startswith("Transportstyrelsens föreskrifter och allmänna råd om användning av däck"))
        self.assertEqual(regulation.in_force, "2009-04-29")
        self.assertEqual(regulation.pdfs, [
            ("TSFS 2009:19 (konsoliderad version)", "https://www.transportstyrelsen.se/TSFS/TSFS%202009_19k.pdf"),
            ("TSFS 2009:19", "https://www.transportstyrelsen.se/TSFS/TSFS_2009-19.pdf"),
        ])
        self.assertEqual(regulation.amended_by, ["TSFS 2009:90", "TSFS 2019:44"])
        self.assertEqual(regulation.amendments[0].scope, "Ändr. 5, 8, 19, 23 och 27 §§.")

    def test_tsfs_amending_titles_and_pages(self):
        self.assertTrue(agency._TSFS_AMENDING.match("Föreskrifter om ändringar i Transportstyrelsens föreskrifter"))
        self.assertFalse(agency._TSFS_AMENDING.match("Transportstyrelsens föreskrifter om fartygsåtervinning"))
        # An amending regulation's page shows its base regulation and lists it as an amendment.
        entry = agency.Entry("TSFS 2019:44", "x", "https://www.transportstyrelsen.se/d")
        with self.assertRaises(agency.NotBase):
            TSFS.parse_detail(fixture("agency-tsfs-detail.html"), entry)
        with self.assertRaises(ValueError):
            TSFS.parse_detail(fixture("agency-tsfs-detail.html"), agency.Entry("TSFS 2019:4", "x", "u"))

    def test_listed_listing(self):
        entries = XFS.parse_listing(fixture("agency-listed-listing.html"), XFS.listing_url)
        self.assertEqual([(e.number, e.base) for e in entries], [
            ("XFS 2013:1", True), ("XFS 2016:2", True), ("XFS 2015:1", True), ("XFS 2022:1", True),
            ("XFS 2014:1", False), ("XFS 2020:2", False), ("XFS 2021:1", False)])
        first, fees, reprinted, bare = entries[:4]
        self.assertEqual(first.title, "Exempelverkets föreskrifter om prov")
        self.assertEqual(first.url, XFS_2013_1)
        self.assertEqual(first.amended_by, ["XFS 2014:1"])
        self.assertEqual(first.pdfs, [("XFS 2013:1", XFS_2013_1),
                                      ("XFS 2013:1 (konsoliderad version)", XFS_2013_1_CONSOLIDATED)])
        # The amending regulation's own number comes from its file name.
        self.assertEqual((fees.title, fees.amended_by), ("Exempelverkets föreskrifter om avgifter", ["XFS 2020:2"]))
        # A base regulation known only through its reprint.
        self.assertEqual(reprinted.amended_by, ["XFS 2021:1"])
        self.assertEqual(reprinted.pdfs[0][0], "XFS 2015:1 (omtryck genom XFS 2021:1)")
        self.assertEqual(bare.title, "XFS 2022:1")
        self.assertEqual(len(bare.pdfs), 1)  # the guidance PDF is not part of the regulation

    def test_listed_folders_and_spaced_numbers(self):
        yfs = agency.ListedAdapter("YFS", "Yverket", ["https://www.example.se/forfattningar/"], separator="[: ]",
                                   base_href=r"grund/yfs-(\d{4})-(\d+)/")
        entries = yfs.parse_listing(fixture("agency-listed-folders.html"), yfs.listing_url)
        self.assertEqual([(e.number, e.base) for e in entries], [
            ("YFS 2011:2", True), ("YFS 2021:1", True), ("YFS 2014:3", False), ("YFS 2016:1", False)])
        stod, fees = entries[:2]
        self.assertEqual(stod.title, "Föreskrifter om stöd")
        # A regulation filed under another base's folder that also has its own folder is a base regulation.
        self.assertEqual(stod.amended_by, ["YFS 2014:3", "YFS 2016:1", "YFS 2021:1"])
        self.assertEqual([label for label, _ in stod.pdfs], ["YFS 2011:2", "YFS 2011:2 (omtryck genom YFS 2014:3)"])
        self.assertEqual(len(fees.pdfs), 1)  # one PDF per label; the corrigendum is skipped

    def test_listed_detail_pages(self):
        zfs = agency.ListedAdapter("ZFS", "Zverket", ["https://www.example.se/regler/"], detail_pages=True,
                                   documents="/contentassets/")
        listing = '<a href="/publ/zfs-20181/">ZFS 2018:1</a><a href="/publ/zfs-20197/">ZFS 2019:7</a>'
        entries = zfs.parse_listing(listing, zfs.listing_url)
        self.assertEqual([e.url for e in entries], ["https://www.example.se/publ/zfs-20181/",
                                                    "https://www.example.se/publ/zfs-20197/"])
        regulation = zfs.parse_detail(fixture("agency-listed-detail.html"), entries[0])
        self.assertEqual(regulation.title, "Zverkets föreskrifter om grundläggande bestämmelser")
        self.assertEqual(regulation.amended_by, ["ZFS 2019:7"])
        self.assertEqual([label for label, _ in regulation.pdfs], ["ZFS 2018:1", "ZFS 2018:1 (konsoliderad version)"])
        with self.assertRaises(agency.NotBase):
            zfs.parse_detail(fixture("agency-listed-detail.html"), entries[1])

    def test_stafs_index_and_markdown(self):
        stafs = agency.SwedacAdapter()
        entries = {e.number: e for e in stafs.parse_listing(fixture("agency-stafs-index.json"), stafs.listing_url)}
        self.assertEqual(sorted(n for n, e in entries.items() if e.base),
                         ["STAFS 2022:7", "STAFS 2024:13", "STAFS 2025:1"])
        self.assertFalse(entries["STAFS 2026:4"].base)  # amends 2022:7
        self.assertFalse(entries["STAFS 2019:3"].base)  # repeals other regulations
        self.assertFalse(entries["STAFS 2015:16"].base)  # repealed, no date known
        self.assertNotIn("Rättelse STAFS 2026:3", entries)
        consolidated = entries["STAFS 2022:7"]
        self.assertTrue(consolidated.url.endswith("/stafs-2022-7-konsol.md"))
        self.assertEqual(consolidated.amended_by, ["STAFS 2026:4"])
        self.assertEqual((entries["STAFS 2024:13"].in_force, entries["STAFS 2024:13"].repealed),
                         ("2025-01-01", "2026-01-01"))
        regulation = stafs.parse_detail("---\nid: STAFS 2022:7\n---\n# STAFS 2022:7 x\n\n## 1 kap.\n\ntext", consolidated)
        self.assertEqual((regulation.version, regulation.amended_through), ("Konsoliderad version", "STAFS 2026:4"))
        self.assertEqual([label for label, _ in regulation.pdfs], ["STAFS 2022:7", "STAFS 2022:7 (konsoliderad version)"])
        self.assertEqual(regulation.text, "### 1 kap.\n\ntext")
        regulation = stafs.parse_detail(fixture("agency-stafs-2025-1.md"), entries["STAFS 2025:1"])
        self.assertEqual((regulation.issued, regulation.published, regulation.in_force),
                         ("2025-02-04", "2025-02-06", "2025-04-01"))
        self.assertTrue(regulation.text.startswith("### Tillämpningsområde\n\n**1 §** Dessa föreskrifter"))
        self.assertIn("[STAFS 2016:1](https://regelverk.swedac.se/foreskrifter/swedac/stafs-2016-1.html)", regulation.text)
        self.assertIn("[^1]: EUT L 42", regulation.text)
        with self.assertRaises(ValueError):
            stafs.parse_detail("---\nid: STAFS 2020:1\n---\n", entries["STAFS 2025:1"])

    def test_prvfs_division_a1(self):
        prv = agency.PrvAdapter()
        entries = prv.parse_listing(fixture("agency-prvfs-a1.html"), prv.listing_url)
        self.assertEqual([e.number for e in entries], ["PRVFS 2026:1", "PRVFS 2011:1", "PRVFS 1977:2"])
        first, repealing, old = entries
        self.assertTrue(first.title.startswith("Patent- och registreringsverkets (PRV) föreskrifter om skydd"))
        self.assertNotIn("Bemyndigande", first.title)
        self.assertEqual(first.amended_by, ["PRVFS 2026:2"])  # an unlabelled link, numbered by its file name
        self.assertTrue(first.url.endswith("/26prvfs-1_o2.pdf"))
        self.assertIn("(PRVFS 1986:1, V:3)", repealing.title)  # a reference in the title, not an amendment
        self.assertEqual(repealing.amended_by, [])
        self.assertEqual(old.amended_by, ["PRVFS 1986:2"])
    def test_afs_a_listing(self):
        adapter = agency.AklagareAdapter()
        entries = adapter.parse_listing(fixture("agency-afs-a-listing.html"), adapter.listing_url)
        self.assertEqual([(e.number, e.base) for e in entries], [
            ("ÅFS 2023:7", True), ("ÅFS 2022:1", False), ("ÅFS 2024:7", False), ("ÅFS 2025:6", False),
            ("ÅFS 2026:2", False)])
        base = entries[0]
        self.assertEqual(base.title, "Åklagarmyndighetens föreskrifter om internationellt samarbete")
        self.assertEqual(base.amended_by, ["ÅFS 2026:2"])
        regulation = adapter.regulation(base)
        self.assertEqual((regulation.issued, regulation.published), ("2023-12-18", "2023-12-19"))
        self.assertEqual(regulation.pdfs, [("ÅFS 2023:7", base.url)])
        self.assertEqual(agency.corpus_id(base.number), "aafs-2023-7")

    def test_pmfs_listing_and_pages(self):
        polisen = agency.PolisenAdapter()
        text = fixture("agency-pmfs-listing.html")
        self.assertEqual(polisen.more_pages(text, polisen.listing_url),
                         [polisen.listing_url + "2/", polisen.listing_url + "3/"])
        entries = polisen.parse_listing(text, polisen.listing_url)
        self.assertEqual([e.number for e in entries], ["PMFS 2026:25", "PMFS 2023:7"])
        self.assertEqual(entries[0].in_force, "2026-11-01")
        self.assertTrue(entries[0].title.startswith("Polismyndighetens föreskrifter och allmänna råd om"))
        self.assertEqual(entries[1].amended_by, ["PMFS 2024:10"])
        self.assertEqual([label for label, _ in entries[1].pdfs], ["PMFS 2023:7", "PMFS 2023:7 (sammanställd version)"])

    def test_paginated_listing_reads_every_page(self):
        polisen = agency.PolisenAdapter()
        first = fixture("agency-pmfs-listing.html")
        pages = {polisen.listing_url: first.encode(), polisen.listing_url + "2/": first.encode(),
                 polisen.listing_url + "3/": first.encode()}
        client = FakeClient(pages)
        args = agency.parse_args(["--series", "PMFS"])
        entries = list(agency._entries(client, agency._Robots(client, polisen.base_url), polisen, args))
        self.assertEqual(len(entries), 6)
        self.assertEqual(client.calls.count(polisen.listing_url + "2/"), 1)

    def test_scb_fs_table_and_detail(self):
        scb = agency.ScbAdapter()
        entries = scb.parse_listing(fixture("agency-scb-fs-listing.html"), scb.listing_url)
        self.assertEqual([(e.number, e.base) for e in entries], [
            ("SCB-FS 2004:9", False), ("SCB-FS 2018:20", False), ("SCB-FS 2019:15", True), ("SCB-FS 2020:16", False)])
        base = entries[2]
        self.assertEqual(base.amended_by, ["SCB-FS 2020:16"])
        self.assertTrue(base.url.startswith("https://www.scb.se/link/"))
        regulation = scb.parse_detail(fixture("agency-scb-fs-detail.html"), base)
        self.assertEqual(regulation.published, "2019-04-04")
        self.assertFalse(regulation.title.endswith(";"))
        self.assertTrue(regulation.text.startswith("Statistiska centralbyrån (SCB) föreskriver"))
        self.assertIn("1 § Ägare till nybyggda hus", regulation.text)
        self.assertEqual(len(regulation.pdfs), 1)
        with self.assertRaises(ValueError):
            scb.parse_detail(fixture("agency-scb-fs-detail.html"), entries[3])

    def test_stemfs_archive(self):
        stem = agency.EnergimyndighetenAdapter()
        text = fixture("agency-stemfs-listing.html")
        self.assertEqual(stem.more_pages(text, stem.listing_url), [stem.listing_url + "&page=2"])
        entries = stem.parse_listing(text, stem.listing_url)
        self.assertEqual([(e.number, e.base) for e in entries],
                         [("STEMFS 2026:1", False), ("STEMFS 2025:4", True), ("STEMFS 2025:1", True)])
        self.assertEqual(entries[1].title,
                         "Statens energimyndighets föreskrifter om tillsynsavgifter för tillhandahållande och "
                         "användning av hållbara flygbränslen")
        self.assertNotIn("\u00ad", entries[2].title)
        self.assertIn("fn=STEMFS%202025_1webb.pdf", entries[2].url)
        self.assertIn("Upph%C3%A4vande", entries[0].url)

    def test_rfs_open_data(self):
        rfs = agency.RiksdagenAdapter()
        entries = {e.number: e for e in rfs.parse_listing(fixture("agency-rfs-list.json"), rfs.listing_url)}
        self.assertEqual(sorted(n for n, e in entries.items() if e.base), ["RFS 2019:1"])
        self.assertFalse(entries["RFS 2018:6"].base)  # repeals another regulation
        self.assertFalse(entries["RFS 2015:5"].base)  # repealed, no repeal date in the data
        self.assertFalse(entries["RFS 2026:6"].base)
        base = entries["RFS 2019:1"]
        self.assertEqual(base.amended_by, ["RFS 2026:6"])
        self.assertTrue(base.url.endswith("/dokument/H7D41f325.html"))  # the consolidated text
        regulation = rfs.parse_detail(fixture("agency-rfs-2019-1.html"), base)
        self.assertEqual((regulation.issued, regulation.amended_through), ("2019-03-28", "RFS 2026:6"))
        self.assertEqual(regulation.version, "Konsoliderad version")
        self.assertTrue(regulation.text.startswith("1 kap. Föreskriftens innehåll"))
        self.assertNotIn("Fulltextversion", regulation.text)
        with self.assertRaises(ValueError):
            rfs.parse_detail(fixture("agency-rfs-2019-1.html"), entries["RFS 2018:6"])

    def test_rafs_register(self):
        ra = agency.RiksarkivetAdapter()
        entries = {e.number: e for e in ra.parse_listing(fixture("agency-rafs-sok.json"), ra.listing_url)}
        self.assertEqual(sorted(n for n, e in entries.items() if e.base), ["RA-FS 2013:3", "RA-FS 2026:1"])
        self.assertFalse(entries["RA-FS 2015:2"].base)  # repealed by a regulation not in the fixture: no date
        repealed = entries["RA-FS 2013:3"]
        self.assertEqual(repealed.repealed, entries["RA-FS 2022:3"].in_force)
        self.assertEqual(repealed.amended_by, ["RA-FS 2018:9", "RA-FS 2022:3"])  # amended, then repealed
        current = entries["RA-FS 2026:1"]
        self.assertEqual((current.in_force, current.repealed), ("2026-10-05", None))
        self.assertEqual(current.url, "https://foreskrifter.riksarkivet.se/api/rafs/pdf/rafs%2FRA-FS%202026-1.pdf")

    def test_listed_series_config(self):
        series = agency.load_series()
        for code, adapter in series.items():
            self.assertEqual(agency.ADAPTERS[code].listing_urls(None), adapter.listing_urls(None))
            self.assertTrue(adapter.listing_url.startswith("https://"), code)
        self.assertEqual(agency.load_series(Path("/nonexistent.json")), {})

    def test_ids_and_numbers(self):
        self.assertEqual(agency.corpus_id("AFS 2023:1"), "afs-2023-1")
        self.assertEqual(agency.corpus_id("HSLF-FS 2016:40"), "hslf-fs-2016-40")
        self.assertEqual(agency.number_key("TSFS 2009:90"), (2009, 90))

    def test_meta_is_valid(self):
        entry = AFS.parse_listing(fixture("agency-afs-listing.html"), AFS.listing_url)[2]
        regulation = AFS.parse_detail(fixture("agency-afs-detail-consolidated.html"), entry)
        meta = agency.build_meta(AFS, entry, regulation, "0" * 64, "2026-10-29T00:00:00Z")
        self.assertEqual(schema.validate(meta), [])
        self.assertEqual((meta["id"], meta["layer"], meta["issuer"]), ("afs-2023-4", "agency", "Arbetsmiljöverket"))


class RunTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.corpus = self.root / "corpus"
        self.state = self.root / "state.json"
        self.manifest = self.root / "manifest.json"
        self.report = self.root / "report.json"

    def main(self, client, *args):
        argv = ["--corpus", str(self.corpus), "--state", str(self.state),
                "--manifest", str(self.manifest), "--report", str(self.report), *args]
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return agency.main(argv, client=client)

    def read_report(self):
        return json.loads(self.report.read_text(encoding="utf-8"))

    def test_afs_run_writes_files_and_is_idempotent(self):
        client = FakeClient(afs_pages(), robots={AFS.base_url: AV_ROBOTS})
        self.assertEqual(self.main(client, "--series", "AFS"), 0)
        report = self.read_report()
        self.assertEqual(report["written"], ["AFS 2023:1", "AFS 2023:4"])
        self.assertEqual(report["failed"], ["AFS 2023:3"])  # no fixture page: a 404
        path = self.corpus / "agency" / "regulations" / "afs-2023-1.md"
        meta, body = frontmatter.load(path.read_text(encoding="utf-8"))
        self.assertEqual(schema.validate(meta), [])
        self.assertEqual(meta["source"], AFS_1)
        self.assertIn("## Fotnoter", body)
        self.assertNotIn("ursprungs", "".join(client.calls))
        before = path.read_bytes()

        # A rerun skips what is done; a refresh with the same text leaves files alone.
        self.assertEqual(self.main(client, "--series", "AFS"), 0)
        self.assertEqual(self.read_report()["skipped"], 2)
        self.assertEqual(self.main(client, "--series", "AFS", "--refresh"), 0)
        self.assertEqual(self.read_report()["unchanged"], 2)
        self.assertEqual(path.read_bytes(), before)

    def test_limit_and_number(self):
        client = FakeClient(afs_pages())
        self.assertEqual(self.main(client, "--series", "AFS", "--limit", "1"), 0)
        self.assertEqual(self.read_report()["written"], ["AFS 2023:1"])
        client = FakeClient(afs_pages())
        self.assertEqual(self.main(client, "--series", "AFS", "--number", "AFS 2023:4"), 0)
        self.assertEqual(self.read_report()["written"], ["AFS 2023:4"])
        self.assertNotIn(AFS_1, client.calls)

    def test_robots_disallow_is_recorded_and_not_fetched(self):
        robots = b"User-agent: *\nDisallow: /arbetsmiljoarbete-och-inspektioner/publikationer/foreskrifter/afs-20231/\n"
        client = FakeClient(afs_pages(), robots={AFS.base_url: robots})
        self.assertEqual(self.main(client, "--series", "AFS", "--number", "AFS 2023:1"), 0)
        self.assertNotIn(AFS_1, client.calls)
        state = json.loads(self.state.read_text(encoding="utf-8"))
        self.assertIn("robots.txt disallows", state["failed"]["AFS 2023:1"])

    def test_listing_disallowed_by_robots_blocks(self):
        client = FakeClient(afs_pages(), robots={AFS.base_url: b"User-agent: *\nDisallow: /\n"})
        self.assertEqual(self.main(client, "--series", "AFS"), 2)
        self.assertTrue(self.read_report()["blocked"])
        self.assertEqual(client.calls, [AFS.base_url + "/robots.txt"])

    def test_403_blocks(self):
        pages = afs_pages()
        pages[AFS_1] = Blocked("403 Forbidden: " + AFS_1)
        self.assertEqual(self.main(FakeClient(pages), "--series", "AFS"), 2)
        state = json.loads(self.state.read_text(encoding="utf-8"))
        self.assertIn("403", state["blocked"])

    def test_listing_error_exits_1(self):
        self.assertEqual(self.main(FakeClient({}), "--series", "AFS"), 1)

    def test_fffs_run_hashes_pdfs(self):
        pages = {
            FFFS.listing_url: fixture("agency-fffs-listing.html").encode(),
            FFFS_DETAIL: fixture("agency-fffs-detail.html").encode(),
            FFFS_PDFS[0]: b"%PDF-1.7 base",
            FFFS_PDFS[1]: b"%PDF-1.7 consolidated",
        }
        client = FakeClient(pages)
        self.assertEqual(self.main(client, "--series", "FFFS"), 0)
        report = self.read_report()
        self.assertEqual((report["written"], report["excluded"], report["pdfs"]), (["FFFS 2015:1"], 2, 2))
        manifest = json.loads(self.manifest.read_text(encoding="utf-8"))
        files = manifest["entries"][0]["files"]
        self.assertEqual([f["url"] for f in files], list(FFFS_PDFS))
        self.assertEqual(files[0]["bytes"], len(b"%PDF-1.7 base"))
        body = (self.corpus / "agency" / "regulations" / "fffs-2015-1.md").read_text(encoding="utf-8")
        self.assertIn("publicerar texten endast som pdf", body)
        self.main(client, "--series", "FFFS")
        self.assertEqual((self.read_report()["skipped"], self.read_report()["pdfs"]), (1, 0))
        self.assertEqual(client.calls.count(FFFS_PDFS[0]), 1)
        # --refresh hashes the PDFs again: a consolidated PDF can change behind the same URL.
        self.main(client, "--series", "FFFS", "--refresh")
        self.assertEqual(self.read_report()["pdfs"], 2)

    def test_non_pdf_response_fails(self):
        pages = {
            FFFS.listing_url: fixture("agency-fffs-listing.html").encode(),
            FFFS_DETAIL: fixture("agency-fffs-detail.html").encode(),
            FFFS_PDFS[0]: b"<html>error</html>",
            FFFS_PDFS[1]: b"%PDF-1.7",
        }
        self.assertEqual(self.main(FakeClient(pages), "--series", "FFFS"), 0)
        self.assertEqual(self.read_report()["failed"], ["FFFS 2015:1"])

    def test_tsfs_reads_only_the_requested_year(self):
        pages = {TSFS_2025: fixture("agency-tsfs-listing.html").encode()}
        client = FakeClient(pages)
        self.assertEqual(self.main(client, "--series", "TSFS", "--year", "2025"), 0)
        report = self.read_report()
        self.assertEqual(report["excluded"], 1)
        self.assertEqual(sorted(report["failed"]), ["TSFS 2025:1", "TSFS 2025:2"])  # no detail fixtures
        self.assertNotIn(TSFS.index_url, client.calls)

    def test_listed_run_hashes_pdfs_and_rebuilds(self):
        pages = {XFS.listing_url: fixture("agency-listed-listing.html").encode()}
        for entry in XFS.parse_listing(fixture("agency-listed-listing.html"), XFS.listing_url):
            for _, url in entry.pdfs:
                pages[url] = b"%PDF-1.7 " + url.encode()
        client = FakeClient(pages)
        with unittest.mock.patch.dict(agency.ADAPTERS, {"XFS": XFS}):
            self.assertEqual(self.main(client, "--series", "XFS"), 0)
            report = self.read_report()
            self.assertEqual(report["written"], ["XFS 2013:1", "XFS 2016:2", "XFS 2015:1", "XFS 2022:1"])
            self.assertEqual((report["excluded"], report["pdfs"]), (3, 5))
            path = self.corpus / "agency" / "regulations" / "xfs-2013-1.md"
            meta, body = frontmatter.load(path.read_text(encoding="utf-8"))
            self.assertEqual(schema.validate(meta), [])
            self.assertEqual(meta["source"], XFS_2013_1)
            self.assertEqual(meta["source_sha256"], hashlib.sha256(pages[XFS_2013_1]).hexdigest())
            self.assertEqual(meta["amended_by"], ["XFS 2014:1"])
            self.assertIn("(konsoliderad version)", body)
            # Every run rebuilds from the listing; PDFs in the manifest are not fetched again.
            self.assertEqual(self.main(client, "--series", "XFS"), 0)
            self.assertEqual((self.read_report()["unchanged"], self.read_report()["pdfs"]), (4, 0))
            self.assertEqual(client.calls.count(XFS_2013_1), 1)

    def test_listed_pdf_disallowed_by_robots_fails(self):
        pages = {XFS.listing_url: fixture("agency-listed-listing.html").encode()}
        client = FakeClient(pages, robots={XFS.base_url: b"User-agent: *\nDisallow: /download/\n"})
        with unittest.mock.patch.dict(agency.ADAPTERS, {"XFS": XFS}):
            self.assertEqual(self.main(client, "--series", "XFS", "--number", "XFS 2013:1"), 0)
        self.assertEqual(self.read_report()["failed"], ["XFS 2013:1"])
        self.assertNotIn(XFS_2013_1, client.calls)

    def test_rate_below_one_second_is_refused(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            agency.parse_args(["--series", "AFS", "--rate", "0.5"])
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            agency.parse_args(["--series", "XYZ"])

    def test_series_and_numbers_ignore_case(self):
        with unittest.mock.patch.dict(agency.ADAPTERS, {"XiFS": XFS}):
            args = agency.parse_args(["--series", "xifs", "--number", "XIFS 2013:1"])
        self.assertEqual((args.series, args.number), (["XiFS"], ["XiFS 2013:1"]))


if __name__ == "__main__":
    unittest.main()
