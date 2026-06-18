# Programming Rules

> **Active, enforced rules distilled from [`feedback/log.md`](../feedback/log.md).**
> The `designing-training-block` skill MUST read this before prescribing, and
> `reviewing-session` honors the RPE conventions. Each rule cites the feedback that
> spawned it. To change a rule, log new feedback (don't silently edit) — the log is the
> audit trail.

## Priorities

- **big5-priority** — Always drive the Big 5 (squat, bench, sumo deadlift, weighted pull-up,
  weighted dip) as the primary lifts. **Bench is the current weakest — bias block design toward
  bench progress** (frequency, volume, variant choice, and supporting accessories like triceps
  and upper-back) without neglecting the others. Re-check "weakest lift" each block from the
  Big-5 e1RM trend; update this rule when it changes. [FB 2026-06-18]

## Loads & progression

- **loads-from-logs** — Suggested loads come from actual Hevy working sets, not planning-sheet
  estimates or guesses. For any exercise, pull the recent working load with
  `python -m scripts.hevy.block_report --exercise "<name>" --recent <days>` and anchor the
  prescription on the **median working load**. This applies to accessories especially, but
  use the log for everything when it's available.
  **Implement-swap conversion:** when rotating an accessory to a different implement
  (dumbbell↔cable↔machine), don't guess — look up the original load in the log/workout CSV,
  then **web-research the equivalent load on the new implement** and prescribe from that.
  [FB 2026-06-14, extended 2026-06-18]
- **accessory-progression** — Accessories progress *gradually*: hold a load for 2–3 weeks,
  then small bumps. Do **not** apply the primary/secondary "+5 lb each week" default to
  accessories. They should still trend up across blocks, just slowly. [FB 2026-06-14]

## Accessory rotation & interference

- **accessory-rotation** — Rotate accessories *mindfully* across blocks: change **only a few**
  per block, never all of them — keep continuity while giving variant exposure over time (no
  doing the identical movement for years). A "rotation" = same target muscle, different
  implement (dumbbell → cable → machine), OR more specific targeting (e.g. general back →
  rear-delt-specific). **Primaries (Big 5) never rotate** — only accessories. When you rotate,
  apply the implement-conversion step of `loads-from-logs`. [FB 2026-06-18]
- **accessory-day-interference** — Accessories must not compromise the *next* training day.
  Schedule: D1 Mon · D2 Tue · D3 Thu · D4 Fri. D1→D2 and D3→D4 are back-to-back (no rest):
  **D1 accessories must not pre-fatigue D2** (esp. back work vs D2 pull-up), and **D3
  accessories must not pre-fatigue D4** (esp. lats/adductors vs D4 sumo). D2→D3 has Wednesday
  off, so **D2 accessories are unconstrained.** This extends CLAUDE.md's primary-lift overlap
  rules down to accessories. [FB 2026-06-18]

## RPE conventions

- **accessory-rpe** — Accessories usually have **no logged RPE**. Treat a blank-RPE accessory
  set as **RPE 7–8**, not as missing data — do not flag it. Only an explicitly logged **RPE 9+**
  on an accessory is a signal worth reacting to. Applies both to `reviewing-session` and to
  reading the log during block design. [FB 2026-06-14]

## Review conventions

- **review-status-emoji** — Every review (session, weekly, block) reports the Big-5 progress
  with a **status emoji** per lift so it's glanceable: 🟢 great (e1RM up / cap held / ahead of
  plan) · 🟡 okay (flat / on plan) · 🔴 needs attention (down, or RPE-cap breach). Show **how
  much each Big-5 lift increased** vs the prior block (or the block's W1 baseline) — e1RM delta
  in lb. Bench gets called out explicitly (it's the priority lift). [FB 2026-06-18]

## By-exercise

> Anchor loads pulled from the log. Refresh with `block_report.py --exercise`.

- **Hip Adduction (Machine)** — working load ~**110–115 lb** (log median 115, max 125, 10
  sessions; flat for months). Not the 90s. [FB 2026-06-14]
