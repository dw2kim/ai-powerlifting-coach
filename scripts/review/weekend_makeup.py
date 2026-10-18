"""Friday make-up — the week's missed accessories as one home routine for the weekend.

Rule `weekend-makeup` (FB 2026-10-17). Runs Friday 12:00 America/New_York from
.github/workflows/weekend-makeup.yml, after D4 (6–7am) is in the log and with the weekend
still ahead:

  1. Time guard — the first Friday firing at/after 12:00 ET does the work; later firings
     no-op against the week's record in reviews/makeup/.
  2. Sync the Hevy log (best-effort, as on Saturday).
  3. Plan vs log for the block week: working sets prescribed vs logged, per exercise.
  4. What's owed — an exercise with nothing logged, or two or more sets short. One set short
     is ignored (athlete's call).
  5. What can be done at home — data/home-gym.json holds the home swap, how it is loaded,
     and the exercises that are never made up. Big-5 lifts and barbell secondaries never
     are, by tier. Capped at MAX_EXERCISES, everything @MAKEUP_RPE.
  6. One routine in the Hevy folder "Weekend Make-up", overwritten every week (the routine
     API has no DELETE). Pushed without a confirm step, the athlete's call: it never touches
     the block's routines.
  7. Telegram the list, write reviews/makeup/<iso-week>.md, commit.

A day with no session is told apart by date. A day already past was skipped, and its
accessories are owed. Today's (D4, on a Friday run) is "not logged yet" and adds nothing:
it may just not be finished in the app.

Flags:
  --force       bypass the time guard (manual runs)
  --dry-run     compute + print; no Hevy write, no Telegram, no record, no commit
  --no-commit   do everything but commit/push
  --skip-sync   don't pull the Hevy log first
  --date        run for the week containing this date (YYYY-MM-DD)
"""
from __future__ import annotations

import argparse
import html
import json
import statistics
from datetime import date as date_cls, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from ..hevy.block_report import KG_TO_LBS, REPO_ROOT, load_window
from ..hevy.push_block import _routine_id, exercise_payload, print_routine_preview
from ..hevy.rest_times import tier_for
from ..hevy.units import lb_to_kg
from ..notifications import telegram
from .weekly_metrics import (
    DAY_WEEKDAY,
    MAKEUP_TITLE_PREFIX,
    _index_exercises,
    _load_block,
    _match_all,
    _normalize,
    _safe_resolver,
    _sessions_in,
    geometry,
    readiness,
)
from .weekly_review import commit, summary, sync_log

EASTERN = ZoneInfo("America/New_York")
HOME_GYM = REPO_ROOT / "data" / "home-gym.json"
MAKEUP_DIR = REPO_ROOT / "reviews" / "makeup"
FOLDER_TITLE = "Weekend Make-up"

# The make-up is catch-up, not a fifth training day: about half an hour, nothing hard.
MAX_EXERCISES = 5
MAKEUP_RPE = 7
# Athlete, 2026-10-17: "ignore it if only 1 set is missed".
MIN_SETS_SHORT = 2
# Fill order when the cap bites. Cuff work first, Monday-bench-adjacent work after the rest.
CLASS_ORDER = ["priority", "standard", "saturday-only", "core"]
# `log` loads: the median of the last few sessions of the home exercise.
LOG_LOOKBACK_DAYS = 365
LOG_ANCHOR_SESSIONS = 3
NEVER_TIERS = {"primary", "secondary"}
WEEKDAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _eastern_now() -> datetime:
    return datetime.now(EASTERN)


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def record_path_for(day: date_cls) -> Path:
    """The week's record. Also the time guard's idempotency key: one make-up per ISO week."""
    iso_year, iso_week, _ = day.isocalendar()
    return MAKEUP_DIR / f"{iso_year}-W{iso_week:02d}.md"


