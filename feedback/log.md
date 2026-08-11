# Feedback Log

> Your voice correcting the program design (athlete → coach). Append-only: I add entries
> here when you give feedback, and **promote the durable ones to
> [`reference/programming-rules.md`](../reference/programming-rules.md)**, which the
> block-design skill is bound to consult. Nothing here is ever rewritten.
>
> **Levels:** `block` · `exercise` · `load` · `general`. Tag each entry with one or more.
> Log new feedback via the `feedback` skill (or just tell me).

---

### 2026-08-11 · load, general · Hevy push — load fidelity + rest timers · Block 5
**Feedback (2 parts):** (1) *"For weight load, please match with the google sheet. I don't want
the two decimal points for the load — you put 70.11 lb for pullup on day 2 week 1, it should be
just 70."* (2) *"Please put the rest time. Rule: primary movement 1 min 15 sec · secondary or
accessories 1 min · core/abs 30 seconds."*

**Both verified — he's right on (1), and (2) was simply never being sent.**

**Root cause of the 70.11 — a unit bug, in two layers.** Hevy stores every set in **kg** and
converts for display, so what he sees in the app is a round-trip, and the round-trip was lossy:
- The block JSON stored `weight_kg` **rounded to 1 decimal**. 70 lb went in as `31.8`, and
  31.8 kg comes back out as **70.107 lb** → the app renders "70.11".
- Hevy's conversion factor is **2.20462**, not the 2.2046226218 this repo used. Confirmed
  against his own log: a 70 lb pull-up *he* entered is stored as `31.75150366049478`, which is
  `70 / 2.20462` to the last digit. Using the "correct" constant would still have been ~0.0001
  lb off, and `reconcile_loads` was re-introducing the 1-decimal rounding every Saturday.

The Sheet was never wrong — `export_block` snaps to the 5 lb grid on display, so the Sheet said
70 while the app said 70.11. Same underlying number, two different amounts of honesty about it.

**Actions taken:**
1. **`scripts/hevy/units.py` (new)** — lb↔kg on Hevy's own factor, at full precision, plus
   `normalize_kg()`, which re-snaps any load to a real 0.5 lb increment before it goes over the
   wire. Defensive: a stale or hand-edited kg value can no longer leak decimals into the app.
2. **`push_block`** now normalizes every set's weight on the way out, and the **dry run prints
   loads in lb** (with the tier and rest timer per exercise) so the push is checkable against
   the Sheet before it's applied. `--json` still dumps the raw payload.
3. **`reconcile_loads`** writes full-precision kg instead of `round(lb / KG_TO_LBS, 1)` — the
   weekly sync can't put the decimals back mid-block.
4. **`scripts/hevy/rest_times.py` (new)** — the rest policy above, resolved from an explicit
   **`tier`** on each exercise entry (`primary`/`secondary`/`accessory`/`core`), with a name
   classifier only as a fallback so a hand-added movement can't push with a blank timer.
5. **`brain/current-block.json` rewritten** — all **382 sets** across all 20 B5 routines
   re-stored at exact loads, and a `tier` added to all 130 exercise entries.
   **Verified: every set now displays as a whole pound in the app and matches the Sheet string
   exactly; every exercise carries a timer.** Previously: 0 exercises had a rest timer at all.

**Caught while in there (unrelated to the feedback, flagged to the athlete):** **Leg Press** was
prescribed 315–365 against a 585 log anchor — deliberately, for the medical ROM rule — but was
**not marked `hold`**, so Saturday's sync would have auto-raised it to 540→630 and silently
undone a medical restriction. This is the exact case the `hold` clause was added for after the
Back Extension catch on 2026-08-07, and it was missed on the *same* block. Held now.
Also noted: **Hip Thrust is not a first exposure** — it's logged under "Hip Thrust (Barbell)"
(2023, up to 275) and "Hip Thrust (Smith Machine)" (2026-05-26, 225), so the block's
"0 logged sessions → empty bar in W1" premise is a name-mapping miss (`exercise-name-mapping`),
not a real gap. Left as-is pending a coaching call.
→ rules: `hevy-load-fidelity`, `hevy-rest-timers` (both new); reinforces `sheet-load-sync`
(the `hold` clause) and `exercise-name-mapping`

