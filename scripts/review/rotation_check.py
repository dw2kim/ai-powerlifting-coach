"""Accessory rotation check (`accessory-rotation`): did this block actually rotate anything?

B7 went out with 12 of its 14 accessories carried over from B6 and **zero** real rotations, and
nothing noticed until the athlete did. This makes the floor mechanical:

    python -m scripts.review.rotation_check                      # current block vs the one before
    python -m scripts.review.rotation_check --block brain/next-block-draft.json
    python -m scripts.review.rotation_check --week 3             # read the block at W3 (mid-block swaps)

**What counts as a rotation.** An accessory in the new block that wasn't in the prior block, paired
one-to-one with an accessory the prior block had and the new one dropped, **for the same muscle**
(Hevy's `primary_muscle_group` on the exercise template). Same target, new implement or angle.
- Same day is preferred when pairing, but any day is accepted.
- A new movement with no dropped partner for its muscle is an **addition** (the 1–2 "expansion"
  movements, or a re-entry). It doesn't count.
- A dropped movement with no new partner is a **drop**. It doesn't count either.

**The floor** (athlete, 2026-11-11): at least 4 rotations, and at least one on every training day.
Exit code 1 if it isn't met, so the design skill and a fresh push both stop on it.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

from scripts.hevy.exercise_map import Resolver

REPO_ROOT = Path(__file__).resolve().parents[2]
CURRENT = REPO_ROOT / "brain" / "current-block.json"
ARCHIVE = REPO_ROOT / "data" / "block-archive"

MIN_ROTATIONS = 4
MIN_PER_DAY = 1


@dataclass
class Lift:
    name: str
    day: str
    template_id: str
    muscle: str


@dataclass
class Report:
    block_id: str
    prior_id: str
    week: int
    prior_week: int | None
    rotations: list[tuple[Lift, Lift]] = field(default_factory=list)  # (out, in)
    additions: list[Lift] = field(default_factory=list)
    drops: list[Lift] = field(default_factory=list)
    carried: list[Lift] = field(default_factory=list)
    days: list[str] = field(default_factory=list)

    def per_day(self) -> dict[str, int]:
        counts = {d: 0 for d in self.days}
        for _, new in self.rotations:
            counts[new.day] = counts.get(new.day, 0) + 1
        return counts

    def failures(self, min_total: int = MIN_ROTATIONS, min_per_day: int = MIN_PER_DAY) -> list[str]:
        out = []
        if len(self.rotations) < min_total:
            out.append(f"{len(self.rotations)} rotations, floor is {min_total}")
        empty = [d for d, n in self.per_day().items() if n < min_per_day]
        if empty:
            out.append(f"no rotation on {', '.join(empty)}")
        return out


def accessories(block: dict, week: int | None, resolver: Resolver) -> list[Lift]:
    """Accessories in one week of a block, or (week=None) everything the block ever carried,
    each once, at the first day it appeared."""
    by_id = {t["id"]: t for t in resolver.templates}
    lifts: dict[str, Lift] = {}
    for p in sorted(block["prescriptions"], key=lambda p: p["week"]):
        if week is not None and p["week"] != week:
            continue
        for ex in p["exercises"]:
            if ex.get("tier") != "accessory":
                continue
            tid = resolver.resolve(ex["name"])
            muscle = by_id.get(tid, {}).get("primary_muscle_group") or "unknown"
            lifts.setdefault(f"{tid}/{p['day'] if week is not None else ''}",
                             Lift(ex["name"], p["day"], tid, muscle))
    return list(lifts.values())


def find_prior(block_id: str, current_path: Path = CURRENT, archive: Path = ARCHIVE) -> Path:
    """The block immediately before `block_id`: the newest archived (or current) block whose id
    sorts before it. The current block counts, because a draft for B8 is checked while B7 is
    still live and not archived yet."""
    candidates = {}
    for path in [*archive.glob("*.json"), current_path]:
        if not path.exists():
            continue
        bid = json.loads(path.read_text()).get("block_id", "")
        # A bridge (two sessions between blocks) isn't a block: compare against the real one.
        if bid and bid < block_id and "BRIDGE" not in bid.upper():
            candidates[bid] = path
    if not candidates:
        raise SystemExit(f"No block found before {block_id} to compare against.")
    return candidates[max(candidates)]


def compare(block: dict, prior: dict, resolver: Resolver, week: int = 1,
            prior_week: int | None = None) -> Report:
    new = accessories(block, week, resolver)
    # The prior block as a whole, unless a week is named: a lift it carried in any week was
    # "in the prior block", even if the last week (a deload, a cut) didn't have it.
    old = accessories(prior, prior_week, resolver)
    old_ids = {l.template_id for l in old}
    new_ids = {l.template_id for l in new}
    rep = Report(block["block_id"], prior["block_id"], week, prior_week,
                 days=[d["label"] for d in block["days"]])
    rep.carried = [l for l in new if l.template_id in old_ids]
    incoming = [l for l in new if l.template_id not in old_ids]
    dropped = [l for l in old if l.template_id not in new_ids]
    # Same-day pairs first, then any day: a chest fly swapped on D1 shouldn't be "used up" by
    # a chest movement added on D3.
    for same_day in (True, False):
        for inn in list(incoming):
            match = next((o for o in dropped if o.muscle == inn.muscle
                          and (o.day == inn.day or not same_day)), None)
            if match:
                rep.rotations.append((match, inn))
                incoming.remove(inn)
                dropped.remove(match)
    rep.additions = incoming
    rep.drops = dropped
    return rep


def render(rep: Report) -> str:
    prior = f"W{rep.prior_week}" if rep.prior_week else "(all weeks)"
    lines = [f"## Rotation check: {rep.block_id} W{rep.week} vs {rep.prior_id} {prior}", ""]
    lines.append("| Day | Out | In | Target |")
    lines.append("|---|---|---|---|")
    for old, new in sorted(rep.rotations, key=lambda r: r[1].day):
        lines.append(f"| {new.day} | {old.name} ({old.day}) | {new.name} | {new.muscle} |")
    if not rep.rotations:
        lines.append("| — | — | — | — |")
    lines.append("")
    per_day = rep.per_day()
    lines.append("**Per day:** " + " · ".join(f"{d} {n}" for d, n in per_day.items())
                 + f" · **total {len(rep.rotations)}**")
    if rep.additions:
        lines.append("**Additions (not rotations):** " + ", ".join(f"{l.name} ({l.day}, {l.muscle})" for l in rep.additions))
    if rep.drops:
        lines.append("**Drops (not rotations):** " + ", ".join(f"{l.name} ({l.day}, {l.muscle})" for l in rep.drops))
    lines.append(f"**Carried over:** {len(rep.carried)}")
    fails = rep.failures()
    lines.append("")
    lines.append("❌ " + "; ".join(fails) + " (`accessory-rotation`)" if fails
                 else "✅ Floor met (`accessory-rotation`)")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--block", type=Path, default=CURRENT, help="Block JSON to check (default: current block)")
    ap.add_argument("--prior", type=Path, help="Block JSON to compare against (default: the one before)")
    ap.add_argument("--week", type=int, default=1, help="Week of the new block to read (default 1)")
    ap.add_argument("--prior-week", type=int, help="Week of the prior block to read (default: all of it)")
    args = ap.parse_args(argv)
    block = json.loads(args.block.read_text())
    prior_path = args.prior or find_prior(block["block_id"])
    prior = json.loads(prior_path.read_text())
    rep = compare(block, prior, Resolver(), args.week, args.prior_week)
    print(render(rep))
    return 1 if rep.failures() else 0


if __name__ == "__main__":
    sys.exit(main())
