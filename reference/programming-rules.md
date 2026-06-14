# Programming Rules

> **Active, enforced rules distilled from [`feedback/log.md`](../feedback/log.md).**
> The `designing-training-block` skill MUST read this before prescribing, and
> `reviewing-session` honors the RPE conventions. Each rule cites the feedback that
> spawned it. To change a rule, log new feedback (don't silently edit) — the log is the
> audit trail.

## Loads & progression

- **loads-from-logs** — Suggested loads come from actual Hevy working sets, not planning-sheet
  estimates or guesses. For any exercise, pull the recent working load with
  `python -m scripts.hevy.block_report --exercise "<name>" --recent <days>` and anchor the
  prescription on the **median working load**. This applies to accessories especially, but
  use the log for everything when it's available. [FB 2026-06-14]
- **accessory-progression** — Accessories progress *gradually*: hold a load for 2–3 weeks,
  then small bumps. Do **not** apply the primary/secondary "+5 lb each week" default to
  accessories. They should still trend up across blocks, just slowly. [FB 2026-06-14]

## RPE conventions

- **accessory-rpe** — Accessories usually have **no logged RPE**. Treat a blank-RPE accessory
  set as **RPE 7–8**, not as missing data — do not flag it. Only an explicitly logged **RPE 9+**
  on an accessory is a signal worth reacting to. Applies both to `reviewing-session` and to
  reading the log during block design. [FB 2026-06-14]

## By-exercise

> Anchor loads pulled from the log. Refresh with `block_report.py --exercise`.

- **Hip Adduction (Machine)** — working load ~**110–115 lb** (log median 115, max 125, 10
  sessions; flat for months). Not the 90s. [FB 2026-06-14]
