# Feedback Log

> Your voice correcting the program design (athlete → coach). Append-only: I add entries
> here when you give feedback, and **promote the durable ones to
> [`reference/programming-rules.md`](../reference/programming-rules.md)**, which the
> block-design skill is bound to consult. Nothing here is ever rewritten.
>
> **Levels:** `block` · `exercise` · `load` · `general`. Tag each entry with one or more.
> Log new feedback via the `feedback` skill (or just tell me).

---

### 2026-07-22 · load, exercise · Sumo Deadlift · conservative L5-S1 cap
**Feedback:** Sumo is the lift that fatigues/flares my lower back — specifically around **L5-S1**,
which is where the pain and next-day soreness show up. Want to be **really conservative** with it.
Initial instinct was to add reps and/or drop load a few pounds.
**Coach correction:** more reps is the *wrong* lever for a fatigue-prone back — injury on deadlifts
happens on the fatigued reps (brace fades, lumbar rounds), and higher reps = more cumulative load +
more reps done tired. The conservative lever is **lower load, LOW reps done fresh, every rep crisp,
stopped short.** Not "lighter for 5s."
**Grounded (Hevy, `block_report --exercise "Sumo Deadlift" --recent 30`):** most recent sumo =
**405×3 @6 (2026-07-03)**; prior = 485×1 @9 (2026-06-26). Median 445 / max 485 over the window.
Athlete recalled the last session as "345×4 @5-6" — **not in the log** (unsynced or misremembered);
the logged 405×3 @6 confirms 405 is a comfortable, already-hit load, so it anchors the ceiling.
**Imaging-consistent:** MRI (2026-07-22) shows the L5-S1 mild bulge + endplate hypertrophy +
foraminal stenosis exactly where he feels it.
**Decision (athlete-confirmed):** durable sumo band **345–405 lb, RPE cap 7, reps ≤4 & crisp,
405 = hard ceiling** while the back is a concern; hard stop on any back rounding or bar-speed drop.
Creep toward 405 only if RPE stays ≤7 **and** the next-morning back check is clean. Distinct from the
temporary injection-series axial cap (that one lifts on doctor clearance; **this one is durable** —
sumo stays the most conservatively loaded Big-5 lift until a long pain-free stretch).
**Actions:** new by-exercise rule `sumo-back-cap`; added a next-day back check on sumo days;
updated `active-issues.md` (Lower back) and `current-block.md` (B4 sumo wave dropped to the band).
→ rules: `sumo-back-cap`

### 2026-07-04 · general · RPE targets must match the Hevy ladder
**Feedback:** Hevy's RPE picker only offers **{6, 7, 7.5, 8, 8.5, 9, 9.5, 10}** — there is no
6.5, and nothing below 6. Prescribing @6.5 or @5.5 gives me a target I can't actually select
or log.
**Surfaced:** finalizing B4 — the draft carried @6.5 (calibration tops + backoffs) and @5.5
(W5 deload) targets; **53 off-ladder values** in total.
**Actions:** (1) snapped B4's `brain/current-block.json` onto the ladder — deload / sub-6 → **@6**
(the loggable floor), submax @6.5 backoff/calibration → **@6** (round *down*, keep it submax);
(2) new rule `rpe-hevy-ladder`. The deload stimulus comes from the **load drop**, not a sub-6 RPE.
Not a tooling bug — a design-knowledge gap; the rule now binds `designing-training-block`.
→ rules: `rpe-hevy-ladder`

### 2026-07-03 · block, general · secondary rotation for the three barbell lifts
**Feedback:** Rotate the *secondary* movement for squat, bench, and deadlift across blocks —
**0–2 per block, coach's discretion.** Don't force it: hold a secondary if I still need to
work the same one. This is separate from `accessory-rotation` (accessories + 1–2 new
movements); it governs only the **secondary slot for the three barbell lifts.** Pull-up and
dip are not included. Approved rotation pools:
- **Squat secondary:** 3-1-0 Tempo Squat · Paused (low-bar) Squat
- **Bench secondary:** Spoto Bench Press · Larsen Press (No Feet) · Close Grip Bench (CGB)
- **Deadlift secondary:** Paused Deadlift · Romanian Deadlift (RDL) · Paused RDL

