#!/usr/bin/env bash
# Merge the open sync pull request on $BRANCH into main. Every sync workflow ends with
# this step, once its collector tests have passed.
#
# Syncs run side by side and all regenerate the same reports, so main may have moved
# since this job started. Before each merge attempt the branch takes in main again;
# conflicts on the reports are resolved by regenerating them, any other conflict is
# left for a person. The corpus audit runs on the merged tree.
set -euo pipefail

: "${BRANCH:?}"
REPORTS="PROGRESS.md progress.svg README.md AGENCIES.md collector/data/agencies-report.json landing/data/sources.json collector/data/pending-integrity.json"

pr=$(gh pr list --head "$BRANCH" --state open --json number --jq '.[0].number // empty')
if [ -z "$pr" ]; then
  echo "No open sync pull request; nothing to merge."
  exit 0
fi

for attempt in 1 2 3 4 5; do
  git fetch -q origin main "$BRANCH"
  # The start step may have merged main into the branch without pushing it; keep that.
  if [ "$(git branch --show-current)" != "$BRANCH" ]; then
    git checkout -q -B "$BRANCH" "origin/$BRANCH"
  fi
  if ! git merge-base --is-ancestor origin/main HEAD; then
    if ! git merge -q --no-edit origin/main; then
      conflicted=$(git diff --name-only --diff-filter=U)
      for file in $conflicted; do
        case " $REPORTS " in
          *" $file "*) ;;
          *) git merge --abort
             echo "::error::#$pr conflicts with main in $file; resolve it by hand"
             exit 1 ;;
        esac
      done
      git checkout --theirs -- $conflicted
      git add -- $conflicted
      git commit -q --no-edit
    fi
  fi
  python3 -I collector/audit.py
  python3 -I collector/plan.py
  python3 -I collector/agencies.py
  git add -- $REPORTS
  if ! git diff --cached --quiet; then
    git commit -q -m "chore(sync): regenerate the reports after merging main"
  fi
  head=$(git rev-parse HEAD)
  if [ "$head" != "$(git rev-parse "origin/$BRANCH")" ]; then
    git push -q --force-with-lease="$BRANCH:$(git rev-parse "origin/$BRANCH")" origin "HEAD:$BRANCH"
  fi
  # GitHub needs a moment to compute the mergeability of a head it just got.
  for try in 1 2 3; do
    sleep 10
    if gh pr merge "$pr" --merge --match-head-commit "$head"; then
      git push origin --delete "$BRANCH" || true
      echo "Merged #$pr into main." >> "${GITHUB_STEP_SUMMARY:-/dev/null}"
      exit 0
    fi
  done
  echo "Merge attempt $attempt failed; taking in main again."
done
echo "::error::could not merge #$pr into main; it stays open for the next run"
exit 1
