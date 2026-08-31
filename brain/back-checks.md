# Back Checks

> **The morning after every session that loads the back** — squat, sumo, **and (from
> 2026-08-29) every run.** While B5 runs squat on D1 and sumo on D4 and running sits on Wed
> night + Sun daytime, that's four: Tue, Sat, Thu and Mon. One word for how the back feels:
> **fine · tight · sore**. That's the whole ask. Nothing to log on the other days.
>
> **Running counts because repetitive axial impact is real loading** on a spine under treatment,
> and it's a brand-new stimulus with no history in this file. See `brain/running-comeback.md` —
> **the knee is tracked separately**, in that file's session log, not here. This file stays
> about the back and keeps its three words.
>
> It's tied to a *session*, not to a calendar. That's the entire point: it answers "did
> loading the back on Monday leave a mark?", which a general "how's your back this week?"
> cannot. If a block ever runs three axial days, it's three checks; if axial work stops,
> it's zero. Adding running added two.
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

## Checks

_The check is the morning after the session date. Newest at the bottom._

| Session date | Lift | Back | Note |
|---|---|---|---|
