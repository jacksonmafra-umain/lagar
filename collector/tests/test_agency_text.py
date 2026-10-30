import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from lagar import agency, agency_text, frontmatter, pdftext
from tests.test_agency import FakeClient
from tests.test_pdftext import HAVE_TOOL, REQUIRED, make_pdf

MASTHEAD = """Migrationsverkets författningssamling
ISSN 1650–2515
Ansvarig utgivare: Helene Sjövall, Migrationsverket

Migrationsverkets föreskrifter om
försörjningskravet för studier

MIGRFS
2026:14
Publicerad den
2026-10-20

beslutade den 20 oktober 2026.
Migrationsverket föreskriver följande.
1 § Den som avser studera ska ha medel för sitt uppehälle under
tillståndstiden.
- i en anmälan om verksamhet,
- i en ansökan.
2 § Kravet gäller även *andra*.

MIGRFS 2026:14

Dessa föreskrifter träder i kraft den 1 november 2026.
"""

PDF_LINES = [
    "Migrationsverkets författningssamling",
    "",
    "Migrationsverkets föreskrifter om försörjningskravet för studier",
    "",
    "MIGRFS 2026:14",
    "Publicerad den 2026-10-20",
    "",
    "beslutade den 20 oktober 2026.",
    "Migrationsverket föreskriver följande och detta är en tillräckligt lång rad.",
    "1 § Den som avser studera ska ha tillräckliga medel för sitt uppehälle under",
    "tillståndstiden och för att täcka kostnaderna för sin återresa till hemlandet.",
    "Dessa föreskrifter träder i kraft den 1 november 2026.",
]


class TextTest(unittest.TestCase):
    def test_dates(self):
        self.assertEqual(agency_text.dates(MASTHEAD), ("2026-10-20", "2026-10-20", "2026-11-01"))
        self.assertEqual(agency_text.dates("Utkom från trycket\nden 23 juni 2026\nbeslutade den 10 juni 2026. "
                                           "Föreskrifterna träder i kraft samma dag som de publiceras."),
                         ("2026-06-10", "2026-06-23", "2026-06-23"))
        self.assertEqual(agency_text.dates("ingen datumuppgift"), (None, None, None))

    def test_markdown_skips_the_masthead_and_running_headers(self):
        text = agency_text.to_markdown(MASTHEAD, "MIGRFS 2026:14")
        self.assertTrue(text.startswith("beslutade den 20 oktober 2026."))
        self.assertIn("**1 §** Den som avser studera ska ha medel för sitt uppehälle under tillståndstiden.", text)
        self.assertIn("\n\n- i en anmälan om verksamhet,\n\n- i en ansökan.", text)
        self.assertIn("\\*andra\\*", text)
        self.assertNotIn("\n\nMIGRFS 2026:14\n\n", text)
        self.assertNotIn("ISSN", text)

    def test_title_from_the_masthead(self):
        self.assertEqual(agency_text.title(MASTHEAD), "Migrationsverkets föreskrifter om försörjningskravet för studier")
        self.assertIsNone(agency_text.title("Ingen början här."))

    def test_unreadable_pdf_is_a_gap(self):
        read = agency_text.read(b"%PDF-1.7 not really", "MIGRFS 2026:14")
        self.assertEqual(read.text, "")
        self.assertTrue(read.gap)


@unittest.skipUnless(HAVE_TOOL or REQUIRED, "pdftotext is not installed")
class RunTextTest(unittest.TestCase):
    MIGRFS = agency.ADAPTERS["MIGRFS"]
    PDF = "https://www.migrationsverket.se/download/18.1/1/MIGRFS_2026_14.pdf"
    LISTING = ('<ul><li class="sv-channel-item"><a href="/download/18.1/1/MIGRFS_2026_14.pdf">MIGRFS 2026:14</a>'
               "</li></ul>")

    def run_collector(self, pdf, *extra):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        client = FakeClient({self.MIGRFS.listing_url: self.LISTING.encode(), self.PDF: pdf})
        argv = ["--series", "MIGRFS", "--corpus", str(root / "corpus"), "--state", str(root / "state.json"),
                "--manifest", str(root / "manifest.json"), *extra]
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(agency.main(argv, client=client), 0)
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        return client, frontmatter.load((root / "corpus/agency/regulations/migrfs-2026-14.md").read_text("utf-8")), manifest

    def test_text_title_and_dates_from_the_pdf(self):
        client, (meta, body), manifest = self.run_collector(make_pdf([PDF_LINES]))
        self.assertEqual(client.calls.count(self.PDF), 1)  # hashed and read from one download
        self.assertEqual(meta["title"], "Migrationsverkets föreskrifter om försörjningskravet för studier")
        self.assertEqual((meta["issued"], meta["in_force"]), ("2026-10-20", "2026-11-01"))
        self.assertIn("Texten är hämtad ur pdf:en MIGRFS 2026:14.", body)
        self.assertIn("**1 §** Den som avser studera", body)
        self.assertEqual(manifest["entries"][0]["files"][0]["url"], self.PDF)

    def test_scanned_pdf_is_recorded_as_a_gap(self):
        _, (meta, body), _ = self.run_collector(make_pdf([None]))
        self.assertEqual(meta["title"], "MIGRFS 2026:14")
        self.assertIn("Pdf:en är inskannad och saknar textlager.", body)

    def test_no_pdf_text(self):
        _, (_, body), _ = self.run_collector(make_pdf([PDF_LINES]), "--no-pdf-text")
        self.assertIn("publicerar texten endast som pdf", body)
        self.assertNotIn("**1 §**", body)


class ToolTest(unittest.TestCase):
    def test_missing_tool_stops_the_run(self):
        original = pdftext.available
        pdftext.available = lambda: False
        self.addCleanup(setattr, pdftext, "available", original)
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(agency.main(["--series", "MIGRFS"], client=FakeClient({})), 1)
        self.assertIn("pdftotext", err.getvalue())


if __name__ == "__main__":
    unittest.main()