### 2026-08-07 · block, general, exercise · accessory balance + muscle coverage · Block 5
**Feedback (5 parts):** (1) D1 is leg- and tricep-heavy, and has too many accessories — drop
one. (2) D3 is too thin. (3) Every day should carry at least one abs/core accessory.
(4) *"Are we targeting all the primary muscles across D1–D4?"* (5) Balance accessories
between D1 and D2 to cover all primary muscles — noting the rest days (Wed between D2/D3,
weekend between D4/D1).

**Coach's audit (the answer to #4): no, we weren't.** Running the coverage check across all
four days exposed three genuine holes and one lopsided day:
- **Lateral delts** — nothing trained them. Presses cover front delts; face pull + reverse
  pec deck cover rear. The lateral head had zero direct work.
- **Biceps** — Concentration Curl had been cut for the window, leaving no direct biceps work.
  Pull-ups and rows don't cover it.
- **Core** — existed on D2 only.
- **D1 was carrying 4 accessories (2 legs + 2 triceps) while D3 carried 3.** Triceps were
  over-served (pushdown + skullcrusher + dip + three bench variants); D3 was the thinnest day
  in the block.
- **Calves: still uncovered, deliberately.** Zero logged history, no Big-5 carryover; not
  worth a slot during a medical window. Named here so it's a decision, not an oversight.

**Verified (Hevy) before prescribing** (`loads-from-logs`): Lateral Raise (Dumbbell) median
**40**, max 50, 68 sessions · Concentration Curl median **38**, max 45, 93 sessions.
Lateral raise prescribed at **30–35, deliberately below the log median** — the 2026-07-28 MRI
shows subacromial bursitis and 60–120° abduction is exactly this movement's arc. Capped at
shoulder height, high rep. A load anchored on the log would have been wrong here; the injury
overrides the median, and that's the one case where `loads-from-logs` yields.

**Actions taken:** D1 → 3 accessories (dropped Skullcrusher for triceps redundancy, moved Hip
Thrust to D3, added Side Plank). D2 gained Lateral Raise. D3 gained Hip Thrust + Dead Bug
(3 → 5 accessories). D4 gained Concentration Curl + Bird Dog. Core is now on all four days as
**four distinct patterns** — anti-lateral-flexion (D1) / anti-rotation (D2) / anti-extension
(D3) / spine-neutral endurance (D4) — rather than the same movement repeated.

