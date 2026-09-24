# Between-blocks record — 2026-Q3-BRIDGE (archived 2026-09-24)

> Everything written between B5's end (2026-09-18) and B6's start (2026-09-28): the Sep 11 clinical
> update, the bridge sessions (Thu Sep 24 / Fri Sep 25, pushed to Hevy as folder `2026-Q3-BRIDGE`),
> the B6 start-date decision and the squat-heavy reversal. B6 carries the live standing orders forward.

---

# Current Block

> ## 🔶 BETWEEN BLOCKS — B5 is closed and reviewed; B6 is not written yet.
> **Two bridge sessions run Thu 2026-09-24 and Fri 2026-09-25. B6 starts Mon 2026-09-28.**
> Everything below the bridge section is the B5 record, kept until B6 replaces this file.

---

## 🌉 2026-09-23 — the two bridge sessions (Thu Sep 24 · Fri Sep 25)

**These belong to no block.** B5 ended Sep 18; B6 starts Mon Sep 28. Their job is not stimulus —
it is to **produce the two readings B6's axial ladder has to be written from**, and to put the
pattern back after ~10 days of almost nothing (2-day W6 deload → Korea → one off-plan session).

> ✅ **IN HEVY, 2026-09-23.** Folder **`2026-Q3-BRIDGE`** → `W1-D1 Thu Sep 24 — Dip + Upper Back`
> and `W1-D2 Fri Sep 25 — Sumo + Spoto`. To push them, B5 was archived to
> `data/block-archive/2026-Q3-B05.{md,json}` and `current-block.json` now holds the bridge spec —
> that slot is the only path to the app. **B6 will archive the bridge the same way.** The rest
> timers and whole-pound loads came through the normal `push_block` guarantees.

### Thu 2026-09-24 — Dip + Upper Back *(D3 shape)*

| Exercise | Load | Sets × reps | RPE | Why this number |
|---|---|---|---|---|
| **Weighted Dip** | **BW+70** | 3 × 5 | @7 | Re-entry, deliberately far under the BW+105 @8 peak (09-10). Strive lift, unaffected by the medication. **Stop above the pinch — depth is the dip variable, ahead of load.** |
| **Close-Grip Bench** | **185** | 3 × 5 | @7 | His *actual* load — B5 prescribed 165→185 and he ran **185 flat for all five sessions**. Writing 175 would just be ignored again (`loads-from-logs`). |
| **Lat Pulldown** | 165 | 3 × 12 | @7 | Log anchor 165–190. |
| **Reverse Pec Deck** | 110 | 3 × 15 | @7 | **Load-bearing, not filler.** Posterior cuff is intact behind two torn anterior tendons; this shares load off them. |
| **Face Pull** | 35 | 3 × 15 | @7 | Same reason. |
| **Dead Bug** *(core)* | BW | 3 × 10/side | — | Anti-extension. |

**Explicitly not on this day**, all three named because the B5 review found them running unnoticed:
**no overhead pressing** (DB *or* barbell — it hit **@10** under a hard @7 cap in B5, on a bursitic
shoulder), **no upright row** (the most impingement-provocative thing in the building for this
shoulder), **no barbell incline**.

### Fri 2026-09-25 — Sumo + Spoto *(D4 shape)* — **the session that matters**

| Exercise | Load | Sets × reps | RPE | Why this number |
|---|---|---|---|---|
| **Sumo Deadlift** | **225 — fixed, a ceiling not a target** | 3 × 3 | @6 | **This is the whole point of the week.** 225 is the comparability load — it is what ran W1–W3 and W6-D2, so this triple joins four weeks of data instead of starting a new series. Untouched since Sep 15. **The number B6's opening rung is written from.** |
| **Spoto Bench** | **235** | 3 × 4 | @7 | Re-entry under the 250×3 @7.5 of 09-11. Spoto is the one lift that progressed every single session of B5 — protect that. |
| **Leg Press (Machine)** | **315** | 3 × 12 | @7 | **Added 09-23** — athlete said the day was too light, and he's right that **quads are uncovered** (Thursday is all upper). 315 is well under his 585 log anchor. **The ROM rule is what makes it safe:** stop before the hips roll off the pad — that posterior tilt at depth is what loads the L3-4 protrusion, and the muscle relaxant blunts the end-range feedback he'd normally get. |
| **Chest Supported Incline Row** | **50/hand** | 3 × 12 | @7 | **Added 09-23** — mid-back, the other uncovered group. **Chest-supported = zero lumbar load**, which is exactly why it replaced Meadows Row. **Forbidden fallback: no barbell bent-over row.** |
| **Seated Leg Curl** | 95 | 3 × 12 | @7 | What he actually ran in W6. |
| **Seated Calf Raise** | **90** | 3 × 12 | @7 | **The corrected anchor.** B5 prescribed 155→175 off a 2023 median on different equipment; his real working load is 90–100. |
| **Bird Dog** *(core)* | BW | 3 × 10/side | — | Spine-neutral, no axial load. |

