import json
import tempfile
import unittest
from pathlib import Path

from lagar import corpusstats, frontmatter, schema
from tests.test_schema import new_layer_meta, template_service


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


def manifest_entry(slug, result="ok", status=200, final_url=None, error=None):
    source = f"https://www.example.se/{slug}"
    entry = {"slug": slug, "source": source, "result": result, "status": status,
             "final_url": final_url or source, "fetched_at": "2026-11-13T00:00:00Z"}
    if error:
        entry["error"] = error
    return entry


class ServiceLinksTest(unittest.TestCase):
    def test_classifies_manifest_entries(self):
        links = corpusstats.service_links({"entries": [
            manifest_entry("a"),
            manifest_entry("b", final_url="https://www.example.se/b-new"),
            manifest_entry("c", "redirected", 301, "https://other.se/c", "HTTP 301 to another host"),
            manifest_entry("d", "not_found", 404, error="HTTP 404"),
            manifest_entry("e", "not_found", 410, error="HTTP 410"),
            manifest_entry("f", "blocked", 403, error="HTTP 403"),
            manifest_entry("g", "no_lead", 200, error="no lead"),
        ]})
        self.assertEqual(links["checked"], 7)
        self.assertEqual(links["ok"], 1)
        self.assertEqual([m["slug"] for m in links["moved"]], ["b", "c"])
        self.assertEqual(links["moved"][0]["final_url"], "https://www.example.se/b-new")
        self.assertEqual([d["slug"] for d in links["dead"]], ["d", "e"])
        self.assertEqual(links["dead"][1]["status"], 410)
        self.assertEqual([f["slug"] for f in links["failed"]], ["f", "g"])
        self.assertEqual(links["failed"][0]["error"], "HTTP 403")

    def test_missing_manifest(self):
        self.assertEqual(corpusstats.service_links(None),
                         {"checked": 0, "ok": 0, "moved": [], "dead": [], "failed": []})


class ServiceReportTest(unittest.TestCase):
    def test_services_per_issuer_and_topic_with_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            service = new_layer_meta("public_service")
            write_doc(root, service, "# Föräldrapenning\n\nText.\n")
            write_doc(root, {**service, "id": "service-barnbidrag", "number": "barnbidrag",
                             "topics": ["family", "money"]}, "# Barnbidrag\n\nText.\n")
            write_doc(root, template_service(), "# Bygglov\n\nText.\n")
            (root / "sources").mkdir()
            (root / "sources/services-manifest.json").write_text(json.dumps({"entries": [
                manifest_entry("foraldrapenning"),
                manifest_entry("barnbidrag", final_url="https://www.example.se/barnbidrag-ny"),
                manifest_entry("bygglov", "not_found", 404, error="HTTP 404"),
            ]}))
            report = corpusstats.summarise(corpusstats.collect(root), "2026-11-13T00:00:00Z")
        services = report["services"]
        self.assertEqual(services["documents"], 3)
        self.assertEqual(services["templates"], 1)
        self.assertEqual(services["issuers"], {"Försäkringskassan": 2, "Kommunen": 1})
        self.assertEqual(services["topics"], {"family": 2, "housing": 1, "money": 1})
        self.assertEqual(services["links"]["checked"], 3)
        self.assertEqual([m["slug"] for m in services["links"]["moved"]], ["barnbidrag"])
        self.assertEqual([d["slug"] for d in services["links"]["dead"]], ["bygglov"])
        self.assertEqual(report["layers"]["service"]["documents"], 3)
        text = corpusstats.render(report)
        self.assertIn("## Public services", text)
        self.assertIn("3 services (1 template", text)
        self.assertIn("| Försäkringskassan | 2 |", text)
        self.assertIn("| family | 2 |", text)
        self.assertIn("3 source pages checked: 1 ok, 1 moved, 1 dead, 0 failed", text)
        self.assertIn("- barnbidrag: https://www.example.se/barnbidrag -> https://www.example.se/barnbidrag-ny", text)
        self.assertIn("- bygglov: HTTP 404 (https://www.example.se/bygglov)", text)

    def test_no_services(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = corpusstats.summarise(corpusstats.collect(tmp), "2026-11-13T00:00:00Z")
        self.assertEqual(report["services"]["documents"], 0)
        self.assertEqual(report["services"]["links"]["checked"], 0)
        self.assertIn("No public services yet.", corpusstats.render(report))


if __name__ == "__main__":
    unittest.main()
