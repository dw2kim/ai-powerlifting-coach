"""Compute the weekly training review numbers from the Hevy log.

Everything here is deterministic — the Hevy session JSON (source of truth) plus the
block plan in brain/current-block.json. The coach-voice narrative is written
separately (narrate.py) from this blob; the chart is drawn from it (render_chart.py).

Produces, for the current block + week:
  - block/week geometry and a data-readiness check (did the expected days get logged?)
  - this week's Big-5 top working sets (load x reps @rpe, e1RM) + plan + RPE-cap flags
  - this week's accessories (planned vs logged)
  - block-to-date e1RM per Big-5 per week (drives the chart trend lines)
  - a long-term e1RM series per Big-5 (drives the cross-block progress panel)

CLI: `python -m scripts.review.weekly_metrics [--date YYYY-MM-DD] [--bw 180]`
prints the blob as JSON.
"""
from __future__ import annotations

import argparse
import glob
import json
from datetime import date as date_cls, timedelta
from pathlib import Path

from ..hevy.block_report import (
    DEFAULT_BW,
    KG_TO_LBS,
    LIFTS,
    REPO_ROOT,
    SESSIONS_DIR,
    e1rm,
)
from ..hevy.exercise_map import OVERRIDES, Resolver, _normalize

BLOCK_JSON = REPO_ROOT / "brain" / "current-block.json"

# The Big-5 primaries, in coaching priority order, by the template id the athlete
# actually logs under (same ids as block_report.LIFTS). is_bw → add bodyweight.
PRIMARIES = [
    ("squat", "Low-bar Squat", "57e29496-c8d7-4f8b-9bca-d1401504cbc8", False),
    ("bench", "Comp Bench", "d8218be2-977f-4000-ac42-66cb11986863", False),
    ("sumo", "Sumo Deadlift", "D20D7BBE", False),
    ("wpu", "Weighted Pull-up", "729237D1", True),
    ("dip", "Weighted Dip", "10347BAC", True),
]
# Plan lookup: primary key → the exercise `name` used in current-block.json prescriptions.
PLAN_NAME = {
    "squat": "Low-bar Squat",
    "bench": "Comp Bench",
    "sumo": "Sumo Deadlift",
    "wpu": "Weighted Pull-up",
    "dip": "Weighted Dip",
}
PRIMARY_NAMES = {name for _, name, _, _ in PRIMARIES}

# Canonical training-day → weekday (Mon=0). D1 Mon · D2 Tue · D3 Thu · D4 Fri.
# Authoritative per current-block.md (commit 960b05e); the JSON `days` weekday field
# is advisory. D4 occasionally slips to Saturday — handled in _label_for_weekday.
DAY_WEEKDAY = {"D1": 0, "D2": 1, "D3": 3, "D4": 4}


def _load_block() -> dict:
    return json.loads(BLOCK_JSON.read_text())


def _safe_resolver():
    """Return a name→template_id lookup. Falls back to a no-op (returns None) if the
    template cache is missing, so accessory matching degrades gracefully."""
    try:
        resolver = Resolver()
    except Exception:
        return lambda name: None

    def resolve(name: str):
        try:
            return resolver.resolve(name)
        except KeyError:
            return None

    return resolve


def _index_exercises(sessions: list[dict]) -> list[dict]:
    """Flatten a window's exercises with normalized title, tokens, template id, and
    session date attached — the lookup table the accessory matcher walks."""
    index = []
    for w in sessions:
        date = (w.get("start_time") or "")[:10]
        for ex in w.get("exercises", []):
            title = ex.get("title") or ""
            ex = {**ex, "_date": date}
            index.append({
                "title_norm": _normalize(title),
                "tokens": set(_normalize(title).split()),
                "tid": ex.get("exercise_template_id"),
                "ex": ex,
            })
    return index


def _match_accessory(name: str, index: list[dict], resolver) -> dict | None:
    """Find the logged exercise for an accessory name. Priority: exact title (raw
    name), exact title (OVERRIDES alias), template id, then strict token-subset."""
    name_norm = _normalize(name)
    alias_norm = _normalize(OVERRIDES.get(name_norm, ""))
    for entry in index:
        if entry["title_norm"] == name_norm:
            return entry["ex"]
    if alias_norm:
        for entry in index:
            if entry["title_norm"] == alias_norm:
                return entry["ex"]
    tid = resolver(name)
    if tid:
        for entry in index:
            if entry["tid"] == tid:
                return entry["ex"]
    name_tokens = set(name_norm.split())
    for entry in index:
        if name_tokens and name_tokens.issubset(entry["tokens"]):
            return entry["ex"]
    return None


