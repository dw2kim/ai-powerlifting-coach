# Feedback Log

> Your voice correcting the program design (athlete → coach). Append-only: I add entries
> here when you give feedback, and **promote the durable ones to
> [`reference/programming-rules.md`](../reference/programming-rules.md)**, which the
> block-design skill is bound to consult. Nothing here is ever rewritten.
>
> **Levels:** `block` · `exercise` · `load` · `general`. Tag each entry with one or more.
> Log new feedback via the `feedback` skill (or just tell me).

---

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