**Also (tooling):** the Plan-tab Sheet now colour-codes each barbell lift's primary + secondary
with one shared tint (squat yellow / bench lavender / deadlift coral). These pool names were
added to `_LIFT_FAMILIES` in `export_block.py` so a rotated-in secondary still colours right.
**Interpretation confirmed with athlete:** scope = barbell-lift secondary slot only; count =
0–2/block at coach discretion.
**Action:** new rule `secondary-rotation`.
→ rules: `secondary-rotation`

### 2026-06-29 · load, general · primary backoff volume (squat + sumo)
**Feedback:** Backoff volume on primary squat and primary sumo runs low in the plan — I
always end up doing one more backoff set than programmed. Program more backoff. Top sets
are fine as-is; this is a backoff-only change.
**Verified (Hevy, B3 `data/logs/sessions/`):**
- **Low-bar Squat (D1)** — did **3 backoff sets every week W1–W4**, even when the sheet
  programmed 2 (W1 plan 2→did 3; W2 plan 3→3; W3 plan 2→3 @174.6kg; W4 plan 2→3 @183.7kg).
  i.e. 3 is the real standing volume, not 2.
- **Sumo Deadlift (D4)** — 3 backoff sets W1–W3 (W3 plan 2→did 3 @183.7kg), then **dropped
  to the planned 2 at W4 peak** (top was a 220kg @9 single — backed off the backoff when
  the top set went maximal). So: 3 backoff except when the top set is a near-max single.
**Action:** new rule `primary-backoff-volume`. **Revised 2026-07-01 from a volume analysis**
(athlete asked to ground the number in history, not lock a flat 4). Per-session working-set
counts across all logs (139 squat / 163 sumo / 83 bench sessions) show his real norm:
squat 5 working (4 backoff), sumo 4 (3 backoff), bench 5 (4 backoff; 5–8 early 2026) — each
tapering one set at the heavy peak. Final scheme (backoff, W1–W5): **squat 4·4·4·3·3, sumo
3·3·3·2·3, comp bench 4·4·4·3·3** (bench +1 vs B3 as the priority lift). Reproduces his B3
squat/sumo set counts; not a flat guess. Top sets untouched.
→ rules: `primary-backoff-volume`

### 2026-06-29 · block, general · accessory expansion / shock (1–2 new per block)
**Feedback:** I want a bit more stimulus variety — expose a couple of new accessory or
secondary movements each block to expand the muscle groups I train and give the body a
little shock. Don't switch too much: primaries stay as they are, and most accessories
carry over. Just intentionally surface 1–2 genuinely new movements per block.
**Action:** extended `accessory-rotation` — each block deliberately introduces 1–2 *new*
accessory/secondary movements targeting an under-trained group, while keeping ≥1 carry-over
per slot and primaries fixed. The design skill must name which 1–2 it added and the group
each expands.
→ rules: `accessory-rotation` (extended)

### 2026-06-18 · general, block · mindful accessory rotation
**Feedback:** When designing a new block, rotate accessories *mindfully* — don't swap every
accessory each block. Rotate only a few, so I get variant exposure over time without losing
continuity. I don't want to do the exact same movement for years. Variants can be: same
target muscle, different implement (e.g. dumbbell → cable → machine), OR more specific
targeting (e.g. "back" generally → rear delt specifically next time). Primaries (Big 5)
don't rotate — only accessories, and only some of them.
→ rules: `accessory-rotation`

### 2026-06-18 · general · accessory day-interference
**Feedback:** Accessories must not impair the *next* training day. With the schedule
D1 Mon / D2 Tue / D3 Thu / D4 Fri: D1→D2 and D3→D4 are back-to-back (no rest), so be
mindful that **D1 and D3 accessories don't compromise D2 and D4**. D2→D3 has Wednesday as a
rest day, so **D2 accessories are unconstrained** — "I don't care what accessory I do on D2."
→ rules: `accessory-day-interference`

