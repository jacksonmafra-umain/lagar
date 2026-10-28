"""Checks that the Swedish and English string tables match the landing page."""

import json
import unittest
from html.parser import HTMLParser
from pathlib import Path

LANDING = Path(__file__).resolve().parents[1]


class Strings(HTMLParser):
    """Maps each data-i18n / data-i18n-attr key to the Swedish text in index.html."""

    def __init__(self):
        super().__init__()
        self.values = {}  # key -> list of Swedish values found in the page
        self.open = []  # stack of (tag, key or None, collected text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        for pair in filter(None, (attrs.get("data-i18n-attr") or "").split(";")):
            attr, key = pair.split(":", 1)
            self.values.setdefault(key, []).append(attrs.get(attr, ""))
        if tag not in ("meta", "link", "br", "img", "input"):
            self.open.append((tag, attrs.get("data-i18n"), []))

    def handle_endtag(self, tag):
        while self.open:
            open_tag, key, text = self.open.pop()
            if key:
                self.values.setdefault(key, []).append(" ".join("".join(text).split()))
            if self.open:
                self.open[-1][2].extend(text)
            if open_tag == tag:
                break

    def handle_data(self, data):
        if self.open:
            self.open[-1][2].append(data)


def page_strings():
    parser = Strings()
    parser.feed((LANDING / "index.html").read_text(encoding="utf-8"))
    return parser.values


def table(lang):
    return json.loads((LANDING / "i18n" / f"{lang}.json").read_text(encoding="utf-8"))


class I18nTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.page = page_strings()
        cls.sv = table("sv")
        cls.en = table("en")

    def test_tables_have_same_keys(self):
        self.assertEqual(set(self.sv), set(self.en))

    def test_every_html_key_in_tables(self):
        self.assertEqual(set(self.page) - set(self.sv), set())

    def test_no_unused_keys(self):
        self.assertEqual(set(self.sv) - set(self.page), set())

    def test_swedish_html_matches_sv_table(self):
        for key, values in self.page.items():
            for value in values:
                with self.subTest(key=key):
                    self.assertEqual(value, self.sv.get(key))

    def test_toggle_name_contains_its_visible_text(self):
        # WCAG 2.5.3: the toggle shows the other language's code
        self.assertTrue(self.sv["nav.toggle"].startswith("EN"))
        self.assertTrue(self.en["nav.toggle"].startswith("SV"))

    def test_no_empty_strings(self):
        for lang, strings in (("sv", self.sv), ("en", self.en)):
            for key, value in strings.items():
                with self.subTest(lang=lang, key=key):
                    self.assertTrue(value.strip())


if __name__ == "__main__":
    unittest.main()
