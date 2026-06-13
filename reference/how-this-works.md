# How This Works

> Operating model for the coaching system. Migrated from Notion 2026-06-10 and adapted
> to the repo: Notion databases → files in `brain/` and `data/`; "Session Log" →
> `data/logs/`. Detailed triage/injury procedures live in `reference/protocols.md` —
> this file is the map, not the territory.

## The split

- **Reference** (rarely changes): `reference/` — goals, profile, protocols, this file.
- **Living** (edited often): `brain/` — current block, active issues, memory; `data/maxes.md`.
- **Append-only**: `data/block-archive/`, `data/logs/`, retrospectives in `brain/memory.md`.

## Per-session routine

When a training session is reported:

1. Read context: goals, memory, active issues, current block, last ~3 logged sessions.
2. Parse input: weights, reps, RPE, joint/form notes.
3. Compare planned vs actual on four axes: weight, RPE target, rep quality, trend.
4. Decide: on-target / undershoot / overshoot / red-flag, and what it means for next
   session.
5. Respond: one-line summary, what's being updated, concrete next-session instruction.
6. Write back: log entry + memory/active-issues/current-block updates where needed,
   committed to git.

(Procedure codified in skill `reviewing-session`.)

## Review cadences

| Cadence | Trigger | Output |
|---|---|---|
| Daily | After each session | Brief compare + next-session adjustment |
| Weekly | Sunday (or end-of-week ping) | Volume/intensity/RPE trend, next-week flags |
| Block | End of W4 (W5 is deload — plan next block during it) | Full debrief, archive block, plan next |
| Quarterly | End of Q | Goal-pacing check vs 12-month targets |
| Yearly | End of calendar year | Lifetime goal pacing + structural changes |
| Incident | On demand (injury, travel, illness) | Incident note, active-issues update, protocol application |

## Conventions

**RPE scale** (reps-in-reserve):
RPE 10 = 0 left · 9 = 1 left · 8 = 2 left · 7 = 3 left · 6 = 4+ left (warmup territory).

**Notation**:
- `5x3@180kg RPE8` = 5 sets of 3 at 180 kg, targeting RPE 8
- `225kg x 3 @ RPE 9` = single set of 3
- `BW+40kg` = bodyweight plus 40 kg (pull-ups/dips)

**Block naming**: `YYYY-QN-BNN`, e.g. `2026-Q2-B01`.
**Session naming**: Date + day label, e.g. `2026-04-20 — D1: Squat+Bench`.

## Triage (summary — full rules in protocols.md)

Default 4 days/week. 3 days: keep all 5 primary patterns, drop accessories first.
2 days: consolidate hard, volume −30–40%. Fever/acute illness: no training, full stop.

## Injury flags

If a session mentions shoulder pain, lower-back tweak, knee sharp pain, or elbow tendon
pain: consult the matching protocol in `reference/protocols.md`, recommend
substitutions, update `brain/active-issues.md`.
