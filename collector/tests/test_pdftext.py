import os
import unittest
from unittest import mock

from lagar import pdftext

# CI installs poppler-utils and sets this, so a missing tool fails instead of skipping.
REQUIRED = os.environ.get("LAGAR_REQUIRE_PDFTOTEXT") == "1"
HAVE_TOOL = pdftext.available()

LINE = "1 § Denna föreskrift gäller inom Stockholms län och omfattar jakt på vildsvin."


def make_pdf(pages):
    """A minimal PDF; each page is a list of text lines, or None for a page with only a drawn box."""
    objects = ["<< /Type /Catalog /Pages 2 0 R >>", None]
    font = 3
    objects.append("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    kids = []
    for lines in pages:
        if lines is None:
            stream = b"0 0 0 rg 72 72 400 600 re f"
        else:
            parts = [b"BT /F1 11 Tf 14 TL 72 760 Td"]
            for line in lines:
                escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
                parts.append(b"(" + escaped.encode("cp1252") + b") Tj T*")
            parts.append(b"ET")
            stream = b"\n".join(parts)
        objects.append((b"<< /Length %d >>\nstream\n" % len(stream)) + stream + b"\nendstream")
        content = len(objects)
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            f"/Resources << /Font << /F1 {font} 0 R >> >> /Contents {content} 0 R >>"
        )
        kids.append(len(objects))
    objects[1] = f"<< /Type /Pages /Kids [{' '.join(f'{k} 0 R' for k in kids)}] /Count {len(kids)} >>"
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, 1):
        offsets.append(len(out))
        body = body if isinstance(body, bytes) else body.encode("latin-1")
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    for offset in offsets:
        out += b"%010d 00000 n \n" % offset
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref)
    return bytes(out)


class ClassifyTest(unittest.TestCase):
    def test_text_pages(self):
        result = pdftext.classify(f"{LINE}\n\f{LINE}\n\f")
        self.assertEqual((result.pages, result.text_pages), (2, 2))
        self.assertTrue(result.usable)
        self.assertNotIn("\f", result.text)

    def test_pages_without_text_are_a_scan(self):
        result = pdftext.classify("\f\f 3 \f")
        self.assertEqual(result.pages, 3)
        self.assertEqual(result.gap, pdftext.NO_TEXT_LAYER)
        self.assertFalse(result.usable)

    def test_mostly_scanned_pages_are_a_scan(self):
        result = pdftext.classify(f"{LINE}\f\f\f")
        self.assertEqual(result.gap, pdftext.NO_TEXT_LAYER)

    def test_cover_page_without_text_is_fine(self):
        self.assertTrue(pdftext.classify(f"\f{LINE}\f{LINE}\f").usable)

    def test_symbols_are_unreadable(self):
        garbled = "\u0001\u0002\u0003 " * 40 + "abcdefghij" * 5
        result = pdftext.classify(garbled)
        self.assertEqual(result.gap, pdftext.UNREADABLE_TEXT)

    def test_shifted_font_encoding_is_decoded(self):
        # 23FS 2001:2 as pdftotext reads it: Jämtland's fonts shift every character.
        shifted = (
            "===OP=cp=OMMNWO=\n======ríâçã=Ñê™å=íêóÅâÉí=\n===========i®åëëíóêÉäëÉå=\n"
            "hìåÖ∏êÉäëÉ=\ns®ÖîÉêâÉí=Ü~ê=ÇÉå=OM=ÇÉÅÉãÄÉê=OMMM=ÄÉëäìí~í=çã=Ñ∏êä®åÖåáåÖ=~î=\n"
            "SSO=_çå®ëÜ~ãå=Ó=eìë™=çÅÜ=î®Ö=SSP=íáää=c®îáâÉåI=ë~ãí=áåÇê~ÖåáåÖ=\n"
            "jÉÇ=ëí∏Ç=~î=NM=â~é=N=¬=~åÇê~=ëíóÅâÉí=NN=çÅÜ=P=¬=íê~ÑáâÑ∏êçêÇåáåÖÉå=ENVVUWNOTSF=\n"
        )
        result = pdftext.classify(shifted * 4 + "\f")
        self.assertTrue(result.usable)
        self.assertIn("23 FS 2001:2", result.text)
        self.assertIn("Utkom från trycket", result.text)
        self.assertIn("Länsstyrelsen", result.text)
        self.assertIn("662 Bonäshamn – Huså och väg 663 till Fäviken, samt", result.text)
        self.assertIn("Med stöd av 10 kap 1 § andra stycket 11 och 3 § trafikförordningen (1998:1276)", result.text)
        self.assertNotIn("=", result.text)

    def test_unshift(self):
        self.assertEqual(pdftext.unshift("i®åëëíóêÉäëÉå=g®ãíä~åÇë=ä®å"), "Länsstyrelsen Jämtlands län")
        self.assertEqual(pdftext.unshift("iûkppqvobipbk=NM=â~éK=N=¬"), "LÄNSSTYRELSEN 10 kap. 1 §")

    def test_shifted_text_that_does_not_decode_stays_a_gap(self):
        # Shifted-looking text whose decoded form is still not text ("æø" -> "†°").
        garbled = "æøæøæø=æø=" * 200
        self.assertEqual(pdftext.classify(garbled).gap, pdftext.UNREADABLE_TEXT)

    def test_letter_spaced_text_is_unreadable(self):
        # 07FS 2008:240: glyphs with wrong widths, word breaks lost.
        spaced = (
            "Läns s t y r e l s e niKr onobe r g sl änskung ör e l s eom upphävande "
            "Lä ns s t y r e l s e nbe s l ut a rme ds t öda v7ka p.7§mi l j öba l ke n( "
        ) * 4
        self.assertEqual(pdftext.classify(spaced).gap, pdftext.LETTER_SPACED)

    def test_short_words_are_readable(self):
        text = "Det är i dag så att en ny väg får gå ut på ön om de vill. " * 10
        self.assertTrue(pdftext.classify(text).usable)

    def test_other_languages_are_readable(self):
        sami = "Naturreservatet Bálggejávrre och Gáddejávrre i Kiruna kommun. " * 20
        czech = "Ředitelství silnic a dálnic ČR, Léčebné lázně Mariánské Lázně. " * 20
        self.assertTrue(pdftext.classify(sami).usable)
        self.assertTrue(pdftext.classify(czech).usable)

    def test_empty_output(self):
        self.assertEqual(pdftext.classify("").gap, pdftext.NO_TEXT_LAYER)


