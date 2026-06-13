# Powerlifting Coach

Versioned strength-coaching system. Runs in Claude Code; the repo IS the coach.

## Layout
- `CLAUDE.md` — persona, standing rules, session-start protocol. Read first, always.
- `brain/` — state Claude maintains and commits (memory, current block, active issues).
- `reference/` — static facts (profile, goals, protocols, how-this-works).
- `data/` — maxes, block archive, session logs.
- `.claude/skills/` — repeatable procedures (Phase 2).

## Migration status (updated 2026-06-10)
- Migrated: memory, current-block, active-issues, profile, maxes, goals, protocols,
  how-this-works. Notion is no longer the source of anything.
- DONE: training-day discrepancy — CLAUDE.md orientation reads days from
  brain/current-block.md; nothing hardcoded. Block file is canonical.
- DONE (Phase 2): reviewing-session + designing-training-block skills authored.
  Further skills (e.g. end-of-block retrospective) deliberately deferred until
  these two survive real use.
- DONE: CSV reconciliation — no real conflict. Both files are snapshots of the same
  Hevy export series: workouts_source_of_truth.csv (11,016 rows) is a 2026-03-15
  snapshot; rows on/before that date in the current export = exactly 11,016. The
  README's "workouts.csv (11,822)" was a ~Jun 3 snapshot. Canonical: the freshest
  export, committed as data/logs/workouts.csv (11,946 rows through 2026-06-09).
  The Drive copy of source_of_truth is now historical; don't re-import it.
- NOTE 2026-06-10: original .git was lost when the repo was zipped/transferred;
  history restarts at the baseline commit.
