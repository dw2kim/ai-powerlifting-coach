# AI Powerlifting Coach

Versioned strength-coaching system for Claude Code and OpenAI Codex. The repo is the
coach: its files hold the instructions, athlete context, current plan, and history.

## Layout

- `CLAUDE.md` / `AGENTS.md` — matching agent instructions: persona, standing rules,
  and the session-start protocol.
- `brain/` — state the coaching agent maintains and commits (memory, current block,
  active issues, back checks, injection series).
- `reference/` — static facts (profile, goals, protocols, how-this-works).
- `data/` — maxes, block archive, session logs.
- `.claude/skills/` — canonical repeatable procedures.
- `.agents/skills/` — Codex link to those same procedures, preventing agent-specific drift.
- `.codex/hooks.json` — Codex project automation.

## Migration status (updated 2026-08-31)

- DONE: Codex compatibility — `AGENTS.md` supplies the project instructions,
  `.agents/skills` exposes the shared procedures, and the Codex hook refreshes this
  README's generated skills table after edits.
- Migrated: memory, current-block, active-issues, profile, maxes, goals, protocols,
  how-this-works. Notion is no longer the source of anything.
- DONE: training-day discrepancy — agent orientation reads days from
  brain/current-block.md; nothing hardcoded. Block file is canonical.
- DONE (Phase 2): six procedures cover block design and amendment, session and block
  review, clinical updates, and durable athlete feedback.
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

_Auto-generated from the shared `.claude/skills/*/SKILL.md` source by `scripts/gen_skills_readme.py`. Codex accesses the same procedures through `.agents/skills`. Do not edit this table by hand — edit the SKILL.md frontmatter._

| Skill | Trigger | What it does |
|---|---|---|
| `amending-live-block` | Triggers on "regenerate block N", "can you push from week X day Y", "add/replace/remove <exercise> for this block", "the load in the app is wrong", or any mid-block plan change. | Change a block that is already running and already pushed to Hevy — add/swap/re-anchor an exercise, change loads or rest times, apply a medical restriction mid-block, or fix something wrong in the app. Corrects the routines in place with push_block --update --start, re-renders the Sheet, and pins holds so the Saturday sync can't undo it |
| `designing-training-block` | Triggers on "design the next block", "plan block N", or starting a new mesocycle. | Design a new training block — pull context from prior block + memory + maxes + goals, propose split, weekly intensity wave, exercise selection with weak-point rationale, write current-block.md + JSON, optionally push to Hevy |
| `feedback` | Triggers on "feedback:", "the program got X wrong", corrections to suggested loads/progression/exercise selection, or any note about how future blocks should be designed differently. | Log athlete feedback about program/block design and turn the durable parts into enforced rules |
| `logging-clinical-update` | Triggers on "here is the MRI/scan result", "I got the injection", "the doctor said", "I'm doing the pain clinic", a new or worsening symptom, or "what should I ask at my appointment". | Log a medical/clinical event and work out what it changes in training — a pasted MRI/ultrasound/radiology report, an injection, a doctor's instruction, a symptom change, or a clinic visit coming up. Updates active-issues.md + current-block.md + memory.md in one pass and maintains the running question list for the next visit |
| `reviewing-block` | Triggers at end of a block, on "review block N", or automatically when the next block is being designed and the prior block has no review. | End-of-block retrospective. Soft review of a completed training block grounded in the Hevy log (source of truth) — what's been done, what to continue, what to improve, action items, plus power/health notes |
| `reviewing-session` | Triggers on "review last session", a pasted set-by-set summary, or any session report. | Review a single training session — planned vs actual on weight/RPE/quality/trend, write log, update brain state, commit |

<!-- SKILLS:END -->
