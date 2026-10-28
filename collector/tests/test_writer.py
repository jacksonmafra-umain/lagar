import tempfile
import unittest
from pathlib import Path
from unittest import mock

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

    def test_carriage_return_and_tab_roundtrip(self):
        meta = {"title": "a\rb\tc\nd", "amended_by": ["x\ry"]}
        loaded, _ = frontmatter.load("---\n" + frontmatter.dump(meta) + "---\n")
        self.assertEqual(loaded, meta)
        self.assertNotIn("\r", frontmatter.dump(meta))

    def test_dump_rejects_other_control_characters(self):
        for bad in ("a\x00b", "a\x1bb", "a\x7fb", "a\x0bb"):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    frontmatter.dump({"title": bad})
                with self.assertRaises(ValueError):
                    frontmatter.dump({"title": ["ok", bad]})

    def test_dump_rejects_keys_load_cannot_read(self):
        for key in ("Title", "my-key", "key with space", "", "nyckel\u00e5"):
            with self.subTest(key=key):
                with self.assertRaises(ValueError):
                    frontmatter.dump({key: "v"})

    def test_body_starting_with_dashes_roundtrips(self):
        text = "---\n" + frontmatter.dump({"id": "sfs-1-1"}) + "---\n---\nnot frontmatter\n"
        meta, body = frontmatter.load(text)
        self.assertEqual(meta, {"id": "sfs-1-1"})
        self.assertEqual(body, "---\nnot frontmatter\n")

    def test_mapping_list_roundtrip(self):
        meta = {
            "id": "sfs-1962-700",
            "amendments": [
                {"number": "1965:280", "title": None, "scope": "\u00e4ndr. 20 kap 4 \u00a7\n31 kap", "in_force": None},
                {"number": "2026:1640", "title": 'Lag "x"', "scope": "upph. 1 \u00a7", "in_force": "2027-01-02"},
            ],
            "in_force": "1965-01-01",
        }
        text = "---\n" + frontmatter.dump(meta) + "---\nbody\n"
        self.assertIn('amendments:\n  - number: "1965:280"\n    title: null\n', text)
        loaded, body = frontmatter.load(text)
        self.assertEqual(loaded, meta)
        self.assertEqual(body, "body\n")
        # Keys follow the schema order: in_force before amendments.
        self.assertLess(text.index("in_force:"), text.index("amendments:"))

    def test_mapping_list_item_keys_follow_schema_order(self):
        item = {"in_force_raw": None, "number": "2000:1", "title": None}
        dumped = frontmatter.dump({"amendments": [item]})
        self.assertEqual(
            dumped, 'amendments:\n  - number: "2000:1"\n    title: null\n    in_force_raw: null\n'
        )

    def test_empty_mapping_list_is_a_flow_list(self):
        self.assertEqual(frontmatter.dump({"amendments": []}), "amendments: []\n")
        loaded, _ = frontmatter.load("---\namendments: []\n---\n")
        self.assertEqual(loaded, {"amendments": []})

    def test_mapping_list_rejects_what_load_cannot_read(self):
        for bad in ([{}], [{"a": ["x"]}], [{"a": {"b": "c"}}], [{"Bad": "x"}], [{"a": "x"}, "y"]):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    frontmatter.dump({"amendments": bad})

    def test_malformed_block_lists_rejected(self):
        for text in (
            "---\namendments:\n---\n",
            "---\namendments:\n    number: \"1\"\n---\n",
            "---\namendments:\n  - number: \"1\"\n    number: \"2\"\n---\n",
            "---\namendments:\n  - number: [\"1\"]\n---\n",
            "---\namendments:\n  - number: \"1\"\n",
        ):
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    frontmatter.load(text)

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

    def test_in_force_is_null_because_source_has_no_such_field(self):
        it = item("sfs-1999-175", "1999:175", "Rättsinformationsförordning (1999:175)",
                  "1999-03-25", None)
        p = riksdagen.parse_text("SFS nr: 1999:175\nIkraft: 1999-05-01\n\nText")
        self.assertIsNone(writer.build_meta(it, p, SHA, NOW)["in_force"])

    def test_build_meta_uses_shared_title_and_type(self):
        it = item("sfs-2026-5", "2026:5", "Förordning (2026:5)\n om  x;", "2026-01-01", None)
        meta = writer.build_meta(it, riksdagen.parse_text("SFS nr: 2026:5\n\nText"), SHA, NOW)
        self.assertEqual(meta["title"], "Förordning (2026:5) om x")
        self.assertEqual(meta["type"], riksdagen.item_type(it))

    def test_write_removes_stale_file_under_other_type_folder(self):
        it = item("sfs-2026-5", "2026:5", "Förordning (2026:5) om x", "2026-01-01", None)
        p = riksdagen.parse_text("SFS nr: 2026:5\n\nText")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            other = writer.build_meta(
                item("sfs-2026-5", "2026:5", "Resolution (2026:5) om x", "2026-01-01", None), p, SHA, NOW)
            old = writer.write(other, "# x\n", root)
            self.assertEqual(old, root / "sfs/other/2026-5.md")
            unrelated = writer.write(
                writer.build_meta(item("sfs-2026-6", "2026:6", "Förordning (2026:6) om y", "2026-01-01", None),
                                  riksdagen.parse_text("SFS nr: 2026:6\n\nText"), SHA, NOW), "# y\n", root)
            new = writer.write(writer.build_meta(it, p, SHA, NOW), "# x\n", root)
            self.assertEqual(new, root / "sfs/ordinances/2026-5.md")
            self.assertFalse(old.exists())
            self.assertTrue(new.exists())
            self.assertTrue(unrelated.exists())

    def test_write_failure_leaves_no_temp_file(self):
        it = item("sfs-2026-5", "2026:5", "Förordning (2026:5) om x", "2026-01-01", None)
        meta = writer.build_meta(it, riksdagen.parse_text("SFS nr: 2026:5\n\nText"), SHA, NOW)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with mock.patch("lagar.writer.os.replace", side_effect=OSError("disk")):
                with self.assertRaises(OSError):
                    writer.write(meta, "# x\n", root)
            self.assertEqual(list(root.rglob(".tmp-*")), [])
            self.assertEqual(list(root.rglob("*.md")), [])

    def test_n_series_document(self):
        it = item("sfs-N2026-1", "N2026:1", "Förordning (N2026:1) om saker", "2026-01-05", None)
        meta = writer.build_meta(it, riksdagen.parse_text("SFS nr: N2026:1\n\nText"), SHA, NOW)
        self.assertEqual(meta["id"], "sfs-n2026-1")
        self.assertEqual(meta["number"], "N2026:1")
        self.assertEqual(meta["source"], "https://data.riksdagen.se/dokument/sfs-N2026-1")
        self.assertEqual(meta["type"], "ordinance")
        self.assertEqual(schema.validate(meta), [])
        self.assertEqual(writer.path_for(meta, Path("corpus")), Path("corpus/sfs/ordinances/n2026-1.md"))

    def test_corpus_id_normalises_irregular_dok_ids(self):
        self.assertEqual(writer.corpus_id("sfs-1999-175"), "sfs-1999-175")
        self.assertEqual(writer.corpus_id("sfs-N2026-1"), "sfs-n2026-1")
        self.assertEqual(writer.corpus_id("sfs-1827-60 s.1007"), "sfs-1827-60-s-1007")
        self.assertEqual(writer.corpus_id("sfs-1878-bih. 56 s. 1"), "sfs-1878-bih-56-s-1")
        self.assertEqual(writer.corpus_id("c1s0bf"), "sfs-c1s0bf")

    def test_irregular_dok_id_document(self):
        it = item("sfs-1827-60 s.1007", "1827:60 s.1007", "Kungörelse om saker", "1827-06-01", None)
        meta = writer.build_meta(it, riksdagen.parse_text("SFS nr: 1827:60 s.1007\n\nText"), SHA, NOW)
        self.assertEqual(meta["id"], "sfs-1827-60-s-1007")
        self.assertEqual(meta["source"], "https://data.riksdagen.se/dokument/sfs-1827-60%20s.1007")
        self.assertEqual(schema.validate(meta), [])
        self.assertEqual(writer.path_for(meta, Path("corpus")), Path("corpus/sfs/other/1827-60-s-1007.md"))

    def test_n_series_amendment_numbers(self):
        it = item("sfs-2026-9", "2026:9", "Lag (2026:9) om saker", "2026-01-05", None)
        p = riksdagen.parse_text("SFS nr: 2026:9\nÄndrad: t.o.m. SFS N2026:1\nOmtryck: SFS N2026:2, 2025:7\n\nText")
        meta = writer.build_meta(it, p, SHA, NOW)
        self.assertEqual(meta["amended_through"], "N2026:1")
        self.assertEqual(meta["reprinted_by"], ["N2026:2", "2025:7"])
        self.assertEqual(schema.validate(meta), [])