**Note on D1↔D2 balance (#5):** they can't be equalized by accessory *count*, and shouldn't
be. D1 carries two primary lifts (9 primary sets) vs D2's one (4). At 3 vs 5 accessories the
two days land at ~18 vs ~19 total working sets — balanced by **volume**, which is what
actually costs recovery. Also, D1→D2 is back-to-back into pull-up day, so D1 structurally
can't hold back or biceps work; that constrains what balance is even possible.
→ rules: `core-every-day`, `muscle-coverage-audit`, `loads-from-logs`

---

### 2026-08-07 (evening) · block, load, general · doctor orders 4 weeks off heavy — B5 axial work rewritten light
**Event (athlete, after the pain-clinic visit):** got the lower-back injection — 4–5 sites,
described as a **"freezing" injection** to loosen the muscle. **No shoulder injection**; the doctor
palpated it and said it's okay. **The doctor was shocked he's still lifting heavy and recommended
stopping heavy lifting for 4 weeks.** Athlete: *"He recommended completely stopping, but I kinda
don't agree. I still need to do light lifting — when I got injured with my actual powerlifting
coach we still did very light lifting and it helped heal the area."* Asked for the coach's opinion
before any change.
**Coach's answer — agreed on the principle, sided with the doctor on the decision.** Graded loading
does beat rest for low back pain; complete rest would be the wrong prescription, so his instinct is
sound. But three things he hadn't weighed: (1) **they're probably not disagreeing** — "heavy" to a
clinician who just learned about 465 lb squats means the 465, not a 185 lb technique squat, so the
fix is to *ask him literally* on 08-14, not to overrule him; (2) **he was shocked, meaning he didn't
know until now** — every plan since 07-03 was built without that fact, so this is a considered
response to new information, which makes it weightier not lighter; (3) **complying costs almost
nothing** — squat was already capped and flat in B4, sumo already demoted by the athlete's own call,
and bench/pull-up/dip don't load the back, so the real cost is four weeks of light squats he'd
largely conceded already.
**Pushed back on him directly:** his self-defined "light" has a documented failure rate — B4 W1 sumo
planned 345 → pulled **425**; squat backoffs hit **@8.5** under a cap written to stop exactly that.
He follows a number on a page; he does not generate one in the moment. So the light work is
prescribed numerically, not as a vibe.
**Corrected the injection record:** "freezing" = **local anesthetic**, 4–5 sites → reads as a
**trigger-point injection** treating myofascial pain, not the disc. This file had called the series
**corticosteroid** since 2026-07-06 and that may have been wrong throughout — flagged for him to
confirm the agent. Also corrected his mechanism story (muscle relaxation doesn't meaningfully
decompress a disc; trigger-point injections break a pain–spasm cycle). **Training conclusion
unchanged and stronger** — anesthetic numbs harder and faster than steroid dulls, so
`masked-pain-load-cap` binds *more*.
**Changes to B5** (athlete approved "write them now at the conservative end"): squat 435–465 @7.5 →
**185–245 ×5 @6 ×3**; sumo 345–365 @7 → **185–225 ×3 @6 ×3**; **Paused RDL and Paused Low-bar Squat
CUT** for the window; Weighted Back Extension moved D4 → D2 and held at **bodyweight through W2**
(the trigger points are in those exact muscles); **bench/pull-up/dip untouched** — no shoulder
injection means `masked-pain-load-cap` doesn't bind them. Flagged that the **bench arch is lumbar
extension under load** and to moderate the arch before the weight. Also flagged that a palpation
("he touched it and said it's okay") is **not** a clearance and doesn't override the 07-28 MRI.
**Deliberate rule break:** `primary-backoff-volume` no longer holds for B5 squat/sumo — a medical
restriction outranks a volume rule. Recorded as `clinical-override` so it isn't read as drift.
**Follow-up same evening — athlete negotiated the numbers.** Three requests + two answers:
- **"225 lb minimum for squat and sumo — I'll be depressed with 185, it's too light."** *Granted,
  with a trade.* 225 is ~48% of his 465 and ~46% of his 485 pull — genuinely light either way, and
  adherence is a real variable: a plan he finds demoralising is a plan he cheats. But it's given as
  a **flat load with no weekly ramp**, so the ceiling *drops* from the planned 245. Higher floor,
  lower ceiling, zero creep vector. Framed that way to him explicitly.
- **"Can we do the dumbbell RDL? Just thinking out loud."** *Declined.* He already hinges on D4
  (light sumo); a second loaded hinge on D2 is precisely what was removed. Offered the thing he
  actually wants instead: **Seated Leg Curl** (48 logged sessions, median 115) — posterior chain
  with zero spinal loading. Concentration Curl dropped to make room; pull-ups carry the biceps.
- **"Can we make more reps since it's light weight?"** *Declined — second time this suggestion has
  come up and been declined* (first was sumo, 2026-07-22). Backs fail on the **fatigued** reps:
  brace fades and the lumbar rounds at the end of a long set no matter how light the bar. The lever
  is **load and SETS, never reps.** Compromise that gives him the volume he's after: squat gets a
  **4th set** of the same crisp fives, every set started fresh. Sumo stays 3×3 — it's the lift that
  flares his back, and a deadlift set costs more lumbar exposure per rep than a squat set.
- **"Can we strive even more on bench/pull-up/dip since I'll have more energy?"** *Declined.* The
  strive plan is already aggressive; recovery isn't one pool you reallocate; and the limiter on
  bench and dip is the **shoulder** (two partial tears + bursitis), which fresh legs don't help.
  Redirected: the real prize is finally **hitting @8 in W4** instead of B4's @6.
- **Injection agent:** athlete confirms **anesthetic only** — "steroid is the next option if this
  isn't working." Confirms the trigger-point read and means a steroid escalation is still ahead.
- ⚠️ **The instruction escalated on re-telling** — first "stop the heavy lifting for four weeks",
  then "he said I need to completely stop working on any of the exercises." Those are different
  instructions. **Unresolved; flagged for confirmation.** Logged as an explicit **athlete override**
  in `active-issues.md` with escalation triggers, same treatment as the 2026-06-13 comp-bench call.
  He is substantially right that pull-ups/dips/bench don't load the lumbar spine — but he is now
  training against medical advice, and that's recorded rather than smoothed over.
→ rules: `clinical-override`, `masked-pain-load-cap` (extended to local anesthetic)

### 2026-08-07 · block, exercise, general · B5 direction — strive selectively, sumo becomes a skill lift
**Feedback (athlete, designing B5):** "Sumo deadlift is something I don't want to strive for — I
just want to do it to keep the technical form. I think it's still valuable and beneficial. If you
don't think that way, let me know." Plus: be very conservative because sumo fatigues his lower
back a lot and *"I see a degradation from the MRI, and I think sumo has some impact on that,
right?"* Squat conservative this block (injections today 2026-08-07 and Fri 2026-08-14, then
done), strive later. Bench: strive slowly. Pull-ups and dips: strive. **Big 5 movements and their
days are fixed — don't replace or move them.** Rotate some secondaries and accessories; use logged
history for loads, best-guess for never-logged movements since the weekly sync corrects them.
**Coach agreement:** keep sumo — argued *harder* for keeping it than the athlete did. Detraining a
hinge makes the return more dangerous, light crisp pulling keeps erectors/glutes doing protective
work, and the above-the-knee hitch only gets fixed with reps at an ownable load. Demoted to a
**skill lift**: fixed 345–365 band, crisp triples, @7, 405 untouched, no PR intent.
**Coach correction #1 — sumo did not cause the MRI findings.** The 2026-07-22 report reads
*age-typical mild multilevel degeneration*; at 37 with 11 training years that's an unremarkable
spine, and imaging correlates poorly with pain. Corrected because the belief matters: if he thinks
sumo is grinding his discs down, the logical end of that is dropping the lift, which is wrong. The
conservatism is justified by his **symptom pattern**, which stands on its own.
**Coach correction #2 — there is no recent shoulder imaging.** He said the MRI shows no bench
issue and partial shoulder-tendon damage; those are two different studies. The 07-22 MRI is
**lumbar only**. The shoulder finding is a **2025-07-18 ultrasound**, 13 months old, and the
re-ordered shoulder MRI still hasn't happened. He's benching on year-old imaging. Strive anyway —
but not on a false belief that a recent scan cleared him.
**Coach correction #3 — the squat cap lifts on doctor clearance, not on the series ending.** He
expected to "go back next week." Built a W3 gate instead: capped track by default, release track
documented, unlocked only by a clinical answer. Athlete chose this option.
**Grounded (Hevy):** B4 comp bench peaked **250×2 @6** against an @8 allowance — the block's one
clear miss, and the origin of `cap-is-a-target`. Paused RDL ran **265–275×5 with backoffs @8.5**,
a heavy second hinge on the back being protected → cut to 225–245 @7 in B5.
**Tooling (third `exercise-name-mapping` instance):** `paused rdl` pointed at the stock
`Romanian Deadlift (Barbell)` — 55 sessions but abandoned since 2026-02-20 — while his live custom
`Paused RDL` template has 60 sessions through 2026-07-28. Anchor read 225 instead of 275. Fixed,
plus `weighted back extension` / `back extension` aliases for the re-introduced movement.
**Actions:** designed B5 (`2026-Q3-B05`); new rules `sumo-skill-lift`, `cap-is-a-target`,
`masked-pain-load-cap`; fixed the RDL + back-extension mappings; re-anchored six accessories off
the log; dropped Iso-Lateral Row and Hip Adduction (both `accessory-day-interference` violations
that ran all of B4).
→ rules: `sumo-skill-lift`, `cap-is-a-target`, `masked-pain-load-cap`, `exercise-name-mapping`

