"""Checks for the static landing page in landing/."""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LANDING = ROOT / "landing"

COLOR_LINE = re.compile(r"^  ([a-z-]+): '(#[0-9a-fA-F]{6})'$")
CSS_VAR = re.compile(r"--color-([a-z-]+):\s*(#[0-9a-fA-F]{6})\s*;")


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


if __name__ == "__main__":
    unittest.main()
