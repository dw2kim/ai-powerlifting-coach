# Back Checks

> **Twice a week, not daily.** The morning after every squat or sumo session — so Tuesday
> and Saturday while B5 runs squat on D1 and sumo on D4. One word for how the back feels:
> **fine · tight · sore**. That's the whole ask. Nothing to log on the other five days.
>
> It's tied to a *session*, not to a calendar. That's the entire point: it answers "did
> loading the back on Monday leave a mark?", which a general "how's your back this week?"
> cannot. If a block ever runs three axial days, it's three checks; if axial work stops,
> it's zero.
>
> It exists because the anesthetic makes the in-session signal useless. RPE and the ≤3/10
> pain rule can't protect a chemically quiet back, so the morning after is the only honest
> read either of us gets. **No check, no progression** — the axial loads don't move without it.
>
> It also answers *your* question. You think the injections might be making things worse;
> the doctor stepped you down because he thinks you're improving. Those are different
> stories and only one of them is being tested. Off-weeks are chemically clean, so comparing
> off-week checks against injection-week checks is what settles it. That comparison needs
> maybe ten of these rows before it says anything.

## How to log one

Tell me ("back was tight this morning") and I'll write the row. Or do it yourself:

```bash
python -m scripts.review.back_checks add 2026-08-18 fine
```

The date is the **session**, not the morning — the check is the morning after, by
definition. `--note "..."` if there's something worth remembering. To see where you stand:
`python -m scripts.review.back_checks`.

The **Lift** column fills itself in — from the Hevy log if it's synced, otherwise from the
block plan. It reads `unknown` when neither can say (a check on a rest day, or a date
outside the block). That's cosmetic: everything that matters joins on the date, so a check
is never refused just because the log hasn't caught up yet.

## Vocabulary — three words, nothing else

| Word | Means |
|---|---|
| `fine` | Normal. Nothing you'd notice if you weren't asked. |
| `tight` | Stiff, guarded, aware of it — but no pain. |
| `sore` | Painful, or it changed how you moved. **Two in a row and axial work stops.** |

Don't reach for a fourth word or a number. The value is in having the same three words
every time, so a run of them means something.

## Escalation — these are hard stops, not "reduce"

Any one of these: cut squat and sumo entirely and get back to the clinic.

- **`sore` two axial days in a row**
- New or worsening **leg symptoms** — pain, numbness, tingling, weakness below the knee
- **Night pain or pain at rest**
- Pain that **doesn't settle within 24 h**

## ⚠️ Medicated window 2026-09-11 → ~2026-09-30

**apo-baclofen 10 mg BID + pms-pregabalin 25 mg BID**, started on or about **2026-09-11**
(drug names and the end date confirmed by the athlete 2026-09-23 — *"one more week to consume"*).
Checks logged inside it read through medication — **tag the row `medicated`** and do not pool them
with the four unmedicated checks on file. `back_checks.py` splits post-injection from clean by
injection date only; it does not know about this course.

**Baclofen is the one that matters beyond pain.** It lowers muscle tone, which is the same quality
the brace depends on — so it is a reason to hold the axial ceiling regardless of what the check
says. Pregabalin at 25 mg BID is a low starting dose; its masking effect is modest.

## Checks

_The check is the morning after the session date. Newest at the bottom._

| Session date | Lift | Back | Note |
|---|---|---|---|
| 2026-08-28 | sumo | tight | First check ever logged. ~18h post-injection (2026-08-28 shot). On W3 D4 sumo 225. |
| 2026-08-31 | squat | tight | Athlete reported "fine-tight in the middle" — recorded as tight (conservative read of an out-of-vocab word). Clean week, 10d post-injection. Squat 275x5 @6 x4. |
| 2026-09-04 | sumo | tight | Athlete reported "fine-tight in the middle" — same as Sep 1, not escalating. Clean week. Sumo ran 295x3 x3 (prescribed 275). |
| 2026-09-15 | sumo | fine | Athlete reported 'back was not tight this morning' (Sep 16). Recorded fine: an explicit negation of 'tight' after three consecutive tight reads, not the ambiguous 'fine-tight in the middle' of Sep 1/5. Sumo 225x3 x3 @6, ~88h post 09-11 injection, outside the flare window — the clean comparable axial read of W6. |
| 2026-09-22 | squat | tight | MEDICATED ROW - athlete on baclofen 10mg BID + pregabalin 25mg BID. Reported 'a little tight, almost fine' (2026-09-23) - ambiguous, rounds down to tight per standing rule. First check after Korea; session was off-plan squat 275/245/245x3. NOT comparable to the four unmedicated rows. |