### 2026-08-07 · load, general · sync the Sheet to the training log — weekly
**Feedback:** "If the Google Sheet says 70 lb for leg extension but my training log average is
120 and my recent log is 140, the Sheet needs to be adjusted to match the log. Also, a new
exercise I hadn't really done — lower back extension — went in at 1 lb, but I can do 90 now,
so it needs adjusting. **Weekly**, the Sheet should update itself accordingly."
**Verified (Hevy, `block_report --exercise`):**
- **Leg Extension** — B4 programs **90–100 lb** (W5 deload **70**, the exact number he quoted).
  Log: median **140**, max **165**, 16 sessions; recent 135 / 145 / 140. The Sheet is **~50 lb
  light**. His recollection was right, if slightly conservative.
- **Weighted Back Extension** — log runs 25 → 70 → 90 → 90 → 70 → **1** (2026-07-17) → 45. Both
  the 1 lb and the 90 are real entries, so the placeholder story checks out. Not in B4 (it was
  cut for Incline DB Press), so nothing to correct there — the pattern is what matters.
**And it generalizes — he under-reported the problem.** A full sweep of B4 found **six** drifted
accessories, not one: Leg Extension +50, Reverse Pec Deck +55, DB Shoulder Press +20, Meadows Row
+20, Concentration Curl +18, Incline DB Press +15.
**Root cause 1 (tooling gap):** `loads-from-logs` binds only at *design* time. A block is frozen
the moment it renders to the Sheet, so five weeks of real training never feed back. There was no
in-block correction path at all.
**Root cause 2 (tooling gap), found while building it:** six plan names didn't resolve to the
template he actually logs under, so they read as "never trained" — Tricep Pushdown (he moved off
that template in Jan 2026 → `Triceps Extension (Cable)`), Reverse Pec Deck, Incline DB Press,
Spoto Bench + Paused Larsen (both pointed at generic `Bench Press (Barbell)` instead of his own
templates, orphaning their history), and 3-1-0 Tempo Squat (he logs 3-0-0). This is why the
Sheet could sit 55 lb light on Reverse Pec Deck unnoticed, and why B4 labelled Incline DB Press
"NEW" when he has **66 logged sessions** of it.
**Actions:** (1) new `scripts/sheets/reconcile_loads.py` — diffs plan vs log, rewrites the weeks
still ahead, re-renders the Sheet; (2) wired into the Saturday review so it runs **weekly** per
his ask, with the drift summary in the Telegram narrative and the weekly snapshot; (3) fixed the
six `OVERRIDES` mappings — all 20 B4 exercises now resolve; (4) rules `sheet-load-sync` and
`exercise-name-mapping`.
**Coach guardrails (deliberate, and he should know):** only **accessories** auto-adjust. Primaries
and barbell secondaries are reported but never rewritten — their loads come from the intensity
wave and from injury caps that *intentionally* sit below the log. The live case proves it: sumo's
log anchor is **385** while `sumo-back-cap` holds it at 345–405 @7 with a hard ceiling, and a
mid-block run showed the log at **425** against a capped plan of 365. An auto-chase there would
have quietly undone the back restriction. Past weeks are never rewritten, and corrections scale
the whole exercise by one factor so the wave and the W5 deload keep their shape.
**Timing note:** B4 is in W5, so there are **zero** weeks left to correct — the drift report is
the deliverable now and it feeds the B4 review + B5 design. The weekly sync starts biting in B5.
→ rules: `sheet-load-sync`, `exercise-name-mapping`

