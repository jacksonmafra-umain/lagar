#!/usr/bin/env bash
# Push the sync branch $BRANCH without changing any workflow file.
#
# GitHub refuses a push that creates or updates files in .github/workflows/ unless the
# token has the workflows permission, which the sync tokens are not given. A sync branch
# never means to change a workflow, but it can still differ from main in one: main may
# have changed a workflow while the sync ran, and taking in main brings that change.
#
# So the branch first takes main's workflows as they are now. If the remote branch
# still has other workflow files, updating it would change them; the branch is then
# started again from this commit instead, and its open pull request (closed when the
# branch goes) is opened again with the same title, body, labels and assignees.
#
# scripts/tests/test_push_sync_branch.py runs it against a local origin.
set -euo pipefail

: "${BRANCH:?}"
WORKFLOWS=.github/workflows

git fetch -q origin main
if ! git diff --quiet HEAD origin/main -- "$WORKFLOWS"; then
  git rm -r -q --ignore-unmatch -- "$WORKFLOWS"
  git checkout origin/main -- "$WORKFLOWS"
  git commit -q -m "chore(sync): keep main's workflows on the sync branch"
fi

if ! git ls-remote --exit-code --heads origin "$BRANCH" > /dev/null; then
  git push -q --force-with-lease="$BRANCH:" origin "HEAD:$BRANCH"
  exit 0
fi

git fetch -q origin "+refs/heads/$BRANCH:refs/remotes/origin/$BRANCH"
remote=$(git rev-parse "origin/$BRANCH")
if git diff --quiet "$remote" HEAD -- "$WORKFLOWS"; then
  git push -q --force-with-lease="$BRANCH:$remote" origin "HEAD:$BRANCH"
  exit 0
fi

pr=$(gh pr list --head "$BRANCH" --state open --json number --jq '.[0].number // empty')
meta=""
if [ -n "$pr" ]; then
  meta=$(gh pr view "$pr" --json title,body,labels,assignees)
fi
echo "::notice::$BRANCH has other workflow files than main; starting it again"
git push -q origin --delete "$BRANCH"
git push -q --force-with-lease="$BRANCH:" origin "HEAD:$BRANCH"

if [ -n "$pr" ]; then
  args=(--base main --head "$BRANCH"
    --title "$(jq -r .title <<< "$meta")"
    --body "$(jq -r .body <<< "$meta")

Started again from #$pr, whose branch had other workflow files than main.")
  while IFS= read -r label; do args+=(--label "$label"); done < <(jq -r '.labels[].name' <<< "$meta")
  while IFS= read -r login; do args+=(--assignee "$login"); done < <(jq -r '.assignees[].login' <<< "$meta")
  gh pr create "${args[@]}"
fi
