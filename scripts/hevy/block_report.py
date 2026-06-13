"""Extract Big-5 actuals from the Hevy log for a date window.

The Hevy training log (data/logs/sessions/*.json) is the source of truth — the
Google Sheets are the athlete's planning surface, not authoritative for what was
lifted. This tool pulls, per Big-5 lift, the heaviest working set each session
plus the window's best e1RM, so a block review is grounded in real numbers.

Usage:
  python -m scripts.hevy.block_report --start 2026-03-09 --end 2026-04-17
  python -m scripts.hevy.block_report --start 2026-04-20 --end 2026-05-13 --md

Lifts are matched by Hevy exercise_template_id (stable) — not day labels, which
go stale in the app. Bodyweight for pull-up/dip e1RM defaults to 180 lb.
"""
from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SESSIONS_DIR = REPO_ROOT / "data" / "logs" / "sessions"
KG_TO_LBS = 2.2046226218
DEFAULT_BW = 180.0

# Big-5 + key variants, by template id (the IDs the athlete actually logs under —
# verified against the live log, not Hevy stock defaults). BW lifts add BW to bar load.
LIFTS = {
    "57e29496-c8d7-4f8b-9bca-d1401504cbc8": ("Low-bar Squat", False),
    "dc821ef2-2735-462c-80e8-7cce49aca94b": ("Paused Low-bar Squat", False),
    "79D0BB3A": ("Comp Bench", False),
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


def analyze(start: str, end: str, bw: float = DEFAULT_BW) -> dict:
    sessions = load_window(start, end)
    per_lift: dict[str, list[dict]] = {name: [] for name, _ in LIFTS.values()}
    for w in sessions:
        date = (w.get("start_time") or "")[:10]
        for ex in w.get("exercises", []):
            tid = ex.get("exercise_template_id")
            if tid not in LIFTS:
                continue
            name, is_bw = LIFTS[tid]
            # heaviest non-warmup set this session
            best = None
            for s in ex.get("sets", []):
                if s.get("type") == "warmup":
                    continue
                wt = s.get("weight_kg")
                reps = s.get("reps")
                if wt is None or reps is None:
                    continue
                lbs = round(wt * KG_TO_LBS, 1)
                total = lbs + bw if is_bw else lbs
                est = e1rm(total, reps)
                cand = {
                    "date": date,
                    "added_lb": lbs,
                    "reps": reps,
                    "rpe": s.get("rpe"),
                    "e1rm": round(est, 1),
                    "is_bw": is_bw,
                }
                if best is None or cand["e1rm"] > best["e1rm"]:
                    best = cand
            if best:
                per_lift[name].append(best)
    return {"sessions": len(sessions), "per_lift": per_lift}


def fmt_set(s: dict) -> str:
    load = f"BW+{s['added_lb']:g}" if s["is_bw"] else f"{s['added_lb']:g}"
    rpe = f"@{s['rpe']}" if s["rpe"] is not None else "@—"
    return f"{load}x{s['reps']} {rpe} (e1RM {s['e1rm']:g})"


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
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--bw", type=float, default=DEFAULT_BW)
    ap.add_argument("--md", action="store_true", help="Markdown output")
    args = ap.parse_args()
    result = analyze(args.start, args.end, args.bw)
    if args.md:
        print(render_md(args.start, args.end, result))
    else:
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