### 2026-07-13 · general · validate reps on data pull — catch mis-logged reps
**Feedback:** In B4 W1 D1 (comp bench, 2026-07-06) I accidentally logged **50 reps instead of 5**
on a backoff set. That should have been caught. When you pull the data, verify the reps are
plausibly punched — don't let an obvious mis-log through.
**Verified (Hevy `data/logs/sessions/`):** the set is `195x50 @6` (`POWER Bench Press`,
15c7a94a…), sitting between three legit `195x5` sets. Left unguarded it Epleys to a **~520 lb**
comp-bench e1RM vs the real 266 — and `block_report.py` picks the best set **by e1RM**, so the
phantom set silently becomes the reported PR and poisons any review touching that window.
Across the *entire* log the only real set above 12 reps is a single 20-rep squat rep-out (2023),
so a rep count over ~20 on a Big-5 lift is a reliable mis-log signal (a trailing-digit slip).
**Root cause (tooling gap):** the report had no rep-sanity check — it trusted every logged rep.
Same class of bug as `loads-from-logs`: the numbers were only as good as the raw log.
**Actions:** added a rep-sanity guard to `block_report.py` — working sets above `--rep-ceiling`
(default **20**) are treated as mis-logs. **Revised 2026-07-13 (athlete: correct, don't exclude):**
the athlete wants the obvious slip *fixed*, not dropped — "the rest were 5 reps, just the one set
was 50, you can tell it's an accident and correct it to 5." So the guard now **auto-corrects**: it
infers the intended reps from the plausible **same-weight sibling sets** that session (`infer_reps`)
and uses the corrected set in the numbers, listing the fix under `corrected` (✏️ `195x50 → 195x5`).
It only **excludes + flags** when there's no same-weight sibling to infer from (never guesses).
Verified: comp-bench e1RM stays honest at 255, exactly one correction across all history, zero
false positives, fallback-to-flag confirmed. New rule `log-rep-sanity`. **Note:** raw JSON still
mirrors Hevy (correction is at read time, self-healing if the app is later fixed); a hand-edit to
the JSON isn't durable (`--full` re-pulls the 50), which is why the fix lives in the report layer.
→ rules: `log-rep-sanity`

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