**Declined for Friday: Bulgarian Split Squat.** It was the obvious third pick on merit — unilateral
quad/glute work, on the B5 D4 already. **Baclofen is why not.** A muscle relaxant plus a
balance-dependent single-leg movement under load is the one combination on this list where the drug
changes the risk rather than just the reading. It comes back in B6 once the course is done.

**Not on this day: no loaded hinge other than the sumo.** RDL is still cut — and he ran a Smith RDL
185×8 ×4 in Korea on Sep 20, so this is worth saying out loud rather than assuming.

### The three rules on these two days

1. **Sumo 225 does not move.** Five written axial numbers ran hot in B5, including one he had agreed
   to in writing that same morning. This is the cheapest possible week to hold one, and the reading
   is worthless at 245.
2. **Back check Saturday morning** after the sumo — `back_checks add 2026-09-25 <fine|tight|sore>`.
   It is a **medicated** row (course runs to ~Sep 30) but it is still the sumo comparable.
3. **Stop on any new leg symptom**, night or rest pain, or pain not settling in 24 h. Standing hard
   stops, unchanged.

---

## 🏋️ 2026-09-23 — B6 is **SQUAT-heavy**, not sumo-heavy. Athlete challenged my call; he was right.

I recommended sumo-heavy earlier today. **He asked me to justify it and the justification does not
hold.** Recording the reversal and the reasoning, because the rule says every block states its axial
emphasis and the *why* is the part that gets lost.

**What I was leaning on:** the 2026-08-29 note in the old block file — *"Sumo's return is B6's whole
job."* **That note predates the 365 squat, the medication, and the B5 review.** It was written when
the assumption was that B6 would open off a clean Sep 8 back check — the one that was never logged
and is now permanently gone. `alternating-axial-emphasis` itself says blocks alternate; **it does not
say which lift goes first.**

**Why squat is the right first emphasis:**

1. **`sumo-back-cap` makes a sumo-heavy block structurally small.** The band is 345–405 with 405 a
   hard ceiling — ~81% of his 501 sumo e1RM. A "heavy" block that cannot pass 405 is not a heavy
   block. Squat has no equivalent ceiling once cleared, against a 511 e1RM.
2. **Sumo is the lift that provokes this back; the squat is not.** The repo's own words: sumo
   *"reproducibly fatigues your back"*, and *"a deadlift set costs more lumbar exposure per rep than
   a squat set."* Making the provocative lift the emphasis in the first block back — with baclofen
   running through W1 and the last check reading `tight` — is the wrong order of operations.
3. **The squat is where the data is.** B5's one genuine axial signal is **365×3 @6** (09-07). Sumo
   has 225 and 295 and nothing else. You build a ladder from the rung you are standing on.
4. **405 squat is owed to him** — declined in W5 *only* because the checks read tight. It is a live,
   earned target with a number attached. Sumo has no equivalent.

**The one honest argument for sumo-first, stated rather than buried:** if the goal were a competition
total, the weaker lift is the bigger gain. But sumo is not his weak lift — 501 vs 511 e1RM, they are
historically level — it is merely *detrained*, and there is no meet scheduled. So
`weak-point-priority` does not pick sumo either.

**What sumo gets instead — and this is not neglect.** Under `sumo-skill-lift` the moderate lift keeps
its day and its pattern at a fixed low band: crisp low reps, no wave, no PR intent, no autoregulating
upward. That is the rule working as written, and it keeps the hinge from detraining while the squat
takes the load.

**So B6 states: current axial emphasis = SQUAT. Prior = none (B5 froze both under a medical cap).**
B7 then runs heavy sumo, which is when `axial-return-ladder` walks it toward 385–405.

---

## 📅 2026-09-23 — B6 starts **Mon Sep 28**, not Oct 5 — revised on the actual drug names

**Yesterday I said Oct 5 and that was written before I knew what he is taking.** Two facts moved it:

1. **The course ends ~Sep 30, not ~Oct 2** — *"I have one more week to consume"* (2026-09-23).
2. **The drugs are baclofen 10 mg BID + pregabalin 25 mg BID.** Pregabalin at 25 mg BID is the low
   end of a *starting* dose; the pain-masking effect is modest, not the blackout I described on
   09-22. *(The stronger objection turns out to be baclofen and trunk tone — see `active-issues.md`.)*

**Why Sep 28 works and the "can't open a block on medicated checks" objection doesn't apply to W1.**
The gate problem is real for the **ladder rungs** — and W1 has no rungs. W1 is the calibration week
by design (fixed loads, RPE cap 7). The course ends **Wednesday of W1**, so W1-D3 and W1-D4 are
already unmedicated and **every check from W2 onward — the ones the ladder is actually gated on — is
clean.** W1 absorbs the tail of the medication at fixed light loads. That is better than waiting.

**What still binds through W1:** squat and sumo at fixed absolute loads, no rung claimed before W2,
and the W1 checks tagged `medicated`.

---

