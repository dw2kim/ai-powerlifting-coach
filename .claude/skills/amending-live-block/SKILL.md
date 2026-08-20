---
name: amending-live-block
description: Change a block that is already running and already pushed to Hevy — add/swap/re-anchor an exercise, change loads or rest times, apply a medical restriction mid-block, or fix something wrong in the app. Corrects the routines in place with push_block --update --start, re-renders the Sheet, and pins holds so the Saturday sync can't undo it. Triggers on "regenerate block N", "can you push from week X day Y", "add/replace/remove <exercise> for this block", "the load in the app is wrong", or any mid-block plan change.
---

# Amending a live block

A block that is already in the Hevy app is a **live artifact he trains off at 6am.** Editing
`current-block.json` is not the change — the change is what shows up in the app and on the
Sheet. This procedure exists because amendments arrive from every direction (feedback, a
clinical update, a mid-block catch) and the traps below were each learned the expensive way.

For designing a *new* block use `designing-training-block`. For a clinical event, run
`logging-clinical-update` first — it decides *what* changes; this skill applies it.

## Bound by

`sheet-load-sync` (the `hold` clause) · `hevy-load-fidelity` · `hevy-rest-timers` ·
`push-is-idempotent-with-update` · `exercise-name-mapping` · `loads-from-logs` ·
`cap-is-a-target` · `accessory-day-interference`

## Never

- **Never ask him to delete routines in the app.** Hevy has **no DELETE for routines** — the
  update path exists precisely so he never has to. *"The right answer to 'should I delete
  it?' is always no — fix the push, not his Saturday."*
- **Never re-push without `--update`.** A plain push is additive: it POSTs a **second** folder
  and a duplicate set of 20 routines that can only be cleared by hand.
- **Never rewrite a week he has already trained.** That week is the record of what was
  prescribed.

## Procedure

### 1. Establish where the block is right now

Week and day from the start date in `brain/current-block.md`. Everything from the **next
untrained session** forward is fair game; everything before it is history. That session is
your `--start W<n>-D<n>`.

### 2. Ground every load in the log — and check the name resolves

`python -m scripts.hevy.block_report --exercise "<name>" --recent 90`, anchor on the
**median** (`loads-from-logs`).

**If it reports no history, that is a mapping bug until proven otherwise**
(`exercise-name-mapping` — four instances, every one silent, every one *under*-prescribing,
which looks responsible and so never feels wrong at review time). The Hip Thrust case put
**45 lb** in front of a lift he has done at **275×12**. Before writing any load for a
movement that looks new: check `OVERRIDES` in `scripts/hevy/exercise_map.py`, look for the
same movement under another template title, and fix the mapping first.

When adding an exercise mid-block, also check `accessory-day-interference` (D1 must not
pre-fatigue D2; D3 must not pre-fatigue D4) and say what the addition costs — B5's CGB was
granted with its cost stated, held flat in the week the dip peaks, and named as first to be
cut.

### 3. Edit `brain/current-block.json`

- **Loads: full-precision kg**, `scripts.hevy.units.lb_to_kg(<lb>)`, never rounded
  (`hevy-load-fidelity`). Prescribe in 5 lb increments — that's what's on the bar.
- **Every exercise entry carries a `tier`** — `primary` / `secondary` / `accessory` / `core`
  — which drives the rest timer, 1:15 / 1:00 / 1:00 / 0:30 (`hevy-rest-timers`). Don't leave
  it to the name classifier and don't re-inflate the numbers; they're his.
- Keep week/day numbering intact so `--update` matches routines by title.

### 4. Sweep for holds — the step that gets skipped

`python -m scripts.sheets.reconcile_loads` (report-only) and confirm **every load
deliberately below the log is pinned** with `"hold": true` + `"hold_reason"`.

This has been missed **twice**, both times on a medical restriction the Saturday sync would
have silently reversed: Weighted Back Extension (2026-08-07) and **Leg Press** (2026-08-11 —
prescribed 315 against a 585 anchor for a medical ROM rule, four days after the `hold` clause
was written, on the same block). An unheld cap dies quietly the following Saturday.

Anything under a medical cap, technique work, first-exposure pattern work, or a contained
addition gets a hold.

### 5. Dry-run and check against the Sheet

`python -m scripts.hevy.push_block` — the default is a dry run. It prints per exercise the
**tier, rest timer and loads in lb**. Read it as the athlete would:

- every load a **whole pound**, matching the Sheet string exactly (a load stored as
  1-decimal kg surfaces as **"70.11 lb"** in the app);
- a **timer on every line**, no blanks.

`--json` dumps the raw kg payload if you need it.

### 6. Apply

```
python -m scripts.hevy.push_block --update --start W<n>-D<n> --apply
```

`--update` PUTs over the routines whose titles match, keeping their existing folder;
`--start` leaves already-trained sessions alone.

**No credentials in the session?** A Claude Code session usually has no `HEVY_API_KEY` or
`GOOGLE_SA_JSON`. **Say so — do not claim the push happened.** Point at the
`workflow_dispatch` workflows that run with the repo secrets: **Actions → "Push block to
Hevy"** (dry run by default; flip `apply`) and **Actions → "Export block to Google Sheet"**.

### 7. Re-render the Sheet

`python -m scripts.sheets.export_block brain/current-block.json --final`
(add `--dry-run` to preview the grids). The Sheet and the app must agree, or the next
weekly sync reports a drift that isn't real.

### 8. Update the prose and commit

`brain/current-block.md` carries the human version — what changed, and **why**, including the
cost of anything granted. If the amendment came from feedback, log it via the `feedback`
skill; if from a clinical event, `logging-clinical-update` owns that record.

Commit atomically, coach voice, naming the change and the numbers, e.g.
`block: re-anchor Hip Thrust onto the Smith — 205/225/225/245 (was empty bar)`.

## Checklist

- [ ] Start point = next **untrained** session
- [ ] Every new/changed load anchored on the log; any "no history" treated as a mapping bug
- [ ] Full-precision kg; `tier` on every entry
- [ ] `reconcile_loads` swept; every deliberately-light load pinned with `hold` + reason
- [ ] Dry run checked against the Sheet — whole pounds, timer on every line
- [ ] Pushed with `--update --start`, never additive
- [ ] Sheet re-rendered
- [ ] `current-block.md` prose updated; committed
