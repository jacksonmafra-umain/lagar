import json
import tempfile
import unittest
from pathlib import Path

from lagar import corpusstats, frontmatter, schema
from tests.test_schema import new_layer_meta


def write_doc(root, meta, body):
    path = root / "corpus" / f"{meta['id']}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("---\n" + frontmatter.dump(meta) + "---\n" + body, encoding="utf-8")


class TextOriginTest(unittest.TestCase):
    def test_markers(self):
        agency = new_layer_meta("agency_regulation")
        self.assertEqual(corpusstats.text_origin({**agency, "text_source": "ocr"}, "x"), corpusstats.OCR)
        self.assertEqual(corpusstats.text_origin(agency, "## Författningstext\n\nTexten är hämtad ur pdf:en X."),
                         corpusstats.PDF)
        self.assertEqual(corpusstats.text_origin(agency, "Pdf:en är inskannad och saknar textlager."),
                         corpusstats.NONE)
        self.assertEqual(corpusstats.text_origin(agency, "## Författningstext\n\n**1 §** Text."), corpusstats.WEB)

    def test_manifest_values(self):
        county = new_layer_meta("county_regulation")
        self.assertEqual(corpusstats.text_origin(county, "Text", ["extracted"]), corpusstats.PDF)
        self.assertEqual(corpusstats.text_origin(county, "Text", ["extracted", "ocr"]), corpusstats.OCR)
        municipal = new_layer_meta("municipal_regulation")
        self.assertEqual(corpusstats.text_origin(municipal, "Länk", [None]), corpusstats.NONE)
        self.assertEqual(corpusstats.text_origin(municipal, "Texten är hämtad från kommunens webbsida.", [None]),
                         corpusstats.WEB)


class ReportTest(unittest.TestCase):
    def test_counts_and_render(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agency = new_layer_meta("agency_regulation")
            self.assertEqual(schema.validate(agency), [])
            write_doc(root, {**agency, "id": "a-1", "source": "https://www.example.se/a.pdf"},
                      "## Författningstext\n\nTexten är hämtad ur pdf:en A.\n\n**1 §** Ett.\n\n**2 §** Två.\n")
            write_doc(root, {**agency, "id": "a-2", "text_source": "ocr", "source": "https://www.example.se/b.pdf"},
                      "## Författningstext\n\nTexten är maskinläst (OCR).\n\n1 § Ett.\n")
            write_doc(root, {**agency, "id": "a-3", "source": "https://www.example.se/c.pdf"},
                      "Pdf:en är inskannad och saknar textlager.\n")
            (root / "sources").mkdir()
            (root / "sources/sfs-pdf-verification.json").write_text(json.dumps(
                {"threshold": 0.97, "entries": [{"status": "match"}, {"status": "match"}, {"status": "differs"}]}))
            report = corpusstats.summarise(corpusstats.collect(root), "2026-10-31T00:00:00Z")
        self.assertEqual(report["documents"], 3)
        layer = report["layers"]["agency"]
        self.assertEqual(layer["types"]["agency_regulation"]["sections"], 3)
        self.assertEqual(layer["text"], {"web": 0, "pdf": 1, "ocr": 1, "none": 1})
        self.assertEqual(layer["hosts"], {"example.se": 3})
        self.assertEqual(report["pdf"]["agency"]["scanned"], 2)
        self.assertEqual(report["pdf"]["agency"]["still_without_text"], 1)
        self.assertEqual(report["quality"]["sfs_pdf_verification"]["match_rate"], 0.6667)
        text = corpusstats.render(report)
        self.assertIn("The corpus holds 3 documents", text)
        self.assertIn("66.7 % match the print", text)
        self.assertIn("Not measured yet", text)


if __name__ == "__main__":
    unittest.main()
