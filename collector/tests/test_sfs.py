import http.client
import io
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path

from lagar import sfs
from lagar.http import Blocked
from lagar.riksdagen import FUNDAMENTAL_LAWS

FIXTURES = Path(__file__).resolve().parent / "fixtures"
ROBOTS = "https://data.riksdagen.se/robots.txt"
TEXT = (FIXTURES / "sfs-1999-175.text").read_bytes()


def http_error(url, code):
    return urllib.error.HTTPError(url, code, "err", {}, io.BytesIO(b""))


def listing_json(ids, pages=1, systemdatum="2026-01-01 00:00:00"):
    docs = []
    for index, dok_id in enumerate(ids):
        year, number = dok_id.removeprefix("sfs-").split("-")
        docs.append(
            {
                "dok_id": dok_id,
                "beteckning": f"{year}:{int(number)}",
                "titel": f"Lag ({year}:{int(number)}) om test {index}",
                "datum": f"{year.lstrip('N')}-01-01",
                "systemdatum": (
                    systemdatum[index] if isinstance(systemdatum, list) else systemdatum
                ),
                "organ": "Justitiedepartementet",
            }
        )
    return json.dumps(
        {"dokumentlista": {"@sidor": str(pages), "dokument": docs}}
    ).encode()


class FakeClient:
    def __init__(self, routes=None, robots=None):
        self.routes = dict(routes or {})
        self.robots = robots
        self.calls = []

    def get(self, url):
        self.calls.append(url)
        if url == ROBOTS:
            if self.robots is None:
                raise http_error(url, 404)
            return self.robots
        for key, value in self.routes.items():
            if key in url:
                if isinstance(value, Exception):
                    raise value
                return value
        if url.endswith(".text"):
            return TEXT
        raise http_error(url, 404)

    def text_calls(self):
        return [c for c in self.calls if c.endswith(".text")]


class SfsTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.state_path = self.tmp / "data" / "state.json"
        self.corpus = self.tmp / "corpus"

    def args(self, *extra):
        return sfs.parse_args(
            ["--corpus", str(self.corpus), "--state", str(self.state_path), *extra]
        )

    def state(self):
        return json.loads(self.state_path.read_text(encoding="utf-8"))

    def test_fundamental_writes_four_files(self):
        routes = {
            f"/dokument/{dok_id}.text": (FIXTURES / f"{dok_id}.text").read_bytes()
            for dok_id in FUNDAMENTAL_LAWS
            if (FIXTURES / f"{dok_id}.text").exists()
        }
        for dok_id in FUNDAMENTAL_LAWS:
            routes.setdefault(f"/dokument/{dok_id}.text", TEXT)
        client = FakeClient(routes)
        summary = sfs.run(client, self.args("--fundamental"))
        self.assertEqual(summary.written, 4)
        self.assertEqual(summary.failed, [])
        self.assertEqual(len(client.text_calls()), 4)
        files = sorted((self.corpus / "fundamental-laws").glob("*.md"))
        self.assertEqual(len(files), 4)
        # No listing systemdatum exists for --fundamental, so nothing is marked done.
        self.assertEqual(self.state()["done"], {})

    def test_limit_stops_after_n(self):
        ids = [f"sfs-2000-{n}" for n in range(1, 6)]
        client = FakeClient({"dokumentlista": listing_json(ids)})
        summary = sfs.run(client, self.args("--limit", "2"))
        self.assertEqual(summary.written, 2)
        self.assertEqual(len(client.text_calls()), 2)

    def test_resume_skips_done(self):
        ids = ["sfs-2000-1", "sfs-2000-2"]
        listing = listing_json(ids)
        sfs.run(FakeClient({"dokumentlista": listing}), self.args())
        client = FakeClient({"dokumentlista": listing})
        summary = sfs.run(client, self.args())
        self.assertEqual(summary.skipped, 2)
        self.assertEqual(summary.written, 0)
        self.assertEqual(client.text_calls(), [])

    def test_n_series_resume_uses_original_dok_id(self):
        listing = listing_json(["sfs-N2026-1"])
        sfs.run(FakeClient({"dokumentlista": listing}), self.args())
        self.assertEqual(list(self.state()["done"]), ["sfs-N2026-1"])
        self.assertEqual([p.name for p in self.corpus.rglob("*.md")], ["n2026-1.md"])
        client = FakeClient({"dokumentlista": listing})
        summary = sfs.run(client, self.args())
        self.assertEqual((summary.skipped, summary.written), (1, 0))

    def test_resume_refetches_when_file_missing(self):
        listing = listing_json(["sfs-2000-1"])
        sfs.run(FakeClient({"dokumentlista": listing}), self.args())
        for path in self.corpus.rglob("*.md"):
            path.unlink()
        client = FakeClient({"dokumentlista": listing})
        summary = sfs.run(client, self.args())
        self.assertEqual(summary.written, 1)

    def test_since_refetches_only_newer(self):
        ids = ["sfs-2000-1", "sfs-2000-2"]
        listing = listing_json(
            ids, systemdatum=["2026-01-01 00:00:00", "2026-06-01 00:00:00"]
        )
        client = FakeClient({"dokumentlista": listing})
        summary = sfs.run(client, self.args("--since", "2026-03-01"))
        self.assertEqual(summary.written, 1)
        self.assertEqual(len(client.text_calls()), 1)
        self.assertIn("sfs-2000-2", client.text_calls()[0])

    def test_blocked_stops_and_records(self):
        client = FakeClient(
            {"dokumentlista": listing_json(["sfs-2000-1", "sfs-2000-2"]),
             "/dokument/sfs-2000-1.text": Blocked("403 Forbidden")}
        )
        summary = sfs.run(client, self.args())
        self.assertTrue(summary.blocked)
        self.assertEqual(len(client.text_calls()), 1)
        self.assertIn("403", self.state()["blocked"])

    def test_main_returns_2_when_blocked(self):
        client = FakeClient({"dokumentlista": Blocked("403 Forbidden")})
        code = sfs.main(
            ["--corpus", str(self.corpus), "--state", str(self.state_path)],
            client=client,
        )
        self.assertEqual(code, 2)

    def test_failed_doc_recorded_and_run_continues(self):
        ids = ["sfs-2000-1", "sfs-2000-2", "sfs-2000-3"]
        client = FakeClient(
            {"dokumentlista": listing_json(ids),
             "/dokument/sfs-2000-2.text": http_error("u", 404)}
        )
        summary = sfs.run(client, self.args())
        self.assertEqual(summary.written, 2)
        self.assertEqual(summary.failed, ["sfs-2000-2"])
        self.assertIn("sfs-2000-2", self.state()["failed"])
        self.assertNotIn("sfs-2000-2", self.state()["done"])

    def test_network_and_decode_errors_are_per_document(self):
        ids = ["sfs-2000-1", "sfs-2000-2", "sfs-2000-3", "sfs-2000-4"]
        client = FakeClient(
            {"dokumentlista": listing_json(ids),
             "/dokument/sfs-2000-1.text": urllib.error.URLError("down"),
             "/dokument/sfs-2000-2.text": TimeoutError("slow"),
             "/dokument/sfs-2000-3.text": b"\xff\xfe\x00bad"}
        )
        summary = sfs.run(client, self.args())
        self.assertEqual(summary.written, 1)
        self.assertEqual(len(summary.failed), 3)

    def test_incomplete_read_is_per_document(self):
        ids = ["sfs-2000-1", "sfs-2000-2"]
        client = FakeClient(
            {"dokumentlista": listing_json(ids),
             "/dokument/sfs-2000-1.text": http.client.IncompleteRead(b"x")}
        )
        summary = sfs.run(client, self.args())
        self.assertEqual(summary.failed, ["sfs-2000-1"])
        self.assertEqual(summary.written, 1)

    def test_limit_stops_paging(self):
        client = FakeClient(
            {"p=1&": listing_json(["sfs-2000-1"], pages=3),
             "p=2&": listing_json(["sfs-2000-2"], pages=3)}
        )
        sfs.run(client, self.args("--limit", "1"))
        listing_calls = [c for c in client.calls if "dokumentlista" in c]
        self.assertEqual(len(listing_calls), 1)

    def test_corrupt_state_exits_1_and_is_kept(self):
        self.state_path.parent.mkdir(parents=True)
        self.state_path.write_text("{not json", encoding="utf-8")
        code = sfs.main(
            ["--corpus", str(self.corpus), "--state", str(self.state_path)],
            client=FakeClient(),
        )
        self.assertEqual(code, 1)
        self.assertEqual(self.state_path.read_text(encoding="utf-8"), "{not json")
        self.state_path.write_text("[]", encoding="utf-8")
        with self.assertRaises(sfs.StateError):
            sfs.run(FakeClient(), self.args())

    def test_invalid_date_rejected(self):
        with self.assertRaises(SystemExit):
            self.args("--since", "2026-13-01")

    def test_only_yyyy_mm_dd_dates_accepted(self):
        for flag in ("--since", "--from", "--to"):
            self.assertEqual(getattr(self.args(flag, "2026-03-01"), {"--since": "since", "--from": "from_date", "--to": "to_date"}[flag]), "2026-03-01")
            for bad in ("20260301", "2026-3-1", "2026-03-01T00:00", "2026-W09-1", "2026-03-01\n", " 2026-03-01", "٢٠٢٦-٠٣-٠١"):
                with self.subTest(flag=flag, bad=bad):
                    with self.assertRaises(SystemExit):
                        self.args(flag, bad)

    def test_negative_limit_rejected(self):
        with self.assertRaises(SystemExit):
            self.args("--limit", "-1")
        self.assertEqual(self.args("--limit", "0").limit, 0)

    def test_blocked_in_state_must_be_string_or_null(self):
        self.state_path.parent.mkdir(parents=True)
        for bad in ('{"blocked": 5}', '{"blocked": {"a": 1}}', '{"done": {"a": 1}}', '{"failed": {"a": []}}'):
            with self.subTest(bad=bad):
                self.state_path.write_text(bad, encoding="utf-8")
                with self.assertRaises(sfs.StateError):
                    sfs.run(FakeClient(), self.args())
        self.state_path.write_text('{"blocked": "403 Forbidden"}', encoding="utf-8")
        sfs.run(FakeClient({"dokumentlista": listing_json([])}), self.args())

    def test_fundamental_run_does_not_store_empty_systemdatum(self):
        client = FakeClient()
        sfs.run(client, self.args("--fundamental"))
        self.assertTrue(all(value for value in self.state()["done"].values()))

    def test_already_done_uses_same_title_and_type_as_writer(self):
        listing = json.dumps({"dokumentlista": {"@sidor": "1", "dokument": [{
            "dok_id": "sfs-2000-1", "beteckning": "2000:1",
            "titel": "/Rubriken upphör att gälla U:2027-01-01/\nFörordning (2000:1) om a;\n"
                     "/Rubriken träder i kraft I:2027-01-01/\nLag (2000:1) om b",
            "datum": "2000-01-01", "systemdatum": "s1", "organ": ""}]}}).encode()
        sfs.run(FakeClient({"dokumentlista": listing}), self.args())
        self.assertEqual([p.parent.name for p in self.corpus.rglob("*.md")], ["ordinances"])
        client = FakeClient({"dokumentlista": listing})
        summary = sfs.run(client, self.args())
        self.assertEqual((summary.skipped, summary.written), (1, 0))

    def test_type_change_between_runs_leaves_single_file(self):
        def listing(title):
            return json.dumps({"dokumentlista": {"@sidor": "1", "dokument": [{
                "dok_id": "sfs-2000-1", "beteckning": "2000:1", "titel": title,
                "datum": "2000-01-01", "systemdatum": title, "organ": ""}]}}).encode()
        sfs.run(FakeClient({"dokumentlista": listing("Resolution (2000:1) om a")}), self.args())
        sfs.run(FakeClient({"dokumentlista": listing("Förordning (2000:1) om a")}), self.args())
        self.assertEqual([str(p.relative_to(self.corpus)) for p in self.corpus.rglob("*.md")],
                         ["sfs/ordinances/2000-1.md"])

    def test_listing_error_raises(self):
        client = FakeClient({"dokumentlista": http_error("u", 500)})
        with self.assertRaises(sfs.ListingError):
            sfs.run(client, self.args())
        self.assertEqual(
            sfs.main(
                ["--corpus", str(self.corpus), "--state", str(self.state_path)],
                client=client,
            ),
            1,
        )

    def test_robots_disallow_blocks(self):
        client = FakeClient(
            robots=b"User-agent: *\nDisallow: /dokumentlista\n"
        )
        summary = sfs.run(client, self.args())
        self.assertTrue(summary.blocked)
        self.assertEqual(client.calls, [ROBOTS])
        self.assertIn("robots", self.state()["blocked"])

    def test_robots_allow_proceeds(self):
        client = FakeClient(
            {"dokumentlista": listing_json(["sfs-2000-1"])},
            robots=b"User-agent: *\nDisallow: /private\n",
        )
        summary = sfs.run(client, self.args())
        self.assertFalse(summary.blocked)
        self.assertEqual(summary.written, 1)

    def test_listing_url_and_pagination(self):
        pages = {
            "p=1&": listing_json(["sfs-2000-1"], pages=2),
            "p=2&": listing_json(["sfs-2000-2"], pages=2),
        }
        client = FakeClient(pages)
        summary = sfs.run(
            client, self.args("--from", "2020-01-01", "--to", "2020-12-31")
        )
        self.assertEqual(summary.written, 2)
        listing_calls = [c for c in client.calls if "dokumentlista" in c]
        self.assertEqual(len(listing_calls), 2)
        self.assertTrue(
            listing_calls[0].startswith(
                "https://data.riksdagen.se/dokumentlista/?doktyp=sfs&utformat=json"
                "&sz=200&p=1&sort=datum&sortorder=asc"
            )
        )
        self.assertTrue(listing_calls[0].endswith("&from=2020-01-01&tom=2020-12-31"))

    def test_dok_id_with_spaces_is_quoted_in_text_url(self):
        listing = json.dumps({"dokumentlista": {"@sidor": "1", "dokument": [{
            "dok_id": "sfs-1827-60 s.1007", "beteckning": "1827:60 s.1007",
            "titel": "Kungörelse om test", "datum": "1827-06-01",
            "systemdatum": "2026-01-01 00:00:00", "organ": ""}]}}).encode()
        client = FakeClient({"dokumentlista": listing})
        summary = sfs.run(client, self.args())
        self.assertEqual(summary.failed, [])
        self.assertIn("https://data.riksdagen.se/dokument/sfs-1827-60%20s.1007.text", client.text_calls())
        self.assertTrue((self.corpus / "sfs/other/1827-60-s-1007.md").exists())
        self.assertEqual(sfs.run(client, self.args()).skipped, 1)

    def test_digitised_print_without_plain_text_fails_cleanly(self):
        client = FakeClient({
            "dokumentlista": listing_json(["sfs-1868-1"]),
            ".text": b"<dokumentstatus><dokument><html>&lt;div&gt;</html></dokument></dokumentstatus>",
        })
        summary = sfs.run(client, self.args())
        self.assertEqual(summary.failed, ["sfs-1868-1"])
        self.assertIn("no plain text", self.state()["failed"]["sfs-1868-1"])
        self.assertFalse(self.corpus.exists() and any(self.corpus.rglob("*.md")))

    def test_state_written_after_each_document(self):
        ids = ["sfs-2000-1", "sfs-2000-2"]
        client = FakeClient({"dokumentlista": listing_json(ids)})
        sfs.run(client, self.args())
        state = self.state()
        self.assertEqual(set(state["done"]), set(ids))
        self.assertEqual(state["failed"], {})
        self.assertIsNone(state["blocked"])


if __name__ == "__main__":
    unittest.main()
