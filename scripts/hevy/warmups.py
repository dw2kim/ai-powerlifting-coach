"""Warm-up ramps for the Big-5 primaries, scaled to the day's top set.

Rule `primary-warmup-ramp` (reference/programming-rules.md). Before this, ramps were written
by hand once per block and copied into every week: a W4 squat went from a 275 warm-up straight
to a 405 top set, and pull-ups and dips carried a single bodyweight set — while the log shows
him adding his own loaded bridge (dip BW×8 → +35×8 → 70×5; pull-up BW×6 → +45×3 → 60×4).

The shapes come from his Hevy log, not a textbook:

- **Barbell (squat / sumo / bench):** open at 135×8, climb on plate landmarks, finish with the
  last warm-up within ~10% and at least 20 lb under the top set. Small jumps near the work,
  bigger ones at the bottom, so the count grows with the top set: a 255 sumo gets 135/185/225,
  a 455 squat gets 135/185/275/365/405 — in line with his logged 315/365/415 → 455, rather
  than a fixed two or three sets.
- **Bodyweight (pull-up / dip):** a BW set, then a loaded bridge at ~60% of the top added load
  (two bridges once the top reaches +80).

Reps taper with %-of-top: 8 on the opener, 5 → 3 → 2 → 1 as it closes on the work.

    python -m scripts.hevy.warmups                    # dry run on brain/current-block.json
    python -m scripts.hevy.warmups --apply            # rewrite warm-ups in place
    python -m scripts.hevy.warmups --spec path.json --apply
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from scripts.hevy.rest_times import tier_for
from scripts.hevy.units import kg_to_lb, lb_to_kg

REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "brain" / "current-block.json"

# Where he actually stops on the bar: 45s on each side, with a 25 between.
_LANDMARKS = [45, 95, 135, 185, 225, 275, 315, 365, 405, 455, 495, 545, 585, 635]
_LAST_PCT = 0.92       # last warm-up at or under this fraction of the top set …
_LAST_GAP_LB = 20      # … and at least this far under it
_BW_REPS = {"pullup": 6, "dip": 8}


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


def _reps_for(pct: float, first: bool) -> int:
    if first:
        # The opener is a groove set whatever the top is — never a 135×3.
        return 8 if pct <= 0.55 else 5
    if pct <= 0.55:
        return 5
    if pct <= 0.65:
        return 5
    if pct <= 0.80:
        return 3
    if pct <= 0.90:
        return 2
    return 1


def barbell_ramp(top_lb: float) -> list[tuple[float, int]]:
    """(load lb, reps) warm-ups ahead of a barbell top set."""
    ceiling = min(top_lb * _LAST_PCT, top_lb - _LAST_GAP_LB)
    opener = 135 if top_lb >= 185 else 45
    candidates = [l for l in _LANDMARKS if opener <= l <= ceiling]
    if not candidates:
        return [(45, 8)] if top_lb > 65 else []
    # Walk down from the top: the two landmarks nearest the work are both kept (small jumps
    # where the bar is heavy), then every other landmark, always ending on the opener.
    # 405 → 135/225/315/365 rather than a 275 → 405 leap; 315 → 135/225/275, as he logs it.
    top_idx = len(candidates) - 1
    picks = {0, top_idx, max(top_idx - 1, 0)}
    picks.update(range(top_idx - 3, 0, -2))
    loads = [candidates[i] for i in sorted(picks)]
    return [(l, _reps_for(l / top_lb, i == 0)) for i, l in enumerate(loads)]


def bodyweight_ramp(kind: str, top_added_lb: float) -> list[tuple[float, int]]:
    """(added lb, reps) warm-ups ahead of a weighted pull-up / dip top set."""
    ramp: list[tuple[float, int]] = [(0.0, _BW_REPS[kind])]
    if top_added_lb < 20:
        return ramp
    pcts = (0.45, 0.75) if top_added_lb >= 80 else (0.6,)
    for p in pcts:
        load = 5 * math.floor(top_added_lb * p / 5)
        if load > ramp[-1][0]:
            ramp.append((float(load), 3))
    return ramp


def ramp_for(name: str, sets: list[dict]) -> list[dict] | None:
    """Warm-up sets for one primary exercise entry, or None if it isn't a loaded Big-5 lift."""
    kind = lift_kind(name)
    working = [s for s in sets if s.get("type") != "warmup" and s.get("weight_kg") is not None]
    if kind is None or not working:
        return None
    top_lb = round(kg_to_lb(max(s["weight_kg"] for s in working)))
    if kind in _BW_REPS:
        steps = bodyweight_ramp(kind, top_lb)
    else:
        steps = barbell_ramp(top_lb)
    return [{"type": "warmup", "weight_kg": lb_to_kg(lb) if lb else 0.0, "reps": reps}
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
