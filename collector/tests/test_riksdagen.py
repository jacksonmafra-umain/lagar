import json
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

    def test_amendments_n_series(self):
        body = "1 § Text.\n\nFörordning (N2026:1).\n\nLag (2026:5).\n\nFörordning (N2025:3)."
        self.assertEqual(riksdagen.amendments(body), ["N2025:3", "N2026:1", "2026:5"])
        self.assertEqual(riksdagen.amendments("Lag (2026:5).\n\nFörordning (N2026:5)."), ["2026:5", "N2026:5"])

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

    def test_chapter_reference_sentence_is_not_a_heading(self):
        md = riksdagen.to_markdown("T", "7 kap. 3 § gäller inte.\n\n8 kap. Straff")
        self.assertNotIn("## 7 kap.", md)
        self.assertIn("\n\n7 kap. 3 § gäller inte.\n\n", md)
        self.assertIn("\n\n## 8 kap. Straff\n", md)

    def test_amendment_needs_sentence_boundary(self):
        body = "1 § Detta följer av vad som anges i se Lag (2000:1).\n\n2 § Text. Lag (2001:2)."
        self.assertEqual(riksdagen.amendments(body), ["2001:2"])
        self.assertEqual(riksdagen.amendments("Lag (2000:1)."), ["2000:1"])
        self.assertEqual(
            riksdagen.amendments("1 § Text. Lag (2000:1). Lag (2000:2)."), ["2000:1", "2000:2"]
        )

    def test_header_continues_past_blank_line_before_known_key(self):
        parsed = riksdagen.parse_text(
            "Lag (1900:1) om x\n\nSFS nr: 1900:1\nÖvrig text:  \n\nUpphävd: 1994-04-01\n"
            "Källa: Regeringskansliet\n\n1 § Text.\n"
        )
        self.assertEqual(parsed.header["Upphävd"], "1994-04-01")
        self.assertEqual(parsed.body, "1 § Text.")

    def test_wrapped_overig_text_is_continuation_and_upphavd_kept(self):
        parsed = riksdagen.parse_text(
            "Lag (1900:1) om x\n\nSFS nr: 1900:1\nÖvrig text: Rättelseblad har\niakttagits.\n"
            "Upphävd: 1994-04-01\nKälla: Regeringskansliet\n\n1 § Text.\n"
        )
        self.assertEqual(parsed.header["Övrig text"], "Rättelseblad har iakttagits.")
        self.assertEqual(parsed.header["Upphävd"], "1994-04-01")
        self.assertEqual(parsed.body, "1 § Text.")

    def test_overig_text_note_after_blank_line_is_continuation(self):
        parsed = riksdagen.parse_text(
            "Lag (1900:1) om x\n\nSFS nr: 1900:1\nÖvrig text: a\n\nfortsättning\n"
            "Upphävd: 1994-04-01\nKälla: R\n\n1 § Text.\n"
        )
        self.assertEqual(parsed.header["Övrig text"], "a fortsättning")
        self.assertEqual(parsed.header["Upphävd"], "1994-04-01")
        self.assertEqual(parsed.body, "1 § Text.")

    def test_overig_text_note_shapes_from_riksdagen(self):
        # sfs-1963-234: empty `Övrig text`, note paragraph, blank, `Upphävd`.
        parsed = riksdagen.parse_text(
            "Kungörelse (1963:234) om x\n\n\nSFS nr:     1963:234\nÖvrig text:  \n\n"
            "Upphävd den dag regeringen bestämmer. Bilagor finns inte med här.\n\n"
            "Upphävd: 1997-12-31\nKälla: Regeringskansliet / Lagrummet\n\n\nText.\n"
        )
        self.assertEqual(
            parsed.header["Övrig text"],
            "Upphävd den dag regeringen bestämmer. Bilagor finns inte med här.",
        )
        self.assertEqual(parsed.header["Upphävd"], "1997-12-31")
        self.assertEqual(parsed.body, "Text.")
        # sfs-1999-178: wrapped `Övrig text` value, blank, note, `Upphävd` with no blank.
        parsed = riksdagen.parse_text(
            "Föreskrifter (1999:178) om x\n\nSFS nr:     1999:178\n"
            "Övrig text:  Bilaga 2 senast ändrad genom\n\n"
            "Rättelseblad 2007:678 har iakttagits.\nUpphävd: 2025-02-21\n"
            "Källa: Regeringskansliet / Lagrummet\n\n\nHar upphävts.\n"
        )
        self.assertEqual(
            parsed.header["Övrig text"],
            "Bilaga 2 senast ändrad genom Rättelseblad 2007:678 har iakttagits.",
        )
        self.assertEqual(parsed.header["Upphävd"], "2025-02-21")
        self.assertEqual(parsed.body, "Har upphävts.")

    def test_note_after_other_key_still_raises(self):
        with self.assertRaises(ValueError):
            riksdagen.parse_text(
                "Lag (1900:1) om x\n\nSFS nr: 1900:1\nÄndrad:  \n\nfortsättning\n"
                "Upphävd: 1994-04-01\nKälla: R\n\n1 § Text.\n"
            )

    def test_unlisted_key_before_kalla_raises_never_drops_upphavd(self):
        with self.assertRaises(ValueError):
            riksdagen.parse_text(
                "Lag (1900:1) om x\n\nSFS nr: 1900:1\nÄndrad:  \nÄndringsregister: x\n"
                "Upphävd: 1994-04-01\nKälla: R\n\n1 § Text.\n"
            )
        # Directly after `Övrig text` it is read as a continuation: parsed, not dropped.
        parsed = riksdagen.parse_text(
            "Lag (1900:1) om x\n\nSFS nr: 1900:1\nÖvrig text:  \nÄndringsregister: x\n"
            "Upphävd: 1994-04-01\nKälla: R\n\n1 § Text.\n"
        )
        self.assertEqual(parsed.header["Upphävd"], "1994-04-01")

    def test_header_must_start_within_five_lines_after_title(self):
        raw = "Lag (1900:1) om x\n" + "".join(f"Rad {n}\n" for n in range(6)) + "SFS nr: 1900:1\nKälla: R\n\n1 § Text.\n"
        parsed = riksdagen.parse_text(raw)
        self.assertEqual(parsed.header, {})
        self.assertTrue(parsed.body.startswith("Rad 0"))
        self.assertIn("SFS nr: 1900:1", parsed.body)
        near = "Lag (1900:1) om x\n" + "".join(f"Rad {n}\n" for n in range(4)) + "SFS nr: 1900:1\nKälla: R\n\n1 § Text.\n"
        self.assertEqual(riksdagen.parse_text(near).header["SFS nr"], "1900:1")

    def test_header_ends_at_first_non_key_line(self):
        parsed = riksdagen.parse_text(
            "Lag (1900:1) om x\n\nSFS nr: 1900:1\n\nInledning: något\n\n1 § Text.\n"
        )
        self.assertEqual(parsed.header, {"SFS nr": "1900:1"})
        self.assertTrue(parsed.body.startswith("Inledning: något"))

    def test_text_preserved_by_markdown(self):
        for dok_id in FIXTURE_IDS:
            body = riksdagen.parse_text(text(dok_id)).body
            md = riksdagen.to_markdown("TITLEX", body)
            lines = md.split("\n")[1:]
            out = "\n".join(lines).replace("**", "")
            out = "\n".join(line[3:] if line.startswith("## ") else line for line in out.split("\n"))
            self.assertEqual(out.split(), body.split(), dok_id)


