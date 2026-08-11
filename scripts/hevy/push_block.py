"""Push a block's routines to Hevy.

Reads a structured spec from `brain/current-block.json` (sidecar to the prose
current-block.md). Creates one routine folder named after the block id, then
one routine per (week, day) under it.

Default is dry-run; pass --apply to actually call the API.

Correcting a block that is already live: `--update` PUTs over the routines whose titles
match instead of skipping them, and `--start W1-D3` leaves the sessions already trained
alone. Hevy exposes no DELETE for routines, so overwriting in place is the only way to fix a
pushed block without the athlete hand-deleting rows in the app.

Loads are stored as kg (the API's unit) but the athlete's app displays lb, so every
`weight_kg` is snapped to the exact kg equivalent of a whole pound on the way out — see
`_snap_weight`.

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
          "rest_seconds": 180,
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

# The API speaks kg; the athlete's app displays lb. A kg value rounded for readability
# (102.1) round-trips to 225.09 lb in the app, so every load shows up with a junk decimal
# and the plate maths stops being obvious mid-set. Snapping to the exact kg equivalent of a
# whole pound (225 lb -> 102.05840825 kg) makes the app render a clean 225. Rule
# `hevy-load-precision`.
LB_TO_KG = 0.45359237


def _set_type(raw: str | None) -> str:
    return raw if raw in _VALID_SET_TYPES else "normal"


def _snap_weight(kg: float | None) -> float | None:
    """Snap a kg load onto the nearest whole pound so the app shows a round number."""
    if kg is None or kg == 0:
        return kg
    return round(round(float(kg) / LB_TO_KG) * LB_TO_KG, 8)


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


def existing_routines(client) -> dict[str, str]:
    """Map routine title -> id for everything already in Hevy.

    Used two ways: to skip what's already there on a resumed push, and (with --update) to PUT
    a corrected routine straight over the old one. The Hevy API has **no DELETE for routines**,
    so overwriting in place is the only way to fix a block that's already live without the
    athlete hand-deleting rows in the app.
    """
    return {
        r["title"]: r["id"]
        for r in client.paginate("/routines", "routines")
        if r.get("title") and r.get("id")
    }


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
                    "weight_kg": _snap_weight(s.get("weight_kg")),
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
        "--start",
        help="Start at this (week, day) and push everything from there on, e.g. W1-D3. "
             "Use it to leave sessions already trained untouched when correcting a live block.",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="Overwrite routines that already exist (PUT) instead of skipping them. This is "
             "how a live block gets corrected — Hevy has no routine DELETE, so re-POSTing "
             "would leave duplicates the athlete has to clean up by hand.",
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
    day_order = {d["label"]: i for i, d in enumerate(spec["days"])}
    resolver = Resolver()

    start_key = None
    if args.start:
        week_s, _, day_s = args.start.upper().partition("-")
        if not day_s or day_s not in day_order:
            raise SystemExit(f"--start must look like W1-D3 (got {args.start!r})")
        start_key = (int(week_s.lstrip("W")), day_order[day_s])

    client = HevyClient() if args.apply else None

    folder_id = args.folder_id
    if args.update and folder_id is None:
        # An update lands on routines that already exist, and they already have a folder.
        # Creating one here would leave an empty folder behind on every correction.
        print("Update mode: reusing each routine's existing folder")
    elif args.apply and folder_id is None:
        folder_resp = client.post(
            "/routine_folders", {"routine_folder": {"title": block_id}}
        )
        folder_id = (folder_resp.get("routine_folder") or folder_resp).get("id")
        print(f"Created folder {block_id} -> {folder_id}")
    elif args.apply:
        print(f"Reusing folder {block_id} -> {folder_id}")
    else:
        print(f"[dry-run] Would create folder: {block_id}")

    existing = existing_routines(client) if args.apply else {}

    for pres in spec["prescriptions"]:
        week = pres["week"]
        if args.week and week != args.week:
            continue
        if start_key and (week, day_order[pres["day"]]) < start_key:
            continue
        day = day_lookup[pres["day"]]
        payload = build_routine_payload(
            block_id, week, day, pres, folder_id, resolver
        )
        title = payload["routine"]["title"]
        if args.apply:
            routine_id = existing.get(title)
            if routine_id and args.update:
                # folder_id isn't part of the update payload — the routine keeps the folder
                # it's already filed under.
                body = {"routine": {k: v for k, v in payload["routine"].items()
                                    if k != "folder_id"}}
                client.put(f"/routines/{routine_id}", body)
                print(f"Updated W{week}-{day['label']} -> {routine_id}")
                continue
            if routine_id:
                print(f"Skipped W{week}-{day['label']} (already in Hevy; --update to overwrite)")
                continue
            resp = client.post("/routines", payload)
            new_id = _routine_id(resp)
            print(f"Created W{week}-{day['label']} -> {new_id}")
            existing[title] = new_id
        else:
            verb = "Would update" if args.update else "Would create"
            print(f"[dry-run] {verb} W{week}-{day['label']}:")
            print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
