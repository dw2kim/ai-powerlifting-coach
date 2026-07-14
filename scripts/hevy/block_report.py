"""Extract Big-5 actuals from the Hevy log for a date window.

The Hevy training log (data/logs/sessions/*.json) is the source of truth — the
Google Sheets are the athlete's planning surface, not authoritative for what was
lifted. This tool pulls, per Big-5 lift, the heaviest working set each session
plus the window's best e1RM, so a block review is grounded in real numbers.

Usage:
  # Big-5 window report (for block reviews):
  python -m scripts.hevy.block_report --start 2026-03-09 --end 2026-04-17 --md

  # Recent working load for ANY exercise (for block design — base loads on logs):
  python -m scripts.hevy.block_report --exercise "Hip Abduction" --recent 90

Lifts are matched by Hevy exercise_template_id (stable) — not day labels, which
go stale in the app. Bodyweight for pull-up/dip e1RM defaults to 180 lb.

Rep-sanity guard: a working set above --rep-ceiling reps (default 20) is a mis-log — a
trailing-digit slip like 5 -> 50. The report AUTO-CORRECTS it: the intended rep count is
inferred from the plausible same-weight sibling sets that session (e.g. a 195x50 sitting
next to three 195x5 sets is read as 195x5), the corrected set is used in the numbers, and
the fix is surfaced under `corrected`. Only when there is no confident same-weight sibling
to infer from is the set instead EXCLUDED and surfaced under `flagged`. Raw JSON is left
untouched (it mirrors Hevy, the source of truth); correction happens at read time.
"""
from __future__ import annotations

import argparse
import glob
import json
import statistics
from collections import Counter
from datetime import date as date_cls, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SESSIONS_DIR = REPO_ROOT / "data" / "logs" / "sessions"
KG_TO_LBS = 2.2046226218
DEFAULT_BW = 180.0

# A working set above this many reps on a tracked Big-5 lift is almost certainly a
# logging slip — a trailing-digit mis-punch (e.g. 5 -> 50), not a real set. Across the
# entire Hevy history the only legit set above 12 reps is a single 20-rep squat rep-out;
# heavy SBD / weighted-pull-up / dip work never goes higher. A phantom high-rep set also
# poisons every e1RM-based number: 195x50 Epleys to ~520 lb and would silently win "best
# e1RM" over a real 266 comp-bench max. Rather than drop the set, the report CORRECTS it
# from its same-weight sibling sets (see infer_reps); a set only gets excluded when it
# can't be confidently inferred. Raise via --rep-ceiling for genuine high-rep protocols.
REP_CEILING = 20


def implausible_reps(reps, ceiling: int = REP_CEILING) -> bool:
    """True if a rep count is too high to be a real set on a tracked strength lift."""
    return reps is not None and reps > ceiling


def infer_reps(target_lbs: float, working_sets: list[dict],
               ceiling: int = REP_CEILING) -> int | None:
    """Best guess for a mis-logged set's intended reps, from its plausible siblings.

    Strength backoff/top schemes hold reps constant at a given weight, so the other
    working sets at the *same weight* that session are the ground truth: 195x50 sitting
    among three 195x5 sets was meant to be 195x5. Returns the most common plausible rep
    count at `target_lbs`, or None if there's no plausible same-weight sibling to trust
    (in which case the caller excludes rather than guesses).
    """
    same_weight = [
        s["reps"] for s in working_sets
        if round(s["weight_kg"] * KG_TO_LBS, 1) == target_lbs
        and s["reps"] is not None and not implausible_reps(s["reps"], ceiling)
    ]
    if not same_weight:
        return None
    return Counter(same_weight).most_common(1)[0][0]

# Big-5 + key variants, by template id (the IDs the athlete actually logs under —
# verified against the live log, not Hevy stock defaults). BW lifts add BW to bar load.
LIFTS = {
    "57e29496-c8d7-4f8b-9bca-d1401504cbc8": ("Low-bar Squat", False),
    "dc821ef2-2735-462c-80e8-7cce49aca94b": ("Paused Low-bar Squat", False),
    # Comp bench = the athlete's custom "POWER Bench Press" template (not Hevy stock).
    "d8218be2-977f-4000-ac42-66cb11986863": ("Comp Bench (POWER)", False),
    "35B51B87": ("Close-Grip Bench", False),
    "74dfcc13-02b2-4eef-95f3-5abf04a2702b": ("Spoto Bench", False),
    "8cd95bf6-daeb-4ca4-b5d1-6ed447248828": ("Paused Larsen Bench", False),
    "D20D7BBE": ("Sumo Deadlift", False),
    "6cee736f-103a-4757-bb8d-e10c614ba473": ("Paused Sumo Deadlift", False),
    "729237D1": ("Weighted Pull-up", True),
    "10347BAC": ("Weighted Dip", True),
}


