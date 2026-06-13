---
name: reviewing-session
description: Review a single training session — planned vs actual on weight/RPE/quality/trend, write log, update brain state, commit. Triggers on "review last session", a pasted set-by-set summary, or any session report.
---

# Reviewing a session

## Input

Either:
- **Pulled from Hevy**: run `python -m scripts.hevy.pull_latest --count 1`. Output is the most recent workout as JSON (id, title, start/end, exercises, sets). Use this when the user says "review last session" or doesn't paste numbers.
- **Pasted by the user**: free-form text. Parse it directly.

When you pull from Hevy, also run `python -m scripts.hevy.sync_archive` to keep `data/logs/` complete.

## Context to load (always)

- `brain/current-block.md` — what was prescribed for this week/day
- `brain/active-issues.md` — open restrictions
- `brain/memory.md` — patterns and recent retrospectives
- Last ~3 entries in `data/logs/sessions/` (or `data/logs/workouts.csv` if pre-sync)

## Procedure

1. **Identify** which block/week/day this is from start_time + the split in current-block.md.
2. **Parse** weights, reps, RPE, exercise notes from the session. Convert kg→lbs if needed (the user thinks in lbs).
3. **Compare** planned vs actual on four axes:
   - **Weight**: hit / under / over
   - **RPE target**: on / under (left in tank) / over (cap breach — flag per current-block standing orders)
   - **Rep quality**: notes about form / bar speed / pauses
   - **Trend**: vs the last 1–3 sessions of the same exercise
4. **Decide**: on-target / undershoot / overshoot / red-flag, and what it implies for next session.
5. **Respond** with: one-line summary, what's being updated, the concrete next-session instruction.
6. **Write back**:
   - Append a session note to `brain/memory.md` if there's a pattern worth remembering
   - Update `brain/current-block.md` if next session's load/reps change
   - Update `brain/active-issues.md` if anything flared
   - Commit with a coach-voice message ("D1 W3: squat top set @8.5 over RPE7.5 cap — pull W4 top to 440")

## Injury flags

If shoulder pain / lower-back tweak / knee sharp pain / elbow tendon pain shows up in notes, consult `reference/protocols.md` and update `brain/active-issues.md`.
