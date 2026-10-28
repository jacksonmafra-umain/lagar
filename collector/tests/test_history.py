import io
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from lagar import frontmatter, history, sfsr, writer

FIXTURES = Path(__file__).resolve().parent / "fixtures"
PAGE = (FIXTURES / "sfsr-1962-700.html").read_text(encoding="utf-8")


def base_meta(number, title, type_, issued, in_force=None, amendments=None):
    id_ = sfsr.doc_id(number)
    meta = {
        "id": id_, "title": title, "type": type_,
        "layer": "fundamental" if type_ == "fundamental_law" else "sfs",
        "number": number, "issued": issued, "in_force": in_force, "repealed": None,
        "amended_by": [], "amended_through": None, "reprinted_by": [], "ministry": None,
        "eli": None, "language": "sv", "authoritative": False,
        "source": "https://data.riksdagen.se/dokument/" + id_,
        "source_sha256": "a" * 64, "fetched_at": "2026-10-27T10:00:00Z",
    }
    if amendments is not None:
        meta["amendments"] = amendments
    return meta


def amendment(number, in_force=None, raw=None):
    return {"number": number, "title": None, "scope": "ändr. 1 §", "preparatory_works": None,
            "celex": None, "in_force": in_force, "in_force_raw": raw}


class HistoryTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.corpus = self.tmp / "corpus"
        register = sfsr.parse_register(PAGE)
        bb = base_meta("1962:700", "Brottsbalk (1962:700)", "act", "1962-12-21")
        writer.write(sfsr.apply_register(bb, register), "# Brottsbalk\n\nText.\n", self.corpus)
        rf = base_meta("1974:152", "Regeringsformen", "fundamental_law", "1974-02-28",
                       in_force="1975-01-01",
                       amendments=[amendment("1976:871", "1977-01-01", "1977-01-01 överg.best."),
                                   amendment("2018:1903", raw="den dag regeringen bestämmer")])
        writer.write(rf, "# Regeringsformen\n", self.corpus)
        writer.write(base_meta("2000:1", "Lag (2000:1) om test", "act", "2000-01-05"), "# T\n", self.corpus)
        self.pdf_manifest = self.tmp / "sfs-pdf-manifest.json"
        self.pdf_manifest.write_text(json.dumps({"entries": [
            {"number": "2018:1903", "published": "2018-11-30"},
            {"number": "2026:1656", "published": "2026-10-08"},
        ]}), encoding="utf-8")

    def steps(self, *numbers):
        statutes = history.load_statutes(self.corpus, numbers)
        return history.plan(statutes, history.load_published(self.pdf_manifest))

    def test_one_commit_per_statute_and_amendment_in_date_order(self):
        steps = self.steps("1974:152", "1962:700")
        self.assertEqual(len(steps), 1 + 2 + 1 + 6)
        dates = [e.when.isoformat() for e, _, _ in steps]
        self.assertEqual(dates, sorted(dates))
        subjects = [e.subject for e, _, _ in steps]
        self.assertEqual(subjects[:3], [
            "Brottsbalk (1962:700): in force",
            "Brottsbalk (1962:700): amended by SFS 1965:280",
            "Brottsbalk (1962:700): amended by SFS 1965:620",
        ])
        self.assertEqual({p for _, p, _ in steps},
                         {"corpus/sfs/acts/1962-700.md", "corpus/fundamental-laws/1974-152.md"})

    def test_date_sources_are_noted(self):
        notes = {e.subject: "\n".join(e.notes) for e, _, _ in self.steps("1974:152", "1962:700")}
        self.assertIn("Date: 1965-01-01, entry into force from the SFS register.",
                      notes["Brottsbalk (1962:700): in force"])
        self.assertIn('Date: 1983-07-01, entry into force from the SFS register (register value "1983-07-01 överg.best.").',
                      notes["Brottsbalk (1962:700): amended by SFS 1983:240"])
        self.assertIn("Date: 1965-01-01, start of the SFS year; the SFS register gives no entry into force "
                      "and no issue date is known.",
                      notes["Brottsbalk (1962:700): amended by SFS 1965:280"])
        self.assertIn("Date: 2026-10-08, publication date from the SFS PDF manifest",
                      notes["Brottsbalk (1962:700): amended by SFS 2026:1656"])
        self.assertIn('entry into force "den dag regeringen bestämmer" is not a date',
                      notes["Regeringsformen: amended by SFS 2018:1903"])

    def test_statute_without_in_force_uses_issue_date(self):
        meta = base_meta("2000:1", "Lag (2000:1) om test", "act", "2000-01-05", amendments=[amendment("2000:2")])
        events = history.events_for(meta, {})
        self.assertEqual(events[0].notes, ["Date: 2000-01-05, issue date; no entry into force is known."])
        # 1 January 2000 is before the statute's own date, so it moves to it.
        self.assertEqual(events[1].when.isoformat(), "2000-01-05")
        self.assertIn("Moved to 2000-01-05", events[1].notes[-1])

    def test_snapshots_accumulate_metadata_only(self):
        steps = self.steps("1962:700")
        _, _, first = steps[0]
        meta, body = frontmatter.load(first)
        self.assertEqual(body, "")
        self.assertEqual(meta["amendments"], [])
        self.assertIsNone(meta["amended_through"])
        self.assertEqual(meta["in_force"], "1965-01-01")
        self.assertNotIn("source_sha256", meta)
        _, _, last = steps[-1]
        meta, _ = frontmatter.load(last)
        self.assertEqual(len(meta["amendments"]), 6)
        # 2026:1656 (published 2026-10-08) comes before 2026:1640 (in force 2027-01-02),
        # but the snapshot keeps register order.
        self.assertEqual(steps[-1][0].subject, "Brottsbalk (1962:700): amended by SFS 2026:1640")
        self.assertEqual([a["number"] for a in meta["amendments"]][-2:], ["2026:1640", "2026:1656"])
        self.assertEqual(meta["amended_through"], "2026:1656")

    def test_missing_register_or_statute_fails(self):
        with self.assertRaises(ValueError):
            self.steps("2000:1")
        with self.assertRaises(ValueError):
            self.steps("1998:808")

    def test_dry_run_lists_commits(self):
        out = io.StringIO()
        code = history.main(["--corpus", str(self.corpus), "--pdf-manifest", str(self.pdf_manifest),
                             "--number", "1962:700", "--dry-run"], stdout=out)
        self.assertEqual(code, 0)
        lines = out.getvalue().splitlines()
        self.assertEqual(lines[0], "1965-01-01  corpus/sfs/acts/1962-700.md  Brottsbalk (1962:700): in force")
        self.assertEqual(lines[-1], "7 commits on history/pilot")

    def test_stream_is_deterministic_and_clamps_old_dates(self):
        steps = self.steps("1974:152", "1962:700")
        data = history.stream(steps, "history/pilot", history.DEFAULT_AUTHOR)
        self.assertEqual(data, history.stream(self.steps("1974:152", "1962:700"), "history/pilot",
                                              history.DEFAULT_AUTHOR))
        self.assertTrue(data.startswith(b"reset refs/heads/history/pilot\ncommit refs/heads/history/pilot\n"))
        self.assertEqual(data.count(b"\ncommit refs/heads/history/pilot\n"), len(steps))
        self.assertIn(b"committer lagar history <history@lagar.invalid> 0 +0000\n", data)
        self.assertIn("git cannot record the real date 1965-01-01".encode(), data)
        self.assertIn(b"committer lagar history <history@lagar.invalid> 425865600 +0000\n", data)  # 1983-07-01

    @unittest.skipUnless(shutil.which("git"), "git is not installed")
    def test_stream_imports_into_git(self):
        repo = self.tmp / "repo"
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        stream = self.tmp / "history.fi"
        code = history.main(["--corpus", str(self.corpus), "--pdf-manifest", str(self.pdf_manifest),
                             "--number", "1974:152", "--number", "1962:700", "--out", str(stream)])
        self.assertEqual(code, 0)
        with stream.open("rb") as fh:
            subprocess.run(["git", "-C", str(repo), "fast-import", "--quiet"], stdin=fh, check=True)
        count = subprocess.run(["git", "-C", str(repo), "rev-list", "--count", "history/pilot"],
                               capture_output=True, text=True, check=True).stdout.strip()
        self.assertEqual(count, "10")
        subprocess.run(["git", "-C", str(repo), "fsck", "--strict"], check=True, capture_output=True)
        shown = subprocess.run(["git", "-C", str(repo), "show", "history/pilot:corpus/sfs/acts/1962-700.md"],
                               capture_output=True, check=True).stdout.decode("utf-8")
        self.assertEqual(len(frontmatter.load(shown)[0]["amendments"]), 6)


if __name__ == "__main__":
    unittest.main()