class ParagraphsTest(unittest.TestCase):
    def test_reflow(self):
        text = (
            "1 § Denna föreskrift gäller\ninom länet.\n\n"
            "2 § Jakt får bedrivas av fastighets-\nägare och av miljö-\noch hälsoskyddsnämnden.\n\n"
            "3\n\n- 4 -\n\nSida 5\n"
        )
        self.assertEqual(
            pdftext.paragraphs(text),
            [
                "1 § Denna föreskrift gäller inom länet.",
                "2 § Jakt får bedrivas av fastighetsägare och av miljö- och hälsoskyddsnämnden.",
            ],
        )

    def test_keeps_hyphen_before_capital(self):
        self.assertEqual(pdftext.paragraphs("Natura-\n2000-område"), ["Natura- 2000-område"])

    def test_breaks_without_blank_lines(self):
        long = "Länsstyrelsen föreskriver med stöd av 2 kap. 2 § sjötrafikförordningen"
        text = "\n".join([
            "03FS 2025:10",
            "Länsstyrelsen i Uppsala läns föreskrifter",
            "om avlysning av vattenområde;",
            long,
            "(1986:300) följande.",
            "1 § Inom Pålsundet får vattenområdet inte användas för båttrafik under",
            "lördagen den 16 augusti 2025.",
            "___________",
            "1. Dessa föreskrifter träder i kraft den 16 augusti 2025.",
            "På Länsstyrelsens vägnar",
            "\f",
        ])
        self.assertEqual(
            pdftext.paragraphs(text),
            [
                "03FS 2025:10",
                "Länsstyrelsen i Uppsala läns föreskrifter om avlysning av vattenområde;",
                long + " (1986:300) följande.",
                "1 § Inom Pålsundet får vattenområdet inte användas för båttrafik under lördagen den 16 augusti 2025.",
                "1. Dessa föreskrifter träder i kraft den 16 augusti 2025.",
                "På Länsstyrelsens vägnar",
            ],
        )


class ExtractWithoutToolTest(unittest.TestCase):
    def test_missing_tool_raises(self):
        with mock.patch.object(pdftext.shutil, "which", return_value=None):
            self.assertFalse(pdftext.available())
            with self.assertRaises(pdftext.PdfTextError):
                pdftext.extract(b"%PDF-1.4\n")


@unittest.skipUnless(HAVE_TOOL or REQUIRED, "pdftotext (poppler-utils) is not installed")
class ExtractTest(unittest.TestCase):
    def test_text_pdf(self):
        data = make_pdf([[LINE, "2 § Länsstyrelsen får meddela undantag."], [LINE]])
        result = pdftext.extract(data)
        self.assertTrue(result.usable, result)
        self.assertEqual((result.pages, result.text_pages), (2, 2))
        self.assertIn("Stockholms län", result.text)
        self.assertEqual(pdftext.paragraphs(result.text)[1], "2 § Länsstyrelsen får meddela undantag.")

    def test_image_only_pdf_is_a_gap(self):
        result = pdftext.extract(make_pdf([None, None]))
        self.assertEqual(result.pages, 2)
        self.assertEqual(result.gap, pdftext.NO_TEXT_LAYER)

    def test_broken_pdf_raises(self):
        with self.assertRaises(pdftext.PdfTextError):
            pdftext.extract(b"not a pdf at all")


if __name__ == "__main__":
    unittest.main()
