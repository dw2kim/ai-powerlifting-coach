"""The next-day back check: capture, compliance gate, and the injection comparison.

Standing order since 2026-07-22 (`sumo-back-cap`, reinforced by `masked-pain-load-cap`):
the morning after every squat or sumo session, record how the back feels — **fine /
tight / sore**. It is the only honest signal while the area is being anesthetized, and
it gates axial progression ("no check, no progression").

It had zero entries across all of B4 and B5 W1 — because there was nowhere to write it.
This module is that place: `brain/daily-checks.md` holds the rows, and everything here
reads them.

What it computes:
  - **compliance** — every axial session in a window, joined to its check (or flagged missing)
  - **escalation** — two "sore" checks in a row stops axial work outright (active-issues.md)
  - **injection comparison** — off-week checks vs injection-week checks. Anesthetic wears
    off in hours and the local flare closes by ~72 h, so an injection-free week is a
    chemically honest read. This is the athlete's own open question — he suspects the
    shots are making things worse — and it is the reason the habit is worth having.

CLI:
    python -m scripts.review.back_checks                      # report on the current block
    python -m scripts.review.back_checks --start .. --end ..  # report on a window
    python -m scripts.review.back_checks add 2026-08-18 fine  # append a check
    python -m scripts.review.back_checks add 2026-08-14 sore --note "injection sites"
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, asdict
from datetime import date as date_cls, timedelta
from pathlib import Path

from ..hevy.block_report import REPO_ROOT, load_window

CHECKS_MD = REPO_ROOT / "brain" / "daily-checks.md"
BLOCK_JSON = REPO_ROOT / "brain" / "current-block.json"

# The three words the standing order uses. Nothing else is a valid status.
STATUSES = ("fine", "tight", "sore")

# The axial lifts the check follows, by the template id the athlete logs under.
AXIAL = {
    "57e29496-c8d7-4f8b-9bca-d1401504cbc8": "squat",
    "dc821ef2-2735-462c-80e8-7cce49aca94b": "squat",   # paused low-bar
    "D20D7BBE": "sumo",
    "6cee736f-103a-4757-bb8d-e10c614ba473": "sumo",    # paused sumo
}

# A trigger-point injection numbs for hours and leaves local soreness for ~24-72 h.
# A check inside that window is reporting the shot, not the back.
FLARE_HOURS = 72

# Checks needed on each side before the injection comparison says anything. Three is
# not statistics — it's the floor below which one bad morning swings the whole answer.
MIN_GROUP = 3

ROW_RE = re.compile(
    r"^\|\s*(?P<date>\d{4}-\d{2}-\d{2})\s*"
    r"\|\s*(?P<lift>squat|sumo|both)\s*"
    r"\|\s*(?P<status>fine|tight|sore)\s*"
    r"\|\s*(?P<note>.*?)\s*\|\s*$",
    re.IGNORECASE,
)


@dataclass
class Check:
    """One next-day back check, keyed on the session it follows."""
    session_date: str   # the squat/sumo session; the check is the morning after
    lift: str           # squat | sumo | both
    status: str         # fine | tight | sore
    note: str = ""

    @property
    def check_date(self) -> str:
        return (date_cls.fromisoformat(self.session_date) + timedelta(days=1)).isoformat()


def load_checks(path: Path = CHECKS_MD) -> list[Check]:
    """Parse the check rows out of brain/daily-checks.md. Unparseable lines are
    ignored on purpose — the file is prose plus a table, and the prose is the point."""
    if not path.exists():
        return []
    out = []
    for line in path.read_text().splitlines():
        m = ROW_RE.match(line.strip())
        if not m:
            continue
        out.append(Check(
            session_date=m.group("date"),
            lift=m.group("lift").lower(),
            status=m.group("status").lower(),
            note=m.group("note").strip(),
        ))
    out.sort(key=lambda c: c.session_date)
    return out


def append_check(session_date: str, status: str, lift: str = "",
                 note: str = "", path: Path = CHECKS_MD) -> Check:
    """Append one check to the table, in date order. `lift` is inferred from the log
    when omitted, so the caller only has to supply the date and the word."""
    date_cls.fromisoformat(session_date)  # validate
    status = status.lower().strip()
    if status not in STATUSES:
        raise ValueError(f"status must be one of {STATUSES}, got {status!r}")
    if not lift:
        found = {s["lift"] for s in axial_sessions(session_date, session_date)}
        if not found:
            raise ValueError(
                f"No squat or sumo session logged on {session_date} — pass an explicit "
                f"lift if the session predates the synced log."
            )
        lift = "both" if len(found) > 1 else found.pop()
    if any(c.session_date == session_date for c in load_checks(path)):
        raise ValueError(f"A check for {session_date} is already logged — edit the row instead.")

    check = Check(session_date, lift, status, note.replace("|", "/"))
    row = f"| {check.session_date} | {check.lift} | {check.status} | {check.note} |"
    lines = path.read_text().splitlines() if path.exists() else []
    # Insert in date order among the existing rows; otherwise append after the header.
    idx = None
    last_row = None
    for i, line in enumerate(lines):
        m = ROW_RE.match(line.strip())
        if not m:
            continue
        last_row = i
        if m.group("date") > check.session_date:
            idx = i
            break
    if idx is None:
        idx = (last_row + 1) if last_row is not None else len(lines)
    lines.insert(idx, row)
    path.write_text("\n".join(lines) + "\n")
    return check


def axial_sessions(start: str, end: str) -> list[dict]:
    """Every squat/sumo session logged in the window, as {date, lift}. One row per
    (date, lift) — a day that trained both gets two."""
    out = []
    for w in load_window(start, end):
        day = (w.get("start_time") or "")[:10]
        lifts = {AXIAL[ex["exercise_template_id"]]
                 for ex in w.get("exercises", [])
                 if ex.get("exercise_template_id") in AXIAL}
        for lift in sorted(lifts):
            out.append({"date": day, "lift": lift})
    out.sort(key=lambda s: (s["date"], s["lift"]))
    return out


def _injection_dates(block: dict | None = None) -> list[dict]:
    """Injection dates for the running block, from current-block.json's `medical`
    key. Absent → no comparison, which is the right answer for a block with no series."""
    if block is None:
        block = json.loads(BLOCK_JSON.read_text()) if BLOCK_JSON.exists() else {}
    med = block.get("medical") or {}
    return med.get("injections") or []


def _in_flare(check_dt: date_cls, injections: list[dict]) -> dict | None:
    """Is this check inside the ~72 h post-injection local-soreness window? If so it
    reports the shot, not the back — that distinction is the whole point of the split."""
    for inj in injections:
        try:
            given = date_cls.fromisoformat(inj["date"])
        except (KeyError, ValueError):
            continue
        if 0 <= (check_dt - given).days <= FLARE_HOURS // 24:
            return inj
    return None


def compliance(start: str, end: str, checks: list[Check] | None = None,
               block: dict | None = None) -> dict:
    """Join every axial session in the window to its check. This is the gate:
    a session with no check is a session that cannot license progression."""
    checks = load_checks() if checks is None else checks
    by_date = {c.session_date: c for c in checks}
    injections = _injection_dates(block)

    rows = []
    for s in axial_sessions(start, end):
        c = by_date.get(s["date"])
        flare = _in_flare(date_cls.fromisoformat(s["date"]) + timedelta(days=1), injections) if c else None
        rows.append({
            "session_date": s["date"],
            "lift": s["lift"],
            "status": c.status if c else None,
            "note": c.note if c else "",
            "logged": c is not None,
            "post_injection": bool(flare),
        })
    # A day that trained both lifts needs one check, not two.
    seen, deduped = set(), []
    for r in rows:
        if r["session_date"] in seen:
            continue
        seen.add(r["session_date"])
        deduped.append(r)

    logged = [r for r in deduped if r["logged"]]
    return {
        "window": {"start": start, "end": end},
        "sessions": deduped,
        "expected": len(deduped),
        "logged": len(logged),
        "missing": [r["session_date"] for r in deduped if not r["logged"]],
        "all_in": bool(deduped) and not any(not r["logged"] for r in deduped),
        "statuses": [r["status"] for r in logged],
    }


def escalation(checks: list[Check] | None = None) -> dict:
    """Two 'sore' checks in a row stops axial work outright — not 'reduce', stop
    (brain/active-issues.md, athlete-override conditions 2026-08-07)."""
    checks = load_checks() if checks is None else checks
    runs = []
    streak: list[Check] = []
    for c in checks:
        if c.status == "sore":
            streak.append(c)
        else:
            if len(streak) >= 2:
                runs.append(streak)
            streak = []
    if len(streak) >= 2:
        runs.append(streak)
    latest = runs[-1] if runs else None
    return {
        "tripped": bool(latest and latest[-1] is checks[-1]),
        "ever_tripped": bool(runs),
        "dates": [c.session_date for c in latest] if latest else [],
    }


def injection_comparison(checks: list[Check] | None = None,
                         block: dict | None = None) -> dict:
    """Off-week checks vs injection-week checks — the athlete's own question.

    If the injection weeks read consistently worse, his suspicion that the shots are
    driving it has evidence and the clinic needs to hear it. If both read the same,
    it is ordinary post-injection soreness, not the back getting worse.
    """
    checks = load_checks() if checks is None else checks
    injections = _injection_dates(block)
    if not injections:
        return {"available": False, "reason": "no injection dates in current-block.json"}

    score = {"fine": 0, "tight": 1, "sore": 2}
    buckets: dict[str, list[Check]] = {"post_injection": [], "clean": []}
    for c in checks:
        key = "post_injection" if _in_flare(date_cls.fromisoformat(c.check_date), injections) else "clean"
        buckets[key].append(c)

    def summarize(group: list[Check]) -> dict:
        if not group:
            return {"n": 0, "mean": None, "counts": {s: 0 for s in STATUSES}}
        return {
            "n": len(group),
            "mean": round(sum(score[c.status] for c in group) / len(group), 2),
            "counts": {s: sum(1 for c in group if c.status == s) for s in STATUSES},
        }

    post, clean = summarize(buckets["post_injection"]), summarize(buckets["clean"])
    verdict = "not enough data"
    if post["n"] >= MIN_GROUP and clean["n"] >= MIN_GROUP:
        delta = post["mean"] - clean["mean"]
        if delta >= 0.5:
            verdict = "injection weeks read worse — tell the clinic"
        elif delta <= -0.5:
            verdict = "injection weeks read better — the treatment is helping"
        else:
            verdict = "no meaningful difference — reads as ordinary post-injection soreness"
    return {
        "available": True,
        "post_injection": post,
        "clean": clean,
        "verdict": verdict,
        "flare_hours": FLARE_HOURS,
    }


def summary(start: str, end: str, block: dict | None = None) -> dict:
    """The blob the weekly review consumes."""
    checks = load_checks()
    return {
        "compliance": compliance(start, end, checks, block),
        "escalation": escalation(checks),
        "injection_comparison": injection_comparison(checks, block),
        "total_logged": len(checks),
    }


def render(summary_blob: dict) -> str:
    comp = summary_blob["compliance"]
    esc = summary_blob["escalation"]
    inj = summary_blob["injection_comparison"]
    lines = [
        f"### Next-day back checks — {comp['window']['start']} → {comp['window']['end']}",
        "",
        f"**{comp['logged']}/{comp['expected']} axial sessions checked.**"
        if comp["expected"] else "No squat or sumo sessions logged in this window.",
        "",
    ]
    for r in comp["sessions"]:
        if r["logged"]:
            mark = {"fine": "🟢", "tight": "🟡", "sore": "🔴"}[r["status"]]
            flare = " *(inside the 72 h post-injection window)*" if r["post_injection"] else ""
            note = f" — {r['note']}" if r["note"] else ""
            lines.append(f"- {mark} **{r['session_date']}** ({r['lift']}) — {r['status']}{note}{flare}")
        else:
            lines.append(f"- ⬜ **{r['session_date']}** ({r['lift']}) — **no check logged**")
    if comp["missing"]:
        lines += ["", f"⚠️ **{len(comp['missing'])} missing.** No check, no progression."]
    if esc["tripped"]:
        lines += ["", f"🚨 **ESCALATION — two 'sore' checks in a row** ({', '.join(esc['dates'])}). "
                      "Axial work stops, not reduces. Back to the clinic."]
    lines.append("")
    if not inj.get("available"):
        lines.append(f"_Injection comparison unavailable: {inj.get('reason')}._")
        return "\n".join(lines)

    p, c = inj["post_injection"], inj["clean"]
    if p["n"] < MIN_GROUP or c["n"] < MIN_GROUP:
        need = max(MIN_GROUP - p["n"], 0), max(MIN_GROUP - c["n"], 0)
        lines.append(
            "**Injection weeks vs clean weeks** — not callable yet: "
            f"{p['n']} post-injection, {c['n']} clean. "
            f"Needs {need[0]} more post-injection and {need[1]} more clean check(s). "
            "This is the comparison that answers whether the shots are making it worse."
        )
    else:
        lines.append(
            "**Injection weeks vs clean weeks** (0=fine, 1=tight, 2=sore): "
            f"post-injection {p['mean']} (n={p['n']}) · clean {c['mean']} (n={c['n']}) "
            f"— {inj['verdict']}"
        )
    return "\n".join(lines)


def _current_block_window(today: date_cls) -> tuple[str, str]:
    block = json.loads(BLOCK_JSON.read_text())
    start = date_cls.fromisoformat(block["start_date"])
    return start.isoformat(), today.isoformat()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd")

    add = sub.add_parser("add", help="Append a back check")
    add.add_argument("session_date", help="Date of the squat/sumo session (YYYY-MM-DD)")
    add.add_argument("status", choices=STATUSES)
    add.add_argument("--lift", default="", choices=["", "squat", "sumo", "both"],
                     help="Inferred from the log when omitted")
    add.add_argument("--note", default="")

    ap.add_argument("--start")
    ap.add_argument("--end")
    ap.add_argument("--date", help="Override 'today'")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if args.cmd == "add":
        c = append_check(args.session_date, args.status, args.lift, args.note)
        print(f"Logged: {c.session_date} ({c.lift}) — {c.status}"
              f"{' — ' + c.note if c.note else ''}  [checked {c.check_date}]")
        return

    today = date_cls.fromisoformat(args.date) if args.date else date_cls.today()
    start, end = (args.start, args.end) if args.start and args.end else _current_block_window(today)
    blob = summary(start, end)
    print(json.dumps(blob, indent=2) if args.json else render(blob))


if __name__ == "__main__":
    main()
