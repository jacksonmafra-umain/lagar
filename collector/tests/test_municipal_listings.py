"""Listing fixtures of every configured kommun, one expectation file per kommun.

Each `fixtures/municipal/<code>.json` names the trimmed listing pages saved next to it
and what parsing them must give:

    {
      "listings": {"https://.../forfattningssamling/": "1440-listing.html"},
      "count": 12,
      "sample": {"number": "...", "title": "...", "url": "https://.../x.pdf"},
      "excluded": ["Reglemente för ..."]
    }

`listings` holds every page the collector reads, followed pages (pagination) included.
`count` is the number of entries over all of them after de-duplication, `sample` one
entry that must be among them and `excluded` titles that must not be.
"""

import io
import json
import unittest
import urllib.error
from pathlib import Path

from lagar import municipal

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "municipal"
CONFIG = Path(__file__).resolve().parents[1] / "data" / "municipalities.json"


class FixtureClient:
    """Serves the saved listing pages; robots.txt is absent (404), so everything is allowed."""

    def __init__(self, pages):
        self.pages = pages

    def fetch_final(self, url, headers=None):
        if url not in self.pages:
            raise urllib.error.HTTPError(url, 404, "not a fixture", {}, io.BytesIO(b""))
        return self.pages[url], "text/html", url


def _expectations():
    return sorted(FIXTURES.glob("[0-9][0-9][0-9][0-9].json"))


class ListingFixturesTest(unittest.TestCase):
    def test_every_fixture_matches_its_config(self):
        config = municipal.load_config(CONFIG)
        for path in _expectations():
            code = path.stem
            with self.subTest(kommun=code):
                expected = json.loads(path.read_text(encoding="utf-8"))
                self.assertIn(code, config)
                kommun = config[code]
                self.assertLessEqual(set(kommun.listings), set(expected["listings"]))
                pages = {url: (FIXTURES / name).read_bytes() for url, name in expected["listings"].items()}
                fetcher = municipal.Fetcher(FixtureClient(pages))
                entries, problems = municipal.list_entries(fetcher, kommun)
                unique = {municipal.corpus_id(code, e.number): e for e in entries}
                self.assertEqual(problems, [])
                self.assertEqual(len(unique), expected["count"])
                for entry in unique.values():
                    self.assertTrue(municipal.check_host(kommun, entry.url))
                    self.assertTrue(entry.title)
                sample = expected["sample"]
                self.assertIn(
                    (sample["number"], sample["title"], sample["url"]),
                    [(e.number, e.title, e.url) for e in unique.values()],
                )
                titles = {e.title for e in unique.values()}
                for title in expected.get("excluded", []):
                    self.assertNotIn(title, titles)


if __name__ == "__main__":
    unittest.main()