def e1rm(weight_lb: float, reps: int) -> float:
    """Epley."""
    return weight_lb * (1 + reps / 30.0)


def load_window(start: str, end: str) -> list[dict]:
    out = []
    for p in glob.glob(str(SESSIONS_DIR / "*.json")):
        w = json.load(open(p))
        st = (w.get("start_time") or "")[:10]
        if start <= st <= end:
            out.append(w)
    out.sort(key=lambda w: w.get("start_time") or "")
    return out


def analyze(start: str, end: str, bw: float = DEFAULT_BW,
            rep_ceiling: int = REP_CEILING) -> dict:
    sessions = load_window(start, end)
    per_lift: dict[str, list[dict]] = {name: [] for name, _ in LIFTS.values()}
    flagged: list[dict] = []
    corrected: list[dict] = []
    for w in sessions:
        date = (w.get("start_time") or "")[:10]
        for ex in w.get("exercises", []):
            tid = ex.get("exercise_template_id")
            if tid not in LIFTS:
                continue
            name, is_bw = LIFTS[tid]
            working = [s for s in ex.get("sets", [])
                       if s.get("type") != "warmup"
                       and s.get("weight_kg") is not None and s.get("reps") is not None]
            # heaviest non-warmup set this session
            best = None
            for s in working:
                lbs = round(s["weight_kg"] * KG_TO_LBS, 1)
                reps = s["reps"]
                # A mis-punched rep count (e.g. 5 -> 50) would Epley to a phantom PR. Read
                # the intended value off the same-weight sibling sets and use that; only
                # exclude when there's no sibling to infer from.
                if implausible_reps(reps, rep_ceiling):
                    fixed = infer_reps(lbs, working, rep_ceiling)
                    if fixed is None:
                        flagged.append({
                            "date": date, "lift": name, "added_lb": lbs, "reps": reps,
                            "rpe": s.get("rpe"), "is_bw": is_bw,
                        })
                        continue
                    corrected.append({
                        "date": date, "lift": name, "added_lb": lbs,
                        "reps_logged": reps, "reps_corrected": fixed,
                        "rpe": s.get("rpe"), "is_bw": is_bw,
                    })
                    reps = fixed
                total = lbs + bw if is_bw else lbs
                cand = {
                    "date": date,
                    "added_lb": lbs,
                    "reps": reps,
                    "rpe": s.get("rpe"),
                    "e1rm": round(e1rm(total, reps), 1),
                    "is_bw": is_bw,
                }
                if best is None or cand["e1rm"] > best["e1rm"]:
                    best = cand
            if best:
                per_lift[name].append(best)
    return {"sessions": len(sessions), "per_lift": per_lift,
            "corrected": corrected, "flagged": flagged}


def recent_loads(name: str, days: int = 90, bw: float = DEFAULT_BW,
                 end: str | None = None, rep_ceiling: int = REP_CEILING) -> dict:
    """Recent top working set per session for ONE exercise (resolved by name).

    For block design: answers "what does the athlete currently train X at?" so
    suggested loads come from the log, not a guess. Reports each session's
    heaviest non-warmup set plus the median working load (the number to anchor
    the next block's prescription on).
    """
    # Local import avoids a hard dependency on the API/.env for the Big-5 mode.
    from .exercise_map import Resolver

    tid = Resolver().resolve(name)
    end = end or date_cls.today().isoformat()
    start = (date_cls.fromisoformat(end) - timedelta(days=days)).isoformat()
    is_bw = LIFTS.get(tid, (None, False))[1]

    rows = []
    flagged: list[dict] = []
    corrected: list[dict] = []
    for w in load_window(start, end):
        date = (w.get("start_time") or "")[:10]
        for ex in w.get("exercises", []):
            if ex.get("exercise_template_id") != tid:
                continue
            working = [s for s in ex.get("sets", [])
                       if s.get("type") != "warmup" and s.get("weight_kg") is not None]
            best = None
            for s in working:
                reps = s.get("reps")
                lbs = round(s["weight_kg"] * KG_TO_LBS, 1)
                if implausible_reps(reps, rep_ceiling):
                    fixed = infer_reps(lbs, working, rep_ceiling)
                    if fixed is None:
                        flagged.append({"date": date, "lift": name, "added_lb": lbs,
                                        "reps": reps, "rpe": s.get("rpe"), "is_bw": is_bw})
                        continue
                    corrected.append({"date": date, "lift": name, "added_lb": lbs,
                                      "reps_logged": reps, "reps_corrected": fixed,
                                      "rpe": s.get("rpe"), "is_bw": is_bw})
                    reps = fixed
                if best is None or lbs > best["added_lb"]:
                    best = {"date": date, "added_lb": lbs, "reps": reps,
                            "rpe": s.get("rpe"), "is_bw": is_bw}
            if best:
                rows.append(best)
    loads = [r["added_lb"] for r in rows]
    return {
        "exercise": name,
        "template_id": tid,
        "window": f"{start} → {end}",
        "sessions": len(rows),
        "median_load": round(statistics.median(loads), 1) if loads else None,
        "max_load": max(loads) if loads else None,
        "recent": rows[-8:],
        "corrected": corrected,
        "flagged": flagged,
    }


