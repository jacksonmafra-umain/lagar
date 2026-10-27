import unittest
from pathlib import Path

from lagar import riksdagen

FIXTURES = Path(__file__).resolve().parent / "fixtures"


FIXTURE_IDS = ["sfs-1999-175", "sfs-1974-152", "sfs-1810-0926", "sfs-1757-0119"]


def text(dok_id):
    return (FIXTURES / (dok_id + ".text")).read_text(encoding="utf-8")


class RiksdagenTests(unittest.TestCase):
    def test_parse_listing_fields_and_pages(self):
        raw = (FIXTURES / "listing-page.json").read_bytes()
        items, pages = riksdagen.parse_listing(raw)
        self.assertEqual(len(items), 200)
        self.assertEqual(pages, 58)
        first = items[0]
        self.assertEqual(first.dok_id, "sfs-2026-1781")
        self.assertEqual(first.number, "2026:1781")
        self.assertEqual(
            first.title,
            "Förordning (2026:1781) om certifiering av systemansvariga för överföringssystem för el",
        )
        self.assertEqual(first.issued, "2026-10-01")
        self.assertEqual(first.systemdatum, "2026-10-13 04:33:48")
        self.assertEqual(first.ministry, "Klimat- och näringslivsdepartementet RSE")

    def test_header_parsed(self):
        parsed = riksdagen.parse_text(text("sfs-1999-175"))
        self.assertEqual(parsed.header["SFS nr"], "1999:175")
        self.assertEqual(parsed.header["Ändrad"], "t.o.m. SFS 2026:851")
        self.assertEqual(parsed.header["Omtryck"], "")
        self.assertTrue(parsed.body.startswith("Ett offentligt rättsinformationssystem"))

    def test_repealed_header(self):
        parsed = riksdagen.parse_text(text("sfs-1757-0119"))
        self.assertEqual(parsed.header["Upphävd"], "1994-04-01")

    def test_print_only_body_is_empty_note(self):
        parsed = riksdagen.parse_text(text("sfs-1757-0119"))
        md = riksdagen.to_markdown("Resolution (1757:0119) på städernas allmänna besvär", parsed.body)
        self.assertTrue(md.startswith("# Resolution (1757:0119)"))
        self.assertTrue(md.endswith("\n"))
        self.assertEqual(riksdagen.to_markdown("T", ""), "# T\n\n_Text available only in print._\n")

    def test_classify(self):
        c = riksdagen.classify
        self.assertEqual(c("Rättsinformationsförordning (1999:175)", "sfs-1999-175"), "ordinance")
        self.assertEqual(c("Lag (2010:283) om värdepappersmarknaden", "sfs-2010-283"), "act")
        self.assertEqual(c("Brottsbalk (1962:700)", "sfs-1962-700"), "act")
        self.assertEqual(c("Resolution (1757:0119) på städernas allmänna besvär", "sfs-1757-0119"), "other_statute")
        self.assertEqual(c("Kungörelse (1974:152) om beslutad ny regeringsform", "sfs-1974-152"), "fundamental_law")

    def test_amendments(self):
        body = "1 § Text.\n\nLag (2010:283).\n\n2 § Mer.\n\nFörordning (2019:1036).\n\nLag (2010:283)."
        self.assertEqual(riksdagen.amendments(body), ["2010:283", "2019:1036"])

    def test_markdown_headings(self):
        parsed = riksdagen.parse_text(text("sfs-1974-152"))
        md = riksdagen.to_markdown("Regeringsformen", parsed.body)
        self.assertTrue(md.startswith("# Regeringsformen\n\n## 1 kap. Statsskickets grunder\n\n**1 §** All offentlig makt"))
        self.assertIn("\n\n## 2 kap. Grundläggande fri- och rättigheter\n\n", md)
        self.assertTrue(md.endswith("\n") and not md.endswith("\n\n"))

    def test_amendments_mid_line_and_split(self):
        body = "1 § Det ska främjas. Lag (2010:1408).\n\n2 § Text. Förordning\n(2001:147).\n\nLag (1976:871) om något"
        self.assertEqual(riksdagen.amendments(body), ["2001:147", "2010:1408"])

    def test_amendments_real_fixture(self):
        found = riksdagen.amendments(riksdagen.parse_text(text("sfs-1999-175")).body)
        self.assertIn("2010:283", found)
        self.assertIn("2001:147", found)
        rf = riksdagen.amendments(riksdagen.parse_text(text("sfs-1974-152")).body)
        self.assertGreater(len(rf), 10)

    def test_header_keys_have_no_parenthesis(self):
        for dok_id in FIXTURE_IDS:
            for key in riksdagen.parse_text(text(dok_id)).header:
                self.assertNotIn("(", key)

    def test_missing_source_line_keeps_body(self):
        parsed = riksdagen.parse_text("Lag (2000:1) om x\n\nSFS nr:  2000:1\nÄndrad:  \n\n1 § Text här.\n")
        self.assertEqual(parsed.header, {"SFS nr": "2000:1", "Ändrad": ""})
        self.assertEqual(parsed.body, "1 § Text här.")

    def test_text_preserved_by_markdown(self):
        for dok_id in FIXTURE_IDS:
            body = riksdagen.parse_text(text(dok_id)).body
            md = riksdagen.to_markdown("TITLEX", body)
            lines = md.split("\n")[1:]
            out = "\n".join(lines).replace("**", "")
            out = "\n".join(l[3:] if l.startswith("## ") else l for l in out.split("\n"))
            self.assertEqual(out.split(), body.split(), dok_id)


if __name__ == "__main__":
    unittest.main()
