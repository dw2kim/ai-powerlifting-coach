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

<!-- SKILLS:START -->

## Skills

_Auto-generated from `.claude/skills/*/SKILL.md` by `scripts/gen_skills_readme.py` (via a PostToolUse hook). Do not edit this table by hand — edit the SKILL.md frontmatter._

| Skill | Trigger | What it does |
|---|---|---|
| `designing-training-block` | Triggers on "design the next block", "plan block N", or starting a new mesocycle. | Design a new training block — pull context from prior block + memory + maxes + goals, propose split, weekly intensity wave, exercise selection with weak-point rationale, write current-block.md + JSON, optionally push to Hevy |
| `feedback` | Triggers on "feedback:", "the program got X wrong", corrections to suggested loads/progression/exercise selection, or any note about how future blocks should be designed differently. | Log athlete feedback about program/block design and turn the durable parts into enforced rules |
| `reviewing-block` | Triggers at end of a block, on "review block N", or automatically when the next block is being designed and the prior block has no review. | End-of-block retrospective. Soft review of a completed training block grounded in the Hevy log (source of truth) — what's been done, what to continue, what to improve, action items, plus power/health notes |
| `reviewing-session` | Triggers on "review last session", a pasted set-by-set summary, or any session report. | Review a single training session — planned vs actual on weight/RPE/quality/trend, write log, update brain state, commit |

<!-- SKILLS:END -->
