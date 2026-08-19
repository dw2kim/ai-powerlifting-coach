---
name: logging-clinical-update
description: Log a medical/clinical event and work out what it changes in training — a pasted MRI/ultrasound/radiology report, an injection, a doctor's instruction, a symptom change, or a clinic visit coming up. Updates active-issues.md + current-block.md + memory.md in one pass and maintains the running question list for the next visit. Triggers on "here is the MRI/scan result", "I got the injection", "the doctor said", "I'm doing the pain clinic", a new or worsening symptom, or "what should I ask at my appointment".
---

# Logging a clinical update

The athlete reports medical events in the middle of training conversations, often by pasting
a raw radiology report. This is the procedure for turning that into (a) an accurate record,
(b) a training decision, and (c) the questions he still needs answered.

**This is not a diagnosis.** The clinic owns the medicine. This skill owns the *record* and
the *training consequence*.

## Bound by

`clinical-override` · `masked-pain-load-cap` · `sumo-back-cap` · `cap-is-a-target`
(read `reference/programming-rules.md` before deciding anything).

## Context to load

- `brain/active-issues.md` — the running clinical record and current restrictions
- `brain/current-block.md` — the medical-override section and the athlete-facing standing orders
- `brain/memory.md` — prior clinical events and the patterns already learned from them
- `reference/programming-rules.md` — the four rules above
- `reference/protocols.md` — Shoulder / Lower Back protocols, escalation triggers

## Procedure

### 1. Capture verbatim, before interpreting

Record what was actually said or written — the report's own Impression line, the doctor's
instruction in his words, the number of injection sites. Paraphrase loses the detail that
turns out to matter three weeks later.

### 2. Separate three things that keep getting merged

Write them as three distinct things in the record. They have different reliability:

| | What it is | How much to trust it |
|---|---|---|
| **Clinical fact** | What the report says / what the doctor said | High — quote it |
| **Athlete's interpretation** | What he took it to mean | Check it. Often wrong, see below |
| **Coach's read** | The training consequence | Yours, and labelled as yours |

### 3. Confirm the facts before writing them down

His medical vocabulary is imprecise **by track record**, and this has cost real accuracy:

- The trigger-point injections were recorded as **corticosteroid from 2026-07-06 to
  2026-08-14**. They were **local anesthetic** the whole time.
- "The MRI shows the shoulder is fine" referred to a **13-month-old ultrasound** — a
  different study, different modality, and the two reads disagree.
- "The series ends Aug 14" — it did not; it stepped down to bi-weekly and continues.

So, before recording: **ask which agent, which study, which date, and what exactly was
said.** If it can't be confirmed now, write it as ❓ **unconfirmed** with the question
attached — never as fact. A guess that lands in `active-issues.md` becomes true by repetition.

Watch for the **instruction escalating on re-telling** (2026-08-07: "stop heavy lifting for
four weeks" → "stop working on any of the exercises" within one evening). Those are
different instructions. Flag the discrepancy; don't silently pick one.

### 4. Decide the training delta — and state a non-change explicitly

Most clinical updates change nothing. **Say so in one line, in the block file**, because his
default reading of any good news is that he's cleared. "Injections went bi-weekly" reads to
him as "recovered"; it isn't.

Check each gate by name and say which binds and on what condition:

- **`clinical-override`** — a doctor's restriction outranks every rule here and every number
  in the block, including volume rules. Clarify *scope* before assuming a conflict ("heavy"
  to a clinician who just heard about a 465 lb squat means the 465). Write the light numbers
  down — "train light" is not a restriction, a number on a page is.
- **`masked-pain-load-cap`** — any active injection (anesthetic **or** steroid) means
  pain- and RPE-based guardrails do not protect that structure. Cap the affected lifts by
  **absolute load**. It lifts on **doctor clearance only** — not on the series ending, not on
  a clean scan, never on how it feels. A **shoulder** injection binds bench and dip the same
  way the back injections bind squat and sumo.
- **`sumo-back-cap`** — durable; outlives any injection series.
- Imaging that reads *better* than expected does not lift a cap driven by masking. A clean
  scan and a numb back are unrelated facts.

If the change touches the running block's loads, days, or exercises, **hand off to
`amending-live-block`** — don't hand-edit the block and leave the app and Sheet stale.

### 5. Propagate — one pass, every file

The recurring failure is a fact that gets fixed in one file and left wrong in another.

- `brain/active-issues.md` — the clinical record: the finding, the date, the restriction and
  its **expiry condition** (a date *or* "on clearance"). Correct anything this update
  contradicts, and mark the old line as corrected rather than deleting it.
- `brain/current-block.md` — the athlete-facing consequence, in one line, including "nothing
  changes" when that's the answer. Update the medical-override section and any injection
  schedule table.
- `brain/current-block.json` → `medical.injections` — **when an injection is given or
  scheduled, add the date here**, not only in the prose. It's what makes the back-check
  comparison possible (`scripts/review/back_checks.py` reads it to split off-weeks from
  injection weeks), and a date that lives only in a paragraph can't be computed with.
- `brain/memory.md` — only if it surfaced a durable pattern.
- **Close resolved questions everywhere they appear.** `memory.md`, 2026-08-16: *"A resolved
  question left open in one file gets re-asked forever — close it everywhere the first time."*
  Grep for the question before you finish.

### 6. Maintain the question list for the next visit

Keep the open items in `brain/active-issues.md` under the relevant section, each with the
date it was first raised. Items have gone **three blocks** unanswered (the shoulder
injection; the return-to-heavy-axial number; telling the clinic he still trains heavy).

Before a visit, run `python -m scripts.review.back_checks` — if the injection-week vs
off-week split has enough data, that comparison *is* clinical input he should bring.

**Pre-visit brief** — when a visit is coming up, produce the short list of what to ask,
ordered by what actually gates programming. Separate **data** questions (what's in the
injection, reconcile the ultrasound against the MRI) from **permission** questions (the
clearance to return to heavy axial load). Declining advice is not a reason to stop
collecting facts.

**Post-visit debrief** — ask the question `memory.md` names as the standing pattern:
**is the doctor acting on the same story the athlete is?** Twice they were not — the doctor
was *shocked* to learn he lifts heavy (2026-08-07), and stepped the injections down on
"improvement" while the athlete accepted for a different reason entirely, that he suspects
the shots are making it worse (2026-08-14). When the two stories differ, the coaching move
is not to adjudicate the medicine — it's to get him to **say his side out loud at the visit.**

### 7. If he is training against advice, log it as an override

Same treatment as the 2026-06-13 comp-bench decision: state the athlete's position, state
the coach's position (including where he is substantively right), and attach **escalation
triggers written as hard stops**, not as "reduce". Make the case once, twice at most; if he
reaffirms, it's his call — record it and proceed under written numbers, which is the safer of
the two ways to disagree with a doctor.

### 8. Commit

Coach-voice message naming the clinical change and whether training moved, e.g.
`medical: injections continue BI-WEEKLY from Aug 14 — no training change`.

## Tone

Direct, and correct him when the medicine he's repeating is wrong — the beliefs drive his
decisions (if he thinks sumo is grinding his discs down, the logical end of that is dropping
the lift, which would be wrong). Give the benign explanation when there is one; the
alternative is him quietly concluding the treatment is harming him and stopping without
telling anyone. Stay out of diagnosis.
