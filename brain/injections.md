# Injections

> The pain-clinic trigger-point series, as dates. **This file outlives blocks** — the series
> started 2026-07-03, ran through all of B4 and into B5, and is still going. That's why it
> doesn't live in `current-block.json`: a block-scoped list silently loses its history the
> moment the next block starts, which would corrupt the one comparison it exists to feed.
>
> Read by `scripts/review/back_checks.py` to split back checks into **post-injection** (within
> ~72 h of a shot — local soreness, reports the shot rather than the back) and **clean**
> (chemically honest). Maintained by the `logging-clinical-update` skill.
>
> **Agent: local anesthetic only** — confirmed 2026-08-14. This was recorded as corticosteroid
> from 2026-07-06 until then and that was wrong throughout. Steroid is the doctor's next option
> if this course fails. Clinical detail and the training consequences live in
> `brain/active-issues.md`; this file is just the timeline.

| Date | Status | Site | Agent | Note |
|---|---|---|---|---|
| 2026-07-03 | given | lower back | anesthetic | First round, ~8 sites mid-left. |
| 2026-07-10 | given | lower back | anesthetic | |
| 2026-07-16 | given | lower back | anesthetic | Thu 11:50am. |
| 2026-08-07 | given | lower back | anesthetic | 4–5 sites. Doctor ordered 4 weeks off heavy lifting. No shoulder injection. |
| 2026-08-14 | given | lower back | anesthetic | Stepped down weekly → bi-weekly. Agent confirmed anesthetic only. |
| 2026-08-28 | given | lower back | anesthetic | W3 D4. Trained 6–7am, before the shot. **Pain much improved. Doctor cleared a graded load increase — "start with a 25% weight increase and see how it goes."** Supersedes the 4-week no-heavy order. |
| 2026-09-11 | ❓ **visit happened, shot UNCONFIRMED** | lower back | anesthetic | W5 D4 (deload). Visit reported 2026-09-22: *"all good, doctor said I'm doing great"* — but he described **a prescription, not a shot**, and was not asked. **Do not count this row as given until confirmed.** Same visit produced a ~3-week course of analgesia + muscle relaxant — see `active-issues.md` → *Visit 2026-09-11*. |

> ⚠️ **2026-09-22 — a new masking source that is not an injection.** A ~3-week oral course (pain +
> muscle relaxant) started on or about **2026-09-11**. It masks the back continuously, not for hours,
> so `back_checks.py`'s post-injection/clean split does **not** capture it — every check from
> 2026-09-11 to ~2026-10-02 is a **medicated** row and is not comparable to the four clean ones on
> file. Tag them in `back-checks.md` rather than letting them average in.

**Shoulder: still none given** — outstanding since 2026-07-07, now three blocks. When one
happens, add it here with site `shoulder`, and `masked-pain-load-cap` starts binding bench and
dip the way it binds squat and sumo.
