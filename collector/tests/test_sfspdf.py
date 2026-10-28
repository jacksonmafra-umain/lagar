import contextlib
import hashlib
import io
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path

from lagar import sfspdf
from lagar.http import Blocked
from lagar.sfs import StateError

FIXTURES = Path(__file__).resolve().parent / "fixtures"
BASE = "https://svenskforfattningssamling.se"
INDEX = BASE + "/regulations/2026/index.html"
INDEX_1 = BASE + "/regulations/2026/index.html%3Fpage=1.html"
DETAIL_1832 = BASE + "/doc/20261832.html"
DETAIL_1831 = BASE + "/doc/20261831.html"
DETAIL_1 = BASE + "/doc/20261.html"
PDF_1832 = BASE + "/sites/default/files/sfs/2026-10/SFS2026-1832.pdf"
PDF_1831 = BASE + "/sites/default/files/sfs/2026-10/SFS2026-1831.pdf"
PDF_1831_FIX = BASE + "/sites/default/files/sfs/2026-11/SFS2026-1831-rattelseblad.pdf"
PDF_1 = BASE + "/sites/default/files/sfs/2026-01/SFS2026-1.pdf"
FAKE_PDF = b"%PDF-1.7 fake bytes"


def fixture(name):
    return (FIXTURES / name).read_bytes()


def http_error(url, code):
    return urllib.error.HTTPError(url, code, "err", {}, io.BytesIO(b""))


def detail_for(number, pdf_path):
    year, num = number.split(":")
    return (
        '<html><body><article class="node">'
        '<div class="field field--name-sfs-number"><div class="field--label">SFS-nummer</div>'
        f'<div class="field--item">{number}</div></div>'
        '<div class="field field--name-announcement"><div class="field--label">Publicerad</div>'
        '<div class="field--item">2026-01-02</div></div>'
        f'<ul><li class="field--item"><a href="../{pdf_path}">{year}:{num} (pdf)</a></li></ul>'
        "</article></body></html>"
    ).encode()


def routes():
    return {
        INDEX: fixture("sfspdf-index.html"),
        INDEX_1: fixture("sfspdf-index-last.html"),
        DETAIL_1832: fixture("sfspdf-detail.html"),
        DETAIL_1831: fixture("sfspdf-detail-rattelse.html"),
        DETAIL_1: detail_for("2026:1", "sites/default/files/sfs/2026-01/SFS2026-1.pdf"),
        PDF_1832: FAKE_PDF + b"1832",
        PDF_1831: FAKE_PDF + b"1831",
        PDF_1831_FIX: FAKE_PDF + b"fix",
        PDF_1: FAKE_PDF + b"1",
        sfspdf.RSS_URL: fixture("sfspdf-rss.xml"),
    }


class FakeClient:
    def __init__(self, routes, robots=None):
        self.routes = routes
        self.robots = robots
        self.calls = []

    def fetch(self, url):
        self.calls.append(url)
        if url == sfspdf.ROBOTS_URL and self.robots is not None:
            return self.robots, "text/plain"
        value = self.routes.get(url)
        if value is None:
            raise http_error(url, 404)
        if isinstance(value, Exception):
            raise value
        return value, "application/pdf" if url.endswith(".pdf") else "text/html"

    def get(self, url):
        return self.fetch(url)[0]


