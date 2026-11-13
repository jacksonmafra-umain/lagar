"""Checks `scripts/health.py` against canned GitHub and site responses."""

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import health

NOW = datetime(2026, 11, 13, 12, 0, tzinfo=timezone.utc)
REPO = "owner/lagar"
DAILY = 'on:\n  schedule:\n    - cron: "23 5 * * *"\n'
WEEKLY = 'on:\n  schedule:\n    - cron: "17 5 * * 3" # Wednesdays\n'
AGENCY = WEEKLY + "          budget=$(( 240 * 60 ))\n"


class FakeWeb:
    """Answers `get(url, token)` from a dict of url -> (status, headers, body)."""

    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    def __call__(self, url, token=None):
        self.calls.append((url, token))
        if url not in self.pages:
            raise OSError(f"no route to {url}")
        status, headers, body = self.pages[url]
        if not isinstance(body, str):
            body = json.dumps(body)
        return status, {k.lower(): v for k, v in headers.items()}, body


def runs_url(name):
    return f"{health.API}/repos/{REPO}/actions/workflows/{name}/runs?status=success&per_page=1"


def run(created, run_id=1):
    return {"workflow_runs": [{"id": run_id, "created_at": created, "html_url": f"https://x/{run_id}"}]}


class WorkflowDirTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / ".github" / "workflows").mkdir(parents=True)

    def workflow(self, name, text):
        (self.root / ".github" / "workflows" / name).write_text(text)


class ScheduleTest(WorkflowDirTest):
    def test_daily_and_weekly_come_from_the_cron_line(self):
        self.workflow("sync-sfs.yml", DAILY)
        self.workflow("sync-so.yml", WEEKLY)
        self.workflow("site.yml", DAILY)
        self.assertEqual(health.sync_schedules(self.root), {"sync-sfs.yml": "daily", "sync-so.yml": "weekly"})

    def test_agency_budget_is_read_from_the_workflow(self):
        self.workflow("sync-agency.yml", AGENCY)
        self.assertEqual(health.agency_budget_minutes(self.root), 240)


class FreshnessTest(WorkflowDirTest):
    def test_old_runs_are_flagged_and_recent_ones_pass(self):
        self.workflow("sync-sfs.yml", DAILY)
        self.workflow("sync-eu.yml", DAILY)
        self.workflow("sync-so.yml", WEEKLY)
        self.workflow("sync-county.yml", WEEKLY)
        web = FakeWeb({
            runs_url("sync-sfs.yml"): (200, {}, run("2026-11-12T05:30:00Z")),
            runs_url("sync-eu.yml"): (200, {}, run("2026-11-09T05:30:00Z")),
            runs_url("sync-so.yml"): (200, {}, run("2026-11-05T04:41:00Z")),
            runs_url("sync-county.yml"): (200, {}, run("2026-11-02T04:41:00Z")),
        })
        findings = {f.subject: f for f in health.check_freshness(self.root, REPO, web, "t", NOW)}
        self.assertEqual(findings["sync-sfs.yml"].level, "ok")
        self.assertEqual(findings["sync-eu.yml"].level, "error")
        self.assertIn("4 days", findings["sync-eu.yml"].message)
        self.assertEqual(findings["sync-so.yml"].level, "ok")
        self.assertEqual(findings["sync-county.yml"].level, "error")

    def test_a_workflow_that_never_succeeded_is_an_error(self):
        self.workflow("sync-sfs.yml", DAILY)
        web = FakeWeb({runs_url("sync-sfs.yml"): (200, {}, {"workflow_runs": []})})
        [finding] = health.check_freshness(self.root, REPO, web, "t", NOW)
        self.assertEqual(finding.level, "error")
        self.assertIn("no successful run", finding.message)

    def test_an_api_failure_is_reported_not_raised(self):
        self.workflow("sync-sfs.yml", DAILY)
        [finding] = health.check_freshness(self.root, REPO, FakeWeb({}), "t", NOW)
        self.assertEqual(finding.level, "error")
        self.assertIn("could not read", finding.message)


