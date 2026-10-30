import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from lagar import agencies, writer
from tests.test_agency import FakeClient
from tests.test_audit import LONG, meta

def _article(title, href, description=None):
    text = f'<div class="text-sm font-light mt-2"> {description} </div>' if description else ""
    return (f'<article class="w-full"><a class="block" href="{href}" target=_blank()>'
            f'<div class="flex"><h2 class="text-base">{title}</h2><svg></svg></div>{text}</a></article>')


INDEX = ("<html><body><main>" + "".join([
    _article("Arbetsmilj&ouml;verkets f&ouml;rfattningssamling (AFS)", "https://www.av.se/foreskrifter/",
             "Arbetsmilj&ouml;verkets f&ouml;reskrifter."),
    _article("Skatteverkets författningssamling (SKVFS)", "https://www.skatteverket.se/skvfs"),
    _article("Kustbevakningens författningssamling (KBVFS)", "https://www.kustbevakningen.se/kbvfs/"),
    _article("Luftfartsverkets föreskrifter (publiceras i Arbetsmiljöverkets serie)", "https://lfv.se/a"),
    _article("Luftfartsverkets föreskrifter (publiceras i Arbetsmiljöverkets serie)", "https://lfv.se/b"),
    _article("Stockholms läns författningssamling (01FS)", "https://www.lansstyrelsen.se/stockholm/fs.html"),
    _article("Uppsala läns författningssamling (03 FS)", "https://www.lansstyrelsen.se/uppsala/fs.html", "Uppsala."),
    _article("Sök rättspraxis", "https://rattspraxis.etjanst.domstol.se/sok/"),
    _article("Elsäkerhetsverkets författningssamling (ELSÄK-FS)", "https://elsakerhetsverket.se/foreskrifter"),
]) + "</main></body></html>").encode()
COURTS = json.dumps([{"domstolKod": "HDO", "domstolNamn": "Högsta domstolen"},
                     {"domstolKod": "ADO", "domstolNamn": "Arbetsdomstolen"},
                     {"domstolKod": "KGG", "domstolNamn": "Kammarrätten i Göteborg"}]).encode()
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
    },
    "sources": {"sok-rattspraxis": {"name": "Rättspraxis", "layer": "case_law", "status": "collected"}},
    "courts": {"KGG": {"status": "no_number", "note": "no report number"}},
    "issues": {"series:KBVFS": 201, "kommun:0114": 301, "county:03": 401, "court:KGG": 501},
    "kommuner": {"0380": {"status": "blocked", "note": "WAF page"}, "0180": {"note": "lokala ordningsföreskrifter are HTML"}},
}
GEO = {
    "regions": [{"code": "01", "name": "Stockholms län"}, {"code": "03", "name": "Uppsala län"}],
    "kommuner": [{"code": "0180", "name": "Stockholm", "regionCode": "01"},
                 {"code": "0114", "name": "Upplands Väsby", "regionCode": "01"},
                 {"code": "0380", "name": "Uppsala", "regionCode": "03"}],
}
COUNTIES = {"counties": {"01": {"landing": "https://www.lansstyrelsen.se/stockholm/", "layout": "pages"}}}
MUNICIPALITIES = {"kommuner": {"0180": {"collection": "KFS"}}}
KOMMUNER = {"websites": {"0180": "https://start.stockholm/", "0114": "https://www.upplandsvasby.se/"}}
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
    index = {"source": agencies.INDEX_URL, "fetched_at": "2026-10-29T16:28:34Z", "pages": agencies.parse_index(INDEX)}
    courts = {"courts": agencies.parse_courts(COURTS)}
    return agencies.build_report(index, CURATED, counts(), TARGETS, COUNTIES, MUNICIPALITIES, MANIFEST, GEO,
                                 courts, KOMMUNER)


