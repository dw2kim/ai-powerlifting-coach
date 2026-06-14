---
name: feedback
description: Log athlete feedback about program/block design and turn the durable parts into enforced rules. Triggers on "feedback:", "the program got X wrong", corrections to suggested loads/progression/exercise selection, or any note about how future blocks should be designed differently.
---

# Logging program-design feedback

This is the athlete's channel for correcting the coach. It feeds future block design.
Two files, two tiers:

- **`feedback/log.md`** — append-only raw record of every piece of feedback.
- **`reference/programming-rules.md`** — the distilled, *active* rules the design skill obeys.

## Procedure

1. **Classify** the feedback by level (one or more):
   - `block` — about a whole block's shape/structure
   - `exercise` — about a specific exercise's selection or fit
   - `load` — about suggested weights / progression rates
   - `general` — a standing programming preference

2. **Ground it in the log if it's about loads/numbers.** Before writing anything, verify
   against the Hevy training log (source of truth):
   `python -m scripts.hevy.block_report --exercise "<name>" --recent <days>`
   Cite the real median/max in the entry. Don't take the remembered number at face value —
   confirm it. (Also catch name mix-ups, e.g. abduction vs adduction.)

3. **Append to `feedback/log.md`** with the dated entry format already in that file:
   date · level(s) · subject · block (if any), the feedback, root cause if it's a system
   bug, actions taken, and `→ rules:` pointing at the rule slug(s) it produces.

4. **Promote durable rules to `reference/programming-rules.md`.** If the feedback implies a
   standing rule (not a one-off), add or update a rule under the right heading
   (Loads & progression / RPE conventions / By-exercise), with a `[FB <date>]` citation back
   to the log. One-off observations stay in the log only.

5. **Fix the root cause when it's a tooling gap.** If the mistake came from how the system
   works (e.g. loads pulled from the sheet instead of the log), fix the tool/skill — a written
   rule alone will recur. Note the fix in the entry.

6. **Commit** both files (and any tooling fix) with a coach-voice message.

## Conventions

- Rules are referenced by stable slugs (e.g. `loads-from-logs`, `accessory-rpe`).
- To change a rule, log new feedback and update the rule — never silently edit the rule; the
  log is the audit trail of why it changed.
- Keep the rules file short and scannable. The log holds the detail.
