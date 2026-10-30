"""Listing fixtures of every configured kommun, one expectation file per kommun.

Each `fixtures/municipal/<code>.json` names the trimmed listing pages saved next to it
and what parsing them must give:

    {
      "listings": {"https://.../forfattningssamling/": "1440-listing.html"},
      "count": 12,
      "sample": {"number": "...", "title": "...", "url": "https://.../x.pdf"},
      "excluded": ["Reglemente för ..."]
    }

`count` is the number of entries over all the listings after de-duplication,
`sample` one entry that must be among them and `excluded` titles that must not be.
"""

import json
import unittest
from pathlib import Path

from lagar import municipal

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "municipal"
CONFIG = Path(__file__).resolve().parents[1] / "data" / "municipalities.json"


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
                self.assertEqual(sorted(expected["listings"]), sorted(kommun.listings))
                parse = municipal.PARSERS[kommun.strategy]
                entries, problems = [], []
                for url, name in expected["listings"].items():
                    found, bad = parse(kommun, (FIXTURES / name).read_bytes(), url)
                    entries += found
                    problems += bad
                unique = {municipal.corpus_id(code, e.number): e for e in reversed(entries)}
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
