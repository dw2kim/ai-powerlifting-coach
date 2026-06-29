# Routine prompt — end-of-W4 next-block draft

> This is the prompt the scheduled Claude Code routine runs (Sunday 13:00 America/Toronto).
> It is intentionally self-contained: the routine starts cold with no memory of prior runs.

You are the strength coach. Today may be the end of Week 4 of the running block. Do this:

1. **Guard.** Run:
   ```
   .venv/bin/python -m scripts.review.draft_next_block check
   ```
   If it exits `3` (skip), **stop immediately** — today is not the W4 Sunday. Do nothing
   else, send nothing. If it exits `0`, it has already synced the Hevy log; continue.

2. **Draft the next block.** Invoke the `designing-training-block` skill in **draft mode**
   (see its "Draft mode" section). Work off the W1–W4 actuals from the freshly-synced Hevy
   log. Obey `reference/programming-rules.md` — especially `primary-backoff-volume` (squat
   backoff 3 sets W1–W4; sumo backoff 3 sets W1–W3, 2 at W4 peak) and the `accessory-rotation`
   expansion clause (introduce 1–2 genuinely new accessory/secondary movements; name them and
   the muscle group each expands). Write `brain/next-block-draft.md` + `brain/next-block-draft.json`
   with the PROVISIONAL banner. Do **not** touch `current-block.*`, do **not** archive, do
   **not** push to Hevy.

3. **Deliver.** Run:
   ```
   .venv/bin/python -m scripts.review.draft_next_block notify
   ```
   This renders the draft to a Google Sheet, sends the Telegram heads-up with the Sheet URL,
   and commits the draft to the `draft/next-block` branch.

Keep it provisional. The athlete reviews it during W5 and finalizes after the block review.
