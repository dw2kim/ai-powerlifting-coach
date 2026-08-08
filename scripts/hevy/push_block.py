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


# Hevy's routine API accepts only these set types; anything else 400s with "Invalid set type".
# A timed hold is a *normal* set carrying duration_seconds — there is no "duration" type.
_VALID_SET_TYPES = {"normal", "warmup", "dropset", "failure"}


def _set_type(raw: str | None) -> str:
    return raw if raw in _VALID_SET_TYPES else "normal"


def _notes_with_scheme(sets: list[dict], notes: str) -> str:
    """Prefix the set scheme + RPE onto the exercise note.

    The routine API rejects a per-set `rpe` key outright ("Unrecognized key(s) in object:
    'rpe'"), so the prescribed RPE has nowhere to live in the payload. Without this it would
    simply vanish on the way into the app — and RPE is the whole autoregulation contract on a
    capped block. Folding it into the note keeps it in front of the athlete mid-session.
    """
    if not sets:
        return notes
    first = sets[0]
    if first.get("duration_seconds"):
        scheme = f"{len(sets)}×{first['duration_seconds']}s"
    elif first.get("reps") is not None:
        scheme = f"{len(sets)}×{first['reps']}"
    else:
        scheme = f"{len(sets)} sets"
    rpe = first.get("rpe")
    if rpe is not None:
        rpe_txt = int(rpe) if float(rpe).is_integer() else rpe
        scheme += f" @{rpe_txt}"
    return f"[{scheme}] {notes}".strip()


def _routine_id(resp) -> str | None:
    """Pull the id out of a POST /routines response.

    The API returns the created routine wrapped in a LIST (`{"routine": [{...}]}`), not a
    bare object — assuming a dict here crashed a push midway and left the block half-created
    in the app.
    """
    obj = resp.get("routine", resp) if isinstance(resp, dict) else resp
    if isinstance(obj, list):
        obj = obj[0] if obj else {}
    return obj.get("id") if isinstance(obj, dict) else None


def existing_titles(client) -> set[str]:
    """Titles already in Hevy, so a resumed push doesn't duplicate what's there."""
    return {r.get("title") for r in client.paginate("/routines", "routines") if r.get("title")}


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
        raw_sets = ex.get("sets", [])
        sets = []
        for set_idx, s in enumerate(raw_sets):
            sets.append(
                {
                    "type": _set_type(s.get("type")),
                    "weight_kg": s.get("weight_kg"),
                    "reps": s.get("reps"),
                    "distance_meters": s.get("distance_meters"),
                    "duration_seconds": s.get("duration_seconds"),
                    "custom_metric": s.get("custom_metric"),
                }
            )
        exercises.append(
            {
                "exercise_template_id": template_id,
                "superset_id": ex.get("superset_id"),
                "rest_seconds": ex.get("rest_seconds"),
                "notes": _notes_with_scheme(raw_sets, ex.get("notes", "")),
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
    parser.add_argument(
        "--folder-id",
        help="Push into an existing routine folder instead of creating one. Use this to "
             "resume after a partial failure, so the block doesn't end up with duplicate "
             "folders in the app.",
    )
    args = parser.parse_args()

    spec = load_spec()
    block_id = spec["block_id"]
    day_lookup = {d["label"]: d for d in spec["days"]}
    resolver = Resolver()

    client = HevyClient() if args.apply else None

    folder_id = args.folder_id
    if args.apply and folder_id is None:
        folder_resp = client.post(
            "/routine_folders", {"routine_folder": {"title": block_id}}
        )
        folder_id = (folder_resp.get("routine_folder") or folder_resp).get("id")
        print(f"Created folder {block_id} -> {folder_id}")
    elif args.apply:
        print(f"Reusing folder {block_id} -> {folder_id}")
    else:
        print(f"[dry-run] Would create folder: {block_id}")

    existing = existing_titles(client) if args.apply else set()

    for pres in spec["prescriptions"]:
        week = pres["week"]
        if args.week and week != args.week:
            continue
        day = day_lookup[pres["day"]]
        payload = build_routine_payload(
            block_id, week, day, pres, folder_id, resolver
        )
        if args.apply:
            title = payload["routine"]["title"]
            if title in existing:
                print(f"Skipped W{week}-{day['label']} (already in Hevy)")
                continue
            resp = client.post("/routines", payload)
            print(f"Created W{week}-{day['label']} -> {_routine_id(resp)}")
            existing.add(title)
        else:
            print(f"[dry-run] W{week}-{day['label']}:")
            print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
