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
- **sheet-load-sync** — `loads-from-logs` binds at *design* time; this keeps it true *during*
  the block. **Every week (Saturday review), reconcile the plan's prescribed loads against the
  Hevy log and correct the weeks still ahead**, then re-render the Sheet — so the Sheet never
  drifts from what he actually lifts. Run
  `python -m scripts.sheets.reconcile_loads [--apply --push]` (report-only by default).
  - **Anchor** = median of the last 3 logged sessions' top working loads. Median, not max —
    it tracks the current level and shrugs off one stray entry.
  - **Only accessories are auto-adjusted.** Big-5 primaries and the barbell secondaries are
    *reported* and left to a coaching call: their loads come from the intensity wave and from
    injury caps (`sumo-back-cap`, the squat axial cap) that deliberately sit **below** the log.
    Auto-chasing the log there would silently undo a restriction.
  - **Only future weeks.** Weeks already trained are the record of what was prescribed.
  - **Shape is preserved** — one scale factor per exercise, so the wave and the W5 deload keep
    their relative depth. This re-bases a wrong anchor; it is not progression
    (`accessory-progression` still governs how loads climb).
  - **First exposures**: a movement programmed at a placeholder load (no history to anchor on)
    gets rebased flat onto the log as soon as there are real sessions — that's the fix for
    "went in at 1 lb, he does 90".
  - **🔒 `hold` overrides the sync.** Set `"hold": true` + `"hold_reason"` on a prescription entry
    and the sync reports it but never rewrites it. **Required whenever a load is deliberately
    below what the log says** — medical restriction, technique work, a deload the athlete keeps
    ignoring. The primaries/secondaries guard alone is *not* enough: an **accessory** can be
    deliberately under-prescribed too, and B5 caught this live — Weighted Back Extension was held
    at bodyweight because trigger-point injections went into those exact muscles, and the sync
    would have rebased it to 45 lb the following Saturday, silently undoing a medical restriction.
    A hold is only lifted by a human. [FB 2026-08-07]
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
- **core-every-day** — **Every training day carries at least one core/abs accessory**, and each
  day gets a **different pattern** so they aren't redundant: anti-lateral-flexion (side plank) ·
  anti-rotation (Pallof press) · anti-extension (dead bug) · spine-neutral endurance (bird dog).
  While the low back is under treatment, prefer **anti-movement** work and avoid **loaded lumbar
  flexion** (cable crunch, sit-ups) and **hip-flexor-dominant** work (hanging leg raise — the
  psoas attaches onto L1–L5 and pulls on the treated segments). [FB 2026-08-07]
- **muscle-coverage-audit** — Before finalizing a block, **audit muscle coverage across all
  training days** and state the result: quads · hamstrings · glutes · erectors · chest · triceps ·
  front delts · lateral delts · rear delts · lats · mid-back · biceps · core. Name any group left
  uncovered **as a deliberate decision with a reason**, not by omission. The B5 audit caught three
  real holes (lateral delts, biceps, core-on-one-day-only) plus a day carrying two triceps
  movements while another day ran thin. **Balance days by working-set volume, not accessory
  count** — a day with two primary lifts needs fewer accessories than a day with one.
  [FB 2026-08-07]
- **accessory-day-interference** — Accessories must not compromise the *next* training day.
  Schedule: D1 Mon · D2 Tue · D3 Thu · D4 Fri. D1→D2 and D3→D4 are back-to-back (no rest):
  **D1 accessories must not pre-fatigue D2** (esp. back work vs D2 pull-up), and **D3
  accessories must not pre-fatigue D4** (esp. lats/adductors vs D4 sumo). D2→D3 has Wednesday
  off, so **D2 accessories are unconstrained.** This extends CLAUDE.md's primary-lift overlap
  rules down to accessories. [FB 2026-06-18]

- **cap-is-a-target** — An RPE cap on a lift that is **not** injury-restricted is a ceiling to
  *approach*, not a number to stay under. B4 proved the failure mode: after three blocks of
  breaching caps, the athlete over-corrected and peaked comp bench at **@6 against an @8
  allowance** on a bench-led block. When a lift is in "strive" posture, write the peak as an
  **instruction plus a load range** — "work up to @8, 255–270×2, take the heaviest set that stays
  ≤@8" — never a single number at a cap RPE. Reserve fixed-load prescriptions for lifts under an
  injury cap, where the load *is* the restriction (`sumo-back-cap`, the squat axial cap).
  [FB 2026-08-07]
