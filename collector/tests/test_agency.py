import contextlib
import io
import json
import tempfile
import unittest
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
        self.assertEqual([e.number for e in entries], ["AFS 2023:1", "AFS 2023:3", "AFS 2023:4"])
        self.assertEqual(entries[0].url, AFS_1)
        self.assertEqual(entries[1].amended_by, ["AFS 2024:1"])
        self.assertEqual(entries[2].amended_by, ["AFS 2024:2"])
        self.assertTrue(all(e.base for e in entries))

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

    def test_rate_below_one_second_is_refused(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            agency.parse_args(["--series", "AFS", "--rate", "0.5"])
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            agency.parse_args(["--series", "XYZ"])


if __name__ == "__main__":
    unittest.main()
