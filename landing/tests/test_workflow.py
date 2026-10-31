"""Checks on the Site workflow that deploys the landing page."""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = (ROOT / ".github" / "workflows" / "site.yml").read_text(encoding="utf-8")


class WorkflowTest(unittest.TestCase):
    def test_deploy_requires_all_vercel_secrets(self):
        deploy = re.search(r"^\s+DEPLOY: (.+)$", WORKFLOW, re.MULTILINE).group(1)
        for secret in ("VERCEL_TOKEN", "VERCEL_ORG_ID", "VERCEL_PROJECT_ID"):
            self.assertIn(f"secrets.{secret} != ''", deploy)

    def test_no_web_app_build(self):
        # the landing page ships alone; the web app is not built or deployed
        self.assertNotIn("gradle", WORKFLOW)
        self.assertNotIn("setup-java", WORKFLOW)

    def test_statistics_trigger_the_workflow(self):
        self.assertEqual(WORKFLOW.count("      - collector/data/statistics.json\n"), 2)

    def test_design_md_triggers_the_workflow(self):
        # landing/tests checks tokens.css against DESIGN.md
        self.assertEqual(WORKFLOW.count("      - DESIGN.md\n"), 2)


if __name__ == "__main__":
    unittest.main()