class TokenTest(unittest.TestCase):
    URL = f"{health.API}/repos/{REPO}"

    def expiring(self, value):
        return FakeWeb({self.URL: (200, {"GitHub-Authentication-Token-Expiration": value}, {})})

    def test_far_expiry_passes(self):
        [f] = health.check_token(REPO, self.expiring("2027-11-12 00:00:00 UTC"), "s", NOW)
        self.assertEqual(f.level, "ok")
        self.assertIn("2027-11-12", f.message)

    def test_expiry_within_30_days_warns(self):
        [f] = health.check_token(REPO, self.expiring("2026-12-01 10:00:00 +0000"), "s", NOW)
        self.assertEqual(f.level, "warning")
        self.assertIn("17 days", f.message)

    def test_expired_token_is_an_error(self):
        web = FakeWeb({self.URL: (401, {}, {"message": "Bad credentials"})})
        [f] = health.check_token(REPO, web, "s", NOW)
        self.assertEqual(f.level, "error")

    def test_missing_token_is_an_error(self):
        [f] = health.check_token(REPO, FakeWeb({}), "", NOW)
        self.assertEqual(f.level, "error")
        self.assertIn("SYNC_TOKEN", f.message)

    def test_token_without_expiry_passes(self):
        [f] = health.check_token(REPO, FakeWeb({self.URL: (200, {}, {})}), "s", NOW)
        self.assertEqual(f.level, "ok")


class SiteTest(unittest.TestCase):
    SITE = "https://site.example"
    STATS = {"generated_at": "2026-11-12T17:18:36Z", "documents": 54835}
    PAGE = '<script src="/_vercel/insights/script.js" defer></script>'

    def web(self, page=PAGE, stats=None, script=200):
        return FakeWeb({
            f"{self.SITE}/": (200, {}, page),
            f"{self.SITE}/_vercel/insights/script.js": (script, {}, "x"),
            f"{self.SITE}/data/statistics.json": (200, {}, stats or self.STATS),
        })

    def levels(self, findings):
        return {f.subject: f.level for f in findings}

    def test_healthy_site_passes(self):
        findings = health.check_site(self.SITE, self.web(), self.STATS)
        self.assertEqual(set(self.levels(findings).values()), {"ok"})

    def test_missing_analytics_tag_or_script_is_flagged(self):
        self.assertEqual(self.levels(health.check_site(self.SITE, self.web(page="<html>"), self.STATS))["analytics"], "error")
        self.assertEqual(self.levels(health.check_site(self.SITE, self.web(script=404), self.STATS))["analytics"], "error")

    def test_stale_figures_are_flagged(self):
        old = {"generated_at": "2026-11-01T00:00:00Z", "documents": 54000}
        findings = health.check_site(self.SITE, self.web(stats=old), self.STATS)
        figures = next(f for f in findings if f.subject == "figures")
        self.assertEqual(figures.level, "warning")
        self.assertIn("54,000", figures.message)
        self.assertIn("54,835", figures.message)

    def test_site_down_is_an_error(self):
        findings = health.check_site(self.SITE, FakeWeb({}), self.STATS)
        self.assertEqual(findings[0].level, "error")
        self.assertEqual(len(findings), 1)


class RunTimeTest(WorkflowDirTest):
    def jobs(self, minutes):
        start = "2026-11-11T05:20:00Z"
        end = datetime(2026, 11, 11, 5, 20, tzinfo=timezone.utc).timestamp() + minutes * 60
        end = datetime.fromtimestamp(end, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        steps = [{"name": "Collect every series", "started_at": start, "completed_at": end}]
        return {"jobs": [{"steps": steps}]}

    def check(self, minutes):
        self.workflow("sync-agency.yml", AGENCY)
        web = FakeWeb({
            runs_url("sync-agency.yml"): (200, {}, run("2026-11-11T05:17:00Z", 7)),
            f"{health.API}/repos/{REPO}/actions/runs/7/jobs": (200, {}, self.jobs(minutes)),
        })
        [f] = health.check_run_time(self.root, REPO, web, "t")
        return f

    def test_short_run_passes(self):
        f = self.check(150)
        self.assertEqual(f.level, "ok")
        self.assertIn("150 of 240 minutes", f.message)

    def test_run_near_the_budget_warns(self):
        self.assertEqual(self.check(200).level, "warning")


class ReportTest(unittest.TestCase):
    def test_report_lists_problems_first_and_counts_them(self):
        findings = [
            health.Finding("freshness", "sync-sfs.yml", "ok", "last success 1 day ago"),
            health.Finding("token", "SYNC_TOKEN", "warning", "expires in 10 days"),
            health.Finding("site", "home", "error", "HTTP 500"),
        ]
        text = health.render(findings, NOW)
        self.assertLess(text.index("HTTP 500"), text.index("expires in 10 days"))
        self.assertLess(text.index("expires in 10 days"), text.index("last success"))
        self.assertIn("2 problems", text)
        self.assertEqual(health.problems(findings), 2)


if __name__ == "__main__":
    unittest.main()
