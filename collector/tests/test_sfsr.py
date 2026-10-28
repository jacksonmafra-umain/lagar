import hashlib
import io
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path

from lagar import frontmatter, sfsr, writer
from lagar.http import Blocked

FIXTURES = Path(__file__).resolve().parent / "fixtures"
PAGE = (FIXTURES / "sfsr-1962-700.html").read_bytes()
URL_BB = "https://rkrattsbaser.gov.se/sfsr?bet=1962:700"
URL_RF = "https://rkrattsbaser.gov.se/sfsr?bet=1974:152"


def http_error(url, code):
    return urllib.error.HTTPError(url, code, "err", {}, io.BytesIO(b""))


def page(number, title, ikraft, entries=""):
    return (
        '<html><body><div class="search-results-content">'
        f'<div class="result-inner-box bold">SFS-nummer · {number} · <a href="/sfst">Visa fulltext</a></div>'
        f'<div class="result-inner-box"><span class="bold">{title}</span></div>'
        f'<div class="result-inner-box"><span class="bold">Ikraft:</span> {ikraft}</div>'
        f"{entries}</div></body></html>"
    ).encode()


def entry(header, **fields):
    boxes = "".join(
        f'<div class="result-inner-sub-box"><span class="bold">{k}:</span> {v}</div>'
        for k, v in fields.items()
    )
    return (
        '<div class="result-inner-sub-box-container">'
        f'<div class="result-inner-sub-box-header">{header}</div>{boxes}</div>'
    )


class FakeClient:
    def __init__(self, routes, robots=None):
        self.routes = routes
        self.robots = robots
        self.calls = []

    def get(self, url):
        self.calls.append(url)
        if url == sfsr.ROBOTS_URL:
            if self.robots is None:
                raise http_error(url, 404)
            return self.robots
        value = self.routes.get(url)
        if value is None:
            raise http_error(url, 404)
        if isinstance(value, Exception):
            raise value
        return value


def stored_meta(number, id_, type_, title):
    layer = "fundamental" if type_ == "fundamental_law" else "sfs"
    return {
        "id": id_, "title": title, "type": type_, "layer": layer, "number": number,
        "issued": "1962-12-21", "in_force": None, "repealed": None, "amended_by": [],
        "amended_through": None, "reprinted_by": [], "ministry": None, "eli": None,
        "language": "sv", "authoritative": False,
        "source": "https://data.riksdagen.se/dokument/" + id_,
        "source_sha256": "a" * 64, "fetched_at": "2026-10-27T10:00:00Z",
    }