class TitleTests(unittest.TestCase):
    def test_collapse_whitespace(self):
        self.assertEqual(riksdagen.collapse_whitespace("  Lag (2026:100) om \n  löneavgift   för\t23 år \n"),
                         "Lag (2026:100) om löneavgift för 23 år")

    def test_listing_title_is_single_line(self):
        raw = json.dumps({"dokumentlista": {"@sidor": "1", "dokument": [{
            "dok_id": "sfs-2026-100", "beteckning": "2026:100",
            "titel": "Lag (2026:100) om särskild beräkning av arbetsgivaravgifter och allmän \nlöneavgift för personer som vid årets ingång fyllt 18 men inte \n23 år",
            "datum": "2026-01-01", "systemdatum": "2026-01-02 00:00:00", "organ": "Finansdepartementet"}]}})
        items, _ = riksdagen.parse_listing(raw)
        self.assertEqual(items[0].title, "Lag (2026:100) om särskild beräkning av arbetsgivaravgifter och allmän löneavgift för personer som vid årets ingång fyllt 18 men inte 23 år")

    def test_markdown_heading_is_single_line(self):
        self.assertEqual(riksdagen.to_markdown("Lag om\n  saker", "").splitlines()[0], "# Lag om saker")

    def test_clean_title_plain_unchanged_except_whitespace(self):
        self.assertEqual(riksdagen.clean_title("Lag (2026:1)  om\nsaker "), "Lag (2026:1) om saker")

    def test_clean_title_keeps_current_title(self):
        raw = ("/Rubriken upphör att gälla U:2027-01-01/\nLag (2026:956) om signalspaning i försvarsunderrättelseverksamhet i krig eller krigsfara\n"
               "/Rubriken träder i kraft I:2027-01-01/\nLag (2026:956) om signalspaning i utrikesunderrättelseverksamhet i krig eller krigsfara")
        self.assertEqual(riksdagen.clean_title(raw),
                         "Lag (2026:956) om signalspaning i försvarsunderrättelseverksamhet i krig eller krigsfara")
        self.assertEqual(riksdagen.classify(riksdagen.clean_title(raw), "sfs-2026-956"), "act")

    def test_clean_title_future_only(self):
        raw = "/Rubriken träder i kraft I:2027-01-01/\nLag (2026:957) om nya saker"
        self.assertEqual(riksdagen.clean_title(raw), "Lag (2026:957) om nya saker")

    def test_listing_applies_clean_title(self):
        raw = json.dumps({"dokumentlista": {"@sidor": "1", "dokument": [{
            "dok_id": "sfs-2026-957", "beteckning": "2026:957",
            "titel": "/Rubriken träder i kraft I:2027-01-01/\nLag (2026:957) om nya saker",
            "datum": "2026-01-01", "systemdatum": "x", "organ": ""}]}})
        self.assertEqual(riksdagen.parse_listing(raw)[0][0].title, "Lag (2026:957) om nya saker")

    def test_statute_title_strips_trailing_semicolon_once_for_all_callers(self):
        raw = "Successionsordning (1810:0926);\n"
        self.assertEqual(riksdagen.statute_title(raw), "Successionsordning (1810:0926)")
        listing = json.dumps({"dokumentlista": {"@sidor": "1", "dokument": [{
            "dok_id": "sfs-1810-0926", "beteckning": "1810:0926", "titel": raw,
            "datum": "1810-09-26", "systemdatum": "x", "organ": ""}]}})
        item = riksdagen.parse_listing(listing)[0][0]
        self.assertEqual(item.title, "Successionsordning (1810:0926)")
        self.assertEqual(riksdagen.statute_title(item.title), item.title)

    def test_item_type_matches_classify_of_cleaned_title(self):
        item = riksdagen.ListingItem("sfs-2026-5", "2026:5", "Förordning (2026:5) om x;", None, "x", None)
        self.assertEqual(riksdagen.item_type(item), "ordinance")
        item = riksdagen.ListingItem("sfs-1974-152", "1974:152", "Kungörelse (1974:152);", None, "x", None)
        self.assertEqual(riksdagen.item_type(item), "fundamental_law")

    def test_amendments_note_at_end_of_body(self):
        self.assertEqual(riksdagen.amendments("1 § Text.\n\nFörordning (N2026:1)."), ["N2026:1"])


if __name__ == "__main__":
    unittest.main()
