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
| 2026-09-11 | **given** | lower back | anesthetic | W5 D4 (deload). **Confirmed by the athlete 2026-09-23**: *"I did get the same pain trigger point injections a few times. It was pretty similar, just on the lower back."* Same visit produced a 3-week oral course — baclofen 10 mg BID + pregabalin 25 mg BID — see `active-issues.md` → *Visit 2026-09-11*. |

> ⚠️ **2026-09-22 — a masking/CNS source that is not an injection.** An oral course started on or
> about **2026-09-11**: **apo-baclofen 10 mg twice daily** (muscle relaxant) + **pms-pregabalin
> 25 mg twice daily** (gabapentinoid). **Athlete confirmed 2026-09-23 he has one week left → the
> course ends ~2026-09-30.** `back_checks.py` splits post-injection from clean on injection dates
> only and cannot see this, so every check from **2026-09-11 to ~2026-09-30** is a **medicated**
> row and is not comparable to the four clean ones on file. Tag them in `back-checks.md` rather
> than letting them average in. First such row logged: **2026-09-22 (squat) — tight**.

> ⚠️ **Steroid is OFF the table, not merely "next".** This file said from 2026-08-07 that steroid
> was the doctor's next option if the anesthetic course failed. Athlete reported **2026-09-23** that
> the doctor ruled it out, in his words: *"that's going to permanently damage my lower back
> somehow."* ❓ **Unconfirmed wording** — that is his paraphrase, not a quote from the doctor, and
> it is a stronger claim than the usual caution (repeated corticosteroid injections can weaken local
> tendon/soft tissue, which is a reason for limiting them, not a prediction of permanent damage).
> **The decision stands either way and nothing in training changes.** Worth one question at the
> next visit so his understanding matches the clinic's reasoning.

**Shoulder: still none given** — outstanding since 2026-07-07, now three blocks. When one
happens, add it here with site `shoulder`, and `masked-pain-load-cap` starts binding bench and
dip the way it binds squat and sumo.
