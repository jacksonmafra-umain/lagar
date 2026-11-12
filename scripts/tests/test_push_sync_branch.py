"""Checks `.github/scripts/push-sync-branch.sh` against a local origin and a stub `gh`.

GitHub refuses a push that changes `.github/workflows/` unless the token has the
workflows permission, which the sync tokens do not get. The script must therefore push
a sync branch whose workflows match main's, and start the branch (and its pull request)
again when updating the remote branch would change its workflow files.
"""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / ".github" / "scripts" / "push-sync-branch.sh"
BRANCH = "data/test-sync"
WORKFLOW = ".github/workflows/site.yml"

STUB_GH = """#!/usr/bin/env bash
{ printf '%s' "$*" | tr '\\n' ' '; echo; } >> "$STUB/log"
case "$1 $2" in
  "pr list") cat "$STUB/pr" ;;
  "pr view") cat "$STUB/meta" ;;
  "pr create") echo "https://github.com/owner/repo/pull/9" ;;
esac
"""


@unittest.skipUnless(shutil.which("git") and shutil.which("jq") and shutil.which("bash"), "needs git, jq and bash")
class PushSyncBranchTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.origin = self.tmp / "origin.git"
        self.work = self.tmp / "work"
        self.stub = self.tmp / "stub"
        self.stub.mkdir()
        (self.stub / "gh").write_text(STUB_GH)
        (self.stub / "gh").chmod(0o755)
        (self.stub / "pr").write_text("")
        (self.stub / "log").write_text("")
        meta = {
            "title": "Sync test",
            "body": "Automated sync.",
            "labels": [{"name": "type: data"}, {"name": "area: corpus"}],
            "assignees": [{"login": "owner"}],
        }
        (self.stub / "meta").write_text(json.dumps(meta))
        self.git("init", "-q", "--bare", "-b", "main", str(self.origin), cwd=self.tmp)
        self.git("clone", "-q", str(self.origin), str(self.work), cwd=self.tmp)
        self.git("config", "user.name", "test")
        self.git("config", "user.email", "test@example.com")
        self.write(WORKFLOW, "version: 1\n")
        self.write("corpus/a.md", "a\n")
        self.commit("start")
        self.git("push", "-q", "origin", "HEAD:main")

    def git(self, *args, cwd=None):
        return subprocess.run(
            ["git", *args], cwd=cwd or self.work, check=True, capture_output=True, text=True
        ).stdout.strip()

    def write(self, path, text):
        target = self.work / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)

    def commit(self, message):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)

    def change_main_workflow(self, text):
        """Commit a workflow change straight to origin's main, as another merge would."""
        other = self.tmp / "other"
        self.git("clone", "-q", str(self.origin), str(other), cwd=self.tmp)
        (other / WORKFLOW).write_text(text)
        self.git("-c", "user.name=t", "-c", "user.email=t@e", "commit", "-q", "-am", "ci", cwd=other)
        self.git("push", "-q", "origin", "HEAD:main", cwd=other)
        shutil.rmtree(other)

    def push(self):
        env = dict(os.environ, BRANCH=BRANCH, STUB=str(self.stub))
        env["PATH"] = f"{self.stub}{os.pathsep}{env['PATH']}"
        subprocess.run(["bash", str(SCRIPT)], cwd=self.work, env=env, check=True, capture_output=True, text=True)

    def remote_file(self, ref, path):
        return self.git("--git-dir", str(self.origin), "show", f"{ref}:{path}", cwd=self.tmp)

    def gh_calls(self):
        return (self.stub / "log").read_text().splitlines()

    def test_new_branch_takes_mains_workflows(self):
        self.git("checkout", "-q", "-b", BRANCH)
        self.write("corpus/b.md", "b\n")
        self.commit("data")
        self.change_main_workflow("version: 2\n")
        self.push()
        self.assertEqual(self.remote_file(BRANCH, WORKFLOW), "version: 2")
        self.assertEqual(self.remote_file(BRANCH, "corpus/b.md"), "b")
        self.assertFalse([c for c in self.gh_calls() if c.startswith("pr create")])

    def test_existing_branch_with_same_workflows_is_updated(self):
        self.git("checkout", "-q", "-b", BRANCH)
        self.write("corpus/b.md", "b\n")
        self.commit("data")
        self.git("push", "-q", "origin", f"HEAD:{BRANCH}")
        self.write("corpus/c.md", "c\n")
        self.commit("more data")
        self.push()
        self.assertEqual(self.git("--git-dir", str(self.origin), "rev-parse", BRANCH, cwd=self.tmp), self.git("rev-parse", "HEAD"))
        self.assertFalse([c for c in self.gh_calls() if c.startswith("pr create")])

    def test_branch_with_other_workflows_starts_again_with_its_pull_request(self):
        self.git("checkout", "-q", "-b", BRANCH)
        self.write("corpus/b.md", "b\n")
        self.commit("data")
        self.git("push", "-q", "origin", f"HEAD:{BRANCH}")
        (self.stub / "pr").write_text("5\n")
        self.change_main_workflow("version: 2\n")
        self.git("fetch", "-q", "origin")
        self.git("merge", "-q", "--no-edit", "origin/main")
        self.push()
        self.assertEqual(self.remote_file(BRANCH, WORKFLOW), "version: 2")
        self.assertEqual(self.remote_file(BRANCH, "corpus/b.md"), "b")
        created = [c for c in self.gh_calls() if c.startswith("pr create")]
        self.assertEqual(len(created), 1)
        for part in ("--title Sync test", "--label type: data", "--label area: corpus", "--assignee owner", "#5"):
            self.assertIn(part, created[0])


if __name__ == "__main__":
    unittest.main()
