"""Push a block's routines to Hevy.

Reads a structured spec from `brain/current-block.json` (sidecar to the prose
current-block.md). Creates one routine folder named after the block id, then
one routine per (week, day) under it.

Default is dry-run; pass --apply to actually call the API.

Spec format:
{
  "block_id": "2026-Q2-B02",
  "weeks": 5,
  "days": [
    {"label": "D1", "focus": "Squat+Bench", "weekday": "Mon"},
    ...
  ],
  "prescriptions": [
    {
      "week": 1, "day": "D1",
      "exercises": [
        {
          "name": "Low-bar Squat",
          "notes": "Top set @ RPE 6, then backoff",
          "sets": [
            {"type": "warmup", "weight_kg": 60, "reps": 5},
            {"type": "normal", "weight_kg": 180, "reps": 3, "rpe": 6}
          ]
        }
      ]
    }
  ]
}
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .client import HevyClient
from .exercise_map import Resolver

REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "brain" / "current-block.json"


def build_routine_payload(
    block_id: str,
    week: int,
    day: dict,
    prescription: dict,
    folder_id: str | None,
    resolver: Resolver,
) -> dict:
    exercises = []
    for ex_idx, ex in enumerate(prescription["exercises"]):
        template_id = resolver.resolve(ex["name"])
        sets = []
        for set_idx, s in enumerate(ex.get("sets", [])):
            sets.append(
                {
                    "type": s.get("type", "normal"),
                    "weight_kg": s.get("weight_kg"),
                    "reps": s.get("reps"),
                    "distance_meters": s.get("distance_meters"),
                    "duration_seconds": s.get("duration_seconds"),
                    "rpe": s.get("rpe"),
                    "custom_metric": s.get("custom_metric"),
                }
            )
        exercises.append(
            {
                "exercise_template_id": template_id,
                "superset_id": ex.get("superset_id"),
                "rest_seconds": ex.get("rest_seconds"),
                "notes": ex.get("notes", ""),
                "sets": sets,
            }
        )
    title = f"W{week}-{day['label']} {day['focus']}"
    routine = {
        "title": title,
        "notes": prescription.get("notes", ""),
        "exercises": exercises,
    }
    if folder_id is not None:
        routine["folder_id"] = folder_id
    return {"routine": routine}


def load_spec() -> dict:
    if not SPEC_PATH.exists():
        raise SystemExit(
            f"{SPEC_PATH} missing. The designing-training-block skill should "
            "write this alongside current-block.md. See push_block.py docstring "
            "for the schema."
        )
    return json.loads(SPEC_PATH.read_text())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually call the Hevy API. Default is dry-run.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Explicit no-op; dry-run is already the default without --apply.",
    )
    parser.add_argument(
        "--week", type=int, help="Push only this week (default: all weeks)"
    )
    args = parser.parse_args()

    spec = load_spec()
    block_id = spec["block_id"]
    day_lookup = {d["label"]: d for d in spec["days"]}
    resolver = Resolver()

    client = HevyClient() if args.apply else None

    folder_id = None
    if args.apply:
        folder_resp = client.post(
            "/routine_folders", {"routine_folder": {"title": block_id}}
        )
        folder_id = (folder_resp.get("routine_folder") or folder_resp).get("id")
        print(f"Created folder {block_id} -> {folder_id}")
    else:
        print(f"[dry-run] Would create folder: {block_id}")

    for pres in spec["prescriptions"]:
        week = pres["week"]
        if args.week and week != args.week:
            continue
        day = day_lookup[pres["day"]]
        payload = build_routine_payload(
            block_id, week, day, pres, folder_id, resolver
        )
        if args.apply:
            resp = client.post("/routines", payload)
            rid = (resp.get("routine") or resp).get("id")
            print(f"Created W{week}-{day['label']} -> {rid}")
        else:
            print(f"[dry-run] W{week}-{day['label']}:")
            print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