class ParseTests(unittest.TestCase):
    def test_fixture_page(self):
        register = sfsr.parse_register(PAGE.decode("utf-8"))
        self.assertEqual(register.number, "1962:700")
        self.assertEqual(register.title, "Brottsbalk (1962:700)")
        self.assertEqual(register.in_force, "1965-01-01")
        self.assertEqual(register.fields["Departement"], "Justitiedepartementet L5")
        numbers = [a["number"] for a in register.amendments]
        self.assertEqual(numbers, ["1965:280", "1965:620", "1983:240", "2013:856", "2026:1640", "2026:1656"])
        first = register.amendments[0]
        self.assertEqual(list(first), ["number", "title", "scope", "preparatory_works", "celex", "in_force", "in_force_raw"])
        # Line breaks inside a field collapse to one space; entities are decoded.
        self.assertEqual(first["scope"], "ändr. 20 kap 4 §, 21 kap 18 § 31 kap 3 §, 33 kap 5 §, 36 kap 13 §")
        self.assertIsNone(first["title"])
        self.assertIsNone(first["in_force"])
        self.assertIsNone(first["in_force_raw"])
        transitional = register.amendments[2]
        self.assertEqual(transitional["title"], "Lag (1983:240) om ändring i brottsbalken")
        self.assertEqual((transitional["in_force"], transitional["in_force_raw"]),
                         ("1983-07-01", "1983-07-01 överg.best."))
        self.assertEqual(register.amendments[3]["celex"], "32011L0093, 32011L0093R[01")
        self.assertEqual(register.amendments[4]["in_force"], "2027-01-02")
        self.assertEqual(register.other_entries, [])

    def test_in_force_values(self):
        cases = {
            None: (None, None),
            "": (None, None),
            "1999-01-01": ("1999-01-01", "1999-01-01"),
            " 1983-07-01  överg.best.": ("1983-07-01", "1983-07-01 överg.best."),
            "2019-07-01 dock 2020-01-01 för 3 §": ("2019-07-01", "2019-07-01 dock 2020-01-01 för 3 §"),
            "den dag regeringen bestämmer": (None, "den dag regeringen bestämmer"),
            "ikrafttr. av 2010:900": (None, "ikrafttr. av 2010:900"),
            "1999-02-30": (None, "1999-02-30"),
            "1999-01-011": (None, "1999-01-011"),
        }
        for raw, want in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(sfsr.parse_in_force(raw), want)

    def test_other_entries_are_reported_not_stored(self):
        html = page("2000:1", "Lag (2000:1) om test", "2000-02-01",
                    entry("Ändring, SFS 2001:5", Omfattning="ändr. 1 §")
                    + entry("Rättelse, SFS 2001:6", Omfattning="x"))
        register = sfsr.parse_register(html.decode("utf-8"))
        self.assertEqual([a["number"] for a in register.amendments], ["2001:5"])
        self.assertEqual(register.other_entries, ["Rättelse, SFS 2001:6"])

    def test_non_register_pages_rejected(self):
        for html in ("<html><body>Sökresultat</body></html>",
                     page("2000:1", "x", "2000-01-01", entry("Ändring, SFS 2001-5"))):
            with self.subTest(html=html):
                with self.assertRaises(ValueError):
                    sfsr.parse_register(html if isinstance(html, str) else html.decode("utf-8"))

    def test_base_in_force_missing_keeps_stored_value(self):
        register = sfsr.parse_register(page("2000:1", "x", "").decode("utf-8"))
        self.assertIsNone(register.in_force)
        meta = {"in_force": "2000-02-01"}
        self.assertEqual(sfsr.apply_register(meta, register), {"in_force": "2000-02-01", "amendments": []})


class RunTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.corpus = self.tmp / "corpus"
        self.manifest = self.tmp / "sources" / "sfsr-manifest.json"
        self.state = self.tmp / "data" / "sfsr-state.json"
        self.bb = writer.write(stored_meta("1962:700", "sfs-1962-700", "act", "Brottsbalk (1962:700)"),
                               "# Brottsbalk (1962:700)\n\n**1 §** Text.\n", self.corpus)
        self.rf = writer.write(stored_meta("1974:152", "sfs-1974-152", "fundamental_law", "Regeringsformen"),
                               "# Regeringsformen\n", self.corpus)

    def args(self, *extra):
        return sfsr.parse_args([
            "--corpus", str(self.corpus), "--manifest", str(self.manifest),
            "--state", str(self.state), *extra,
        ])

    def test_writes_frontmatter_manifest_and_keeps_body(self):
        before_meta, before_body = frontmatter.load(self.bb.read_text(encoding="utf-8"))
        client = FakeClient({URL_BB: PAGE})
        report = self.tmp / "report.json"
        summary = sfsr.run(client, self.args("--number", "1962:700", "--report", str(report)))
        self.assertEqual(summary.written, ["1962:700"])
        self.assertEqual(client.calls, [sfsr.ROBOTS_URL, URL_BB])
        meta, body = frontmatter.load(self.bb.read_text(encoding="utf-8"))
        self.assertEqual(body, before_body)
        self.assertEqual(meta["in_force"], "1965-01-01")
        self.assertEqual(len(meta["amendments"]), 6)
        self.assertEqual({k: v for k, v in meta.items() if k not in ("in_force", "amendments")},
                         {k: v for k, v in before_meta.items() if k != "in_force"})
        manifest = json.loads(self.manifest.read_text(encoding="utf-8"))
        self.assertEqual(manifest["source"], "https://rkrattsbaser.gov.se")
        [item] = manifest["entries"]
        self.assertEqual(item["sha256"], hashlib.sha256(PAGE).hexdigest())
        self.assertEqual((item["number"], item["url"], item["bytes"], item["amendments"]),
                         ("1962:700", URL_BB, len(PAGE), 6))
        self.assertEqual(json.loads(report.read_text(encoding="utf-8"))["written"], ["1962:700"])

    def test_resume_skips_recorded_and_refresh_is_idempotent(self):
        sfsr.run(FakeClient({URL_BB: PAGE}), self.args("--number", "1962:700"))
        before = self.bb.read_bytes()
        client = FakeClient({URL_BB: PAGE})
        summary = sfsr.run(client, self.args("--number", "1962:700"))
        self.assertEqual((summary.skipped, client.calls), (1, [sfsr.ROBOTS_URL]))
        summary = sfsr.run(FakeClient({URL_BB: PAGE}), self.args("--number", "1962:700", "--refresh"))
        self.assertEqual(summary.unchanged, ["1962:700"])
        self.assertEqual(self.bb.read_bytes(), before)

    def test_failures_are_per_statute(self):
        client = FakeClient({URL_BB: PAGE, URL_RF: b"<html>Inga tr\xc3\xa4ffar</html>"})
        summary = sfsr.run(client, self.args("--number", "1974:152", "--number", "2000:1",
                                             "--number", "1962:700"))
        self.assertEqual(summary.failed, ["1974:152", "2000:1"])
        self.assertEqual(summary.written, ["1962:700"])
        failed = json.loads(self.state.read_text(encoding="utf-8"))["failed"]
        self.assertIn("not in the corpus", failed["2000:1"])
        # A statute missing from the corpus is not fetched at all.
        self.assertNotIn("https://rkrattsbaser.gov.se/sfsr?bet=2000:1", client.calls)

    def test_page_for_another_statute_rejected(self):
        client = FakeClient({URL_RF: PAGE})
        summary = sfsr.run(client, self.args("--number", "1974:152"))
        self.assertEqual(summary.failed, ["1974:152"])
        self.assertIsNone(frontmatter.load(self.rf.read_text(encoding="utf-8"))[0]["in_force"])

    def test_blocked_stops_and_records(self):
        client = FakeClient({URL_RF: Blocked("403 Forbidden"), URL_BB: PAGE})
        summary = sfsr.run(client, self.args("--all"))
        self.assertTrue(summary.blocked)
        self.assertEqual(client.calls, [sfsr.ROBOTS_URL, URL_BB, URL_RF])
        self.assertEqual(json.loads(self.state.read_text(encoding="utf-8"))["blocked"], "403 Forbidden")
        self.assertEqual(sfsr.main(self.args_list("--number", "1974:152"), client=client), 2)

    def args_list(self, *extra):
        return ["--corpus", str(self.corpus), "--manifest", str(self.manifest),
                "--state", str(self.state), *extra]

    def test_robots_disallow_blocks_before_any_page(self):
        client = FakeClient({URL_BB: PAGE}, robots=b"User-agent: *\nDisallow: /sfsr\n")
        summary = sfsr.run(client, self.args("--pilot"))
        self.assertTrue(summary.blocked)
        self.assertEqual(client.calls, [sfsr.ROBOTS_URL])

    def test_all_lists_corpus_statutes_in_number_order(self):
        client = FakeClient({})
        sfsr.run(client, self.args("--all"))
        self.assertEqual(client.calls[1:], [URL_BB, URL_RF])

    def test_pilot_and_arguments(self):
        self.assertEqual(sfsr.PILOT, ("1974:152", "1962:700", "1998:808"))
        self.assertEqual(self.args("--pilot").rate, 2.0)
        for bad in (["--number", "1962-700"], ["--pilot", "--rate", "0.5"], ["--pilot", "--all"], []):
            with self.subTest(bad=bad):
                with self.assertRaises(SystemExit):
                    sfsr.parse_args(bad)

    def test_sfs_rewrite_after_register_keeps_fields(self):
        sfsr.run(FakeClient({URL_BB: PAGE}), self.args("--number", "1962:700"))
        meta, _ = frontmatter.load(self.bb.read_text(encoding="utf-8"))
        fresh = stored_meta("1962:700", "sfs-1962-700", "act", "Brottsbalk (1962:700)")
        kept = writer.keep_register_fields(fresh, self.corpus)
        self.assertEqual(kept, meta)


if __name__ == "__main__":
    unittest.main()