- **clinical-override** — **A doctor's training restriction outranks every rule in this file and
  every number in the block.** When one lands, rewrite the block to fit it rather than negotiating
  around it, and record the instruction verbatim in `active-issues.md` with its expiry. Two
  corollaries learned 2026-08-07:
  - **Clarify the scope before assuming a conflict.** "Stop heavy lifting" from a clinician who
    just heard about a 465 lb squat almost certainly means *the 465*, not a 185 lb technique squat.
    Athlete and doctor usually aren't disagreeing — they're using one word for two different
    things. Get the specific question asked before treating it as a dispute.
  - **Write the light numbers down.** This athlete follows a number on a page reliably and cannot
    reliably generate one in the moment (B4 W1 sumo: planned 345, pulled 425; squat backoffs @8.5
    under a cap written to stop that). "Train light" as a instruction is not a restriction.
  Volume rules yield too — `primary-backoff-volume` was deliberately broken for B5's squat/sumo.
  [FB 2026-08-07]
- **masked-pain-load-cap** — When an injection is active in a joint or region — **corticosteroid
  *or* local anesthetic ("freezing")** — the pain signal is **chemically muffled**, so pain-based
  and RPE-based guardrails stop protecting that structure. Cap the affected lifts **by absolute
  load** for the injection window and the weeks after, and lift the cap on **doctor clearance** —
  not on the series ending, not on a clean scan, and never on how it feels. **Anesthetic is the
  worse case, not the milder one**: it produces profound, immediate numbness for hours, where a
  steroid dulls pain gradually over days. Established for the lower back / squat + sumo; **applies
  to the shoulder and bench the moment a shoulder injection starts** (still not given as of
  2026-08-07 — the athlete must report it so bench and dip get the same treatment). [FB 2026-08-07]

## What lands in the app

- **hevy-load-precision** — **Every prescribed load must render in Hevy as a whole pound.** The
  API speaks kg and the athlete's app displays lb, so a kg value rounded for readability (102.1)
  comes out as **225.09 lb** on his screen — a junk decimal on every set, and the plate maths stops
  being obvious mid-session. Store `weight_kg` as the **exact** kg equivalent of the intended
  pound load (`lb × 0.45359237`, full precision), never a 1-decimal kg. `push_block._snap_weight`
  enforces it on the way out and `reconcile_loads` must not re-round it on the weekly sync.
  Prescribe in **5 lb increments** — that's what's on the bar and in the stack. The Google Sheet
  already showed clean numbers; this makes Hevy match it. [FB 2026-08-11]
- **rest-times-programmed** — **Every exercise in a pushed block carries `rest_seconds`.** Not
  optional, not "he'll know" — the app runs the timer so the decision isn't made mid-session while
  tired. [FB 2026-08-11]
- **rest-times-athlete-set** — **The rest values are the athlete's, not the coach's** (set
  2026-08-11, after a first pass at 2–5 min was rejected as far too long):
  - **Primary — squat · bench · sumo · weighted pull-up · weighted dip: 75s.** Top sets *and*
    backoffs; a backoff of a primary is still the primary.
  - **Secondary + all accessories: 60s.** Includes the barbell secondaries (Spoto, CGB).
  - **Core / abs: 30s.**

  He trains dense and reports that he takes another 5–10 s past the buzzer anyway, so the timer is
  a **floor, not a ceiling** — treat these as defaults, not caps, and don't quietly re-inflate them
  in a later block. **Say so in the block file where a set genuinely wants more**: the W4 comp-bench
  work-up to @8 and the W3 dip peak are the two in B5, because an under-rested top set reads
  heavier than it is and B4's defining miss was peaking **@6 against an @8 allowance**. Changing
  these numbers takes new feedback from him, not a coaching preference. [FB 2026-08-11]
- **push-is-idempotent-with-update** — A block that's already live gets **corrected in place**:
  `push_block --update --start W<n>-D<n>` PUTs over the routines whose titles match and leaves
  everything before the start point alone. **Hevy has no DELETE for routines**, so a plain re-push
  is additive and strands duplicates the athlete has to clear by hand. Never ask him to delete
  routines to make room for a correction. [FB 2026-08-11]

## RPE conventions

- **accessory-rpe** — Accessories usually have **no logged RPE**. Treat a blank-RPE accessory
  set as **RPE 7–8**, not as missing data — do not flag it. Only an explicitly logged **RPE 9+**
  on an accessory is a signal worth reacting to. Applies both to `reviewing-session` and to
  reading the log during block design. [FB 2026-06-14]
