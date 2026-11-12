"""Checks that the sync workflows and their shared merge script agree.

Every sync workflow regenerates the same reports, so two syncs that run in the same
week conflict on them. `.github/scripts/merge-sync-pr.sh` resolves those conflicts by
regenerating the reports; a report it does not know about stops the merge and leaves
the pull request open.
"""

import re
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"
MERGE_SCRIPT = ROOT / ".github" / "scripts" / "merge-sync-pr.sh"
RETRY_WORKFLOW = WORKFLOWS / "merge-sync-prs.yml"

# The tool that writes each shared report, as the merge script must run it.
GENERATORS = {
    "PROGRESS.md": "collector/plan.py",
    "progress.svg": "collector/plan.py",
    "README.md": "collector/plan.py",
    "collector/data/pending-integrity.json": "collector/audit.py",
    "AGENCIES.md": "collector/agencies.py",
    "collector/data/agencies-report.json": "collector/agencies.py",
    "landing/data/sources.json": "collector/agencies.py",
    "STATISTICS.md": "collector/stats.py",
    "collector/data/statistics.json": "collector/stats.py",
}


def sync_workflows():
    return sorted(WORKFLOWS.glob("sync-*.yml"))


def generated(workflow):
    match = re.search(r"^\s+GENERATED:\s*(.+)$", workflow.read_text(), re.MULTILINE)
    return match.group(1).split() if match else []


def script_reports():
    match = re.search(r'^REPORTS="([^"]+)"', MERGE_SCRIPT.read_text(), re.MULTILINE)
    return match.group(1).split()


class SyncWorkflowTest(unittest.TestCase):
    def test_every_sync_workflow_uses_the_merge_script(self):
        for workflow in sync_workflows():
            with self.subTest(workflow=workflow.name):
                self.assertIn("bash .github/scripts/merge-sync-pr.sh", workflow.read_text())

    def test_sync_pushes_go_through_the_push_script(self):
        # A raw push carries workflow changes from main, which the sync tokens may not make.
        for path in [*sync_workflows(), MERGE_SCRIPT]:
            with self.subTest(file=path.name):
                text = path.read_text()
                self.assertIn("bash .github/scripts/push-sync-branch.sh", text)
                self.assertNotRegex(text, r'git push [^\n]*HEAD:\$BRANCH')

    def test_syncs_and_their_retry_use_the_sync_token(self):
        for path in [*sync_workflows(), RETRY_WORKFLOW]:
            with self.subTest(workflow=path.name):
                text = path.read_text()
                self.assertIn("GH_TOKEN: ${{ secrets.SYNC_TOKEN || github.token }}", text)
                self.assertIn("token: ${{ secrets.SYNC_TOKEN || github.token }}", text)

    def test_reports_shared_by_syncs_are_regenerated_on_merge(self):
        counts = Counter(f for w in sync_workflows() for f in set(generated(w)))
        shared = {f for f, n in counts.items() if n > 1}
        self.assertIn("STATISTICS.md", shared)
        missing = shared - set(script_reports())
        self.assertFalse(missing, f"merge-sync-pr.sh cannot resolve conflicts in {sorted(missing)}")

    def test_merge_script_runs_the_generator_of_every_report(self):
        text = MERGE_SCRIPT.read_text()
        for report in script_reports():
            with self.subTest(report=report):
                self.assertIn(report, GENERATORS, f"no known generator for {report}")
                self.assertIn(f"python3 -I {GENERATORS[report]}", text)

    def test_failed_sync_merges_are_retried_daily(self):
        text = RETRY_WORKFLOW.read_text()
        self.assertIn("schedule:", text)
        self.assertIn("workflow_dispatch:", text)
        self.assertIn("bash .github/scripts/merge-sync-pr.sh", text)
        self.assertIn("data/", text)
        self.assertIn("-sync", text)
        # Same guarantee as the sync workflows: tests pass before anything is merged.
        self.assertIn("unittest discover -s collector/tests", text)


if __name__ == "__main__":
    unittest.main()
