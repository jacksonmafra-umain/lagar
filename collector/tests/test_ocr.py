import os
import unittest
from unittest import mock

from lagar import ocr, pdftext
from tests.test_pdftext import make_pdf

# CI installs tesseract with the Swedish model and sets this, so a missing tool fails instead of skipping.
REQUIRED = os.environ.get("LAGAR_REQUIRE_OCR") == "1"
HAVE_TOOLS = ocr.available()

HEADER = "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext"


def tsv(*words):
    """TSV rows for (block, paragraph, line, confidence, word) tuples, with the page and block rows tesseract adds."""
    rows = [HEADER, "1\t1\t0\t0\t0\t0\t0\t0\t2480\t3508\t-1\t", "2\t1\t1\t0\t0\t0\t0\t0\t100\t100\t-1\t"]
    for n, (block, par, line, conf, word) in enumerate(words, 1):
        rows.append(f"5\t1\t{block}\t{par}\t{line}\t{n}\t0\t0\t10\t10\t{conf}\t{word}")
    return "\n".join(rows) + "\n"


class ParseTsvTest(unittest.TestCase):
    def test_lines_and_paragraphs(self):
        text, total, count = ocr.parse_tsv(tsv(
            (1, 1, 1, 92, "Denna"), (1, 1, 1, 90, "författning"),
            (1, 1, 2, 91, "gäller."),
            (1, 2, 1, 95, "Ny"), (1, 2, 1, 93, "paragraf."),
        ))
        self.assertEqual(text, "Denna författning\ngäller.\n\nNy paragraf.")
        self.assertEqual((total, count), (461, 5))

    def test_low_confidence_lines_are_dropped(self):
        text, _total, count = ocr.parse_tsv(tsv(
            (1, 1, 1, 92, "Riksarkivet"),
            (2, 1, 1, 40, "Sa"), (2, 1, 1, 22, "J/jf%**?/"),
        ))
        self.assertEqual((text, count), ("Riksarkivet", 1))

    def test_blank_words_and_layout_rows_are_skipped(self):
        text, _total, count = ocr.parse_tsv(tsv((1, 1, 1, 95, " "), (1, 1, 1, 90, "Text")))
        self.assertEqual((text, count), ("Text", 1))


class ResultTest(unittest.TestCase):
    LINE = "1 § Denna föreskrift gäller inom Stockholms län och omfattar jakt på vildsvin."

    def test_confident_text_is_usable(self):
        read = ocr.result([(self.LINE, 90.0 * 12, 12), (self.LINE, 85.0 * 12, 12)])
        self.assertTrue(read.usable)
        self.assertEqual(read.pages, 2)

    def test_low_confidence_is_a_gap(self):
        read = ocr.result([(self.LINE, 50.0 * 12, 12)])
        self.assertEqual(read.gap, ocr.LOW_CONFIDENCE)

    def test_empty_pages_stay_a_scan(self):
        self.assertEqual(ocr.result([("", 0.0, 0), ("", 0.0, 0)]).gap, pdftext.NO_TEXT_LAYER)


class AvailableTest(unittest.TestCase):
    def test_missing_tool(self):
        with mock.patch("lagar.ocr.shutil.which", return_value=None):
            self.assertFalse(ocr.available())
            with self.assertRaises(ocr.OcrError):
                ocr.extract(b"%PDF-1.4")

    def test_missing_swedish_model(self):
        listed = mock.Mock(stdout=b'List of available languages in "/usr/share/tessdata/" (2):\neng\nosd\n')
        with mock.patch("lagar.ocr.shutil.which", return_value="/usr/bin/tool"), \
                mock.patch("lagar.ocr.subprocess.run", return_value=listed):
            self.assertFalse(ocr.available())


@unittest.skipUnless(HAVE_TOOLS or REQUIRED, "pdftoppm and tesseract with the Swedish model are not installed")
class ExtractTest(unittest.TestCase):
    def test_rendered_page_is_read(self):
        pdf = make_pdf([["Föreskrifter om gallring hos Riksarkivet;", "beslutade den 19 oktober 1992.",
                         "Denna författning träder i kraft den 2 november 1992."]])
        read = ocr.extract(pdf)
        self.assertTrue(read.usable, read.gap)
        self.assertIn("beslutade den 19 oktober 1992", read.text)
        self.assertIn("träder i kraft", read.text)

    def test_blank_page_stays_a_gap(self):
        self.assertFalse(ocr.extract(make_pdf([None])).usable)

    def test_broken_pdf_raises(self):
        with self.assertRaises(ocr.OcrError):
            ocr.extract(b"%PDF-1.4\nnot a pdf")