def _best_working_set(ex: dict, is_bw: bool, bw: float) -> dict | None:
    """Heaviest non-warmup set in an exercise block, by e1RM."""
    best = None
    for s in ex.get("sets", []):
        if s.get("type") == "warmup":
            continue
        wt, reps = s.get("weight_kg"), s.get("reps")
        if wt is None or reps is None or reps == 0:
            continue
        lbs = round(wt * KG_TO_LBS, 1)
        total = lbs + bw if is_bw else lbs
        est = e1rm(total, reps)
        cand = {
            "added_lb": lbs,
            "reps": reps,
            "rpe": s.get("rpe"),
            "e1rm": round(est, 1),
            "is_bw": is_bw,
        }
        if best is None or cand["e1rm"] > best["e1rm"]:
            best = cand
    return best


def _sessions_in(start: str, end: str) -> list[dict]:
    out = []
    for p in glob.glob(str(SESSIONS_DIR / "*.json")):
        w = json.load(open(p))
        st = (w.get("start_time") or "")[:10]
        if start <= st <= end:
            out.append(w)
    out.sort(key=lambda w: w.get("start_time") or "")
    return out


def _best_for_template(sessions: list[dict], tid: str, is_bw: bool, bw: float) -> dict | None:
    """Best working set for a template id across a set of sessions, with the date
    and the athlete's exercise note attached."""
    best = None
    for w in sessions:
        date = (w.get("start_time") or "")[:10]
        for ex in w.get("exercises", []):
            if ex.get("exercise_template_id") != tid:
                continue
            bs = _best_working_set(ex, is_bw, bw)
            if bs and (best is None or bs["e1rm"] > best["e1rm"]):
                best = {**bs, "date": date, "notes": (ex.get("notes") or "").strip()}
    return best


def _label_for_weekday(wd: int, taken: set) -> str | None:
    """Map a session's weekday to a D-label. Saturday (5) folds into D4 when D4
    hasn't already been logged Friday — covers the documented Fri→Sat slip."""
    label = next((d for d, w in DAY_WEEKDAY.items() if w == wd), None)
    if label is None and wd == 5 and "D4" not in taken:
        label = "D4"
    return label


def fmt_load(added_lb: float, is_bw: bool) -> str:
    return f"BW+{added_lb:g}" if is_bw else f"{added_lb:g}"


def _planned_top(block: dict, week: int, name: str, is_bw: bool, bw: float) -> dict | None:
    """The planned top set for a lift in a given week (first set of the first
    prescription block matching the name), in lbs."""
    for presc in block.get("prescriptions", []):
        if presc.get("week") != week:
            continue
        for ex in presc.get("exercises", []):
            if ex.get("name") != name:
                continue
            sets = ex.get("sets", [])
            if not sets:
                return None
            top = sets[0]
            wt, reps = top.get("weight_kg"), top.get("reps")
            if wt is None:
                return None
            lbs = round(wt * KG_TO_LBS, 1)
            return {
                "added_lb": lbs,
                "reps": reps,
                "rpe": top.get("rpe"),
                "is_bw": is_bw,
                "notes": (ex.get("notes") or "").strip(),
            }
    return None