class ParserTests(unittest.TestCase):
    def test_index_rows_and_next_page(self):
        items, next_url = sfspdf.parse_index(
            fixture("sfspdf-index.html").decode(), INDEX
        )
        self.assertEqual(
            [(i.number, i.detail_url, i.published) for i in items],
            [
                ("2026:1832", DETAIL_1832, "2026-10-27"),
                ("2026:1831", DETAIL_1831, "2026-10-27"),
            ],
        )
        self.assertEqual(next_url, INDEX_1)

    def test_last_index_page_has_no_next(self):
        items, next_url = sfspdf.parse_index(
            fixture("sfspdf-index-last.html").decode(), INDEX_1
        )
        self.assertEqual([i.number for i in items], ["2026:1"])
        self.assertIsNone(next_url)

    def test_detail_number_date_and_pdf(self):
        detail = sfspdf.parse_detail(fixture("sfspdf-detail.html").decode(), DETAIL_1832)
        self.assertEqual(detail.number, "2026:1832")
        self.assertEqual(detail.published, "2026-10-27")
        self.assertEqual(detail.pdf_urls, [PDF_1832])

    def test_detail_with_correction_sheet_lists_both_files(self):
        detail = sfspdf.parse_detail(
            fixture("sfspdf-detail-rattelse.html").decode(), DETAIL_1831
        )
        self.assertEqual(detail.pdf_urls, [PDF_1831, PDF_1831_FIX])

    def test_detail_ignores_pdf_links_outside_the_article(self):
        html = '<a href="/x.pdf">x</a><article></article>'
        self.assertEqual(sfspdf.parse_detail(html, DETAIL_1).pdf_urls, [])

    def test_rss_items(self):
        items = sfspdf.parse_rss(fixture("sfspdf-rss.xml"))
        self.assertEqual(
            [(i.number, i.detail_url) for i in items],
            [("2026:1832", DETAIL_1832), ("2026:1831", DETAIL_1831)],
        )

    def test_number_key_sorts_numerically(self):
        numbers = ["2026:200", "2025:9", "2026:1832", "2026:3"]
        self.assertEqual(
            sorted(numbers, key=sfspdf.number_key),
            ["2025:9", "2026:3", "2026:200", "2026:1832"],
        )


class RunTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.manifest = self.tmp / "sources" / "manifest.json"
        self.state = self.tmp / "data" / "state.json"

    def args(self, *extra):
        return sfspdf.parse_args(
            ["--manifest", str(self.manifest), "--state", str(self.state), *extra]
        )

    def run_quiet(self, client, args):
        with contextlib.redirect_stdout(io.StringIO()):
            return sfspdf.run(client, args)

    def load(self):
        return json.loads(self.manifest.read_text(encoding="utf-8"))

    def test_year_walk_writes_sorted_manifest(self):
        summary = self.run_quiet(FakeClient(routes()), self.args("--year", "2026"))
        self.assertEqual(summary.recorded, ["2026:1832", "2026:1831", "2026:1"])
        manifest = self.load()
        self.assertEqual(manifest["source"], BASE)
        self.assertEqual(
            [e["number"] for e in manifest["entries"]], ["2026:1", "2026:1831", "2026:1832"]
        )
        entry = manifest["entries"][2]
        self.assertEqual(entry["detail_url"], DETAIL_1832)
        self.assertEqual(entry["published"], "2026-10-27")
        (file,) = entry["files"]
        body = FAKE_PDF + b"1832"
        self.assertEqual(file["url"], PDF_1832)
        self.assertEqual(file["bytes"], len(body))
        self.assertEqual(file["sha256"], hashlib.sha256(body).hexdigest())
        self.assertEqual(file["content_type"], "application/pdf")
        self.assertRegex(file["retrieved_at"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
        self.assertEqual(
            [f["url"] for f in manifest["entries"][1]["files"]], [PDF_1831, PDF_1831_FIX]
        )

    def test_limit_stops_after_n_new_entries(self):
        client = FakeClient(routes())
        summary = self.run_quiet(client, self.args("--year", "2026", "--limit", "1"))
        self.assertEqual(summary.recorded, ["2026:1832"])
        self.assertNotIn(INDEX_1, client.calls)

    def test_rerun_skips_recorded_numbers_without_refetching(self):
        self.run_quiet(FakeClient(routes()), self.args("--year", "2026"))
        before = self.manifest.read_bytes()
        client = FakeClient(routes())
        summary = self.run_quiet(client, self.args("--year", "2026"))
        self.assertEqual((summary.recorded, summary.skipped), ([], 3))
        self.assertFalse([c for c in client.calls if "/doc/" in c or c.endswith(".pdf")])
        self.assertEqual(self.manifest.read_bytes(), before)

    def test_rss_mode_reads_only_the_feed(self):
        client = FakeClient(routes())
        summary = self.run_quiet(client, self.args("--rss"))
        self.assertEqual(summary.recorded, ["2026:1832", "2026:1831"])
        self.assertNotIn(INDEX, client.calls)

    def test_detail_failure_is_recorded_and_run_continues(self):
        r = routes()
        r[PDF_1831] = b"<html>not a pdf</html>"
        summary = self.run_quiet(FakeClient(r), self.args("--year", "2026"))
        self.assertEqual(summary.failed, ["2026:1831"])
        self.assertEqual(summary.recorded, ["2026:1832", "2026:1"])
        state = json.loads(self.state.read_text(encoding="utf-8"))
        self.assertIn("not a PDF", state["failed"]["2026:1831"])
        # A later successful run clears the failure.
        self.run_quiet(FakeClient(routes()), self.args("--year", "2026"))
        state = json.loads(self.state.read_text(encoding="utf-8"))
        self.assertEqual(state["failed"], {})

    def test_number_mismatch_on_detail_page_fails(self):
        r = routes()
        r[DETAIL_1832] = detail_for("2026:9", "sites/default/files/sfs/2026-01/SFS2026-9.pdf")
        summary = self.run_quiet(FakeClient(r), self.args("--year", "2026"))
        self.assertIn("2026:1832", summary.failed)

    def test_pdf_off_site_is_refused(self):
        r = routes()
        r[DETAIL_1] = detail_for("2026:1", "x.pdf").replace(
            b'href="../x.pdf"', b'href="https://example.org/x.pdf"'
        )
        client = FakeClient(r)
        summary = self.run_quiet(client, self.args("--year", "2026"))
        self.assertEqual(summary.failed, ["2026:1"])
        self.assertNotIn("https://example.org/x.pdf", client.calls)

    def test_blocked_stops_and_keeps_recorded_entries(self):
        r = routes()
        r[DETAIL_1831] = Blocked("403 Forbidden")
        report = self.tmp / "report.json"
        summary = self.run_quiet(
            FakeClient(r), self.args("--year", "2026", "--report", str(report))
        )
        self.assertTrue(summary.blocked)
        self.assertEqual([e["number"] for e in self.load()["entries"]], ["2026:1832"])
        state = json.loads(self.state.read_text(encoding="utf-8"))
        self.assertIn("403", state["blocked"])
        self.assertEqual(
            json.loads(report.read_text(encoding="utf-8")),
            {"recorded": ["2026:1832"], "skipped": 0, "failed": [], "blocked": True},
        )

    def test_robots_disallow_blocks_before_any_page(self):
        client = FakeClient(routes(), robots=b"User-agent: *\nDisallow: /doc/\n")
        summary = self.run_quiet(client, self.args("--year", "2026"))
        self.assertTrue(summary.blocked)
        self.assertEqual(client.calls, [sfspdf.ROBOTS_URL])

    def test_cache_keeps_pdf_bytes_by_year(self):
        cache = self.tmp / "cache"
        self.run_quiet(
            FakeClient(routes()), self.args("--year", "2026", "--cache", str(cache))
        )
        self.assertEqual(
            (cache / "2026" / "SFS2026-1832.pdf").read_bytes(), FAKE_PDF + b"1832"
        )
        self.assertTrue((cache / "2026" / "SFS2026-1831-rattelseblad.pdf").exists())

    def test_index_failure_exits_1_but_saves_progress(self):
        r = routes()
        del r[INDEX_1]
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
            io.StringIO()
        ):
            code = sfspdf.main(
                ["--manifest", str(self.manifest), "--state", str(self.state),
                 "--year", "2026"],
                client=FakeClient(r),
            )
        self.assertEqual(code, 1)
        self.assertEqual(len(self.load()["entries"]), 2)

    def test_corrupt_manifest_is_never_reset(self):
        self.manifest.parent.mkdir(parents=True)
        self.manifest.write_text("{not json", encoding="utf-8")
        with self.assertRaises(StateError):
            self.run_quiet(FakeClient(routes()), self.args("--year", "2026"))
        self.assertEqual(self.manifest.read_text(encoding="utf-8"), "{not json")

    def test_year_or_rss_is_required(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            sfspdf.parse_args([])


if __name__ == "__main__":
    unittest.main()
