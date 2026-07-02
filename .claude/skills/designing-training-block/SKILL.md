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
2. **Pick a theme** for the new block tied to a specific goal or weak point. State it in one
   sentence. **Bench is the standing priority lift** (rule `big5-priority`) — bias the theme
   and structure toward bench unless the Big-5 trend shows a weaker lift; re-check from the
   e1RM trend and update the rule if the weakest lift has changed.
3. **Choose the split** (4 day default; 3-day variant noted). Show how it manages overlap per CLAUDE.md's "Managing Training Overlap" rules — explicitly call out which pairs are staggered and why.
4. **Build the weekly wave** (W1–W4 + W5 = deload or peak): top-set RPE target and rep scheme per week, per primary lift.
   - **Backoff volume** (rule `primary-backoff-volume`): program **squat (D1) and sumo (D4)
     backoff at 4 sets, flat across W1–W4** (including the peak — no taper). Top sets are
     unchanged; this is backoff-only. Other primaries keep their existing backoff scheme.
5. **Assign accessories** with weak-point chain: weak point → target → exercise → expected carryover. Offer one alternative per slot.
   - **Rotate mindfully** (rule `accessory-rotation`): carry most accessories over from the
     prior block; change only a **few** for variant exposure. A rotation = same target, new
     implement (DB→cable→machine) OR more specific targeting (general back → rear delt).
     Primaries never rotate. State explicitly which slots you rotated and why.
   - **Expansion/shock** (rule `accessory-rotation`, extended): on top of carry-over,
     deliberately introduce **1–2 genuinely new** accessory/secondary movements that expand
     an under-trained muscle group for novel stimulus. Name which 1–2 you added and the group
     each expands. Keep ≥1 carry-over per slot; primaries stay fixed.
   - **Respect day-interference** (rule `accessory-day-interference`): D1 accessories must not
     pre-fatigue D2 (Mon→Tue), and D3 accessories must not pre-fatigue D4 (Thu→Fri). D2
     accessories are unconstrained (Wed rest before D3). Call out the check for D1 and D3.
   - **Loads come from the log, not guesses** (rule `loads-from-logs`). For every accessory
     (and primaries when useful), pull the real working load:
     `python -m scripts.hevy.block_report --exercise "<name>" --recent 90` and anchor on the
     median. Never copy a planning-sheet number without checking it against the log.
   - **When you rotate to a new implement, convert the load** (rule `loads-from-logs`): look up
     the original load in the log, then **web-research the equivalent on the new implement**
     (e.g. "cable row 15 lb → machine row equivalent") and prescribe from that — don't guess.
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

## Draft mode (automated end-of-W4 next-block draft)

The scheduled routine (`scripts/review/draft_next_block.py`, fired weekly Sun 13:00
America/Toronto and gated to the **W4 Sunday** of the running block) invokes this skill in
**draft mode**. The intent: hand the athlete a reviewable *draft* of the next block during
the W5 deload, so it can be finalized before the new block starts. W5 is a deload — it
produces no design-relevant data, so W1–W4 actuals are the inputs and drafting now is correct.

Draft mode differs from a normal design run:

- **Skip Step 0 (review gate).** The block isn't complete at W4 (W5 deload remains), so there
  is no end-of-block review yet. Draft anyway, off W1–W4 actuals. The *real*
  `reviewing-block` retrospective still runs after W5, at finalization.
- **Skip Steps 7–8 (archive + overwrite).** Do **not** touch `brain/current-block.{md,json}`
  and do **not** archive. The current block is still being trained.
- **Write to the draft files instead:** `brain/next-block-draft.md` + `brain/next-block-draft.json`
  (same schema as `current-block.*`). Both get a banner at the top:
  `> ⚠️ PROVISIONAL — drafted end of W4 from W1–W4 actuals. Finalize after W5 deload + block review.`
- **Skip Step 9 (Hevy push).** A provisional draft is never pushed to Hevy.
- **Still run Steps 1–6 in full**, obeying all binding rules — including
  `primary-backoff-volume` (squat/sumo backoff volume) and the `accessory-rotation`
  expansion clause (1–2 new movements). Loads come from the freshly-synced Hevy log
  (`loads-from-logs`).

After writing the draft files, the routine renders the draft to a Google Sheet
(`scripts/sheets/export_block.py`, matching the B1–B3 layout) and notifies via Telegram with
the Sheet URL. The draft files are committed to a branch, not master.

### Finalization (after W5, athlete-driven)

1. Run `reviewing-block` for the now-complete block (the real, Hevy-grounded retrospective).
2. Reconcile the reviewed lessons against the W4 draft (and any edits the athlete made in the
   Sheet during W5).
3. Promote the draft into `brain/current-block.{md,json}`, archive the prior block (Steps 7–8),
   commit, and offer the Hevy push (Step 9).
