import json
import tempfile
import unittest
from pathlib import Path

from lagar import sfsverify, writer

PDF_TEXT = """Svensk författningssamling
Förordning
om ansvarig länsstyrelse
Utfärdad den 27 augusti 2026
1 §    Denna förordning är meddelad med stöd av 8 kap. 7 § regeringsformen
och innehåller bestämmelser om upp-
gifter enligt lagen (1969:620).
Denna förordning träder i kraft den 1 januari 2027.
SFS 2026:1700
"""

BODY = (
    "# Förordning (2026:1700) om ansvarig länsstyrelse\n\n"
    "/Träder i kraft I:2027-01-01/ **1 §** Denna förordning är meddelad med stöd av "
    "8 kap. 7 § regeringsformen och innehåller bestämmelser om uppgifter enligt lagen (1969:620).\n\n"
    "Denna förordning träder i kraft den 1 januari 2027.\n"
)


def meta(number, **extra):
    id_ = "sfs-" + number.replace(":", "-")
    return {
        "id": id_, "title": f"Förordning ({number})", "type": "ordinance", "layer": "sfs",
        "number": number, "issued": "2026-08-27", "in_force": None, "repealed": None,
        "amended_by": [], "amended_through": None, "reprinted_by": [], "ministry": None,
        "eli": None, "language": "sv", "authoritative": False,
        "source": "https://data.riksdagen.se/dokument/" + id_,
        "source_sha256": "a" * 64, "fetched_at": "2026-10-27T10:00:00Z", **extra,
    }


def pdf_entry(number):
    year, n = number.split(":")
    return {
        "number": number,
        "detail_url": f"https://svenskforfattningssamling.se/doc/{year}{n}.html",
        "published": "2026-09-01",
        "files": [{"url": f"https://svenskforfattningssamling.se/sites/default/files/sfs/2026-09/SFS{year}-{n}.pdf"}],
    }


class WordTests(unittest.TestCase):
    def test_pdf_joins_line_end_hyphenation(self):
        self.assertIn("uppgifter", sfsverify.pdf_words("om upp-\ngifter enligt"))

    def test_pdf_keeps_hyphen_before_capital(self):
        # "Stock-\nholms" style breaks join, but a dash before a name stays a break.
        self.assertEqual(sfsverify.pdf_words("EU-\nRådet"), ["eu", "rådet"])

    def test_corpus_drops_heading_markers_and_markup(self):
        words = sfsverify.corpus_words(BODY)
        self.assertEqual(words[:4], ["1", "denna", "förordning", "är"])
        self.assertNotIn("2027-01-01", " ".join(words))
        self.assertIn("1969:620", words)

    def test_compare_reports_first_missing_run(self):
        coverage, first = sfsverify.compare(["a", "b", "c", "d"], ["a", "x", "d"])
        self.assertEqual(coverage, 0.5)
        self.assertEqual(first, "b c")

    def test_compare_empty_corpus(self):
        self.assertEqual(sfsverify.compare([], ["a"]), (0.0, None))


class RunTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.corpus = self.tmp / "corpus"
        self.cache = self.tmp / "cache"
        self.manifest = self.tmp / "sfs-pdf-manifest.json"
        self.out = self.tmp / "verification.json"
        numbers = ["2026:1700", "2026:1701", "2026:1702", "2026:1703", "2026:1704"]
        self.manifest.write_text(json.dumps({"entries": [pdf_entry(n) for n in numbers]}), encoding="utf-8")
        writer.write(meta("2026:1700"), BODY, self.corpus)
        writer.write(meta("2026:1701"), BODY.replace("regeringsformen", "regeringsformen och tryckfrihetsförordningen"),
                     self.corpus)
        writer.write(meta("2026:1702", amended_by=["2026:1800"]), BODY + "Ny paragraf.\n", self.corpus)
        writer.write(meta("2026:1703"), BODY, self.corpus)  # PDF not cached
        for number in ("2026:1700", "2026:1701", "2026:1702", "2026:1704"):
            path = self.cache / "2026" / f"SFS2026-{number.split(':')[1]}.pdf"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"%PDF-")

    def args(self, *extra):
        return sfsverify.parse_args([
            "--manifest", str(self.manifest), "--cache", str(self.cache),
            "--corpus", str(self.corpus), "--out", str(self.out), *extra,
        ])

    def test_statuses_and_report(self):
        summary = sfsverify.run(self.args(), extract=lambda path: PDF_TEXT)
        self.assertEqual(summary, {
            "match": 1, "differs": 1, "amended": 1, "pdf_not_cached": 1, "no_corpus_document": 1,
        })
        report = json.loads(self.out.read_text(encoding="utf-8"))
        self.assertEqual(report["threshold"], sfsverify.THRESHOLD)
        by_number = {e["number"]: e for e in report["entries"]}
        self.assertEqual(by_number["2026:1700"]["coverage"], 1.0)
        self.assertEqual(by_number["2026:1701"]["first_difference"], "och tryckfrihetsförordningen")
        self.assertNotIn("first_difference", by_number["2026:1702"])
        self.assertEqual(by_number["2026:1704"], {"number": "2026:1704", "status": "no_corpus_document"})

    def test_extractor_failure_is_recorded(self):
        def broken(path):
            raise ValueError("bad xref")

        summary = sfsverify.run(self.args("--number", "2026:1700"), extract=broken)
        self.assertEqual(summary, {"extract_failed": 1})
        entry = json.loads(self.out.read_text(encoding="utf-8"))["entries"][0]
        self.assertEqual(entry["error"], "ValueError: bad xref")


if __name__ == "__main__":
    unittest.main()
