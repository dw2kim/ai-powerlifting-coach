---
name: designing-training-block
description: Design a new training block — pull context from prior block + memory + maxes + goals, propose split, weekly intensity wave, exercise selection with weak-point rationale, write current-block.md + JSON, optionally push to Hevy. Triggers on "design the next block", "plan block N", or starting a new mesocycle.
---

# Designing a training block

## Context to load

- `data/block-archive/` — the most recent archived block(s) and what came out of them
- `brain/memory.md` — retrospectives, recurring patterns
- `brain/current-block.md` — the block ending now (what worked / what didn't)
- `data/maxes.md` — reference maxes for prescriptions
- `reference/goals.md` — 3-month / 12-month targets to drive periodization
- `reference/profile.md` — weak points, preferences
- `brain/active-issues.md` — anything to work around
- `reference/programming-rules.md` — **active rules from athlete feedback. Binding.** Read
  before prescribing. Check `feedback/log.md` for any exercise-level notes too.

## Procedure

0. **Gate: ensure the prior block has a review.** Check `reviews/` for a file matching the
   block that's ending. If it's missing, **run the `reviewing-block` skill first** and write
   `reviews/<prior-block-id>.md` before designing anything new. A new block is designed off the
   prior block's lessons — don't skip the retrospective. The review (Hevy-grounded actuals +
   action items) is the primary input to step 1.

1. **Retrospect** the ending block: top hits, misses, RPE drift, injury flags. Summarize in 5
   bullets. If you just wrote the review in step 0, pull these straight from it.
2. **Pick a theme** for the new block tied to a specific goal or weak point. State it in one sentence.
3. **Choose the split** (4 day default; 3-day variant noted). Show how it manages overlap per CLAUDE.md's "Managing Training Overlap" rules — explicitly call out which pairs are staggered and why.
4. **Build the weekly wave** (W1–W4 + W5 = deload or peak): top-set RPE target and rep scheme per week, per primary lift.
5. **Assign accessories** with weak-point chain: weak point → target → exercise → expected carryover. Offer one alternative per slot.
   - **Loads come from the log, not guesses** (rule `loads-from-logs`). For every accessory
     (and primaries when useful), pull the real working load:
     `python -m scripts.hevy.block_report --exercise "<name>" --recent 90` and anchor on the
     median. Never copy a planning-sheet number without checking it against the log.
   - **Progress accessories gradually** (rule `accessory-progression`): hold 2–3 weeks, small
     bumps — not +5 lb/week.
   - **Accessory RPE** (rule `accessory-rpe`): assume 7–8; don't prescribe or expect logged RPE
     on them unless it's a 9+ situation.
6. **Write**:
   - `brain/current-block.md` — prose for humans (this is what you read on your phone)
   - `brain/current-block.json` — structured spec for `push_block.py`. Schema in `scripts/hevy/push_block.py` docstring.
7. **Archive** the prior block: move `brain/current-block.md` (pre-overwrite) to `data/block-archive/<old-block-id>.md`. Same for the .json if present.
8. **Commit** atomically with a one-paragraph message explaining the block's theme.
9. **Offer to push to Hevy**:
   - Always start with `python -m scripts.hevy.push_block` (dry-run). Show the user the routine titles and a sample payload.
   - On confirmation: `python -m scripts.hevy.push_block --apply`. Routines land in a folder named after the block id.

## First-time setup gates

Before push_block can run:
- `.env` must exist with `HEVY_API_KEY`
- `scripts/hevy/exercise_templates.json` must exist (`python -m scripts.hevy.exercise_map --bootstrap`)
- Any new exercise names must resolve — if `Resolver.resolve()` errors, add an entry to `OVERRIDES` in `scripts/hevy/exercise_map.py`.
