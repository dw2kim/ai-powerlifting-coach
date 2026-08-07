"""Reconcile the live block's prescribed loads against the Hevy training log.

`loads-from-logs` binds at **design** time: when a block is drafted, loads are anchored on
the log. But a block runs five weeks and the plan freezes the moment it's rendered to the
Sheet. Two things rot from there:

  1. **Drift** — the athlete trains an accessory well above (or below) what the Sheet says.
     Leg Extension was programmed 90–100 lb while the log shows a 140 lb working load: the
     Sheet is ~45 lb light, so he ignores it and the plan stops being the plan.
  2. **First exposures** — a newly introduced movement gets a placeholder load because
     there was no history to anchor on (Weighted Back Extension went in around 1 lb). After
     a session or two there IS history — 90 lb — and the placeholder is nonsense.

This module diffs plan vs log, and can rewrite the block's **remaining** weeks so the Sheet
tracks reality. Rule: `sheet-load-sync`. Run weekly off the Saturday review.

SAFETY — what this will and won't touch:

  * **Only accessories are auto-adjusted.** Big-5 primaries and the barbell secondaries
    (Spoto, Tempo Squat, Paused RDL, …) are *reported* as drift and never rewritten. Their
    loads come from the intensity wave and from injury caps — `sumo-back-cap`, the squat
    axial cap — so chasing the log there would quietly undo a deliberate restriction. An
    auto-raise of sumo toward its logged median is exactly the failure mode to avoid.
  * **Only future weeks.** Weeks already trained are the record of what was prescribed;
    they're left alone. Default start is the week *after* the current one.
  * **The block's shape is preserved.** Corrections scale every working set by one factor,
    so the intensity wave and the W5 deload keep their relative depth — this re-bases a
    wrong anchor, it does not invent progression (`accessory-progression`).
  * **The anchor is a median, not a max.** The median of the last few sessions tracks the
    current working level while shrugging off one stray entry (the 1 lb back-extension set
    sitting between 90s). Loads snap to the 5 lb grid the Sheet already uses.

CLI:
  python -m scripts.sheets.reconcile_loads                 # report only (default)
  python -m scripts.sheets.reconcile_loads --apply         # rewrite remaining weeks
  python -m scripts.sheets.reconcile_loads --apply --push  # …and re-render the Sheet
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
from datetime import date as date_cls, timedelta

from ..hevy.block_report import DEFAULT_BW, KG_TO_LBS, REPO_ROOT
from ..review.weekly_metrics import (
    BLOCK_JSON,
    PRIMARY_NAMES,
    _best_working_set,
    _index_exercises,
    _match_accessory,
    _safe_resolver,
    _sessions_in,
)
from .export_block import _family, _round5

# How far back to look for "what does he actually train this at?".
DEFAULT_RECENT_DAYS = 120
# The anchor is the median of this many most-recent sessions — enough to be robust to one
# stray entry, short enough to track a fast-moving accessory instead of lagging it.
DEFAULT_ANCHOR_SESSIONS = 3
# Drift below BOTH of these is noise; don't churn the Sheet over it.
DEFAULT_THRESHOLD_LB = 10.0
DEFAULT_THRESHOLD_PCT = 0.10
# Outside this ratio the prescription isn't "drifted", it's a placeholder — the block's
# week-to-week shape is meaningless, so rebase flat instead of scaling it.
REBASE_RATIO = 3.0
# A prescribed reference at or below this is a placeholder, not a real load.
PLACEHOLDER_LB = 5.0

def load_block(path=None) -> dict:
    return json.loads((path or BLOCK_JSON).read_text())


def current_week(block: dict, today: date_cls) -> int:
    """1-based block week containing `today`, clamped to the block's length."""
    weeks = block.get("weeks", 0)
    start = block.get("start_date")
    if not start:
        raise ValueError("block JSON missing start_date")
    elapsed = (today - date_cls.fromisoformat(start)).days
    return max(1, min(weeks, elapsed // 7 + 1))


def _working_sets(ex: dict) -> list[dict]:
    return [s for s in ex.get("sets", []) if s.get("type") != "warmup"]


def prescribed_by_week(block: dict, name: str) -> dict[int, float]:
    """Heaviest prescribed working load (lb) per week for one exercise name."""
    out: dict[int, float] = {}
    for presc in block.get("prescriptions", []):
        week = presc.get("week")
        for ex in presc.get("exercises", []):
            if ex.get("name") != name:
                continue
            for s in _working_sets(ex):
                wt = s.get("weight_kg")
                if wt is None:
                    continue
                lbs = wt * KG_TO_LBS
                if week not in out or lbs > out[week]:
                    out[week] = lbs
    return out


def _identity(name: str, index: list[dict], resolver) -> tuple[str, str] | None:
    """Pin an exercise name to a stable logged identity, reusing the weekly-review
    matcher: ('tid', <template id>) when the log carries one, else ('title', <norm>).
    Returning an identity (not a single exercise) lets us collect every session."""
    exemplar = _match_accessory(name, index, resolver)
    if exemplar is None:
        # Nothing logged in the window. If the name still resolves to a real Hevy template,
        # this is a genuinely untrained movement (a first exposure), NOT a mapping gap —
        # return the identity so the report says "nothing logged" without crying wolf.
        tid = resolver(name)
        return ("tid", tid) if tid else None
    tid = exemplar.get("exercise_template_id")
    if tid:
        return ("tid", tid)
    title = exemplar.get("title") or ""
    from ..hevy.exercise_map import _normalize
    return ("title", _normalize(title))


def logged_history(name: str, index: list[dict], resolver, bw: float) -> dict:
    """Per-session heaviest working load (lb) for one exercise, oldest → newest.

    `matched` distinguishes "he never logged this" from "he logged it with no weight" —
    a bodyweight movement (hanging leg raise) records `weight_kg: null`, so an empty
    `rows` list on its own would wrongly read as missing data.
    """
    ident = _identity(name, index, resolver)
    if ident is None:
        return {"matched": False, "dates": [], "rows": []}
    kind, value = ident
    per_date: dict[str, float] = {}
    dates: set[str] = set()
    for entry in index:
        match = entry["tid"] == value if kind == "tid" else entry["title_norm"] == value
        if not match:
            continue
        date = entry["ex"].get("_date") or ""
        dates.add(date)
        best = _best_working_set(entry["ex"], False, bw)
        if best is None:
            continue
        if date not in per_date or best["added_lb"] > per_date[date]:
            per_date[date] = best["added_lb"]
    return {
        "matched": True,
        "dates": sorted(dates),
        "rows": [{"date": d, "top_lb": per_date[d]} for d in sorted(per_date)],
    }


def _anchor(history: list[dict], n: int) -> float | None:
    """Current working level: median of the last `n` sessions' top loads."""
    if not history:
        return None
    return statistics.median([r["top_lb"] for r in history[-n:]])


def _classify(name: str, ref_lb: float | None, anchor_lb: float | None,
              matched: bool, threshold_lb: float, threshold_pct: float) -> str:
    if _family(name) != "Acc" or name in PRIMARY_NAMES:
        return "review-manually"
    if anchor_lb is None:
        # Logged, but every set is unweighted → a bodyweight movement, nothing to sync.
        if matched and not ref_lb:
            return "bodyweight"
        return "no-data"
    if anchor_lb <= 0 and (ref_lb or 0) <= 0:
        return "bodyweight"
    if ref_lb is None or ref_lb <= 0:
        return "first-exposure"
    if ref_lb <= PLACEHOLDER_LB or anchor_lb <= PLACEHOLDER_LB:
        return "first-exposure"
    ratio = anchor_lb / ref_lb
    if ratio >= REBASE_RATIO or ratio <= 1 / REBASE_RATIO:
        return "first-exposure"      # shape is a placeholder, not a wave — rebase flat
    delta = abs(anchor_lb - ref_lb)
    if delta >= threshold_lb and delta / ref_lb >= threshold_pct:
        return "drift"
    return "ok"


def _proposal(verdict: str, anchor_lb: float | None,
              by_week: dict[int, float], from_week: int) -> dict | None:
    """New per-week loads for the weeks still ahead. `scale` keeps the block's wave and
    deload depth; `rebase` flattens a placeholder onto the logged anchor.

    The scale is taken against the median of the **weeks being rewritten**, not against the
    trained-weeks reference that detected the drift. That keeps this idempotent: once the
    future weeks sit on the anchor, the next run computes a scale of 1.0 and proposes
    nothing. Scaling off the trained weeks instead would re-apply the same correction every
    Saturday and ratchet the loads up week after week.
    """
    future = {w: lb for w, lb in by_week.items() if w >= from_week}
    if verdict not in ("drift", "first-exposure") or not future or anchor_lb is None:
        return None
    if verdict == "drift":
        base = statistics.median(future.values())
        if not base:
            return None
        scale = anchor_lb / base
        targets = {w: _round5(lb * scale) for w, lb in future.items()}
        mode = "scale"
    else:
        scale = None
        targets = {w: _round5(anchor_lb) for w in future}
        mode = "rebase"
    if all(targets[w] == _round5(future[w]) for w in future):
        return None                              # already in sync — nothing to do
    return {"mode": mode, "scale": round(scale, 4) if scale else None, "by_week": targets}


def reconcile(block: dict, today: date_cls | None = None, *,
              recent_days: int = DEFAULT_RECENT_DAYS,
              anchor_sessions: int = DEFAULT_ANCHOR_SESSIONS,
              threshold_lb: float = DEFAULT_THRESHOLD_LB,
              threshold_pct: float = DEFAULT_THRESHOLD_PCT,
              from_week: int | None = None,
              bw: float = DEFAULT_BW) -> dict:
    """Diff every exercise in the block against the log. Read-only — returns a report."""
    today = today or date_cls.today()
    week_no = current_week(block, today)
    from_week = from_week if from_week is not None else week_no + 1
    weeks = block.get("weeks", 0)

    window_start = (today - timedelta(days=recent_days)).isoformat()
    index = _index_exercises(_sessions_in(window_start, today.isoformat()))
    resolver = _safe_resolver()

    names: list[str] = []
    for presc in block.get("prescriptions", []):
        for ex in presc.get("exercises", []):
            n = ex.get("name")
            if n and n not in names:
                names.append(n)

    items = []
    for name in names:
        by_week = prescribed_by_week(block, name)
        # Detect drift against the weeks he has ALREADY trained — "the plan said 90, you
        # did 140" is the honest comparison, and those weeks are never rewritten, so the
        # reference stays stable across repeated weekly runs. Before the block starts
        # (nothing trained yet) fall back to the whole block.
        trained = {w: lb for w, lb in by_week.items() if w < from_week}
        basis = trained or by_week
        ref_lb = statistics.median(basis.values()) if basis else None
        hist = logged_history(name, index, resolver, bw)
        rows = hist["rows"]
        anchor_lb = _anchor(rows, anchor_sessions)
        verdict = _classify(name, ref_lb, anchor_lb, hist["matched"],
                            threshold_lb, threshold_pct)
        drift = (anchor_lb - ref_lb) if (anchor_lb is not None and ref_lb) else None
        items.append({
            "name": name,
            "family": _family(name),
            "adjustable": _family(name) == "Acc" and name not in PRIMARY_NAMES,
            "verdict": verdict,
            "prescribed": {
                "by_week": {w: _round5(lb) for w, lb in sorted(by_week.items())},
                "reference_lb": _round5(ref_lb) if ref_lb else None,
            },
            "log": {
                "matched": hist["matched"],
                "sessions": len(hist["dates"]),
                "anchor_lb": anchor_lb,
                "median_lb": (statistics.median([r["top_lb"] for r in rows])
                              if rows else None),
                "max_lb": max((r["top_lb"] for r in rows), default=None),
                "last_date": hist["dates"][-1] if hist["dates"] else None,
                "recent": rows[-6:],
            },
            "drift_lb": round(drift, 1) if drift is not None else None,
            "drift_pct": round(drift / ref_lb, 3) if (drift is not None and ref_lb) else None,
            "proposal": _proposal(verdict, anchor_lb, by_week, from_week),
        })

    return {
        "generated_for": today.isoformat(),
        "block_id": block.get("block_id"),
        "weeks": weeks,
        "week_no": week_no,
        "from_week": from_week,
        "weeks_remaining": max(0, weeks - from_week + 1),
        "window": f"{window_start} → {today.isoformat()}",
        "anchor_sessions": anchor_sessions,
        "items": items,
    }


def _retarget_note(note: str | None, old_lb: int, new_lb: int) -> str | None:
    """Update a "140×10" load token in a prescription note so it doesn't contradict the
    cells after a rewrite. Only a load followed by ×reps is touched — a bare rep scheme
    like "3×10" has no weight in it and is left alone."""
    if not note or old_lb == new_lb:
        return note
    return re.sub(rf"\b{old_lb}(?=\s*[×x]\s*\d)", str(new_lb), note)


def apply_corrections(block: dict, report: dict) -> list[dict]:
    """Rewrite the remaining weeks' loads in-place. Returns the applied changes.

    Every working set of an affected exercise scales by the same factor, so a top/backoff
    split keeps its relationship. Only items the report marked `adjustable` with a
    proposal are touched.
    """
    proposals = {
        it["name"]: it for it in report["items"]
        if it["adjustable"] and it.get("proposal")
    }
    if not proposals:
        return []

    changes: list[dict] = []
    from_week = report["from_week"]
    for presc in block.get("prescriptions", []):
        week = presc.get("week")
        if week is None or week < from_week:
            continue
        for ex in presc.get("exercises", []):
            item = proposals.get(ex.get("name"))
            if not item:
                continue
            target = item["proposal"]["by_week"].get(week)
            if target is None:
                continue
            working = _working_sets(ex)
            weights = [s["weight_kg"] for s in working if s.get("weight_kg")]
            if not weights:
                continue
            # Scale off this exercise-entry's own heaviest set so a backoff entry lands
            # proportionally, not on the top set's number.
            week_top_lb = item["prescribed"]["by_week"].get(week)
            entry_top_lb = _round5(max(weights) * KG_TO_LBS)
            if not week_top_lb or not entry_top_lb:
                continue
            factor = target / week_top_lb
            new_entry_top = _round5(entry_top_lb * factor)
            for s in working:
                wt = s.get("weight_kg")
                if not wt:
                    continue
                old_lb = _round5(wt * KG_TO_LBS)
                new_lb = _round5(old_lb * factor)
                if new_lb == old_lb:
                    continue
                s["weight_kg"] = round(new_lb / KG_TO_LBS, 1)
            ex["notes"] = _retarget_note(ex.get("notes"), entry_top_lb, new_entry_top)
            if new_entry_top != entry_top_lb:
                changes.append({
                    "week": week, "day": presc.get("day"), "name": ex.get("name"),
                    "from_lb": entry_top_lb, "to_lb": new_entry_top,
                    "mode": item["proposal"]["mode"],
                })
    return changes


# --- Rendering -------------------------------------------------------------------------

_ICON = {"drift": "📈", "first-exposure": "🆕", "review-manually": "👀",
         "no-data": "❓", "ok": "✅", "bodyweight": "⚪"}


def render_md(report: dict, changes: list[dict] | None = None) -> str:
    """Coach-readable summary — used in the weekly snapshot and the Telegram narrative."""
    lines = [
        f"### Sheet ↔ log load reconciliation — {report['block_id']} "
        f"W{report['week_no']}/{report['weeks']}",
        "",
        f"_Log window {report['window']} · anchor = median of last "
        f"{report['anchor_sessions']} sessions · corrections apply from W{report['from_week']} "
        f"({report['weeks_remaining']} week(s) left)._",
        "",
    ]

    def rows(verdict: str) -> list[dict]:
        return [it for it in report["items"] if it["verdict"] == verdict]

    def line(it: dict) -> str:
        p = it["prescribed"]["reference_lb"]
        a = it["log"]["anchor_lb"]
        d = it["drift_lb"]
        sheet_s = f"{p:g} lb" if p is not None else "—"
        if a is None:
            gap = "" if it["log"]["matched"] else " — name may not match the Hevy template"
            return f"- {_ICON[it['verdict']]} **{it['name']}** — sheet {sheet_s}, nothing logged{gap}"
        bit = f"**{it['name']}** — sheet {sheet_s} → log {a:g} lb"
        if d is not None:
            bit += f" (**{d:+g} lb**)"
        prop = it.get("proposal")
        if prop:
            weeks = ", ".join(f"W{w} → {lb}" for w, lb in sorted(prop["by_week"].items()))
            bit += f" · {prop['mode']}: {weeks}" if weeks else ""
        return f"- {_ICON[it['verdict']]} {bit}"

    for verdict, heading in (
        ("drift", "Drifted — sheet no longer matches what he trains"),
        ("first-exposure", "First exposures — placeholder loads to rebase"),
        ("review-manually", "Primaries & secondaries — reported only, never auto-adjusted"),
        ("no-data", "No log data in window — left as programmed"),
    ):
        group = rows(verdict)
        if not group:
            continue
        if verdict == "review-manually":
            group = [it for it in group
                     if it["drift_lb"] is not None and abs(it["drift_lb"]) >= DEFAULT_THRESHOLD_LB]
            if not group:
                continue
        lines += [f"**{heading}**", ""] + [line(it) for it in group] + [""]

    ok = len(rows("ok"))
    if ok:
        lines += [f"_{ok} exercise(s) already on-target._", ""]

    if changes is not None:
        if changes:
            lines += ["**Applied to the block + Sheet:**", ""]
            lines += [f"- W{c['week']} {c['day']} · {c['name']}: {c['from_lb']} → {c['to_lb']} lb"
                      for c in changes]
        else:
            lines += ["_No corrections applied (nothing adjustable, or no weeks left "
                      "in the block)._"]
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("block_json", nargs="?", help="Block JSON (default brain/current-block.json)")
    ap.add_argument("--date", help="Override 'today' (YYYY-MM-DD)")
    ap.add_argument("--recent", type=int, default=DEFAULT_RECENT_DAYS,
                    help=f"Log lookback days (default {DEFAULT_RECENT_DAYS})")
    ap.add_argument("--anchor-sessions", type=int, default=DEFAULT_ANCHOR_SESSIONS,
                    help="Sessions in the median that sets the anchor "
                         f"(default {DEFAULT_ANCHOR_SESSIONS})")
    ap.add_argument("--threshold-lb", type=float, default=DEFAULT_THRESHOLD_LB)
    ap.add_argument("--threshold-pct", type=float, default=DEFAULT_THRESHOLD_PCT)
    ap.add_argument("--from-week", type=int,
                    help="First week to rewrite (default: the week after the current one)")
    ap.add_argument("--bw", type=float, default=DEFAULT_BW)
    ap.add_argument("--apply", action="store_true", help="Write the corrections to the block JSON")
    ap.add_argument("--push", action="store_true", help="Re-render the Sheet after --apply")
    ap.add_argument("--json", action="store_true", help="Emit the raw report as JSON")
    args = ap.parse_args()

    from pathlib import Path
    path = Path(args.block_json) if args.block_json else BLOCK_JSON
    block = load_block(path)
    today = date_cls.fromisoformat(args.date) if args.date else None

    report = reconcile(block, today, recent_days=args.recent,
                       anchor_sessions=args.anchor_sessions,
                       threshold_lb=args.threshold_lb, threshold_pct=args.threshold_pct,
                       from_week=args.from_week, bw=args.bw)

    changes = None
    if args.apply:
        changes = apply_corrections(block, report)
        if changes:
            path.write_text(json.dumps(block, indent=2, ensure_ascii=False) + "\n")

    if args.json:
        print(json.dumps({"report": report, "changes": changes}, indent=2))
    else:
        print(render_md(report, changes))

    if args.push:
        if not args.apply:
            raise SystemExit("--push requires --apply (nothing new to render otherwise)")
        from .export_block import export
        export(block, block.get("block_id", "block"), final=True)


if __name__ == "__main__":
    main()