def time_guard(force: bool, now: datetime, already_done: bool) -> tuple[bool, str]:
    """(should we run, why). Two Friday firings so one lands at/after 12:00 ET in EDT and
    EST; the first one past noon does the work and the record makes the rest no-ops. A
    late firing still ships, the same lesson as the Saturday review's guard."""
    if force:
        return True, "forced"
    if now.weekday() != 4:
        return False, "not Friday"
    if now.hour < 12:
        return False, "before 12:00 ET"
    if already_done:
        return False, "this week's make-up already shipped"
    return True, "this firing does the work"


# --- the home gym --------------------------------------------------------------------

def load_home(path: Path = HOME_GYM) -> dict:
    return json.loads(path.read_text())


def swaps_by_template(home: dict, resolve) -> dict[str, dict]:
    """The swap table keyed by Hevy template id, so a block that renames an exercise still
    finds its swap. A key that resolves to nothing is a typo in the data file: fail loud,
    or that exercise is silently never made up again."""
    out: dict[str, dict] = {}
    for key, swap in home.get("swaps", {}).items():
        tid = resolve(key)
        if not tid:
            raise SystemExit(f"{_rel(HOME_GYM)}: swap {key!r} doesn't resolve to a Hevy "
                             "template. Fix the key or add it to exercise_map.OVERRIDES.")
        out[tid] = {**swap, "key": key}
    return out


