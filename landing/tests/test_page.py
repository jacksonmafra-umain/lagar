"""Checks for the static landing page in landing/."""

import re
import unittest
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
LANDING = ROOT / "landing"

COLOR_LINE = re.compile(r"^  ([a-z-]+): '(#[0-9a-fA-F]{6})'$")
CSS_VAR = re.compile(r"--color-([a-z-]+):\s*(#[0-9a-fA-F]{6})\s*;")
LAYER_LINE = re.compile(
    r"^  ([a-z-]+):\s*\{ base: '#[0-9a-fA-F]{6}', text: '(#[0-9a-fA-F]{6})', dark: '(#[0-9a-fA-F]{6})' \}",
    re.MULTILINE,
)
LAYER_VAR = re.compile(r"--layer-([a-z-]+):\s*(#[0-9a-fA-F]{6})\s*;")


def design_colors():
    """Return the `colors` and `colors-dark` maps from the DESIGN.md frontmatter."""
    blocks = {}
    current = None
    for line in (ROOT / "DESIGN.md").read_text(encoding="utf-8").splitlines():
        if line in ("colors:", "colors-dark:"):
            current = blocks.setdefault(line[:-1], {})
            continue
        if current is None:
            continue
        match = COLOR_LINE.match(line)
        if match:
            current[match.group(1)] = match.group(2).lower()
        elif not line.startswith("  "):
            current = None
    return blocks["colors"], blocks["colors-dark"]


def token_blocks():
    """Split tokens.css into the light :root block and the dark media block."""
    css = (LANDING / "css" / "tokens.css").read_text(encoding="utf-8")
    dark_start = css.index("@media (prefers-color-scheme: dark)")
    light = dict((k, v.lower()) for k, v in CSS_VAR.findall(css[:dark_start]))
    dark = dict((k, v.lower()) for k, v in CSS_VAR.findall(css[dark_start:]))
    return light, dark


class Page(HTMLParser):
    """Collects what the tests need from index.html in one pass."""

    def __init__(self):
        super().__init__()
        self.lang = None
        self.ids = set()
        self.tags = set()
        self.urls = []  # (tag, attribute, value)
        self.i18n_hrefs = {}
        self.text = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.tags.add(tag)
        if tag == "html":
            self.lang = attrs.get("lang")
        if "id" in attrs:
            self.ids.add(attrs["id"])
        for name in ("href", "src"):
            if attrs.get(name):
                self.urls.append((tag, name, attrs[name]))
        if "data-i18n" in attrs and "href" in attrs:
            self.i18n_hrefs[attrs["data-i18n"]] = attrs["href"]

    def handle_data(self, data):
        self.text.append(data)


def parse_page():
    page = Page()
    page.feed((LANDING / "index.html").read_text(encoding="utf-8"))
    page.text = " ".join(" ".join(page.text).split())
    return page


class PageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.page = parse_page()

    def test_html_lang_is_sv(self):
        self.assertEqual(self.page.lang, "sv")

    def test_required_sections_present(self):
        for id_ in ["hero", "why", "inside", "catalog", "sources", "open"]:
            self.assertIn(id_, self.page.ids)
        self.assertIn("footer", self.page.tags)

    def test_primary_cta_points_to_app(self):
        self.assertEqual(self.page.i18n_hrefs.get("hero.cta"), "/app/")

    def test_independence_note_present(self):
        self.assertIn("Oberoende projekt. Inte en myndighetstjänst.", self.page.text)

    def test_links_are_https_or_local(self):
        for tag, name, url in self.page.urls:
            with self.subTest(url=url):
                self.assertNotIn("utm_", url)
                parsed = urlparse(url)
                if parsed.scheme:
                    self.assertIn(parsed.scheme, ("https", "mailto"))
                    continue
                if url.startswith("#"):
                    self.assertIn(url[1:], self.page.ids)
                    continue
                path = url.split("#")[0].split("?")[0]
                # fonts/ and app/ are added by the build script
                if path.startswith(("/app/", "fonts/")):
                    continue
                self.assertTrue((LANDING / path.lstrip("/")).is_file(), path)

    def test_no_third_party_assets(self):
        for tag, name, url in self.page.urls:
            if tag == "a":
                continue
            with self.subTest(url=url):
                self.assertFalse(urlparse(url).netloc, f"{tag} {name} loads from another host")


class TokensTest(unittest.TestCase):
    def test_tokens_match_design_md(self):
        colors, colors_dark = design_colors()
        light, dark = token_blocks()
        self.assertTrue(light, "no light tokens")
        self.assertEqual(set(light), set(dark))
        for role, value in light.items():
            self.assertEqual(value, colors[role], role)
        for role, value in dark.items():
            self.assertEqual(value, colors_dark[role], role)

    def test_layer_tokens_match_design_md(self):
        layers = dict(
            (name, (text.lower(), dark.lower()))
            for name, text, dark in LAYER_LINE.findall((ROOT / "DESIGN.md").read_text(encoding="utf-8"))
        )
        css = (LANDING / "css" / "tokens.css").read_text(encoding="utf-8")
        dark_start = css.index("@media (prefers-color-scheme: dark)")
        light = dict((k, v.lower()) for k, v in LAYER_VAR.findall(css[:dark_start]))
        dark = dict((k, v.lower()) for k, v in LAYER_VAR.findall(css[dark_start:]))
        self.assertTrue(light, "no layer tokens")
        self.assertEqual(set(light), set(dark))
        for name in light:
            self.assertEqual(light[name], layers[name][0], name)
            self.assertEqual(dark[name], layers[name][1], name)


if __name__ == "__main__":
    unittest.main()
