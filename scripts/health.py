"""Weekly health report for the lagar automation.

Reads the state of the other workflows and the public site, and writes a Markdown
report. The `Health` workflow (`.github/workflows/health.yml`) runs it every week and
keeps one `Health report` issue open while the report lists problems.

Checks (see "Weekly: health report" in docs/roadmap.md):

- freshness: the last successful run of each sync workflow; a daily sync older than
  3 days or a weekly one older than 10 is an error. Daily or weekly comes from the
  workflow's cron line.
- token: the expiry date GitHub reports for SYNC_TOKEN; a warning 30 days before.
- site: the landing page answers, loads the Vercel analytics script and serves the
  same figures (`data/statistics.json`) as the checkout.
- run time: the agency sync's collect step against the budget in sync-agency.yml.

Usage: python3 -I scripts/health.py [--repo OWNER/NAME] [--site URL] [--out FILE]
GITHUB_TOKEN reads the workflow runs; SYNC_TOKEN is only used to read its own expiry.
The report is written whatever it finds; the exit status is 0 unless the script itself
fails, and the number of problems goes to the `problems` step output.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

API = "https://api.github.com"
SITE = "https://grundlagar.vercel.app"
ROOT = Path(__file__).resolve().parents[1]
USER_AGENT = "lagar-health (+https://github.com/jacksonmafra-umain/lagar)"

MAX_AGE_DAYS = {"daily": 3, "weekly": 10}
TOKEN_WARN_DAYS = 30
# A run that used more than this share of the agency budget is close to leaving series out.
RUN_TIME_WARN_SHARE = 0.8
COLLECT_STEP = "Collect every series"
ANALYTICS = "/_vercel/insights/script.js"

LEVELS = ("error", "warning", "ok")


@dataclass(frozen=True)
class Finding:
    check: str
    subject: str
    level: str  # one of LEVELS
    message: str


def http_get(url: str, token: str | None = None) -> tuple[int, dict[str, str], str]:
    """GET a URL; returns the status, lower-cased headers and body, also for 4xx/5xx."""
    headers = {"User-Agent": USER_AGENT}
    if url.startswith(API):
        headers["Accept"] = "application/vnd.github+json"
        if token:
            headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, _lower(response.headers), response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as error:
        return error.code, _lower(error.headers), error.read().decode("utf-8", "replace")


def _lower(headers) -> dict[str, str]:
    return {key.lower(): value for key, value in headers.items()}


def _parse_time(value: str) -> datetime:
    """Parses GitHub's ISO times and the token header ('2027-01-01 00:00:00 UTC' or '+0000')."""
    value = value.strip().replace("Z", "+00:00").replace(" UTC", " +00:00")
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S %z"):
        try:
            return datetime.strptime(value.replace("+00:00", "+0000"), fmt)
        except ValueError:
            continue
    raise ValueError(f"unknown time format: {value!r}")