def snap_dumbbell(lb: float, equipment: dict) -> float:
    """Down onto the home dumbbell grid, inside what's on the rack. Down, not nearest: the
    make-up runs @7, and a home set that came out heavier than the gym's isn't catch-up."""
    step = equipment.get("dumbbell_step_lb", 5)
    lo = equipment.get("dumbbell_min_lb", step)
    hi = equipment.get("dumbbell_max_lb", lb)
    snapped = int((lb + 1e-6) // step) * step
    return float(max(lo, min(hi, snapped)))


def home_log_load(tid: str, today: date_cls) -> float | None:
    """Median top working load of the last LOG_ANCHOR_SESSIONS sessions of an exercise
    (`loads-from-logs`). Reads the whole archive, make-ups included: home history is
    exactly the history a home exercise should be anchored on."""
    start = (today - timedelta(days=LOG_LOOKBACK_DAYS)).isoformat()
    tops = []
    for w in load_window(start, today.isoformat()):
        for ex in w.get("exercises", []):
            if ex.get("exercise_template_id") != tid:
                continue
            loads = [s["weight_kg"] for s in ex.get("sets", [])
                     if s.get("type") != "warmup" and s.get("weight_kg")]
            if loads:
                tops.append(max(loads) * KG_TO_LBS)
    return statistics.median(tops[-LOG_ANCHOR_SESSIONS:]) if tops else None


# --- plan vs log -----------------------------------------------------------------------

def _working(sets: list[dict]) -> list[dict]:
    return [s for s in sets if s.get("type") != "warmup"]


def _week_prescriptions(block: dict, week_no: int) -> list[dict]:
    week = [p for p in block.get("prescriptions", []) if p.get("week") == week_no]
    return sorted(week, key=lambda p: DAY_WEEKDAY.get(p.get("day"), 9))


def day_statuses(block: dict, geo: dict, today: date_cls,
                 week_sessions: list[dict]) -> dict[str, str]:
    """logged / skipped / pending, per planned day of the week.

    Logged by weekday (the review's own mapping, Friday→Saturday slip included) or by a
    workout titled from that day's routine, which also catches a day trained on the wrong
    weekday. Unlogged and already past = skipped; unlogged today or later = pending."""
    week_no = geo["week_no"]
    days = [p["day"] for p in _week_prescriptions(block, week_no)]
    logged = set(readiness(week_sessions, days)["logged"])
    for w in week_sessions:
        for d in days:
            if (w.get("title") or "").startswith(f"W{week_no}-{d}"):
                logged.add(d)
    week_mon = date_cls.fromisoformat(geo["week_start"])
    out = {}
    for d in days:
        if d in logged:
            out[d] = "logged"
        elif week_mon + timedelta(days=DAY_WEEKDAY[d]) < today:
            out[d] = "skipped"
        else:
            out[d] = "pending"
    return out


def diff_week(block: dict, week_no: int, statuses: dict[str, str],
              week_sessions: list[dict], resolve, swaps: dict[str, dict]) -> list[dict]:
    """One row per planned exercise: working sets prescribed vs logged across the week.

    Matched week-wide, not per day, because an exercise moved to another day was still
    done. A logged swap or equivalent (`also_counts`, e.g. the DB rear-delt fly when the
    pec deck was taken) counts as the exercise — `equipment-fallbacks`."""
    index = _index_exercises(week_sessions)
    rows: dict[str, dict] = {}
    for presc in _week_prescriptions(block, week_no):
        day = presc["day"]
        for ex in presc.get("exercises", []):
            name = ex.get("name", "")
            row = rows.setdefault(name, {
                "name": name, "tier": tier_for(ex), "tid": resolve(name),
                "days": [], "planned": 0, "entry": ex,
            })
            row["days"].append(day)
            if statuses.get(day) != "pending":
                row["planned"] += len(_working(ex.get("sets", [])))

    # An equivalent that is planned in its own right this week is that exercise's sets, not
    # this one's: D4's CS row must not cover a missed D1 Iso-Lateral Row.
    planned_tids = {r["tid"] for r in rows.values() if r["tid"]}
    for row in rows.values():
        swap = swaps.get(row["tid"]) or {}
        also = {_normalize(t) for t in swap.get("also_counts", [])}
        hits = {id(e): e for e in _match_all(row["name"], index, resolve)}
        hits.update({id(e["ex"]): e["ex"] for e in index
                     if e["title_norm"] in also
                     and (e["tid"] == row["tid"] or e["tid"] not in planned_tids)})
        row["logged"] = sum(len(_working(e.get("sets", []))) for e in hits.values())
        short = row["planned"] - row["logged"]
        if row["planned"] == 0:
            row["status"], row["owed"] = "pending", 0
        elif row["logged"] == 0:
            row["status"], row["owed"] = "missed", row["planned"]
        elif short >= MIN_SETS_SHORT:
            row["status"], row["owed"] = "short", short
        elif short == 1:
            row["status"], row["owed"] = "one short", 0
        else:
            row["status"], row["owed"] = "done", 0
    return list(rows.values())


def _day_label(day: str) -> str:
    return f"{WEEKDAY_NAMES[DAY_WEEKDAY[day]]} {day}"


def _done_days(row: dict, statuses: dict[str, str]) -> str:
    days = [d for d in row["days"] if statuses.get(d) != "pending"]
    return " + ".join(_day_label(d) for d in days)


def plan_makeup(rows: list[dict], statuses: dict[str, str], swaps: dict[str, dict],
                equipment: dict, resolve, log_load) -> tuple[list[dict], list[dict]]:
    """(routine items, owed-but-not-made-up). `log_load(tid)` is the log anchor for a
    home exercise, injected so this stays testable without the archive."""
    items, excluded = [], []
    order = list(DAY_WEEKDAY)
    for pos, row in enumerate(rows):
        if row["owed"] == 0:
            continue
        swap = swaps.get(row["tid"])
        where = _done_days(row, statuses)
        if row["tier"] in NEVER_TIERS:
            why = "Big-5 lift or barbell secondary. Never made up at home; the weekly review handles it."
        elif swap is None:
            why = f"No home swap on file. Add one to {_rel(HOME_GYM)} if it should be."
        elif swap.get("class") == "never":
            why = swap.get("why", "Marked never in the home swap table.")
        else:
            why = None
        if why:
            excluded.append({"name": row["name"], "where": where, "owed": row["owed"],
                             "why": why})
            continue

        first = (_working(row["entry"].get("sets", [])) or [{}])[0]
        mode = swap.get("load", "none")
        lb = None
        if mode == "plan" and first.get("weight_kg"):
            lb = first["weight_kg"] * KG_TO_LBS
        elif mode == "log":
            lb = log_load(resolve(swap["home"])) or swap.get("default_lb")
        if lb is not None:
            lb = snap_dumbbell(lb, equipment)
        reps = swap.get("reps", first.get("reps"))
        duration = first.get("duration_seconds") if "reps" not in swap else None
        items.append({
            "home": swap["home"],
            "for": row["name"],
            "where": where,
            "class": swap["class"],
            "tier": row["tier"],
            "sets": row["owed"],
            "reps": None if duration else reps,
            "duration_seconds": duration,
            "load_lb": lb,
            "note": swap.get("note", ""),
            "_sort": (CLASS_ORDER.index(swap["class"]),
                      min(order.index(d) for d in row["days"]), pos),
        })

    items.sort(key=lambda i: i.pop("_sort"))
    for over in items[MAX_EXERCISES:]:
        excluded.append({"name": over["for"], "where": over["where"], "owed": over["sets"],
                         "why": f"Over the {MAX_EXERCISES}-exercise cap. The make-up is "
                                "catch-up, not a fifth session."})
    return items[:MAX_EXERCISES], excluded


# --- the routine -------------------------------------------------------------------------

def weekend(geo: dict) -> tuple[date_cls, date_cls]:
    mon = date_cls.fromisoformat(geo["week_start"])
    return mon + timedelta(days=5), mon + timedelta(days=6)


def _span(a: date_cls, b: date_cls) -> str:
    if a.month == b.month:
        return f"{a:%b} {a.day}–{b.day}"
    return f"{a:%b} {a.day}–{b:%b} {b.day}"


def routine_title(geo: dict) -> str:
    sat, sun = weekend(geo)
    return f"{MAKEUP_TITLE_PREFIX} · W{geo['week_no']} · {_span(sat, sun)}"


def routine_notes(geo: dict) -> str:
    return (f"{geo['block_id']} W{geo['week_no']}: what the gym week didn't get to. Best on "
            "Saturday. SAT ONLY lines pre-tire Monday's bench, so skip them on Sunday. "
            f"Everything @{MAKEUP_RPE}, nothing to failure.")


def spec_exercises(items: list[dict]) -> list[dict]:
    """Items as block-JSON prescription entries, the shape `exercise_payload` takes."""
    out = []
    for i in items:
        sat_only = "SAT ONLY · " if i["class"] == "saturday-only" else ""
        note = f"{sat_only}Missed {i['where']} ({i['for']}). {i['note']}".strip()
        kg = lb_to_kg(i["load_lb"]) if i["load_lb"] is not None else None
        out.append({
            "name": i["home"],
            "tier": i["tier"],
            "notes": note,
            "sets": [{"type": "normal", "weight_kg": kg, "reps": i["reps"],
                      "duration_seconds": i["duration_seconds"], "rpe": MAKEUP_RPE}
                     for _ in range(i["sets"])],
        })
    return out


def build_payload(geo: dict, items: list[dict], resolver) -> dict:
    return {"routine": {
        "title": routine_title(geo),
        "notes": routine_notes(geo),
        "exercises": [exercise_payload(ex, resolver) for ex in spec_exercises(items)],
    }}


def _folder_id(client) -> int:
    for f in client.paginate("/routine_folders", "routine_folders"):
        if f.get("title") == FOLDER_TITLE:
            return f["id"]
    resp = client.post("/routine_folders", {"routine_folder": {"title": FOLDER_TITLE}})
    return (resp.get("routine_folder") or resp).get("id")


def push(client, payload: dict) -> tuple[str, str | None]:
    """PUT over last week's make-up, or create the first one. Only a routine in the make-up
    folder AND titled as a make-up is overwritten, so a routine added there by hand is safe."""
    folder_id = _folder_id(client)
    for r in client.paginate("/routines", "routines"):
        if r.get("folder_id") == folder_id and \
                (r.get("title") or "").startswith(MAKEUP_TITLE_PREFIX):
            client.put(f"/routines/{r['id']}", payload)
            return "updated", r["id"]
    body = {"routine": {**payload["routine"], "folder_id": folder_id}}
    return "created", _routine_id(client.post("/routines", body))


# --- what he reads ---------------------------------------------------------------------

def _scheme(i: dict) -> str:
    unit = f"{i['duration_seconds']}s" if i["duration_seconds"] else f"{i['reps']}"
    load = f" @ {i['load_lb']:g} lb" if i["load_lb"] is not None else ""
    return f"{i['sets']}×{unit}{load}"


def render_message(geo: dict, statuses: dict, items: list, excluded: list,
                   deload: bool, synced: bool) -> str:
    esc = html.escape
    head = f"{geo['block_id']} W{geo['week_no']}"
    sync_note = "\n⚠️ Hevy sync failed, so this ran on last night's log." if not synced else ""
    if deload:
        return f"🛌 <b>Weekend make-up · {head}</b>\nDeload week. Nothing to make up. Rest.{sync_note}"
    pending = [d for d, s in statuses.items() if s == "pending"]
    lines = []
    if items:
        sat, sun = weekend(geo)
        lines += [f"🏠 <b>Weekend make-up · {head}</b> ({_span(sat, sun)})",
                  f"Hevy → <i>{FOLDER_TITLE}</i> → <i>{esc(routine_title(geo))}</i>", "",
                  f"<b>Owed ({len(items)})</b>"]
        for i in items:
            tag = " · <b>SAT ONLY</b>" if i["class"] == "saturday-only" else ""
            swap = "" if i["home"] == i["for"] else f" (for {esc(i['for'])})"
            lines.append(f"• {esc(i['home'])}{swap}: {_scheme(i)} · missed "
                         f"{esc(i['where'])}{tag}")
    else:
        lines += [f"✅ <b>Weekend make-up · {head}</b>",
                  "Nothing owed that can be done at home. The make-up routine in Hevy is "
                  "last week's, so ignore it."]
    if excluded:
        lines += ["", "<b>Owed, not made up</b>"]
        lines += [f"• {esc(e['name'])} ({esc(e['where'])}): {esc(e['why'])}" for e in excluded]
    if pending:
        days = ", ".join(_day_label(d) for d in pending)
        lines += ["", f"⏳ {days} not logged yet, so nothing from it is in here. If you "
                      "trained it, finish the workout in Hevy and re-run the job."]
    if items:
        lines += ["", f"Best on Saturday. Everything @{MAKEUP_RPE}."]
    return "\n".join(lines) + sync_note


def render_record(geo: dict, statuses: dict, rows: list, items: list, excluded: list,
                  deload: bool, generated: datetime, pushed: str) -> str:
    out = [f"# Weekend make-up — {geo['block_id']} · Week {geo['week_no']}/{geo['weeks']}",
           "", f"_Generated {generated:%Y-%m-%d %H:%M %Z}. Hevy log = source of truth. "
               "Rule `weekend-makeup`._", ""]
    if deload:
        return "\n".join(out + ["Deload week: nothing made up.", ""])
    out += [f"**Hevy:** {pushed}", "", "## In the routine", ""]
    if items:
        out += ["| Home exercise | Sets × reps @ load | For | Missed | Class |",
                "|---|---|---|---|---|"]
        out += [f"| {i['home']} | {_scheme(i)} | {i['for']} | {i['where']} | {i['class']} |"
                for i in items]
    else:
        out.append("Nothing owed that can be done at home.")
    if excluded:
        out += ["", "## Owed, not made up", "", "| Exercise | Day | Sets owed | Why |",
                "|---|---|---|---|"]
        out += [f"| {e['name']} | {e['where']} | {e['owed']} | {e['why']} |" for e in excluded]
    days = " · ".join(f"{_day_label(d)} {s}" for d, s in statuses.items())
    out += ["", "## The week, planned vs logged", "", f"Days: {days}", "",
            "| Exercise | Day | Tier | Planned sets | Logged | Status |",
            "|---|---|---|---|---|---|"]
    out += [f"| {r['name']} | {' + '.join(r['days'])} | {r['tier']} | {r['planned']} | "
            f"{r['logged']} | {r['status']} |" for r in rows]
    return "\n".join(out) + "\n"


# --- entrypoint --------------------------------------------------------------------------

def _in_block(block: dict, day: date_cls) -> bool:
    start = date_cls.fromisoformat(block["start_date"])
    return start <= day < start + timedelta(days=7 * block.get("weeks", 0))


def _is_deload(block: dict, week_no: int) -> bool:
    phase = (block.get("week_phases") or {}).get(str(week_no)) or {}
    return "deload" in (phase.get("label") or "").lower()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-commit", action="store_true")
    ap.add_argument("--skip-sync", action="store_true")
    ap.add_argument("--date")
    args = ap.parse_args()

    now = _eastern_now()
    today = date_cls.fromisoformat(args.date) if args.date else now.date()
    record = record_path_for(today)
    proceed, why = time_guard(args.force or bool(args.date), now, record.exists())
    print(f"Eastern now = {now:%Y-%m-%d %H:%M %Z} → {'proceed' if proceed else 'skip'} — {why}")
    if not proceed:
        summary("### ⏭️ Weekend make-up skipped", "", f"**Reason:** {why}.")
        return

    block = _load_block()
    if not _in_block(block, today):
        summary("### ⏭️ Weekend make-up skipped", "",
                f"**Reason:** {today} is outside the running block {block.get('block_id')}.")
        return

    synced = sync_log(args.skip_sync or args.dry_run)
    geo = geometry(block, today)
    deload = _is_deload(block, geo["week_no"])
    resolve = _safe_resolver()
    week_sessions = _sessions_in(geo["week_start"], geo["week_end"])
    statuses = day_statuses(block, geo, today, week_sessions)
    home = load_home()
    swaps = swaps_by_template(home, resolve)
    rows = diff_week(block, geo["week_no"], statuses, week_sessions, resolve, swaps)
    items, excluded = ([], []) if deload else plan_makeup(
        rows, statuses, swaps, home["equipment"], resolve,
        lambda tid: home_log_load(tid, today) if tid else None)
    message = render_message(geo, statuses, items, excluded, deload, synced)

    from ..hevy.exercise_map import Resolver
    payload = build_payload(geo, items, Resolver()) if items else None

    if args.dry_run:
        print("\n===== MESSAGE =====\n" + message)
        if payload:
            print("\n===== ROUTINE (not pushed) =====")
            print_routine_preview(payload, spec_exercises(items))
        print("\n===== RECORD =====\n" + render_record(
            geo, statuses, rows, items, excluded, deload, now, "dry run, not pushed"))
        summary("### 🔍 Dry run — nothing pushed, sent or committed")
        return

    pushed = "nothing pushed — nothing owed"
    if payload:
        from ..hevy.client import HevyClient
        action, rid = push(HevyClient(), payload)
        pushed = f"{action} `{payload['routine']['title']}` in folder `{FOLDER_TITLE}` ({rid})"
        print(f"Hevy: {pushed}")

    sent = True
    try:
        telegram.send_message(message)
    except Exception as exc:  # noqa: BLE001 — the routine is already in the app; say so, then fail
        sent = False
        print(f"⚠️ Telegram not sent ({exc}).")

    MAKEUP_DIR.mkdir(parents=True, exist_ok=True)
    record.write_text(render_record(geo, statuses, rows, items, excluded, deload, now, pushed))
    if not args.no_commit:
        commit([REPO_ROOT / "data" / "logs", record],
               message=f"chore(makeup): weekend make-up {geo['block_id']} W{geo['week_no']} "
                       f"— {len(items)} exercise(s)")

    summary(f"### ✅ Weekend make-up — {geo['block_id']} W{geo['week_no']}", "",
            f"- Hevy: {pushed}", f"- Telegram: {'sent' if sent else '**not sent**'}",
            f"- Record: `{_rel(record)}`")
    if not sent:
        raise SystemExit("Telegram message not sent — the routine and record are in place.")


if __name__ == "__main__":
    main()