class IndexTests(unittest.TestCase):
    def test_entries_with_official_url_and_description(self):
        pages = agencies.parse_index(INDEX)
        self.assertEqual(len(pages), 9)
        self.assertEqual([p["slug"] for p in pages], sorted(p["slug"] for p in pages))
        afs = next(p for p in pages if p["slug"] == "arbetsmiljoverkets-forfattningssamling-afs")
        self.assertEqual(afs["title"], "Arbetsmiljöverkets författningssamling (AFS)")
        self.assertEqual(afs["url"], "https://www.av.se/foreskrifter/")
        self.assertEqual(afs["description"], "Arbetsmiljöverkets föreskrifter.")
        self.assertIsNone(next(p for p in pages if p["slug"].endswith("kbvfs"))["description"])

    def test_slugify_folds_diacritics(self):
        self.assertEqual(agencies.slugify("Elsäkerhetsverkets författningssamling (ELSÄK-FS)"),
                         "elsakerhetsverkets-forfattningssamling-elsak-fs")

    def test_fetch_checks_robots_first(self):
        client = FakeClient({agencies.INDEX_URL: INDEX},
                            robots={agencies.INDEX_HOST: b"User-agent: *\nDisallow:\n"})
        index = agencies.fetch_index(client, "2026-10-29T00:00:00Z")
        self.assertEqual(client.calls, [agencies.INDEX_HOST + "/robots.txt", agencies.INDEX_URL])
        self.assertEqual(len(index["pages"]), 9)

    def test_fetch_refused_when_robots_disallows(self):
        client = FakeClient({agencies.INDEX_URL: INDEX},
                            robots={agencies.INDEX_HOST: b"User-agent: *\nDisallow: /rattskalla/\n"})
        with self.assertRaises(agencies.Blocked):
            agencies.fetch_index(client, "2026-10-29T00:00:00Z")
        self.assertNotIn(agencies.INDEX_URL, client.calls)

    def test_courts_from_api(self):
        self.assertEqual([c["code"] for c in agencies.parse_courts(COURTS)], ["ADO", "HDO", "KGG"])

    def test_court_url_matches_lagrummet_link(self):
        self.assertEqual(agencies.court_url("RHN"), "https://rattspraxis.etjanst.domstol.se/sok/sokning?filter="
                         "domstolskodLista%3D%255B%2522RHN%2522%255D%26arVagledande%3Dtrue%26sortering%3D%2522desc%2522")


