"""Push a block's routines to Hevy.

Reads a structured spec from `brain/current-block.json` (sidecar to the prose
current-block.md). Creates **one routine folder per week** — `<block-id>-W<n>`, e.g.
`2026-Q4-B08-W1` — and files that week's routines under it, so a training week is one tap
in the app instead of a scroll through twenty routines (FB 2026-11-21). Set
`"folder_layout": "single"` in the spec for the old one-folder-per-block shape; B7 and
earlier are pinned to it because they are already live.

Default is dry-run; pass --apply to actually call the API.

Correcting a block that is already live: `--update` PUTs over the routines whose titles
match instead of skipping them, and `--start W1-D3` leaves the sessions already trained
alone. Hevy exposes no DELETE for routines, so overwriting in place is the only way to fix a
pushed block without the athlete hand-deleting rows in the app.

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
          "tier": "primary",
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

Two things this module guarantees on the way out, because the app is what the athlete
actually trains off:

- **Loads match the Google Sheet.** Every weight is re-snapped onto a real loading increment
  and converted with Hevy's own factor, so a 70 lb prescription reads "70" in the app rather
  than "70.11". See `units.py`.
- **Every exercise carries a rest timer** — primary 1:15 (1:00 in the warm-up week and the
  deload), secondary/accessory 1:00, core 0:30 — from the entry's `tier`. See `rest_times.py`.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .client import HevyClient
from .exercise_map import Resolver
from .rest_times import fmt_rest, is_light_week, rest_seconds_for, tier_for, week_phase
from .units import fmt_lb, normalize_kg

REPO_ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = REPO_ROOT / "brain" / "current-block.json"


# Hevy's routine API accepts only these set types; anything else 400s with "Invalid set type".
# A timed hold is a *normal* set carrying duration_seconds — there is no "duration" type.
_VALID_SET_TYPES = {"normal", "warmup", "dropset", "failure"}

def _set_type(raw: str | None) -> str:
    return raw if raw in _VALID_SET_TYPES else "normal"


def _superset_id(ex: dict) -> int | None:
    """Hevy's `superset_id` is a NUMBER. A string here is silently coerced to NaN.

    B7's first push died on this: the block JSON used readable labels ("d1a", "d2b") and
    Hevy answered `400 Expected number, received nan` — twice, once per exercise in W1-D1's
    superset pair — after the routine folder had already been created. The dry run could not
    catch it, because it printed loads and timers and never looked at superset_id.

    So: accept an int, accept a digit string, and refuse anything else loudly at build time
    rather than at the API. Exercises sharing a superset share the number, and it only has to
    be unique within the routine.
    """
    raw = ex.get("superset_id")
    if raw is None or isinstance(raw, int) and not isinstance(raw, bool):
        return raw
    if isinstance(raw, str) and raw.strip().lstrip("-").isdigit():
        return int(raw)
    raise SystemExit(
        f"superset_id must be a number or null, got {raw!r} on {ex.get('name', '?')}. "
        "Hevy coerces a non-numeric superset_id to NaN and rejects the routine with "
        "'Expected number, received nan'. Number the supersets within each routine (0, 1, …)."
    )


def _notes_with_scheme(sets: list[dict], notes: str) -> str:
    """Prefix the set scheme + RPE onto the exercise note.

    The routine API rejects a per-set `rpe` key outright ("Unrecognized key(s) in object:
    'rpe'"), so the prescribed RPE has nowhere to live in the payload. Without this it would
    simply vanish on the way into the app — and RPE is the whole autoregulation contract on a
    capped block. Folding it into the note keeps it in front of the athlete mid-session.

    Warm-ups are left out: the scheme is the work. A bodyweight warm-up ×8 ahead of 4×5 read
    as "[5×8]" — wrong set count, and the warm-up's reps in place of the working reps. Runs of
    identical working sets collapse, so a top set + backoffs reads "1×3 @8 + 4×5 @7".
    """
    working = [s for s in sets if s.get("type") != "warmup"]
    if not working:
        return notes

    def _unit(s: dict) -> tuple:
        return (s.get("duration_seconds"), s.get("reps"), s.get("rpe"))

    groups: list[list[dict]] = []
    for s in working:
        if groups and _unit(groups[-1][0]) == _unit(s):
            groups[-1].append(s)
        else:
            groups.append([s])

    def _fmt(group: list[dict]) -> str:
        first, n = group[0], len(group)
        if first.get("duration_seconds"):
            txt = f"{n}×{first['duration_seconds']}s"
        elif first.get("reps") is not None:
            txt = f"{n}×{first['reps']}"
        else:
            txt = f"{n} sets"
        rpe = first.get("rpe")
        if rpe is not None:
            rpe_txt = int(rpe) if float(rpe).is_integer() else rpe
            txt += f" @{rpe_txt}"
        return txt

    scheme = " + ".join(_fmt(g) for g in groups)
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


def existing_routines(client, folder_ids: set | None = None) -> dict[str, str]:
    """Map routine title -> id for what's already in Hevy.

    Used two ways: to skip what's already there on a resumed push, and (with --update) to PUT
    a corrected routine straight over the old one. The Hevy API has **no DELETE for routines**,
    so overwriting in place is the only way to fix a block that's already live without the
    athlete hand-deleting rows in the app.

    `folder_ids` narrows the map to this block's own folders. Routine titles are
    `W<n>-D<n> <focus>` and carry no block id, so two blocks that keep the same split
    produce the *same* titles — B3 and B4 both had "W1-D1 Squat + Comp Bench". Unscoped, a
    new block's push would skip (or, with --update, overwrite) a leftover routine from the
    prior block. Pass None to fall back to the whole account, which is what an update does
    when the block's folders can't be found. FB 2026-11-21.
    """
    # Compare as strings: `--folder-id` arrives from argparse as "200" while Hevy returns
    # folder_id 200, and a str/int miss here silently turns a resume into duplicates.
    wanted = None if folder_ids is None else {str(f) for f in folder_ids}
    out: dict[str, str] = {}
    for r in client.paginate("/routines", "routines"):
        if not (r.get("title") and r.get("id")):
            continue
        if wanted is not None and str(r.get("folder_id")) not in wanted:
            continue
        out[r["title"]] = r["id"]
    return out


def folder_layout(spec: dict) -> str:
    """`"per-week"` (the default) or `"single"`.

    The athlete asked for a folder per week so he opens one week in the app rather than
    scrolling a whole block (FB 2026-11-21). Default is per-week so nobody has to remember
    the key on a new block; B7 and earlier carry `"single"` in their own JSON, because
    re-shaping the folders of a block he is already training off is not a correction.
    """
    layout = spec.get("folder_layout", "per-week")
    if layout not in ("single", "per-week"):
        raise SystemExit(
            f'folder_layout must be "single" or "per-week" (got {layout!r})'
        )
    return layout


def folder_title(block_id: str, layout: str, week: int) -> str:
    """`2026-Q4-B08-W1` per-week, or the bare block id under the old single layout."""
    return block_id if layout == "single" else f"{block_id}-W{week}"


def resolve_folder(client, title: str, *, create: bool, apply: bool) -> str | None:
    """Folder id for `title`: reuse one that already exists, create it only if asked to.

    Reuse before create, because a retry after a partial failure must not add a second
    folder — B7 left two empty ones in a single morning and Hevy has no API delete for
    folders. `create=False` is update mode, which must never add a folder: the routines it
    PUTs keep whatever folder they are already filed under.
    """
    if not apply:
        print(f"[dry-run] Would use folder: {title}")
        return None
    same_title = existing_folders(client, title)
    if same_title:
        if len(same_title) > 1:
            print(f"⚠️  {len(same_title)} folders are titled {title}: "
                  f"{', '.join(str(i) for i in same_title)}. Filling the first; "
                  f"delete the others in the app (Hevy has no API delete for folders).")
        print(f"Reusing existing folder {title} -> {same_title[0]}")
        return same_title[0]
    if not create:
        print(f"⚠️  No folder titled {title} — its routines keep the folder they're in.")
        return None
    resp = client.post("/routine_folders", {"routine_folder": {"title": title}})
    fid = (resp.get("routine_folder") or resp).get("id")
    print(f"Created folder {title} -> {fid}")
    return fid


def existing_folders(client, title: str) -> list[str]:
    """Ids of every routine folder already titled `title`, oldest (lowest id) first.

    Why this exists: a push that dies partway has already created its folder, and the next
    attempt used to create *another* one. B7 did this twice in one morning — folders 4003373
    and 4003492, both empty — and Hevy has no DELETE for routines, so cleanup is by hand in
    the app. Looking the folder up by title makes a retry idempotent, which is what it should
    have been, and means nobody has to remember a folder id or which branch they are on.

    Tolerant of the response shape (a `routine_folders` list, a bare list, or a single
    object) and never fatal: if the lookup fails, the caller falls back to creating one and
    says so, because a duplicate folder is annoying and a blocked push is worse.
    """
    try:
        items = list(client.paginate("/routine_folders", "routine_folders"))
    except Exception as exc:  # noqa: BLE001 - shape/endpoint drift must not block a push
        print(f"⚠️  Could not list routine folders ({exc}); falling back to creating one.")
        return []
    found = []
    for it in items:
        if not isinstance(it, dict):
            continue
        f = it.get("routine_folder") if isinstance(it.get("routine_folder"), dict) else it
        if f.get("title") == title and f.get("id") is not None:
            found.append(f["id"])
    # Lowest id first: the one created first is the one to fill.
    return sorted(found, key=lambda i: (len(str(i)), str(i)))


# Hevy files every cable movement under equipment "machine". These are the cable ones whose
# template title doesn't say "(Cable)".
_CABLE_TITLES = {"face pull", "pallof press", "triceps pushdown", "rope straight arm pulldown"}


def superset_station(template: dict) -> str:
    """Where in the gym an exercise is done, for `superset-same-equipment`.

    Free weights you carry with you (dumbbell, kettlebell, barbell, band, bodyweight) are their
    equipment type. A cable movement is "cable": one stack, swap the handle. Any other machine is
    its own station — you can't hold the chest fly machine while you're on the leg curl.
    """
    eq = template.get("equipment") or "none"
    title = (template.get("title") or "").lower()
    if eq == "machine":
        if "cable" in title or title in _CABLE_TITLES:
            return "cable"
        return f"machine:{title}"
    return eq


def check_supersets(exercises: list[dict], resolver: Resolver, where: str = "") -> None:
    """Refuse a superset whose members aren't done on the same equipment
    (`superset-same-equipment`): dumbbell + dumbbell or cable + cable, never machine + anything."""
    paired = [ex for ex in exercises if _superset_id(ex) is not None]
    if not paired:
        return
    by_id = {t["id"]: t for t in getattr(resolver, "templates", [])}
    groups: dict[int, list[tuple[str, str]]] = {}
    for ex in paired:
        ss = _superset_id(ex)
        tpl = by_id.get(resolver.resolve(ex["name"]), {"title": ex["name"]})
        groups.setdefault(ss, []).append((ex["name"], superset_station(tpl)))
    for ss, members in groups.items():
        stations = {st for _, st in members}
        machine = any(st.startswith("machine:") for st in stations)
        if len(stations) > 1 or (machine and len(members) > 1):
            listing = ", ".join(f"{n} [{st}]" for n, st in members)
            raise ValueError(
                f"{where} superset {ss} mixes equipment: {listing}. "
                "superset-same-equipment: pair only dumbbell+dumbbell, cable+cable, etc. — "
                "never a machine with anything. Unpair it (superset_id: null) or swap one side."
            )


def exercise_payload(ex: dict, resolver: Resolver, light_week: bool = False) -> dict:
    """One prescription entry as the routine API wants it. Shared with the weekend make-up
    (scripts/review/weekend_makeup.py) so both land in the app the same way."""
    template_id = resolver.resolve(ex["name"])
    raw_sets = ex.get("sets", [])
    sets = []
    for s in raw_sets:
        sets.append(
            {
                "type": _set_type(s.get("type")),
                # Normalized, not passed through: the app displays lb, and an
                # imprecisely-stored kg shows up there as "70.11" instead of "70".
                "weight_kg": normalize_kg(s.get("weight_kg")),
                "reps": s.get("reps"),
                "distance_meters": s.get("distance_meters"),
                "duration_seconds": s.get("duration_seconds"),
                "custom_metric": s.get("custom_metric"),
            }
        )
    return {
        "exercise_template_id": template_id,
        "superset_id": _superset_id(ex),
        "rest_seconds": rest_seconds_for(ex, light_week),
        "notes": _notes_with_scheme(raw_sets, ex.get("notes", "")),
        "sets": sets,
    }


def build_routine_payload(
    block_id: str,
    week: int,
    day: dict,
    prescription: dict,
    folder_id: str | None,
    resolver: Resolver,
    light_week: bool = False,
) -> dict:
    check_supersets(prescription["exercises"], resolver, f"W{week}-{day['label']}:")
    exercises = [
        exercise_payload(ex, resolver, light_week) for ex in prescription["exercises"]
    ]
    # A prescription may override the day's shared focus. The `days` list is block-wide, so
    # editing it to retitle one session would rename that day in *every* week and strand the
    # rest as duplicates — the exact `push-is-idempotent-with-update` failure this avoids.
    focus = prescription.get("focus") or day["focus"]
    title = f"W{week}-{day['label']} {focus}"
    routine = {
        "title": title,
        "notes": prescription.get("notes", ""),
        "exercises": exercises,
    }
    if folder_id is not None:
        routine["folder_id"] = folder_id
    return {"routine": routine}


def _sets_summary(sets: list[dict]) -> str:
    """Collapse a payload's sets into one lb-denominated line, as the app will show them."""
    if not sets:
        return "—"
    parts = []
    for s in sets:
        if s.get("duration_seconds"):
            rep_txt = f"{s['duration_seconds']}s"
        else:
            rep_txt = f"×{s.get('reps')}" if s.get("reps") is not None else "×?"
        load = fmt_lb(s.get("weight_kg"))
        tag = "warmup " if s.get("type") == "warmup" else ""
        parts.append(f"{tag}{load} lb {rep_txt}")
    # Identical sets collapse to "3 × 225 lb ×5" rather than repeating three times.
    if len(set(parts)) == 1:
        return f"{len(parts)} × {parts[0]}"
    return " | ".join(parts)


def print_routine_preview(payload: dict, spec_exercises: list[dict]) -> None:
    """Human-checkable dry-run view: loads in lb and the rest timer, per exercise.

    The raw payload is kg and unreadable at a glance, which is how a block once went out with
    "70.11 lb" loads and no rest timers. This is the view to check against the Sheet.
    """
    routine = payload["routine"]
    print(f"  {routine['title']}")
    for ex, src in zip(routine["exercises"], spec_exercises):
        rest = fmt_rest(ex["rest_seconds"])
        # superset_id is shown because it is pushed: an unprintable field is a field nobody
        # checks, and a bad one took out B7's first push after the folder was created.
        ss = ex.get("superset_id")
        ss_tag = f" SS{ss}" if ss is not None else ""
        print(
            f"    {src['name']:<32} {tier_for(src):<10} rest {rest:>5}{ss_tag:<5} "
            f"{_sets_summary(ex['sets'])}"
        )


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
        "--skip-rotation-check",
        action="store_true",
        help="Push a new block even if it misses the accessory-rotation floor. Only on the "
        "athlete's say-so.",
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
        help="Push every selected week into this one existing folder instead of resolving "
             "a folder per week. Use this to resume after a partial failure, so the block "
             "doesn't end up with duplicate folders in the app.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Dry-run: dump the raw kg payload instead of the lb preview.",
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

    # A brand-new block (not a correction, not a resume) has to clear the rotation floor first.
    # B7 went out with zero real accessory rotations and nobody caught it. FB 2026-11-11.
    if not (args.update or args.folder_id or args.start or args.week):
        from scripts.review.rotation_check import compare, find_prior, render

        rep = compare(spec, json.loads(find_prior(block_id).read_text()), resolver)
        print(render(rep))
        if rep.failures():
            if args.apply and not args.skip_rotation_check:
                raise SystemExit(
                    "Refusing to push: the block misses the accessory-rotation floor. Rotate more, "
                    "or pass --skip-rotation-check on the athlete's say-so."
                )
            print("⚠️  Rotation floor not met"
                  + (" — pushing anyway (--skip-rotation-check)." if args.apply else "."))

    client = HevyClient() if args.apply else None
    layout = folder_layout(spec)

    # Which sessions this invocation actually touches. Folders are resolved only for the
    # weeks that get a routine, so a `--start W3-D2` correction doesn't leave empty W1/W2
    # folders behind in the app.
    selected = []
    for pres in spec["prescriptions"]:
        week = pres["week"]
        if args.week and week != args.week:
            continue
        if start_key and (week, day_order[pres["day"]]) < start_key:
            continue
        selected.append(pres)
    weeks = sorted({p["week"] for p in selected})

    folders: dict[int, str | None] = {}
    if args.folder_id:
        print(f"Using folder {args.folder_id} for every selected week (--folder-id)")
        folders = {w: args.folder_id for w in weeks}
    else:
        if args.update:
            # An update lands on routines that already exist, and they already have a
            # folder. Creating one here would leave an empty folder behind on every
            # correction. The lookup still runs, to scope the title match to this block.
            print("Update mode: reusing each routine's existing folder")
        # Ascending week order, so the app lists W1 … W5 in the order he trains them.
        for w in weeks:
            folders[w] = resolve_folder(
                client,
                folder_title(block_id, layout, w),
                create=not args.update,
                apply=bool(args.apply),
            )
            if layout == "single":
                folders = dict.fromkeys(weeks, folders[w])
                break

    found = {f for f in folders.values() if f is not None}
    existing = existing_routines(client, found or None) if args.apply else {}

    for pres in selected:
        week = pres["week"]
        day = day_lookup[pres["day"]]
        light = is_light_week(week, week_phase(spec, week))
        payload = build_routine_payload(
            block_id, week, day, pres, folders.get(week), resolver, light
        )
        title = payload["routine"]["title"]
        if args.apply:
            # `replaces_title` is how a routine that was retitled in the app gets reused
            # instead of orphaned. Hevy has no DELETE, so a routine whose title no longer
            # matches the plan can only be reclaimed by PUTting the new title over its id.
            routine_id = existing.get(title) or existing.get(pres.get("replaces_title", ""))
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
        elif args.json:
            print(f"[dry-run] W{week}-{day['label']}:")
            print(json.dumps(payload, indent=2))
        else:
            # Say when the week was judged light, so a working W1 pushed at 1:00 shows up
            # here rather than in the app.
            tag = " (light week: primaries rest 1:00)" if light else ""
            print(f"[dry-run] W{week}-{day['label']}:{tag}")
            print_routine_preview(payload, pres["exercises"])


if __name__ == "__main__":
    main()
