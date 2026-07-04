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
- **primary-backoff-volume** — Backoff volume matches the athlete's **actual logged
  working-set counts** (from the Hevy log: 139 squat / 163 sumo / 83 bench sessions), NOT a
  flat guess, and **tapers one set at the W4 peak** (which is what he already does when the
  top goes heavy). Backoff sets (excl. the top set), W1·W2·W3·W4·W5:
  - **Low-bar Squat (D1)**: **4·4·4·3·3** — his standing 5-working-set norm.
  - **Sumo Deadlift (D4)**: **3·3·3·2·3** — his recent 4-working-set norm; drops at the heavy-single peak.
  - **Comp Bench (D1, priority)**: **4·4·4·3·3** — one more than B3 (was 3); within his
    historical 5–8 working-set capacity, and bench is the priority push.
  **Top sets are unchanged** — backoff-only. Other lifts keep their existing scheme.
  [FB 2026-06-29, revised from volume analysis 2026-07-01]

## Accessory rotation & interference

- **accessory-rotation** — Rotate accessories *mindfully* across blocks: change **only a few**
  per block, never all of them — keep continuity while giving variant exposure over time (no
  doing the identical movement for years). A "rotation" = same target muscle, different
  implement (dumbbell → cable → machine), OR more specific targeting (e.g. general back →
  rear-delt-specific). **Primaries (Big 5) never rotate** — only accessories. When you rotate,
  apply the implement-conversion step of `loads-from-logs`.
  **Expansion/shock:** beyond carry-over, each block deliberately introduces **1–2 genuinely
  new** accessory/secondary movements that expand an under-trained muscle group for novel
  stimulus — while keeping ≥1 carry-over per slot and primaries fixed. State explicitly which
  1–2 movements were added and which group each expands. [FB 2026-06-18, extended 2026-06-29]
- **secondary-rotation** — Rotate the **secondary** movement for the three barbell lifts
  (squat, bench, sumo deadlift) across blocks: **0–2 rotations per block, coach's discretion.**
  Hold a secondary when a weak point is better served by staying on it — don't rotate for its
  own sake. Distinct from `accessory-rotation` (accessories + the 1–2 new-movement expansion);
  this governs only the barbell-lift secondary slot. **Primaries never change; pull-up & dip
  secondaries are out of scope.** Draw a rotated-in secondary from the athlete's approved pools:
  - **Squat:** 3-1-0 Tempo Squat · Paused (low-bar) Squat
  - **Bench:** Spoto Bench Press · Larsen Press (No Feet) · Close Grip Bench (CGB)
  - **Deadlift:** Paused Deadlift · Romanian Deadlift (RDL) · Paused RDL

  When you rotate, apply the variant/implement load-conversion step of `loads-from-logs`. The
  Sheet colour-codes each lift's primary + secondary with one shared tint. [FB 2026-07-03]
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
- **Competition bench** — logged under the custom Hevy template **"POWER Bench Press"** (this
  IS the comp bench; resolves from "comp bench"/"competition bench"). Treat it as the Big-5
  bench lift. [FB 2026-06-18]
- **Bench secondary** — **CGB is the default secondary** for bench improvement, but it can
  **rotate** (per `accessory-rotation`) among CGB / paused bench / incline bench / similar.
  Pick the secondary that best serves the bench weak point for that block. [FB 2026-06-18]
