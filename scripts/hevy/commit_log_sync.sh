#!/usr/bin/env bash
# Pull the Hevy log into data/logs/ and commit it straight to BRANCH.
#
# Run by .github/workflows/sync-hevy-log.yml at the end of every training day. Kept as a
# script rather than inline YAML so the commit/push logic can be tested without the Hevy
# API — point SYNC_CMD at a stub.
#
#   BRANCH     branch to commit to and push (required)
#   SYNC_CMD   the sync to run (default: python -m scripts.hevy.sync_archive)
#
# Exit 0 = committed, or nothing new to commit. Non-zero = something is wrong and NOTHING
# was committed: the sync failed, it touched files outside data/logs/, or the push was
# rejected three times running.
set -euo pipefail

: "${BRANCH:?BRANCH must be set}"
SYNC_CMD="${SYNC_CMD:-python -m scripts.hevy.sync_archive}"

summary() {  # the Actions run summary, when there is one
  echo "$1"
  if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then echo "$1" >> "$GITHUB_STEP_SUMMARY"; fi
}

for attempt in 1 2 3; do
  # Deliberately not inside an `if`: bash suspends `set -e` in conditions, so a failed sync
  # there would fall through and commit whatever it half-wrote. Here a failed API call
  # (HevyError → non-zero exit) ends the run with nothing committed.
  # Unquoted on purpose — SYNC_CMD is a command line, not a single word.
  $SYNC_CMD

  # The sync only ever writes data/logs/. Anything else changing is a bug — refuse it.
  stray="$(git status --porcelain -- . ':(exclude)data/logs')"
  if [ -n "$stray" ]; then
    echo "::error::Sync changed files outside data/logs/ — refusing to commit."
    echo "$stray"
    summary "Refused to commit: the sync changed files outside data/logs/."
    exit 2
  fi

  git add -- data/logs
  if git diff --cached --quiet; then
    summary "No new sessions in Hevy — nothing to commit."
    exit 0
  fi

  added="$(git diff --cached --name-only --diff-filter=A -- data/logs/sessions | wc -l | tr -d ' ')"
  updated="$(git diff --cached --name-only --diff-filter=M -- data/logs/sessions | wc -l | tr -d ' ')"
  git commit -q -m "chore(sync): Hevy log $(TZ=America/Toronto date +%F) — ${added} new, ${updated} updated"

  if git push -q origin "HEAD:${BRANCH}"; then
    summary "Committed: $(git log --oneline -1)"
    exit 0
  fi

  # Rejected: something else (the Saturday review) pushed first, and its tip may already
  # carry these same sessions. Rebasing two independent syncs of one API conflicts on the
  # rebuilt CSV and cursor, so drop this commit and re-sync on top of theirs instead.
  echo "Push rejected (attempt ${attempt}); re-syncing on the new tip."
  git fetch -q origin "${BRANCH}"
  git reset -q --hard "origin/${BRANCH}"
done

echo "::error::Push rejected three times — nothing committed."
summary "Push rejected three times — nothing committed."
exit 1
