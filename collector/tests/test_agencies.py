import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from lagar import agencies, writer
from tests.test_agency import FakeClient
from tests.test_audit import LONG, meta

SITEMAP = b"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://www.lagrummet.se/rattskalla/</loc><lastmod>2026-09-15T06:58:02+00:00</lastmod></url>
  <url><loc>https://www.lagrummet.se/rattskalla/arbetsmiljoverkets-forfattningssamling-afs/</loc>
    <lastmod>2025-12-08T10:23:10+00:00</lastmod></url>
  <url><loc>https://www.lagrummet.se/rattskalla/skatteverkets-forfattningssamling-skvfs/</loc></url>
  <url><loc>https://www.lagrummet.se/rattskalla/kustbevakningens-forfattningssamling-kbvfs/</loc></url>
  <url><loc>https://www.lagrummet.se/rattskalla/luftfartsverkets-foreskrifter-publiceras-i-arbetsmiljoverkets-serie/</loc></url>
  <url><loc>https://www.lagrummet.se/rattskalla/luftfartsverkets-foreskrifter-publiceras-i-arbetsmiljoverkets-serie-2/</loc></url>
  <url><loc>https://www.lagrummet.se/rattskalla/stockholms-lans-forfattningssamling-01fs/</loc></url>
  <url><loc>https://www.lagrummet.se/rattskalla/sok-rattspraxis/</loc></url>
  <url><loc>https://www.lagrummet.se/rattskalla/125/</loc></url>
  <url><loc>https://www.example.se/elsewhere/</loc></url>
