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
- **`python -m scripts.sheets.export_movement_library --pools`** — the movement library:
  primaries, the three secondary pools, and the barbell accessories, each with a live verdict.
  **Run it before choosing any primary, secondary or barbell accessory.** The secondary pools
  are complete — nothing outside them is legal — and a movement marked `Blocked — medical` is
  not selectable while that holds. The accessory list is only the barbell subset; DB/cable/
  machine accessories are still chosen under `accessory-rotation`. See `secondary-rotation`.

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
   - **Backoff volume** (rule `primary-backoff-volume`): backoff sets match the athlete's
     logged working-set norm, tapering one at the W4 peak — squat **4·4·4·3·3**, sumo
     **3·3·3·2·3**, comp bench **4·4·4·3·3** (W1–W5). Top sets unchanged; backoff-only. Other
     lifts keep their existing scheme.
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
   - **Start from the outgoing block's drift report** (rule `sheet-load-sync`): run
     `python -m scripts.sheets.reconcile_loads` against the block that's ending. It sweeps every
     exercise at once and tells you which prescriptions were wrong all block — a faster and more
     complete starting point than per-exercise pulls. If it reports an exercise as unmatched,
     that's a **name-mapping bug**, not missing history: fix `OVERRIDES` in
     `scripts/hevy/exercise_map.py` before prescribing (rule `exercise-name-mapping`), or you
     will program a well-trained lift as a first exposure.
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
   - **Loads: full-precision kg, never rounded** (rule `hevy-load-fidelity`). Write every
     `weight_kg` as `scripts.hevy.units.lb_to_kg(<lb>)` — Hevy stores kg and displays lb, and a
     1-decimal kg makes a 70 lb prescription read **"70.11 lb"** in the app. Prescribe in 5 lb
     increments; that's what's on the bar and in the stack.
   - **Every exercise entry gets a `tier`** — `primary` / `secondary` / `accessory` / `core`
     (rules `hevy-rest-timers`, `rest-times-athlete-set`). It drives the pushed rest timer
     (1:15 / 1:00 / 1:00 / 0:30). Don't leave it to the name classifier, and **don't re-inflate
     the numbers** — they're the athlete's, not a coaching preference. Where a set genuinely
     wants longer (a peak / @8 test), say so **in the block prose** rather than overriding the
     field.
   - **Mark `hold` on anything deliberately prescribed below the log** (rule `sheet-load-sync`) —
     medical caps, technique work, first-exposure pattern work. Sweep the finished JSON against
     `reconcile_loads` output and confirm every under-prescribed lift is pinned; an unheld one
     gets auto-raised by the next Saturday sync, which is how a restriction quietly dies.
7. **Archive** the prior block: move `brain/current-block.md` (pre-overwrite) to `data/block-archive/<old-block-id>.md`. Same for the .json if present.
8. **Commit** atomically with a one-paragraph message explaining the block's theme.
9. **Offer to push to Hevy**:
   - Always start with `python -m scripts.hevy.push_block` (dry-run). It prints, per exercise,
     the **tier, rest timer and loads in lb** — the same units as the Sheet. **Check that
     against the Sheet before applying**: whole-pound loads, and a timer on every line
     (rules `hevy-load-fidelity`, `hevy-rest-timers`). `--json` dumps the raw kg payload.
   - On confirmation: `python -m scripts.hevy.push_block --apply`. Routines land in a folder named after the block id.
   - **Correcting a block that is already live** — that's a different job with its own traps
     (the `hold` sweep, the mapping check, the Sheet re-render). **Use the
     `amending-live-block` skill**, which owns that path end to end; don't improvise it here.
   - **⚠️ Without `--update` the push is additive** — a plain re-push POSTs again and creates a
     **second** folder plus a duplicate set of routines, which then can only be cleared by hand.
   - **No credentials in the session?** A Claude Code session usually has no `HEVY_API_KEY` (and
     no `GOOGLE_SA_JSON`). Don't claim the push happened — say so, and point at the
     `workflow_dispatch` workflows that run with the repo secrets:
     **Actions → "Push block to Hevy"** (defaults to a dry run; flip `apply` to write) and
     **Actions → "Export block to Google Sheet"**. Note that `actions_run_trigger` may 403 —
     the GitHub App token often lacks Actions-write, so the athlete clicks the button.

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
(`scripts/sheets/export_block.py`, two colour-coded tabs — "&lt;Block N&gt; Overview" + "&lt;Block N&gt; Plan") and notifies via Telegram with
the Sheet URL. The draft files are committed to a branch, not master.

### Finalization (after W5, athlete-driven)

1. Run `reviewing-block` for the now-complete block (the real, Hevy-grounded retrospective).
2. Reconcile the reviewed lessons against the W4 draft (and any edits the athlete made in the
   Sheet during W5).
3. Promote the draft into `brain/current-block.{md,json}`, archive the prior block (Steps 7–8),
   commit, and offer the Hevy push (Step 9).
