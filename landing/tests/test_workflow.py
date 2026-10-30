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

    def test_production_waits_for_the_pages_run_of_the_same_commit(self):
        # the web app reads the API from Pages; deploying it first serves a new app against the old API
        wait = WORKFLOW.index("name: Wait for the API deploy")
        self.assertLess(wait, WORKFLOW.index("name: Deploy production"))
        step = WORKFLOW[wait:WORKFLOW.index("name: Deploy production")]
        self.assertIn("--workflow pages.yml", step)
        self.assertIn("--commit", step)
        self.assertIn("gh run watch", step)
        self.assertIn("actions: read", WORKFLOW)

    def test_design_md_triggers_the_workflow(self):
        # landing/tests checks tokens.css against DESIGN.md
        self.assertEqual(WORKFLOW.count("      - DESIGN.md\n"), 2)


if __name__ == "__main__":
    unittest.main()
