# Feedback Log

> Your voice correcting the program design (athlete → coach). Append-only: I add entries
> here when you give feedback, and **promote the durable ones to
> [`reference/programming-rules.md`](../reference/programming-rules.md)**, which the
> block-design skill is bound to consult. Nothing here is ever rewritten.
>
> **Levels:** `block` · `exercise` · `load` · `general`. Tag each entry with one or more.
> Log new feedback via the `feedback` skill (or just tell me).

---

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
