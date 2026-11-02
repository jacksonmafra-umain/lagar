import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import export_corpus

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "export"
CRIMINAL_CODE = FIXTURES / "sfs-1962-700.md"
EMPLOYMENT = FIXTURES / "sfs-1982-80.md"
AGENCY = FIXTURES / "lmfs-2009-1.md"
CASE = FIXTURES / "ad-2020-nr-69.md"
REPEALED = FIXTURES / "sfs-1942-118.md"


def load(path):
    return next(export_corpus.documents([path]))


def sections(path, **kwargs):
    return list(export_corpus.section_records(load(path), **kwargs))


def bundle_texts(out):
    return {p.name: p.read_text(encoding="utf-8") for p in sorted(out.glob("bundle-*.md"))}


class StatuteSectionTests(unittest.TestCase):
    def test_one_record_per_section_with_chapter_and_citation(self):
        records = [r for r in sections(CRIMINAL_CODE) if r["section"]]
        self.assertEqual(
            [r["citation"] for r in records[:3]],
            ["1 kap. 1 § brottsbalken (1962:700)", "1 kap. 2 § brottsbalken (1962:700)",
             "1 kap. 3 § brottsbalken (1962:700)"],
        )
        self.assertIn("2 kap. 3 § brottsbalken (1962:700)", [r["citation"] for r in records])
        self.assertTrue(all(r["text"].count("§**") == 1 for r in records))

    def test_both_versions_of_a_changing_section_are_kept_apart(self):
        third = [r for r in sections(CRIMINAL_CODE) if r["chapter"] == "1" and r["section"] == "3"]
        self.assertEqual(len(third), 2)
        ending, coming = third
        self.assertEqual(ending["version"], "/Upphör att gälla U:den dag som regeringen bestämmer/")
        self.assertEqual(ending["in_force"], "1965-01-01")
        self.assertEqual(coming["version"], "/Träder i kraft I:den dag som regeringen bestämmer/")
        self.assertIsNone(coming["in_force"])
        self.assertIn(coming["version"], coming["text"])

    def test_dated_repeal_marker_sets_repealed(self):
        sixth = next(r for r in sections(CRIMINAL_CODE) if r["chapter"] == "1" and r["section"] == "6")
        self.assertEqual(sixth["version"], "/Upphör att gälla U:2031-09-10/")
        self.assertEqual(sixth["repealed"], "2031-09-10")

    def test_headings_travel_with_the_next_section(self):
        records = sections(CRIMINAL_CODE)
        first = records[0]
        self.assertEqual(first["section"], "1")
        self.assertTrue(first["text"].startswith("FÖRSTA AVDELNINGEN"))
        chapter_two = next(r for r in records if r["chapter"] == "2" and r["section"] == "1")
        self.assertTrue(chapter_two["text"].startswith("## 2 kap. Om svensk domstols behörighet"))
        third = next(r for r in records if r["chapter"] == "2" and r["section"] == "3")
        self.assertEqual(third["heading"], "Brott som har begåtts utanför Sverige / Allmänna grunder för behörighet")
        second = next(r for r in records if r["chapter"] == "2" and r["section"] == "2")
        self.assertNotIn("Brott som har begåtts utanför Sverige", second["text"])
        court = next(r for r in sections(EMPLOYMENT) if r["section"] == "43")
        self.assertEqual(court["heading"], "Rättegången")

    def test_transitional_provisions_are_not_part_of_the_last_section(self):
        records = sections(EMPLOYMENT, chunk_words=40)
        last = next(r for r in records if r["section"] == "43")
        self.assertNotIn("Övergångsbestämmelser", last["text"])
        tail = records[records.index(last) + 1 :]
        self.assertGreater(len(tail), 1)
        for record in tail:
            self.assertIsNone(record["section"])
            self.assertEqual(record["heading"], "Övergångsbestämmelser")
            self.assertEqual(record["citation"], "lagen (1982:80) om anställningsskydd")

    def test_sections_without_a_space_before_the_sign(self):
        records = [r for r in sections(AGENCY) if r["section"]]
        self.assertEqual(records[0]["citation"], "1 § LMFS 2009:1")

    def test_no_text_is_lost(self):
        for path in (CRIMINAL_CODE, EMPLOYMENT, AGENCY, CASE):
            doc = load(path)
            joined = " ".join(r["text"] for r in export_corpus.section_records(doc, chunk_words=30))
            self.assertEqual(joined.split(), doc.rest.split(), path.name)


