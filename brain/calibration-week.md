# Calibration Week — 2026-09-22 → 2026-09-25

> **This is not a block.** B5 closed 2026-09-18. B6 is not designed yet. This week is an
> athlete-directed **calibration week**: three sessions whose only job is to re-anchor the Big 5
> on a free bar after the Korea trip, so B6 opens on measured numbers instead of guessed ones.
>
> Delete or archive this file when B6 is written.

**Days**: Tue Sep 22 (D1), Thu Sep 24 (D2), Fri Sep 25 (D3) — athlete's own schedule.

---

## Why a calibration week exists at all

The block plan already called for this. `current-block.md` closes with: *"he lands Mon Sep 21 …
expect 2–4 rough days from eastward jet lag — **W1 is a re-entry week, write it that way**."*
The athlete arrived at the same conclusion independently and named it calibration. Same thing,
better name: B6 is a `axial-return-ladder` block whose opening rung (365 squat vs 275, 295 sumo
vs 345) depends on numbers nobody currently has.

### What the Korea log actually gave us — and didn't

Two sessions, both pulled from Hevy (`data/logs/workouts.csv`, synced 2026-09-22):

| Date | Session | Work |
|---|---|---|
| Sep 19 | "Morning workout ☀️" (65 min) | Smith bench 225×8 ×3; Smith squat 275×8 ×3; BW Pull Up 12/10/10; Rope Pushdown 60×8–10 ×3; EZ Curl 60×10 ×3 |
| Sep 20 | "Morning workout ☀️" (100 min) | Smith RDL 185×8 ×4; Smith Incline 185×8 ×4; Lat Pulldown 140×12 ×3; Hip Adduction 105×12 ×3; Machine Crunch 20×15 ×3; Hammer Curl 40×10 ×3; DB Tricep Ext 45×10 ×3 |

**Every set is Smith machine. Not one RPE was logged.** That is the whole problem:

1. **Smith loads don't transfer.** Fixed bar path, no stabilization demand, no comparability with
   any free-bar number in `data/maxes.md`. Smith squat 275×8 is not evidence he can free-squat
   275×8, in either direction.
2. **No RPE means no intensity read.** `loads-from-logs` needs actual working sets to anchor
   against; blank-RPE accessory work is fine per `accessory-rpe`, but these were *primaries*.
3. **Back-to-back days, both long**, then a 14-hour flight. Sep 20's session ran 100 minutes and
   included 4×8 loaded hinge (Smith RDL) — the movement class that was **CUT** in B5.

So: seven days off a free bar, no usable intensity data, a loaded hinge two days before a
long-haul flight. B6 cannot be designed off this. Hence three calibration sessions.

---

## D1 — Tue 2026-09-22: Squat + Bench + Pull-up

Delivered in-session (athlete was leaving for the gym; **not pushed to Hevy — no `HEVY_API_KEY`
in the session container**, he trained off the chat message).

| # | Exercise | Sets × Reps | Load | RPE | Rest |
|---|---|---|---|---|---|
| 1 | Low-bar Squat — ramp | 135×5, 185×3, 225×3 | — | ≤6 | 1:15 |
| 2 | Low-bar Squat — top | 1 × 3 | 275 | **≤7 hard cap** | 1:15 |
| 3 | Low-bar Squat — backoff | 2 × 3 | 245 | ≤7 | 1:15 |
| 4 | Comp Bench — ramp | 135×5, 185×3, 225×2 | — | ≤6 | 1:00 |
| 5 | Comp Bench — top | 1 × 3 | 245 | ≤7 | 1:15 |
| 6 | Comp Bench — backoff | 2 × 5 | 225 | ≤7 | 1:15 |
| 7 | Weighted Pull-up | 3 × 4 | BW+55 | ≤7 | 1:00 |
| 8 | Cable Pallof Press | 3 × 12 | 20 | 6 | 0:30 |

Rest times per the athlete's own rule: 1:15 primary / 1:00 secondary + accessory / 0:30 core.
Shoulder warm-up (band pull-aparts, scap push-ups) prescribed — **no cold benching** is still in
force per `active-issues.md`.

### Decisions and their reasons

- **275 squat top, not 315+.** He peaked 365×3 @6 on Sep 7 and the graded-return cap moved to
  275 on 2026-08-28. The cap **moved, it did not lift**. First free bar in 7 days, 1–2 days off a
  14 h flight — 275 is a load with three weeks of comparable history behind it, so it reads
  cleanly against them. If it moves at @6, that's the evidence for B6 opening at 365.
- **No sumo, no loaded hinge on D1.** The back took 14 hours compressed in a seat, preceded by
  4×8 Smith RDL. Sumo is the canary (`sumo-back-cap`) and needs a fresh day with its own check —
  it goes D2. Loading a hinge on D1 is the fastest route from calibration week to a flare.
- **Bench 245 @7, not 265–275.** e1RM is 293 and his trained band is 265–275, but with Smith-only
  trip data and one night of real sleep, @7 at 245 gives a clean comparable against 275×2 @8.5
  (Sep 7) without spending anything.
- **No dip on D1.** `Bench + Weighted Dip` never heavy together. Dip is coming off a BW+105 block
  high — it pairs with sumo on D2, where pressing is off the table anyway.
- **Pull-up at BW+55**, the bottom of his logged band: he did 32 bodyweight reps on Sep 19, lats
  are not fresh, and this is a movement check rather than a load check.
- **No arm work.** He ran curls and triceps on *both* Korea days. `muscle-coverage-audit` against
  the **log**, not the plan — the 2026-09-16 lesson. Sixty minutes goes to the Big 5.

### Sleep / travel context as reported
Landed back in Canada from Korea. Night of Sep 21→22: asleep ~00:00, woke ~06:30, reported as
slept well. **~6.5 h, one night.** Eastward jet lag from Korea is ~13–16 h of circadian shift;
one good night is not recovery, and the session was written with a stop rule (drop the 275, keep
the 245 backoffs) rather than a push.

---

## D2 — Thu 2026-09-24 and D3 — Fri 2026-09-25: NOT YET WRITTEN

Athlete explicitly deferred these to a later session so he could train D1 on time.

**Intended shape, to be confirmed against D1's actuals and the Sep 23 back check:**
- **D2 (Thu)**: Sumo + Weighted Dip. Sumo opens at 295 on a `fine` check, 245–275 on `tight`,
  and is pulled entirely on `sore`. Dip gets the day because pressing is otherwise absent.
- **D3 (Fri)**: the remaining coverage — secondary bench pattern, posterior cuff/scap work, and
  whatever D1 and D2 reveal is lagging.

**Do not write these without first reading the D1 actuals out of Hevy** — that is the entire
point of the week.

---

## What this week has to answer before B6 is designed

1. **Where is the squat really?** 275 @≤7 crisp → B6 opens at 365 with 405 live in W2–W3, which
   is the lift he is owed. Grindy or wandering bar path → B6 opens at 275 and the ladder starts
   a rung lower.
2. **Where is sumo really?** Held 225–295 for all of B5. B6 is the first block under
   `alternating-axial-emphasis` and **sumo's return is B6's whole job**.
3. **Do the back checks actually come in?** Four consecutive misses (Sep 8, 11, 12, 14) and one
   recovered `fine` (Sep 15). Three sessions this week, three checks owed. The 2026-09-16 memory
   entry proposes asking at the *end* of a good session rather than as a standing Saturday order
   — this week is the test of that.
