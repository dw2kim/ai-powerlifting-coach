"""Map local exercise names to Hevy exercise_template_id.

Bootstrap once: `python -m scripts.hevy.exercise_map --bootstrap` fetches all
templates and writes scripts/hevy/exercise_templates.json. Commit that file.

Resolution order:
1. Exact match on title (case-insensitive)
2. Manual override (OVERRIDES dict)
3. Token-subset fuzzy match (all tokens of the query appear in the title)

Unmatched names raise — better than silently dropping an exercise in a routine push.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from .client import HevyClient

CACHE_PATH = Path(__file__).with_name("exercise_templates.json")

# Add entries here when a local name doesn't match Hevy's template title.
# Key = local name (case-insensitive); value = Hevy template title (exact).
OVERRIDES: dict[str, str] = {
    # User logs under their own custom templates, not Hevy stock — verified against
    # the live training log (block_report). Keep these pointed at the custom titles
    # so pushed routines link to existing exercise history.
    "low-bar squat": "Low-bar Squat",
    "paused low-bar squat": "Paused Low Bar Squat",
    "cgb": "Bench Press - Close Grip (Barbell)",
    "spoto bench": "Bench Press (Barbell)",
    "paused larsen bench": "Bench Press (Barbell)",
    "sumo deadlift": "Sumo Deadlift",
    "paused sumo deadlift": "Paused Sumo Deadlift",
    "paused rdl": "Romanian Deadlift (Barbell)",
    "weighted pull-up": "Pull Up (Weighted)",
    "wpu": "Pull Up (Weighted)",
    "weighted dip": "Triceps Dip (Weighted)",
    "ohp": "Overhead Press (Barbell)",
    "db lateral raise": "Lateral Raise (Dumbbell)",
    "iso-lateral row": "Iso-Lateral Row (Machine)",
    "leg extension": "Leg Extension (Machine)",
    "seated leg curl": "Seated Leg Curl (Machine)",
    "cable curl": "Bicep Curl (Cable)",
    "lat pulldown": "Lat Pulldown (Cable)",
    "hip abduction": "Hip Abduction (Machine)",
    "hip adduction": "Hip Adduction (Machine)",
    # Athlete's competition bench is logged under a custom template "POWER Bench Press".
    "comp bench": "POWER Bench Press",
    "competition bench": "POWER Bench Press",
    "power bench press": "POWER Bench Press",
    "db shoulder press": "Shoulder Press (Dumbbell)",
    "concentration curl": "Concentration Curl",
    "rear delt fly": "Rear Delt Reverse Fly (Machine)",
    "tricep pushdown": "Triceps Pushdown",
    "meadows row": "Meadows Rows (Barbell)",
    "weighted back ext": "Back Extension (Weighted Hyperextension)",
    "face pull": "Face Pull",
    # No native cable-pullover template; Pullover (Machine) is the closest stand-in.
    "cable lat pullover": "Pullover (Machine)",
}


def _normalize(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())


def load_cache() -> list[dict]:
    if not CACHE_PATH.exists():
        raise RuntimeError(
            f"{CACHE_PATH} missing. Run: python -m scripts.hevy.exercise_map --bootstrap"
        )
    return json.loads(CACHE_PATH.read_text())


def bootstrap() -> None:
    client = HevyClient()
    templates = list(client.paginate("/exercise_templates", "exercise_templates"))
    CACHE_PATH.write_text(json.dumps(templates, indent=2, sort_keys=True))
    print(f"Wrote {len(templates)} templates to {CACHE_PATH}")


class Resolver:
    def __init__(self):
        self.templates = load_cache()
        self._by_title: dict[str, str] = {
            _normalize(t["title"]): t["id"] for t in self.templates
        }

    def resolve(self, name: str) -> str:
        norm = _normalize(name)
        if norm in OVERRIDES:
            override_title = _normalize(OVERRIDES[norm])
            if override_title in self._by_title:
                return self._by_title[override_title]
            raise KeyError(
                f"Override for '{name}' points to '{OVERRIDES[norm]}' but no such template"
            )
        if norm in self._by_title:
            return self._by_title[norm]
        tokens = set(norm.split())
        candidates = [
            (title, tid)
            for title, tid in self._by_title.items()
            if tokens.issubset(set(title.split()))
        ]
        if len(candidates) == 1:
            return candidates[0][1]
        if len(candidates) > 1:
            raise KeyError(
                f"Ambiguous match for '{name}': {[c[0] for c in candidates[:5]]}. "
                "Add to OVERRIDES."
            )
        raise KeyError(f"No exercise template found for '{name}'. Add to OVERRIDES.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bootstrap", action="store_true")
    parser.add_argument("--resolve", help="Test resolution for a name")
    args = parser.parse_args()
    if args.bootstrap:
        bootstrap()
    elif args.resolve:
        print(Resolver().resolve(args.resolve))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
