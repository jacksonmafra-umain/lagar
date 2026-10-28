import tempfile
import unittest
from pathlib import Path

from lagar import frontmatter, riksdagen, schema, writer

FIXTURES = Path(__file__).resolve().parent / "fixtures"
SHA = "a" * 64
NOW = "2026-10-27T10:00:00Z"


def parsed(dok_id):
    return riksdagen.parse_text((FIXTURES / f"{dok_id}.text").read_text(encoding="utf-8"))


def item(dok_id, number, title, issued, ministry):
    return riksdagen.ListingItem(dok_id, number, title, issued, "2026-01-01", ministry)


class WriterTests(unittest.TestCase):
    def test_dump_load_roundtrip(self):
        meta = {
            "id": "sfs-1999-175",
            "title": 'Lag: om "citat" \\ och\nrad',
            "in_force": None,
            "authoritative": False,
            "amended_by": ["2000:1", "2001:2"],
            "reprinted_by": [],
        }
        text = "---\n" + frontmatter.dump(meta) + "---\n# Body\n"
        loaded, body = frontmatter.load(text)
        self.assertEqual(loaded, meta)
        self.assertEqual(body, "# Body\n")
        with self.assertRaises(ValueError):
            frontmatter.load("---\nid: bare\n---\n")

    def test_build_meta_1999_175(self):
        it = item("sfs-1999-175", "1999:175", "Rättsinformationsförordning (1999:175)",
                  "1999-03-25", "Justitiedepartementet KRIM")
        meta = writer.build_meta(it, parsed("sfs-1999-175"), SHA, NOW)
        self.assertEqual(schema.validate(meta), [])
        self.assertEqual(meta["type"], "ordinance")
        self.assertEqual(meta["layer"], "sfs")
        self.assertEqual(meta["number"], "1999:175")
        self.assertEqual(meta["issued"], "1999-03-25")
        self.assertEqual(meta["amended_through"], "2026:851")
        self.assertEqual(meta["ministry"], "Justitiedepartementet KRIM")
        self.assertEqual(meta["source"], "https://data.riksdagen.se/dokument/sfs-1999-175")
        self.assertIs(meta["authoritative"], False)
        self.assertEqual(meta["language"], "sv")
        self.assertIsNone(meta["eli"])
        self.assertIsNone(meta["in_force"])

    def test_build_meta_drops_own_number_from_amended_by(self):
        it = item("sfs-2026-337", "2026:337", "Förordning om test (2026:337)",
                  "2026-05-01", "Justitiedepartementet")
        p = riksdagen.parse_text(
            "Förordning om test\n\n"
            "1 §   Text.\n\n"
            "2 §   Mer text.\n\n"
            "Förordning (2026:337).\n\n"
            "Förordning (2026:400).\n")
        meta = writer.build_meta(it, p, SHA, NOW)
        self.assertNotIn("2026:337", meta["amended_by"])
        self.assertIn("2026:400", meta["amended_by"])

    def test_build_meta_fundamental_title(self):
        it = item("sfs-1974-152", "1974:152", "Kungörelse (1974:152) om beslutad ny regeringsform;",
                  "1974-02-28", "Justitiedepartementet L6")
        meta = writer.build_meta(it, parsed("sfs-1974-152"), SHA, NOW)
        self.assertEqual(meta["title"], "Regeringsformen")
        self.assertEqual(meta["type"], "fundamental_law")
        self.assertEqual(meta["reprinted_by"], ["2011:109", "2014:1385", "2018:1903", "2022:1600"])

    def test_paths(self):
        root = Path("corpus")
        for type_, id_, want in [
            ("fundamental_law", "sfs-1974-152", "corpus/fundamental-laws/1974-152.md"),
            ("act", "sfs-2010-110", "corpus/sfs/acts/2010-110.md"),
            ("ordinance", "sfs-1999-175", "corpus/sfs/ordinances/1999-175.md"),
            ("other_statute", "sfs-1757-0119", "corpus/sfs/other/1757-0119.md"),
        ]:
            self.assertEqual(writer.path_for({"type": type_, "id": id_}, root), Path(want))

    def test_write_roundtrip_and_refuses_invalid(self):
        it = item("sfs-1999-175", "1999:175", "Rättsinformationsförordning (1999:175)",
                  "1999-03-25", "Justitiedepartementet KRIM")
        p = parsed("sfs-1999-175")
        meta = writer.build_meta(it, p, SHA, NOW)
        md = riksdagen.to_markdown(meta["title"], p.body)
        with tempfile.TemporaryDirectory() as tmp:
            path = writer.write(meta, md, Path(tmp))
            self.assertEqual(path, Path(tmp) / "sfs/ordinances/1999-175.md")
            loaded, body = frontmatter.load(path.read_text(encoding="utf-8"))
            self.assertEqual(loaded, meta)
            self.assertEqual(body, md)
            bad = dict(meta, source_sha256="xyz", id="sfs-2000-1", number="2000:1")
            with self.assertRaises(ValueError):
                writer.write(bad, md, Path(tmp))
            self.assertFalse((Path(tmp) / "sfs/ordinances/2000-1.md").exists())

    def test_n_series_document(self):
        it = item("sfs-N2026-1", "N2026:1", "Förordning (N2026:1) om saker", "2026-01-05", None)
        meta = writer.build_meta(it, riksdagen.parse_text("SFS nr: N2026:1\n\nText"), SHA, NOW)
        self.assertEqual(meta["id"], "sfs-n2026-1")
        self.assertEqual(meta["number"], "N2026:1")
        self.assertEqual(meta["source"], "https://data.riksdagen.se/dokument/sfs-N2026-1")
        self.assertEqual(meta["type"], "ordinance")
        self.assertEqual(schema.validate(meta), [])
        self.assertEqual(writer.path_for(meta, Path("corpus")), Path("corpus/sfs/ordinances/n2026-1.md"))

    def test_n_series_amendment_numbers(self):
        it = item("sfs-2026-9", "2026:9", "Lag (2026:9) om saker", "2026-01-05", None)
        p = riksdagen.parse_text("SFS nr: 2026:9\nÄndrad: t.o.m. SFS N2026:1\nOmtryck: SFS N2026:2, 2025:7\n\nText")
        meta = writer.build_meta(it, p, SHA, NOW)
        self.assertEqual(meta["amended_through"], "N2026:1")
        self.assertEqual(meta["reprinted_by"], ["N2026:2", "2025:7"])
        self.assertEqual(schema.validate(meta), [])
