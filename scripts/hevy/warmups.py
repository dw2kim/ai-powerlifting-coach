"""Warm-up ramps for the Big-5 primaries, scaled to the day's top set.

Rule `primary-warmup-ramp` (reference/programming-rules.md). Before this, ramps were written
by hand once per block and copied into every week: a W4 squat went from a 275 warm-up straight
to a 405 top set, and pull-ups and dips carried a single bodyweight set while he added his own
loaded set anyway.

The ramps are **his**, as he described them (2026-10-01), checked against the log:

- **Every barbell lift opens at 135×8.**
- **Squat / sumo climb a plate a side, +90:** 135 → 225 → 315 → 405 → 495.
- **Bench climbs 135 → 185 → 225 → 275 → 315 …** — the usual 45/25 plate stops.
- A step is only a warm-up if it sits **≥20 lb under the top set**; the ramp stops there.
- **Pull-up / dip open at bodyweight, logged as 1 lb** (how he enters BW in Hevy), then one
  loaded set: **pull-up +45** (every 2026 session), **dip +35 up to a +70 top, +45 above**.
  A +90 pull-up gets a second step, +70×1, as he's logged ahead of his heavier tops.

Reps after the opener taper with %-of-top: 5 → 3 → 2 → 1.

    python -m scripts.hevy.warmups                    # dry run on brain/current-block.json
    python -m scripts.hevy.warmups --apply            # rewrite warm-ups in place
    python -m scripts.hevy.warmups --spec path.json --apply
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.hevy.rest_times import tier_for
from scripts.hevy.units import kg_to_lb, lb_to_kg

REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "brain" / "current-block.json"

_OPENER = (135, 8)
_STEPS = {
    "squat": [135, 225, 315, 405, 495, 585],      # +90: one plate a side
    "deadlift": [135, 225, 315, 405, 495, 585],
    "bench": [135, 185, 225, 275, 315, 365, 405],
}
_MIN_GAP_LB = 20       # a step this close to the top set is the work, not a warm-up
_BW_LB = 1             # he logs bodyweight as 1 lb
_BW_REPS = 8


def lift_kind(name: str) -> str | None:
    n = name.lower()
    if "pull-up" in n or "pull up" in n or "pullup" in n:
        return "pullup"
    if "dip" in n:
        return "dip"
    if "squat" in n:
        return "squat"
    if "deadlift" in n or "sumo" in n:
        return "deadlift"
    if "bench" in n:
        return "bench"
    return None


def _reps_for(pct: float) -> int:
    if pct <= 0.65:
        return 5
    if pct <= 0.80:
        return 3
    if pct <= 0.90:
        return 2
    return 1


def barbell_ramp(kind: str, top_lb: float) -> list[tuple[float, int]]:
    """(load lb, reps) warm-ups ahead of a barbell top set."""
    if top_lb < _OPENER[0] + _MIN_GAP_LB:
        return []
    loads = [l for l in _STEPS[kind] if l <= top_lb - _MIN_GAP_LB]
    return [_OPENER] + [(l, _reps_for(l / top_lb)) for l in loads[1:]]


def bodyweight_ramp(kind: str, top_added_lb: float) -> list[tuple[float, int]]:
    """(added lb, reps) warm-ups ahead of a weighted pull-up / dip top set."""
    ramp: list[tuple[float, int]] = [(_BW_LB, _BW_REPS)]
    if kind == "pullup":
        first, reps = 45, 3
    else:
        first, reps = (35 if top_added_lb <= 70 else 45), 5
    # Dropped to 35 if 45 would sit on top of a light top set (+45, +50).
    if first > top_added_lb - 10:
        first = 35 if 35 <= top_added_lb - 10 else 0
    if first:
        ramp.append((first, reps))
    if kind == "pullup" and top_added_lb >= 90:
        ramp.append((70, 1))
    return ramp


def ramp_for(name: str, sets: list[dict]) -> list[dict] | None:
    """Warm-up sets for one primary exercise entry, or None if it isn't a loaded Big-5 lift."""
    kind = lift_kind(name)
    working = [s for s in sets if s.get("type") != "warmup" and s.get("weight_kg") is not None]
    if kind is None or not working:
        return None
    top_lb = round(kg_to_lb(max(s["weight_kg"] for s in working)))
    if kind in ("pullup", "dip"):
        steps = bodyweight_ramp(kind, top_lb)
    else:
        steps = barbell_ramp(kind, top_lb)
    return [{"type": "warmup", "weight_kg": lb_to_kg(lb), "reps": reps}
            for lb, reps in steps]


def apply_to_spec(spec: dict) -> list[tuple[str, str, list, list]]:
    """Rewrite warm-ups on every primary in place. Returns (session, lift, old, new) changes."""
    changes = []
    for p in spec.get("prescriptions", []):
        for ex in p.get("exercises", []):
            if tier_for(ex) != "primary":
                continue
            ramp = ramp_for(ex["name"], ex.get("sets", []))
            if ramp is None:
                continue
            old = [s for s in ex["sets"] if s.get("type") == "warmup"]
            working = [s for s in ex["sets"] if s.get("type") != "warmup"]
            if _summary(old) != _summary(ramp):
                changes.append((f"W{p['week']}-{p['day']}", ex["name"], _summary(old), _summary(ramp)))
            ex["sets"] = ramp + working
    return changes


def _summary(sets: list[dict]) -> list[str]:
    return [f"{round(kg_to_lb(s.get('weight_kg') or 0))}×{s.get('reps')}" for s in sets]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--spec", type=Path, default=SPEC_PATH)
    ap.add_argument("--apply", action="store_true", help="write the ramps back into the spec")
    args = ap.parse_args()

    spec = json.loads(args.spec.read_text())
    changes = apply_to_spec(spec)
    for session, name, old, new in changes:
        print(f"{session:<8} {name:<20} {' '.join(old) or '—':<28} → {' '.join(new)}")
    if not changes:
        print("Warm-ups already match the ramp.")
    if args.apply and changes:
        args.spec.write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n")
        print(f"\nWrote {len(changes)} ramp(s) to {args.spec}")


if __name__ == "__main__":
    main()