</urlset>
"""
CURATED = {
    "series": {
        "arbetsmiljoverkets-forfattningssamling-afs": {"series": "AFS", "agency": "Arbetsmiljöverket",
                                                       "status": "collected"},
        "skatteverkets-forfattningssamling-skvfs": {"series": "SKVFS", "agency": "Skatteverket",
                                                    "status": "blocked", "note": "WAF"},
        "kustbevakningens-forfattningssamling-kbvfs": {"series": "KBVFS", "agency": "Kustbevakningen"},
    },
    "shared": {
        "luftfartsverkets-foreskrifter-publiceras-i-arbetsmiljoverkets-serie": {"agency": "Luftfartsverket",
                                                                                 "published_in": "AFS"},
        "luftfartsverkets-foreskrifter-publiceras-i-arbetsmiljoverkets-serie-2": {"agency": "Luftfartsverket",
                                                                                   "published_in": "AFS"},
    },
    "sources": {"sok-rattspraxis": {"name": "Rättspraxis", "layer": "case_law", "status": "collected"}},
}
GEO = {
    "regions": [{"code": "01", "name": "Stockholms län"}, {"code": "03", "name": "Uppsala län"}],
    "kommuner": [{"code": "0180", "name": "Stockholm", "regionCode": "01"},
                 {"code": "0114", "name": "Upplands Väsby", "regionCode": "01"},
                 {"code": "0380", "name": "Uppsala", "regionCode": "03"}],
}
COUNTIES = {"counties": {"01": {"landing": "https://www.lansstyrelsen.se/stockholm/", "layout": "pages"}}}
MUNICIPALITIES = {"kommuner": {"0180": {"collection": "KFS"}}}
MANIFEST = {"gaps": [{"municipality_code": "0180", "reason": "robots.txt disallows the document URL"}]}
TARGETS = [{"layer": "agency", "type": None, "series": "AFS", "label": "AFS", "target": 3}]


def counts(**overrides):
    base = {"series": {("agency", "AFS"): 2, ("region", "01FS"): 4},
            "years": {("region", "01FS"): {2025, 2026}}, "kommun": {"0180": 5},
            "court": {"HDO": 3, "ADO": 7}, "court_name": {"HDO": "Högsta domstolen", "ADO": "Arbetsdomstolen"},
            "type": {"act": 2, "case_report": 10}}
    base.update(overrides)
    return base


def report():
    sitemap = {"source": agencies.SITEMAP_URL, "fetched_at": "2026-10-29T16:28:34Z",
               "pages": agencies.parse_sitemap(SITEMAP)}
    return agencies.build_report(sitemap, CURATED, counts(), TARGETS, COUNTIES, MUNICIPALITIES, MANIFEST, GEO)


class SitemapTests(unittest.TestCase):
    def test_pages_under_rattskalla_only_without_index(self):
        pages = agencies.parse_sitemap(SITEMAP)
        slugs = [p["slug"] for p in pages]
        self.assertEqual(len(slugs), 8)
        self.assertNotIn("", slugs)
        self.assertEqual(slugs, sorted(slugs))
        afs = next(p for p in pages if p["slug"].endswith("-afs"))
        self.assertEqual(afs["lastmod"], "2025-12-08")
        self.assertIsNone(next(p for p in pages if p["slug"] == "125")["lastmod"])

    def test_fetch_checks_robots_first(self):
        client = FakeClient({agencies.SITEMAP_URL: SITEMAP},
                            robots={agencies.SITEMAP_HOST: b"User-agent: *\nDisallow:\n"})
        sitemap = agencies.fetch_sitemap(client, "2026-10-29T00:00:00Z")
        self.assertEqual(client.calls, [agencies.SITEMAP_HOST + "/robots.txt", agencies.SITEMAP_URL])
        self.assertEqual(len(sitemap["pages"]), 8)

    def test_fetch_refused_when_robots_disallows(self):
        client = FakeClient({agencies.SITEMAP_URL: SITEMAP},
                            robots={agencies.SITEMAP_HOST: b"User-agent: *\nDisallow: /rattskalla-sitemap.xml\n"})
        with self.assertRaises(agencies.Blocked):
            agencies.fetch_sitemap(client, "2026-10-29T00:00:00Z")
        self.assertNotIn(agencies.SITEMAP_URL, client.calls)


class ReportTests(unittest.TestCase):
    def test_agency_series_status_counts_and_order(self):
        rows = report()["agency_series"]
        self.assertEqual([r["series"] for r in rows], ["AFS", "SKVFS", "KBVFS"])
        afs, skvfs, kbvfs = rows
        self.assertEqual((afs["status"], afs["documents"], afs["target"]), ("collected", 2, 3))
        self.assertEqual((skvfs["status"], skvfs["note"]), ("blocked", "WAF"))
        self.assertEqual((kbvfs["status"], kbvfs["documents"], kbvfs["target"]), ("no_adapter", 0, None))
        self.assertTrue(afs["lagrummet"].startswith(agencies.PAGE_PREFIX))

    def test_shared_series_deduplicated_and_inherit_status(self):
        [row] = report()["shared_series"]
        self.assertEqual((row["agency"], row["published_in"], row["status"]), ("Luftfartsverket", "AFS", "collected"))

    def test_counties_from_geo_with_config_and_counts(self):
        stockholm, uppsala = report()["counties"]
        self.assertEqual((stockholm["status"], stockholm["documents"], stockholm["years"], stockholm["text"]),
                         ("partial", 4, "2025–2026", "HTML text"))
        self.assertIsNotNone(stockholm["lagrummet"])
        self.assertEqual((uppsala["status"], uppsala["landing"], uppsala["lagrummet"]), ("no_adapter", None, None))

    def test_municipalities_configured_and_missing_per_county(self):
        m = report()["municipalities"]
        [stockholm] = m["configured"]
        self.assertEqual((stockholm["documents"], stockholm["status"]), (5, "partial"))
        self.assertIn("robots.txt", stockholm["note"])
        self.assertEqual(m["not_configured"], [
            {"region_code": "01", "county": "Stockholms län", "kommuner": ["Upplands Väsby"]},
            {"region_code": "03", "county": "Uppsala län", "kommuner": ["Uppsala"]},
        ])

    def test_courts_sources_unclassified_and_summary(self):
        r = report()
        self.assertEqual([c["code"] for c in r["courts"]], ["ADO", "HDO"])
        self.assertEqual([s["name"] for s in r["other_sources"]], ["Rättspraxis"])
        self.assertEqual([u["slug"] for u in r["unclassified"]], ["125"])
        self.assertEqual(r["summary"]["by_status"], {"collected": 1, "blocked": 1, "no_adapter": 1})
        self.assertEqual((r["summary"]["kommuner"], r["summary"]["kommuner_configured"]), (3, 1))
        self.assertEqual(r["layers"]["case_law"], 10)

    def test_markdown_lists_every_section(self):
        text = agencies.render_markdown(report())
        for heading in ("# Agencies and sources", "## Agency regulation series", "## Agencies publishing in another series",
                        "## County regulations (Länsstyrelserna)", "## Municipal regulations (kommuner)",
                        "## Courts (case law)", "## SFS, EU and other sources", "## Unclassified sitemap pages"):
            self.assertIn(heading, text)
        self.assertIn("| not collected: blocked by a WAF | 1 |", text)
        self.assertIn("| Skatteverket | not collected: blocked by a WAF | 0 | - | WAF |", text)
        self.assertIn("- Stockholms län (1): Upplands Väsby", text)
        self.assertIn("(COVERAGE.md)", text)


class CorpusTests(unittest.TestCase):
    def test_tally_counts_series_kommuner_and_courts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            writer.write(meta("AFS 2023:1", type_="agency_regulation", id="afs-2023-1", layer="agency",
                              issuer="Arbetsmiljöverket", source="https://example.se/afs-2023-1"), LONG, root)
            writer.write(meta("2026:1"), LONG, root)
            tally = agencies.tally_corpus(root)
        self.assertEqual(tally["series"], {("agency", "AFS"): 1})
        self.assertEqual(tally["years"], {("agency", "AFS"): {2023}})
        self.assertEqual(tally["type"], {"agency_regulation": 1, "act": 1})


class MainTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        for name, data in (("curated", CURATED), ("targets", TARGETS), ("counties", COUNTIES),
                           ("municipalities", MUNICIPALITIES), ("geo", GEO)):
            (self.dir / f"{name}.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def args(self, *extra):
        d = self.dir
        return ["--cache", str(d / "cache.json"), "--curated", str(d / "curated.json"), "--corpus", str(d / "corpus"),
                "--targets", str(d / "targets.json"), "--counties", str(d / "counties.json"),
                "--municipalities", str(d / "municipalities.json"), "--municipal-manifest", str(d / "none.json"),
                "--geo", str(d / "geo.json"), "--report", str(d / "report.json"), "--out", str(d / "AGENCIES.md"),
                *extra]

    def test_refresh_writes_cache_report_and_markdown(self):
        client = FakeClient({agencies.SITEMAP_URL: SITEMAP}, robots={agencies.SITEMAP_HOST: b""})
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(agencies.main(self.args("--refresh"), client=client), 0)
        cache = json.loads((self.dir / "cache.json").read_text(encoding="utf-8"))
        self.assertEqual(len(cache["pages"]), 8)
        self.assertEqual(json.loads((self.dir / "report.json").read_text(encoding="utf-8"))["summary"]["series"], 3)
        first = (self.dir / "AGENCIES.md").read_text(encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(agencies.main(self.args()), 0)
        self.assertEqual((self.dir / "AGENCIES.md").read_text(encoding="utf-8"), first)

    def test_rate_below_minimum_rejected(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            agencies.main(self.args("--rate", "0.5"))


class CuratedDataTests(unittest.TestCase):
    def test_curated_statuses_and_shared_series_are_known(self):
        data = Path(__file__).resolve().parents[1] / "data"
        curated = json.loads((data / "agencies.json").read_text(encoding="utf-8"))
        statuses = {e.get("status") for group in ("series", "sources") for e in curated[group].values()}
        self.assertLessEqual(statuses - {None}, set(agencies.STATUSES))
        series = {e["series"] for e in curated["series"].values()}
        for entry in curated["shared"].values():
            self.assertIn(entry["published_in"], series, entry["agency"])


if __name__ == "__main__":
    unittest.main()
