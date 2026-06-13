"""Incremental sync of Hevy workouts to data/logs/.

First run: paginates /workouts from the start, writes one JSON file per workout
to data/logs/sessions/<id>.json, regenerates workouts.csv in the Hevy export
schema, and stores the latest updated_at in data/logs/.sync_cursor.

Subsequent runs: hits /workouts/events?since=<cursor> for updated/deleted IDs,
upserts JSON files, regenerates workouts.csv, advances cursor.

Idempotent. Run with `python -m scripts.hevy.sync_archive`.
"""
from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path

from .client import HevyClient

REPO_ROOT = Path(__file__).resolve().parents[2]
LOGS_DIR = REPO_ROOT / "data" / "logs"
SESSIONS_DIR = LOGS_DIR / "sessions"
CSV_PATH = LOGS_DIR / "workouts.csv"
CURSOR_PATH = LOGS_DIR / ".sync_cursor"

KG_TO_LBS = 2.2046226218

CSV_FIELDS = [
    "title",
    "start_time",
    "end_time",
    "description",
    "exercise_title",
    "superset_id",
    "exercise_notes",
    "set_index",
    "set_type",
    "weight_lbs",
    "reps",
    "distance_km",
    "duration_seconds",
    "rpe",
]


def _fmt_dt(iso: str | None) -> str:
    if not iso:
        return ""
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    # Match Hevy export format: "Jun 9, 2026, 6:52 AM"
    return dt.strftime("%b ") + str(dt.day) + dt.strftime(", %Y, ") + dt.strftime("%I:%M %p").lstrip("0")


def _kg_to_lbs(kg) -> str:
    if kg is None:
        return ""
    return f"{round(float(kg) * KG_TO_LBS, 1)}"


def read_cursor() -> str | None:
    if CURSOR_PATH.exists():
        return CURSOR_PATH.read_text().strip() or None
    return None


def write_cursor(value: str) -> None:
    CURSOR_PATH.write_text(value + "\n")


def save_session(workout: dict) -> None:
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    path = SESSIONS_DIR / f"{workout['id']}.json"
    path.write_text(json.dumps(workout, indent=2, sort_keys=True))


def delete_session(workout_id: str) -> None:
    path = SESSIONS_DIR / f"{workout_id}.json"
    if path.exists():
        path.unlink()


def rebuild_csv() -> int:
    rows: list[dict] = []
    if not SESSIONS_DIR.exists():
        return 0
    workouts = [json.loads(p.read_text()) for p in SESSIONS_DIR.glob("*.json")]
    workouts.sort(key=lambda w: w.get("start_time") or "")
    for w in workouts:
        title = w.get("title", "")
        start = _fmt_dt(w.get("start_time"))
        end = _fmt_dt(w.get("end_time"))
        desc = w.get("description") or ""
        for ex in w.get("exercises", []):
            ex_title = ex.get("title", "")
            ss_id = ex.get("superset_id")
            ex_notes = ex.get("notes") or ""
            for s in ex.get("sets", []):
                rows.append(
                    {
                        "title": title,
                        "start_time": start,
                        "end_time": end,
                        "description": desc,
                        "exercise_title": ex_title,
                        "superset_id": "" if ss_id is None else ss_id,
                        "exercise_notes": ex_notes,
                        "set_index": s.get("index", 0),
                        "set_type": s.get("type", "normal"),
                        "weight_lbs": _kg_to_lbs(s.get("weight_kg")),
                        "reps": s.get("reps") if s.get("reps") is not None else "",
                        "distance_km": s.get("distance_meters") / 1000
                        if s.get("distance_meters") is not None
                        else "",
                        "duration_seconds": s.get("duration_seconds")
                        if s.get("duration_seconds") is not None
                        else "",
                        "rpe": s.get("rpe") if s.get("rpe") is not None else "",
                    }
                )
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CSV_PATH.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def full_sync(client: HevyClient) -> str | None:
    latest_updated: str | None = None
    count = 0
    for w in client.paginate("/workouts", "workouts", page_size=10):
        save_session(w)
        count += 1
        upd = w.get("updated_at")
        if upd and (latest_updated is None or upd > latest_updated):
            latest_updated = upd
    print(f"Full sync: wrote {count} workouts")
    return latest_updated


def incremental_sync(client: HevyClient, since: str) -> str | None:
    """Walk /workouts/events?since=<cursor>. Events typically have type
    'updated' or 'deleted'. Returns new cursor (latest updated_at seen)."""
    latest = since
    page = 1
    seen = 0
    while True:
        data = client.get("/workouts/events", since=since, page=page, pageSize=10)
        events = data.get("events", [])
        for ev in events:
            etype = ev.get("type")
            if etype == "deleted":
                wid = ev.get("id") or ev.get("workout", {}).get("id")
                if wid:
                    delete_session(wid)
            else:
                workout = ev.get("workout") or ev
                if workout.get("id"):
                    save_session(workout)
                    upd = workout.get("updated_at")
                    if upd and upd > (latest or ""):
                        latest = upd
            seen += 1
        page_count = data.get("page_count", 1)
        if page >= page_count or not events:
            break
        page += 1
    print(f"Incremental sync: {seen} events")
    return latest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--full", action="store_true", help="Force full re-sync (ignores cursor)"
    )
    args = parser.parse_args()

    client = HevyClient()
    cursor = None if args.full else read_cursor()

    if cursor:
        print(f"Cursor: {cursor}")
        new_cursor = incremental_sync(client, cursor)
    else:
        print("No cursor — running full sync")
        new_cursor = full_sync(client)

    n = rebuild_csv()
    print(f"Rebuilt {CSV_PATH} ({n} rows)")

    if new_cursor:
        write_cursor(new_cursor)
        print(f"Cursor → {new_cursor}")


if __name__ == "__main__":
    main()
