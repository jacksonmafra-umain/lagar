import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROMPT = ROOT / "docs/replicate/PROMPT.md"
PIN = "46a8e7d3f386bbbec82917a9725fe03220268ab5"
REPO = "github.com/jacksonmafra-umain/lagar/"

SECTIONS = [
    "How to use this prompt",
    "Phase 0: Ground rules",
    "Phase 1: Onboarding",
    "Phase 2: Legal-structure research",
    "Phase 3: Plan",
    "Phase 4: Build",
    "Reference A: Architecture contracts",
    "Reference B: Security rules",
    "Reference C: Reusing lagar",
]


def text() -> str:
    return PROMPT.read_text(encoding="utf-8")


def section(heading: str, level: str = "## ", body: str | None = None) -> str:
    """The body under a heading, up to the next heading of the same level."""
    source = text() if body is None else body
    match = re.search(rf"^{re.escape(level)}{re.escape(heading)}\s*$", source, re.MULTILINE)
    if match is None:
        raise AssertionError(f"missing heading {level}{heading}")
    rest = source[match.end():]
    end = re.search(rf"^{re.escape(level)}(?!#)", rest, re.MULTILINE)
    return rest[: end.start()] if end else rest


def lagar_links(body: str | None = None) -> list[str]:
    source = text() if body is None else body
    return [m.group(1).rstrip("/") for m in re.finditer(r"github\.com/jacksonmafra-umain/lagar/(?:blob|tree)/[0-9a-f]{40}/([^)\s#>`]+)", source)]


class ReplicatePromptTests(unittest.TestCase):
    def test_has_the_phase_and_reference_sections(self):
        headings = re.findall(r"^## (.+?)\s*$", text(), re.MULTILINE)
        self.assertEqual(SECTIONS, [h for h in headings if h in SECTIONS])
        for heading in SECTIONS:
            self.assertEqual(1, headings.count(heading), heading)

    def test_stays_under_size_budget(self):
        self.assertLess(len(PROMPT.read_bytes()), 60_000)

    def test_names_no_agent_product_or_private_spec(self):
        lowered = text().lower()
        for word in ["claude", "codex", "copilot", "gemini", "windsurf", "aider", "chatgpt", "agents.md", "lagar-implementation-prompt"]:
            self.assertNotIn(word, lowered)
        self.assertIsNone(re.search(r"\bcursor\b", lowered))

    def test_has_no_owner_specific_details(self):
        for detail in ["grundlagar.vercel.app", "VERCEL_PROJECT_ID"]:
            self.assertNotIn(detail, text())

    def test_links_are_pinned_to_one_commit(self):
        links = re.findall(rf"{re.escape(REPO)}[^)\s>`]*", text())
        self.assertTrue(links)
        for link in links:
            self.assertRegex(link, rf"^{re.escape(REPO)}(blob|tree)/{PIN}/")

    def test_linked_paths_exist(self):
        paths = lagar_links()
        self.assertTrue(paths)
        for path in paths:
            self.assertTrue((ROOT / path).exists(), path)

    def test_ground_rules_are_stated(self):
        rules = section("Phase 0: Ground rules")
        for phrase in ["robots.txt", "machine-translate", "confirm", "person's language"]:
            self.assertIn(phrase, rules)

    def test_onboarding_asks_every_question(self):
        onboarding = section("Phase 1: Onboarding")
        labels = re.findall(r"^\d+\. \*\*(.+?)\.?\*\*", onboarding, re.MULTILINE)
        self.assertEqual(["Country", "Languages", "Experience level", "Starting point", "Features", "Project identity"], labels)
        languages = onboarding[onboarding.index("**Languages"): onboarding.index("**Experience level")]
        for phrase in ["UI", "authoritative", "fallback"]:
            self.assertIn(phrase, languages)
        features = onboarding[onboarding.index("**Features"): onboarding.index("**Project identity")]
        for feature in ["collectors", "corpus", "static API", "app", "landing page", "MCP server", "sync workflows", "amendment history"]:
            self.assertIn(feature, features)
        self.assertIn("GitHub owner", onboarding[onboarding.index("**Project identity"):])

    def test_prompt_resumes_from_saved_answers(self):
        self.assertIn("docs/replication/onboarding.md", section("Phase 1: Onboarding"))
        usage = section("How to use this prompt")
        for path in ["docs/replication/onboarding.md", "docs/country-profile.md"]:
            self.assertIn(path, usage)
        self.assertIn("skip", usage.lower())

    def test_profile_contract_lists_every_key(self):
        research = section("Phase 2: Legal-structure research")
        for key in ["country", "languages", "divisions", "layers", "types", "frontmatter", "sources", "case_law_privacy", "gaps"]:
            self.assertIn(f"`{key}`", research)
        self.assertIn("docs/country-profile.md", research)
        self.assertIn("collector/data/country-profile.json", research)

    def test_prompt_allows_several_divisions_and_languages(self):
        research = section("Phase 2: Legal-structure research")
        self.assertIn("any number of levels", research)
        self.assertIn("several authoritative languages", research)
        self.assertNotIn("three scopes", text().replace("three fixed scopes", ""))

    def test_supranational_layer_is_conditional(self):
        research = section("Phase 2: Legal-structure research")
        self.assertIn("only when", research[research.index("Supranational"):])

    def test_research_ends_with_a_confirmation_gate(self):
        last = section("Phase 2: Legal-structure research").strip().split("\n\n")[-1]
        self.assertIn("approve", last)
        self.assertIn("no code", last.lower())


if __name__ == "__main__":
    unittest.main()