def _days(delta) -> str:
    days = int(delta.total_seconds() // 86400)
    return "1 day" if days == 1 else f"{days} days"


# --- workflow files -------------------------------------------------------------------


def sync_schedules(root: Path) -> dict[str, str]:
    """Maps each sync workflow file to 'daily' or 'weekly', from its cron day-of-week."""
    schedules = {}
    for path in sorted((root / ".github" / "workflows").glob("sync-*.yml")):
        match = re.search(r'cron:\s*"([^"]+)"', path.read_text())
        if match:
            day_of_week = match.group(1).split()[4]
            schedules[path.name] = "daily" if day_of_week == "*" else "weekly"
    return schedules


def agency_budget_minutes(root: Path) -> int:
    text = (root / ".github" / "workflows" / "sync-agency.yml").read_text()
    match = re.search(r"budget=\$\(\(\s*(\d+)\s*\*\s*60\s*\)\)", text)
    if not match:
        raise ValueError("no budget line in sync-agency.yml")
    return int(match.group(1))


def _last_success(repo, workflow, get, token):
    url = f"{API}/repos/{repo}/actions/workflows/{workflow}/runs?status=success&per_page=1"
    status, _, body = get(url, token)
    if status != 200:
        raise OSError(f"HTTP {status}")
    runs = json.loads(body).get("workflow_runs", [])
    return runs[0] if runs else None


# --- checks ---------------------------------------------------------------------------


def check_freshness(root, repo, get, token, now) -> list[Finding]:
    findings = []
    for workflow, cadence in sync_schedules(root).items():
        try:
            last = _last_success(repo, workflow, get, token)
        except (OSError, ValueError) as error:
            findings.append(Finding("freshness", workflow, "error", f"could not read its runs: {error}"))
            continue
        if last is None:
            findings.append(Finding("freshness", workflow, "error", "no successful run"))
            continue
        age = now - _parse_time(last["created_at"])
        limit = MAX_AGE_DAYS[cadence]
        level = "error" if age.total_seconds() > limit * 86400 else "ok"
        message = f"{cadence}; last success {_days(age)} ago ({last['html_url']})"
        if level == "error":
            message += f", over the {limit} day limit"
        findings.append(Finding("freshness", workflow, level, message))
    return findings


def check_token(repo, get, token, now) -> list[Finding]:
    if not token:
        return [Finding("token", "SYNC_TOKEN", "error", "SYNC_TOKEN is not set; sync pull requests fall back to the workflow token")]
    try:
        status, headers, _ = get(f"{API}/repos/{repo}", token)
    except OSError as error:
        return [Finding("token", "SYNC_TOKEN", "error", f"could not reach GitHub: {error}")]
    if status != 200:
        return [Finding("token", "SYNC_TOKEN", "error", f"GitHub answers HTTP {status}; the token is expired, revoked or lacks access")]
    expiry = headers.get("github-authentication-token-expiration")
    if not expiry:
        return [Finding("token", "SYNC_TOKEN", "ok", "valid, no expiry date reported")]
    left = _parse_time(expiry) - now
    level = "warning" if left.total_seconds() < TOKEN_WARN_DAYS * 86400 else "ok"
    return [Finding("token", "SYNC_TOKEN", level, f"expires {expiry} (in {_days(left)})")]


def check_site(site, get, local_stats) -> list[Finding]:
    try:
        status, _, page = get(f"{site}/")
    except OSError as error:
        return [Finding("site", "home", "error", f"{site} unreachable: {error}")]
    if status != 200:
        return [Finding("site", "home", "error", f"{site} answers HTTP {status}")]
    findings = [Finding("site", "home", "ok", f"{site} answers 200")]

    if ANALYTICS not in page:
        findings.append(Finding("site", "analytics", "error", "the page has no Vercel analytics script tag"))
    else:
        try:
            script_status = get(f"{site}{ANALYTICS}")[0]
        except OSError as error:
            script_status = str(error)
        level = "ok" if script_status == 200 else "error"
        findings.append(Finding("site", "analytics", level, f"{ANALYTICS} answers {script_status}"))

    try:
        stats_status, _, body = get(f"{site}/data/statistics.json")
        remote = json.loads(body) if stats_status == 200 else None
    except (OSError, ValueError):
        remote = None
    if remote is None:
        findings.append(Finding("site", "figures", "error", "data/statistics.json is missing or unreadable"))
    elif (remote.get("documents"), remote.get("generated_at")) == (local_stats.get("documents"), local_stats.get("generated_at")):
        findings.append(Finding("site", "figures", "ok", f"{remote['documents']:,} documents, same as main"))
    else:
        findings.append(Finding("site", "figures", "warning",
                                f"the site shows {remote.get('documents', 0):,} documents ({remote.get('generated_at')}); "
                                f"main has {local_stats.get('documents', 0):,} ({local_stats.get('generated_at')}); "
                                "the last Site deploy is behind"))
    return findings


def check_run_time(root, repo, get, token) -> list[Finding]:
    subject = "sync-agency.yml"
    try:
        budget = agency_budget_minutes(root)
        last = _last_success(repo, subject, get, token)
        if last is None:
            return [Finding("run time", subject, "warning", "no successful run to measure")]
        status, _, body = get(f"{API}/repos/{repo}/actions/runs/{last['id']}/jobs", token)
        if status != 200:
            raise OSError(f"HTTP {status}")
        steps = [s for job in json.loads(body)["jobs"] for s in job.get("steps", []) if s["name"] == COLLECT_STEP]
    except (OSError, ValueError, KeyError) as error:
        return [Finding("run time", subject, "error", f"could not read the last run: {error}")]
    if not steps or not steps[0].get("completed_at"):
        return [Finding("run time", subject, "warning", f"no completed '{COLLECT_STEP}' step in the last run")]
    step = steps[0]
    minutes = round((_parse_time(step["completed_at"]) - _parse_time(step["started_at"])).total_seconds() / 60)
    level = "warning" if minutes > budget * RUN_TIME_WARN_SHARE else "ok"
    return [Finding("run time", subject, level, f"collect step took {minutes} of {budget} minutes ({last['html_url']})")]


# --- report ---------------------------------------------------------------------------


def problems(findings) -> int:
    return sum(1 for f in findings if f.level != "ok")


def render(findings, now) -> str:
    count = problems(findings)
    icon = {"error": "❌", "warning": "⚠️", "ok": "✅"}
    lines = [
        "## Health report",
        "",
        f"{now:%Y-%m-%d %H:%M} UTC: {count} problem{'s' if count != 1 else ''}.",
        "",
        "| | check | subject | result |",
        "| --- | --- | --- | --- |",
    ]
    for f in sorted(findings, key=lambda f: LEVELS.index(f.level)):
        lines.append(f"| {icon[f.level]} | {f.check} | {f.subject} | {f.message.replace('|', '/')} |")
    lines += ["", "What each check means and what to do: `docs/roadmap.md`, \"Weekly: health report\" and \"When something breaks\"."]
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", "jacksonmafra-umain/lagar"))
    parser.add_argument("--site", default=SITE)
    parser.add_argument("--out", type=Path, help="write the report here (default: stdout)")
    args = parser.parse_args(argv)

    now = datetime.now(timezone.utc)
    token = os.environ.get("GITHUB_TOKEN", "")
    local_stats = json.loads((ROOT / "collector" / "data" / "statistics.json").read_text())
    findings = [
        *check_freshness(ROOT, args.repo, http_get, token, now),
        *check_run_time(ROOT, args.repo, http_get, token),
        *check_token(args.repo, http_get, os.environ.get("SYNC_TOKEN", ""), now),
        *check_site(args.site.rstrip("/"), http_get, local_stats),
    ]
    report = render(findings, now)
    if args.out:
        args.out.write_text(report)
    else:
        sys.stdout.write(report)
    if output := os.environ.get("GITHUB_OUTPUT"):
        with open(output, "a") as handle:
            handle.write(f"problems={problems(findings)}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