def fmt_set(s: dict) -> str:
    load = f"BW+{s['added_lb']:g}" if s["is_bw"] else f"{s['added_lb']:g}"
    rpe = f"@{s['rpe']}" if s["rpe"] is not None else "@—"
    return f"{load}x{s['reps']} {rpe} (e1RM {s['e1rm']:g})"


def _load_str(row: dict) -> str:
    return f"BW+{row['added_lb']:g}" if row["is_bw"] else f"{row['added_lb']:g}"


def fmt_flag(f: dict) -> str:
    rpe = f"@{f['rpe']}" if f["rpe"] is not None else "@—"
    return f"{f['date']} · {f['lift']} · {_load_str(f)}x{f['reps']} {rpe}"


def fmt_correction(c: dict) -> str:
    rpe = f"@{c['rpe']}" if c["rpe"] is not None else "@—"
    load = _load_str(c)
    return (f"{c['date']} · {c['lift']} · {load}x{c['reps_logged']} → "
            f"{load}x{c['reps_corrected']} {rpe}")


def render_md(start: str, end: str, result: dict) -> str:
    lines = [f"### Big-5 actuals (Hevy) — {start} → {end}", ""]
    lines.append(f"_{result['sessions']} sessions in window._")
    lines.append("")
    for name, _ in LIFTS.values():
        rows = result["per_lift"].get(name, [])
        if not rows:
            continue
        best = max(rows, key=lambda r: r["e1rm"])
        lines.append(f"**{name}** — best e1RM {best['e1rm']:g} lb ({fmt_set(best)})")
        prog = " · ".join(fmt_set(r) for r in rows)
        lines.append(f"  - {prog}")
        lines.append("")
    corrected = result.get("corrected", [])
    if corrected:
        lines.append(f"> ✏️ **{len(corrected)} mis-logged rep count(s) auto-corrected** "
                     f"(reps > {REP_CEILING}) from same-weight sibling sets — used as "
                     f"corrected in the numbers above:")
        for c in corrected:
            lines.append(f">   - {fmt_correction(c)}")
        lines.append("")
    flagged = result.get("flagged", [])
    if flagged:
        lines.append(f"> ⚠️ **{len(flagged)} suspected mis-logged set(s)** "
                     f"(reps > {REP_CEILING}, no same-weight sibling to infer from) — "
                     f"excluded from the numbers. Fix the reps in Hevy, then re-sync:")
        for f in flagged:
            lines.append(f">   - {fmt_flag(f)}  ← check reps")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", help="Window start (Big-5 mode)")
    ap.add_argument("--end", help="Window end (Big-5 mode); default today in --exercise mode")
    ap.add_argument("--exercise", help="Recent working load for one exercise (by name)")
    ap.add_argument("--recent", type=int, default=90, help="Lookback days for --exercise")
    ap.add_argument("--bw", type=float, default=DEFAULT_BW)
    ap.add_argument("--rep-ceiling", type=int, default=REP_CEILING,
                    help="Working sets above this many reps are treated as mis-logs and "
                         f"auto-corrected from same-weight siblings (default {REP_CEILING})")
    ap.add_argument("--md", action="store_true", help="Markdown output (Big-5 mode)")
    args = ap.parse_args()

    if args.exercise:
        result = recent_loads(args.exercise, args.recent, args.bw, args.end,
                              args.rep_ceiling)
        print(json.dumps(result, indent=2))
        return

    if not (args.start and args.end):
        ap.error("Big-5 mode needs --start and --end (or use --exercise)")
    result = analyze(args.start, args.end, args.bw, args.rep_ceiling)
    if args.md:
        print(render_md(args.start, args.end, result))
    else:
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