def geometry(block: dict, today: date_cls) -> dict:
    """Block week number, this week's Mon–Sun window, and which days are expected
    to be done by `today`."""
    weeks = block.get("weeks", 0)
    start = block.get("start_date")
    if not start:
        raise ValueError("current-block.json missing start_date (W1 Monday).")
    start_d = date_cls.fromisoformat(start)
    days_elapsed = (today - start_d).days
    week_no = max(1, min(weeks, days_elapsed // 7 + 1))
    week_mon = start_d + timedelta(days=(week_no - 1) * 7)
    week_sun = week_mon + timedelta(days=6)
    expected = [d for d, wd in DAY_WEEKDAY.items() if wd <= today.weekday()] \
        if week_mon <= today <= week_sun else list(DAY_WEEKDAY)
    return {
        "block_id": block.get("block_id"),
        "weeks": weeks,
        "week_no": week_no,
        "week_start": week_mon.isoformat(),
        "week_end": week_sun.isoformat(),
        "expected_days": expected,
    }


def readiness(week_sessions: list[dict], expected_days: list[str]) -> dict:
    """Which expected training days have a logged session, and any sets missing RPE."""
    taken: set = set()
    by_label: dict[str, str] = {}
    for w in week_sessions:
        wd = date_cls.fromisoformat((w.get("start_time") or "")[:10]).weekday()
        label = _label_for_weekday(wd, taken)
        if label:
            taken.add(label)
            by_label[label] = (w.get("start_time") or "")[:10]
    missing = [d for d in expected_days if d not in taken]
    # A Big-5 *top* set logged this week without an RPE = a real data gap to flag.
    # (Backoff sets are often logged without RPE — only the working top matters.)
    rpe_gaps = []
    for w in week_sessions:
        for ex in w.get("exercises", []):
            tid = ex.get("exercise_template_id")
            if tid not in LIFTS:
                continue
            best = _best_working_set(ex, LIFTS[tid][1], 0.0)
            if best and best["rpe"] is None:
                rpe_gaps.append(LIFTS[tid][0])
    return {
        "expected": expected_days,
        "logged": sorted(taken, key=lambda d: DAY_WEEKDAY[d]),
        "logged_dates": by_label,
        "missing": missing,
        "all_in": not missing,
        "rpe_gaps": sorted(set(rpe_gaps)),
    }


def build_stats(today: date_cls | None = None, bw: float = DEFAULT_BW) -> dict:
    today = today or date_cls.today()
    block = _load_block()
    geo = geometry(block, today)
    week_no = geo["week_no"]
    week_sessions = _sessions_in(geo["week_start"], geo["week_end"])

    # --- This week: Big-5 actual vs plan, with RPE-cap flags ---
    big5 = []
    for key, name, tid, is_bw in PRIMARIES:
        actual = _best_for_template(week_sessions, tid, is_bw, bw)
        plan = _planned_top(block, week_no, PLAN_NAME[key], is_bw, bw)
        flag = "none"
        if actual and plan and actual.get("rpe") is not None and plan.get("rpe") is not None:
            over = actual["rpe"] - plan["rpe"]
            if over >= 1:
                flag = "hot"          # 1+ RPE over plan
            elif over >= 0.5:
                flag = "warm"         # drifting over cap
            elif actual["rpe"] <= plan["rpe"]:
                flag = "on"
        big5.append({
            "key": key, "name": name, "is_bw": is_bw,
            "actual": actual, "plan": plan, "rpe_flag": flag,
        })

    # --- This week: accessories (planned vs logged) ---
    # Athletes log some accessories under custom titles (e.g. "Paused RDL") and
    # others under Hevy stock titles. Match in priority order: raw name, the
    # OVERRIDES title, the resolved template id, then a strict token-subset — so
    # both custom and stock logging are caught without "Press" token collisions.
    week_index = _index_exercises(week_sessions)
    resolver = _safe_resolver()
    accessories = []
    seen_acc = set()
    for presc in block.get("prescriptions", []):
        if presc.get("week") != week_no:
            continue
        for ex in presc.get("exercises", []):
            name = ex.get("name", "")
            if name in PRIMARY_NAMES or name in ("Paused Low-bar Squat", "CGB"):
                continue  # primaries + tracked variants handled elsewhere
            if name in seen_acc:
                continue
            seen_acc.add(name)
            match = _match_accessory(name, week_index, resolver)
            actual = _best_working_set(match, False, bw) if match else None
            if actual:
                actual["date"] = (match.get("_date") or "")
            accessories.append({
                "name": name,
                "logged": actual is not None,
                "actual": actual,
            })

    # --- Block-to-date: best e1RM per Big-5 per week (chart trend lines) ---
    by_week = {}
    for w in range(1, week_no + 1):
        mon = date_cls.fromisoformat(block["start_date"]) + timedelta(days=(w - 1) * 7)
        sessions = _sessions_in(mon.isoformat(), (mon + timedelta(days=6)).isoformat())
        row = {}
        for key, _name, tid, is_bw in PRIMARIES:
            best = _best_for_template(sessions, tid, is_bw, bw)
            row[key] = best["e1rm"] if best else None
        by_week[w] = row

    # --- Long-term: best e1RM per Big-5 per calendar month, last ~6 months ---
    longterm = {key: [] for key, *_ in PRIMARIES}
    horizon = (today - timedelta(days=190)).isoformat()
    all_recent = _sessions_in(horizon, today.isoformat())
    monthly: dict = {key: {} for key, *_ in PRIMARIES}
    for w in all_recent:
        month = (w.get("start_time") or "")[:7]
        for key, _name, tid, is_bw in PRIMARIES:
            for ex in w.get("exercises", []):
                if ex.get("exercise_template_id") != tid:
                    continue
                bs = _best_working_set(ex, is_bw, bw)
                if bs:
                    cur = monthly[key].get(month)
                    if cur is None or bs["e1rm"] > cur:
                        monthly[key][month] = bs["e1rm"]
    for key in monthly:
        longterm[key] = [
            {"month": m, "e1rm": v} for m, v in sorted(monthly[key].items())
        ]

    return {
        "generated_for": today.isoformat(),
        "bodyweight": bw,
        "geometry": geo,
        "readiness": readiness(week_sessions, geo["expected_days"]),
        "big5": big5,
        "accessories": accessories,
        "block_to_date": by_week,
        "longterm": longterm,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="Override 'today' (YYYY-MM-DD)")
    ap.add_argument("--bw", type=float, default=DEFAULT_BW)
    args = ap.parse_args()
    today = date_cls.fromisoformat(args.date) if args.date else None
    print(json.dumps(build_stats(today, args.bw), indent=2))


if __name__ == "__main__":
    main()