class ReportTests(unittest.TestCase):
    def test_agency_series_status_counts_and_order(self):
        rows = report()["agency_series"]
        self.assertEqual([r["series"] for r in rows], ["AFS", "SKVFS", "KBVFS"])
        afs, skvfs, kbvfs = rows
        self.assertEqual((afs["status"], afs["documents"], afs["target"]), ("collected", 2, 3))
        self.assertEqual((skvfs["status"], skvfs["note"]), ("blocked", "WAF"))
        self.assertEqual((kbvfs["status"], kbvfs["documents"], kbvfs["target"]), ("no_adapter", 0, None))
        self.assertEqual((afs["url"], afs["description"]), ("https://www.av.se/foreskrifter/",
                                                            "Arbetsmiljöverkets föreskrifter."))
        self.assertEqual((afs["issue"], kbvfs["issue"]), (None, "https://github.com/jacksonmafra-umain/lagar/issues/201"))

    def test_shared_series_deduplicated_and_inherit_status(self):
        [row] = report()["shared_series"]
        self.assertEqual((row["agency"], row["published_in"], row["status"]), ("Luftfartsverket", "AFS", "collected"))
        self.assertEqual(row["url"], "https://lfv.se/a")

    def test_counties_from_geo_with_config_and_counts(self):
        stockholm, uppsala = report()["counties"]
        self.assertEqual((stockholm["status"], stockholm["documents"], stockholm["years"], stockholm["text"]),
                         ("partial", 4, "2025–2026", "HTML text"))
        self.assertEqual(stockholm["url"], "https://www.lansstyrelsen.se/stockholm/")
        self.assertEqual((uppsala["status"], uppsala["url"], uppsala["description"]),
                         ("no_adapter", "https://www.lansstyrelsen.se/uppsala/fs.html", "Uppsala."))
        self.assertTrue(uppsala["issue"].endswith("/401"))

    def test_municipalities_configured_and_missing_per_county(self):
        m = report()["municipalities"]
        stockholm = next(k for k in m["configured"] if k["code"] == "0180")
        self.assertEqual((stockholm["documents"], stockholm["status"]), (5, "partial"))
        self.assertIn("robots.txt", stockholm["note"])
        self.assertEqual(stockholm["url"], "https://start.stockholm/")
        issue = "https://github.com/jacksonmafra-umain/lagar/issues/301"
        self.assertEqual(m["not_configured"], [
            {"region_code": "01", "county": "Stockholms län",
             "kommuner": [{"code": "0114", "kommun": "Upplands Väsby", "url": "https://www.upplandsvasby.se/",
                           "issue": issue}]},
        ])
        self.assertIn("lokala ordningsföreskrifter are HTML", stockholm["note"])

    def test_curated_kommun_without_config_is_listed_with_its_reason(self):
        r = report()
        uppsala = next(k for k in r["municipalities"]["configured"] if k["code"] == "0380")
        self.assertEqual((uppsala["status"], uppsala["collection"], uppsala["documents"], uppsala["note"]),
                         ("blocked", None, 0, "WAF page"))
        self.assertEqual(r["summary"]["kommuner_configured"], 1)

    def test_courts_sources_unclassified_and_summary(self):
        r = report()
        self.assertEqual([(c["code"], c["status"]) for c in r["courts"]],
                         [("ADO", "collected"), ("HDO", "collected"), ("KGG", "no_number")])
        self.assertTrue(r["courts"][2]["issue"].endswith("/501"))
        self.assertEqual((r["summary"]["courts"], r["summary"]["courts_collected"]), (3, 2))
        self.assertEqual([s["name"] for s in r["other_sources"]], ["Rättspraxis"])
        self.assertEqual([u["title"] for u in r["unclassified"]], ["Elsäkerhetsverkets författningssamling (ELSÄK-FS)"])
        self.assertEqual(r["summary"]["by_status"], {"collected": 1, "blocked": 1, "no_adapter": 1})
        self.assertEqual((r["summary"]["kommuner"], r["summary"]["kommuner_configured"]), (3, 1))
        self.assertEqual(r["layers"]["case_law"], 10)

    def test_markdown_lists_every_section(self):
        text = agencies.render_markdown(report())
        for heading in ("# Agencies and sources", "## Agency regulation series", "## Agencies publishing in another series",
                        "## County regulations (Länsstyrelserna)", "## Municipal regulations (kommuner)",
                        "## Courts (case law)", "## SFS, EU and other sources", "## Unclassified lagrummet.se entries"):
            self.assertIn(heading, text)
        self.assertIn("| not collected: blocked by a WAF | 1 |", text)
        self.assertIn("| [SKVFS](https://www.skatteverket.se/skvfs) | Skatteverket | not collected: blocked by a WAF | 0 | - | - | WAF |",
                      text)
        self.assertIn("- Stockholms län (1): [Upplands Väsby](https://www.upplandsvasby.se/) "
                      "([#301](https://github.com/jacksonmafra-umain/lagar/issues/301))", text)
        self.assertNotIn("lagrummet.se/rattskalla/arbetsmiljoverkets", text)
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
                           ("municipalities", MUNICIPALITIES), ("geo", GEO), ("kommuner", KOMMUNER)):
            (self.dir / f"{name}.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def args(self, *extra):
        d = self.dir
        return ["--cache", str(d / "cache.json"), "--courts", str(d / "courts.json"),
                "--kommuner", str(d / "kommuner.json"), "--landing", str(d / "landing" / "sources.json"),
                "--curated", str(d / "curated.json"), "--corpus", str(d / "corpus"),
                "--targets", str(d / "targets.json"), "--counties", str(d / "counties.json"),
                "--municipalities", str(d / "municipalities.json"), "--municipal-manifest", str(d / "none.json"),
                "--geo", str(d / "geo.json"), "--report", str(d / "report.json"), "--out", str(d / "AGENCIES.md"),
                *extra]

    def test_refresh_writes_cache_report_and_markdown(self):
        client = FakeClient({agencies.INDEX_URL: INDEX, agencies.COURTS_URL: COURTS},
                            robots={agencies.INDEX_HOST: b"", agencies.COURTS_HOST: b""})
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(agencies.main(self.args("--refresh"), client=client), 0)
        cache = json.loads((self.dir / "cache.json").read_text(encoding="utf-8"))
        self.assertEqual(len(cache["pages"]), 9)
        courts = json.loads((self.dir / "courts.json").read_text(encoding="utf-8"))
        self.assertEqual(len(courts["courts"]), 3)
        self.assertEqual(json.loads((self.dir / "report.json").read_text(encoding="utf-8"))["summary"]["series"], 3)
        catalog = json.loads((self.dir / "landing" / "sources.json").read_text(encoding="utf-8"))
        self.assertEqual(set(catalog["sections"]), {"series", "shared", "counties", "kommuner", "courts", "sources"})
        self.assertEqual([k["code"] for k in catalog["sections"]["kommuner"]], ["0114", "0180", "0380"])
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
        self.assertLessEqual({e["status"] for e in curated["courts"].values()}, set(agencies.STATUSES))

    def test_every_kommun_has_an_https_website(self):
        root = Path(__file__).resolve().parents[2]
        geo = json.loads((root / agencies.DEFAULT_GEO).read_text(encoding="utf-8"))
        websites = json.loads((root / agencies.DEFAULT_KOMMUNER).read_text(encoding="utf-8"))["websites"]
        self.assertEqual(set(websites), {k["code"] for k in geo["kommuner"]})
        for code, url in websites.items():
            self.assertRegex(url, r"^https://[a-z0-9.-]+\.[a-z]+/$", code)

    def test_committed_report_links_official_pages_only(self):
        root = Path(__file__).resolve().parents[2]
        text = (root / "AGENCIES.md").read_text(encoding="utf-8")
        self.assertNotRegex(text, r"lagrummet\.se/rattskalla/[a-z0-9]")


if __name__ == "__main__":
    unittest.main()