class ChunkTests(unittest.TestCase):
    def test_case_law_is_chunked_by_heading_and_size(self):
        records = sections(CASE, chunk_words=20)
        self.assertTrue(all(r["section"] is None for r in records))
        self.assertTrue(all(export_corpus.words(r["text"]) <= 20 for r in records))
        self.assertIn("Referat", [r["heading"] for r in records])
        self.assertEqual([r["seq"] for r in records], list(range(1, len(records) + 1)))

    def test_long_paragraph_is_split_between_words(self):
        self.assertEqual(export_corpus.pieces("a b c d e", 2), ["a b", "c d", "e"])
        self.assertEqual(export_corpus.pieces("a b\nc d\ne", 4), ["a b\nc d", "e"])


class CitationNameTests(unittest.TestCase):
    def test_definite_form_of_the_title(self):
        cases = {
            "Lag (1982:80) om anställningsskydd": "lagen (1982:80) om anställningsskydd",
            "Brottsbalk (1962:700)": "brottsbalken (1962:700)",
            "Förordning (2017:1000) om något": "förordningen (2017:1000) om något",
            "Regeringsform (1974:152)": "regeringsformen (1974:152)",
            "Kungörelse (1950:1) om något": "kungörelsen (1950:1) om något",
            "Tillkännagivande (1990:2) om något": "tillkännagivandet (1990:2) om något",
        }
        for title, name in cases.items():
            self.assertEqual(export_corpus.citation_name({"title": title}), name)

    def test_other_titles_fall_back_to_the_number(self):
        meta = {"title": "Lantmäteriverkets föreskrifter om stämpelskatt", "number": "LMFS 2009:1"}
        self.assertEqual(export_corpus.citation_name(meta), "LMFS 2009:1")


class SelectionTests(unittest.TestCase):
    def test_only_in_force_leaves_out_repealed_documents(self):
        ids = {d.id for d in export_corpus.documents([FIXTURES], only_in_force=True, as_of="2026-11-02")}
        self.assertNotIn("sfs-1942-118", ids)
        self.assertIn("sfs-1982-80", ids)
        repealed = load(REPEALED).meta["repealed"]
        early = {d.id for d in export_corpus.documents([REPEALED], only_in_force=True, as_of="1900-01-01")}
        self.assertEqual(early, {"sfs-1942-118"}, repealed)

    def test_layers_filter(self):
        ids = {d.id for d in export_corpus.documents([FIXTURES], layers={"agency", "case_law"})}
        self.assertEqual(ids, {load(AGENCY).id, load(CASE).id})

    def test_missing_path_is_an_error(self):
        with self.assertRaises(FileNotFoundError):
            list(export_corpus.documents([FIXTURES / "missing.md"]))


class TargetTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)

    def select(self):
        return export_corpus.documents([FIXTURES])

    def test_dataset_has_one_record_per_document(self):
        counts = export_corpus.export_dataset(self.select(), self.tmp)
        documents = [json.loads(line) for line in (self.tmp / "documents.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(counts["documents"], 5)
        self.assertEqual(len({d["id"] for d in documents}), 5)
        self.assertEqual(list(documents[0])[:3], ["id", "layer", "type"])
        self.assertTrue(all(set(export_corpus.DOCUMENT_KEYS) < set(d) for d in documents))
        lines = (self.tmp / "sections.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), counts["sections"])

    def test_bundles_never_exceed_the_cap(self):
        for cap in (150, 400, 2_000):
            out = self.tmp / str(cap)
            manifest = export_corpus.export_notebooklm(self.select, out, "ultra", cap)
            texts = bundle_texts(out)
            self.assertEqual(len(texts), manifest["sources"])
            for bundle in manifest["bundles"]:
                size = export_corpus.words(texts[bundle["file"]])
                self.assertLessEqual(size, cap)
                self.assertEqual(size, bundle["words"])

    def test_no_document_lost_or_duplicated(self):
        manifest = export_corpus.export_notebooklm(self.select, self.tmp, "ultra", 150)
        units = [u for b in manifest["bundles"] for u in b["documents"]]
        whole = [u["id"] for u in units if u["part"] is None]
        self.assertEqual(len(whole), len(set(whole)))
        by_id = {}
        for unit in units:
            by_id.setdefault(unit["id"], []).append(unit["part"])
        self.assertEqual(set(by_id), {d.id for d in self.select()})
        for parts in by_id.values():
            if parts != [None]:
                total = len(parts)
                self.assertEqual(parts, [f"{n}/{total}" for n in range(1, total + 1)])
        text = "\n\n".join(bundle_texts(self.tmp).values())
        for doc in self.select():
            for paragraph in export_corpus.paragraphs(doc.rest):
                self.assertTrue(all(word in text for word in paragraph.split()[:3]))
        self.assertEqual(manifest["documents"], 5)

    def test_split_parts_keep_every_word_in_order(self):
        doc = load(CRIMINAL_CODE)
        units = list(export_corpus.notebook_units(doc, 150))
        self.assertGreater(len(units), 1)
        body = []
        for _, _, text in units:
            head, _, rest = text.partition("\n\nSource: ")
            body.extend(rest.partition("\n\n")[2].split())
        self.assertEqual(body, doc.rest.split())

    def test_split_happens_at_chapter_or_section_boundaries(self):
        doc = load(CRIMINAL_CODE)
        units = list(export_corpus.notebook_units(doc, 400))
        self.assertGreater(len(units), 1)
        for number, total, text in units:
            self.assertIn(f"(part {number}/{total})", text.split("\n", 1)[0])
            first = export_corpus.paragraphs(text)[2]
            boundary = export_corpus.chapter_of(first) or export_corpus.section_of(first)
            if number > 1:
                self.assertIsNotNone(boundary, first[:60])

    def test_manifest_is_deterministic(self):
        first, second = self.tmp / "a", self.tmp / "b"
        export_corpus.export_notebooklm(self.select, first, "free", 300)
        export_corpus.export_notebooklm(self.select, second, "free", 300)
        self.assertEqual((first / "manifest.json").read_bytes(), (second / "manifest.json").read_bytes())
        self.assertEqual(bundle_texts(first), bundle_texts(second))

    def test_stale_bundles_are_removed(self):
        export_corpus.export_notebooklm(self.select, self.tmp, "ultra", 150)
        many = len(bundle_texts(self.tmp))
        export_corpus.export_notebooklm(self.select, self.tmp, "ultra", 100_000)
        self.assertLess(len(bundle_texts(self.tmp)), many)
        self.assertEqual(len(bundle_texts(self.tmp)), 1)

    def test_tier_limit_fails_before_writing(self):
        out = self.tmp / "notebook"
        with mock.patch.dict(export_corpus.TIERS, {"free": 2}):
            with self.assertRaisesRegex(export_corpus.TierError, "needs \\d+ sources; the free plan allows 2"):
                export_corpus.export_notebooklm(self.select, out, "free", 150)
        self.assertFalse(out.exists())

    def test_bundle_starts_with_title_and_source_line(self):
        export_corpus.export_notebooklm(lambda: export_corpus.documents([EMPLOYMENT]), self.tmp)
        text = bundle_texts(self.tmp)["bundle-001.md"]
        self.assertTrue(text.startswith(
            "# Lag (1982:80) om anställningsskydd\n\n"
            "Source: https://data.riksdagen.se/dokument/sfs-1982-80 | In force: 1982-04-01\n\n"
        ))

    def test_files_have_a_readable_header(self):
        result = export_corpus.export_files(self.select(), self.tmp)
        self.assertEqual(result["files"], 5)
        text = (self.tmp / "sfs" / "sfs-1982-80.md").read_text(encoding="utf-8")
        self.assertTrue(text.startswith("# Lag (1982:80) om anställningsskydd\n\n- Number: 1982:80\n"))
        self.assertIn("- Source: https://data.riksdagen.se/dokument/sfs-1982-80\n", text)
        self.assertNotIn("---", text.split("\n\n", 2)[1])


class CommandLineTests(unittest.TestCase):
    def run_main(self, *args):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = export_corpus.main(list(args))
        return code, stdout.getvalue(), stderr.getvalue()

    def test_tier_error_exits_with_a_message(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(export_corpus.TIERS, {"free": 1}):
            code, _, err = self.run_main("--target", "notebooklm", "--cap", "150", "--out", tmp, str(FIXTURES))
        self.assertEqual(code, 1)
        self.assertIn("the free plan allows 1", err)

    def test_unknown_layer_is_rejected(self):
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            export_corpus.main(["--target", "files", "--out", "x", "--layers", "laws"])

    def test_layers_and_in_force_flags(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out, _ = self.run_main(
                "--target", "files", "--out", tmp, "--layers", "sfs", "--only-in-force", str(FIXTURES)
            )
            self.assertEqual(code, 0)
            self.assertEqual(sorted(p.name for p in Path(tmp, "sfs").iterdir()), ["sfs-1962-700.md", "sfs-1982-80.md"])
        self.assertIn("2 files", out)


if __name__ == "__main__":
    unittest.main()