### 2026-06-18 · load · implement-swap load conversion (web research)
**Feedback:** When rotating an accessory to a different implement, don't guess the new load.
Check the workout CSV (source of truth) for what I lifted on the original, then **web-research
the equivalent load on the new implement** so the suggestion is realistic. Example: if I did
cable row at 15 lb, look up what a 15 lb cable row converts to on the machine before
prescribing the machine version.
→ rules: `loads-from-logs` (extended with implement-conversion step)

### 2026-06-18 · general · Big-5 priority + bench focus
**Feedback:** Keep driving the Big 5 (squat, bench, deadlift, pull-up, dip). **Bench is my
current weakest — prioritize improving it.** Bias block design toward bench progress (frequency,
volume, variant selection, supporting accessories) without neglecting the others.
→ rules: `big5-priority`

### 2026-06-18 · exercise · comp bench = "POWER Bench Press" + bench secondaries
**Feedback:** "POWER Bench Press" is the custom Hevy template I made for the **competition
bench** — that's my comp bench, treat it as the Big-5 bench. **CGB is a great secondary** for
bench improvement, but I'm open to other secondaries too (paused bench, incline bench, etc.).
**Actions:** repointed exercise_map overrides comp/competition/power bench → "POWER Bench
Press" (d8218be2); block_report now labels it "Comp Bench (POWER)" and dropped the unused
stock Bench Press (Barbell) entry; recorded comp-bench + bench-secondary notes in
programming-rules.
→ rules: `big5-priority`, by-exercise (competition bench, bench secondary)

### 2026-06-18 · general · review format (Big-5 delta + status emoji)
**Feedback:** In reviews, show **how much I increased** on each Big-5 lift (vs the prior
block / baseline), and add a **status emoji** so I can see at a glance whether I'm doing
great / okay / bad on each lift.
→ rules: `review-status-emoji`

---

### 2026-06-14 · load, exercise · Weighted Dip · Block 3
**Source:** Mid-block review (coach-surfaced, athlete to confirm).
**Finding:** B3 dip top sets were planned at BW+25-40, but the Hevy log shows actuals of
BW+45×6@6 (W1) and BW+70×6@7 (W2) — i.e. he trains dips ~30-35 lb heavier than programmed,
at on-target RPE. Same root cause as the adduction case: dip loads were sheet-derived, not
log-derived. Reinforces `loads-from-logs`. Recalibrate dip prescriptions off the log (anchor
~BW+70 working, progress gradually per `accessory-progression` — though dip is a primary
Big-5 lift here, so it can progress faster than an accessory).
→ rules: `loads-from-logs`

### 2026-06-14 · load, exercise · Hip Adduction · Block 3
**Feedback:** The suggested Block 3 load dropped into the 90s; I train this at ~110–115.
Loads should be based on my actual training logs whenever possible.
**Verified (Hevy):** Hip Adduction median **115 lb**, max 125, over 10 sessions — flat at
115 for months. The 90s were wrong.
**Root cause:** Block 3's JSON was built from the planning sheet's numbers, not the Hevy
log. A tooling gap, not just a memory gap.
**Actions taken:** (1) extended `block_report.py` with `--exercise` to pull real working
loads; (2) promoted rules `loads-from-logs`; (3) corrected B3 adduction to ~115 (W3–W5).
**Note:** said "abduction" but meant adduction (the D3 machine accessory).
→ rules: `loads-from-logs`

### 2026-06-14 · general · accessory RPE convention
**Feedback:** I usually don't log RPE on accessories. Unless I explicitly enter RPE 9 or
higher, assume accessory work is around RPE 7–8.
→ rules: `accessory-rpe`

### 2026-06-14 · general · accessory progression
**Feedback:** Accessory progression should be more gradual than primary/secondary lifts.
Still progress over time, but not aggressively — no default +5 lb every week.
→ rules: `accessory-progression`