- **rpe-hevy-ladder** — Every prescribed RPE must be a value the Hevy app can actually record:
  **{6, 7, 7.5, 8, 8.5, 9, 9.5, 10}**. There is **no 6.5, and nothing below 6** — never program
  @6.5 / @5.5 / @5. Round submax (backoff / calibration) targets **down** to the nearest ladder
  value to keep them easy; **deloads target @6** (the floor), with the deload driven by the
  **load drop**, not a sub-6 RPE. Binds `designing-training-block` output and any hand edit to a
  block JSON. [FB 2026-07-04]

## Data hygiene

- **log-rep-sanity** — The Hevy log is the source of truth, but raw reps can be mis-punched
  (a trailing-digit slip like **5 → 50**). Since e1RM is Epley-based, one phantom high-rep set
  would silently become the reported PR (195x50 → ~520 lb) and poison any window that touches it.
  **When pulling data, `block_report.py` validates reps and auto-corrects obvious slips:** a
  working set above `--rep-ceiling` reps (**default 20** — the whole log has exactly one legit
  >12-rep set, a 2023 squat rep-out) is repaired by inferring the intended reps from the
  **same-weight sibling sets** that session (195x50 next to three 195x5 → read as 195x5), and the
  fix is reported under `corrected`. A set is only **excluded + `flagged`** when there's no
  same-weight sibling to infer from — then don't trust the number; have the athlete fix it in Hevy.
  Correction is at read time (raw JSON stays a faithful Hevy mirror; self-heals if the app is
  fixed). Applies to every read of the log: block design, block/weekly/session reviews. When a
  review surfaces a `corrected` set, mention it so the athlete can clean the source. [FB 2026-07-13]
- **exercise-name-mapping** — A plan name that doesn't resolve to the Hevy template he *currently*
  logs under reads as "no history", and every log-grounded rule silently degrades to a guess —
  it's what let the Sheet sit 55 lb light on Reverse Pec Deck and label a 66-session Incline DB
  Press "NEW". When adding or renaming an exercise, resolve it against the log
  (`block_report.py --exercise "<name>"`) and add an `OVERRIDES` entry in
  `scripts/hevy/exercise_map.py` if it doesn't match. Templates get **abandoned** as well as
  renamed (he moved off "Triceps Pushdown" in Jan 2026) — point the override at the one with
  recent sessions. `reconcile_loads` flags unmatched names; treat that as a bug, not a data gap.
  [FB 2026-08-07]

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
- **sumo-skill-lift** — **Sumo is programmed as a SKILL lift, not a strength lift** (athlete
  decision 2026-08-07). It stays one of the Big 5 and keeps its day, but it is **not periodized
  for progression**: no PR intent, no intensity wave, no autoregulating up, no "felt easy so I
  added weight." Prescribe a **fixed low band, crisp low reps, technique focus** (tall lockout,
  no hitch) and hold it. This sits *inside* `sumo-back-cap` and is tighter still — B5 runs
  345–365 @7 and does not touch the 405 ceiling at all.
  **Why keep it rather than drop it:** detraining a hinge makes returning to it more dangerous;
  light crisp pulling keeps erectors and glutes doing protective work; and the above-the-knee
  hitch only gets fixed with reps at an ownable load.
  **On causation — do not tell the athlete sumo damaged his spine.** The 2026-07-22 MRI reads
  *age-typical mild multilevel degeneration*, which is unremarkable at 37 with 11 training years,
  and imaging correlates poorly with pain. The conservatism is justified by his **symptom
  pattern**, not by the images. Getting this backwards pushes toward dropping the lift, which is
  the wrong call. Revisit the skill-lift framing only after a long pain-free stretch **and** a
  doctor's clearance. [FB 2026-08-07]
- **sumo-back-cap** — Sumo is the athlete's lower-back canary (fatigues/flares at **L5-S1**,
  imaging-consistent). Program it as the **most conservatively loaded Big-5 lift**: working band
  **345–405 lb, RPE cap 7, reps ≤4 and every rep crisp, 405 = hard ceiling** while the back is a
  concern. **Never grind sumo** — any back rounding or bar-speed drop = rack it. Progress toward
  the ceiling only when RPE holds ≤7 **and** the next-morning back check is clean. This is a
  **durable** rule, distinct from the temporary injection-series axial cap in `active-issues.md`
  (that one lifts on doctor clearance; this stays until a long pain-free stretch). Revisit the band
  upward only on sustained clean pulling. [FB 2026-07-22]
