---
name: reviewing-block
description: End-of-block retrospective. Soft review of a completed training block grounded in the Hevy log (source of truth) — what's been done, what to continue, what to improve, action items, plus power/health notes. Triggers at end of a block, on "review block N", or automatically when the next block is being designed and the prior block has no review.
---

# Reviewing a block (end-of-block retrospective)

## Where reviews live

`reviews/` at repo root. One file per block, `reviews/<block-id>.md`, indexed in
`reviews/README.md`. **One block must have exactly one review before the next block is
designed** — the `designing-training-block` skill checks for this and calls this skill if
the prior review is missing.

## Source of truth

**The Hevy training log is authoritative for what was lifted.** The Google Sheets are the
athlete's planning surface (planned loads, RPE targets, athlete notes) — useful for the
*plan* and the *subjective notes*, but never the source for actual numbers.

## Procedure

1. **Establish the block window.** Get start/end dates from `brain/current-block.md` (or the
   archived block file). If fuzzy, cluster Hevy session dates — blocks aren't tagged in the app.
2. **Pull the actuals** (source of truth):
   `python -m scripts.hevy.block_report --start <YYYY-MM-DD> --end <YYYY-MM-DD> --md`
   This emits, per Big-5 lift (+ key variants), the heaviest working set each session and the
   window's best e1RM, matched by the athlete's real template IDs. If a window seems to miss a
   lift, check whether it was logged under a new template id and add it to `LIFTS` in
   `scripts/hevy/block_report.py`.
3. **Pull the plan + subjective notes** from the block's Google Sheet (planned loads, RPE
   targets, athlete notes) and from `brain/memory.md` retrospectives.
4. **Write the review** to `reviews/<block-id>.md` with these sections:
   - **1. What's been done** — block summary + a Big-5 plan-vs-actual table with real e1RMs.
   - **2. What to continue** — what's working; keep it.
   - **3. What to improve / change** — the honest part. Name RPE-cap breaches explicitly.
   - **4. Action items** — concrete, carried into the next block. Check off ones already addressed.
   - **Coach's notes — power & health** — one short paragraph each. Tie to the Big-5 weak points
     and to `brain/active-issues.md` (shoulder).
5. **Update the index** `reviews/README.md`: add the row with window + one-line verdict + link.
6. **Append a one-line pointer** to `brain/memory.md` if the review surfaced a durable pattern.
7. **Commit** with a coach-voice message.

## Tone

Soft but honest (per CLAUDE.md). It's a review to learn from, not a scolding — but if a cap was
blown or a deload was skipped, say so plainly. Always include the WHY.
