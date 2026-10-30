"""Tests for the Friday make-up (scripts/review/weekend_makeup.py, rule `weekend-makeup`).

Run: python -m unittest discover -s tests

Synthetic block + sessions, so the owed/not-owed rules are pinned without the archive:
one set short is ignored, two short is owed, today's unlogged day is "not logged yet"
rather than missed, and nothing heavy or Big-5 ever lands in a home routine.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

from scripts.hevy.exercise_map import Resolver
from scripts.hevy.push_block import exercise_payload
from scripts.review import weekend_makeup as wm
from scripts.review import weekly_metrics as wmx

ET = ZoneInfo("America/New_York")
KG = 1 / 2.2046226218

TIDS = {
    "Comp Bench": "BENCH", "Chest Fly (Machine)": "FLY_M", "Chest Fly (Dumbbell)": "FLY_DB",
    "Reverse Pec Deck": "PEC", "Rear Delt Reverse Fly (Dumbbell)": "RDF_DB",
    "Face Pull": "FACE", "Band Pullaparts": "BAND", "Leg Extension": "LEGEXT",
    "Concentration Curl": "CURL", "Dead Bug": "DEADBUG", "Lateral Raise": "LAT",
    "CS Row": "CSROW", "Iso Row": "ISOROW", "Mystery Machine": "MYSTERY",
}


def resolve(name):
    return TIDS.get(name)


def _sets(n, lb=50, reps=10):
    return [{"type": "normal", "weight_kg": lb * KG, "reps": reps} for _ in range(n)]


def _ex(name, n, tier="accessory", lb=50, reps=10):
    return {"name": name, "tier": tier, "sets": [{"type": "warmup", "weight_kg": 0, "reps": 8}]
            + _sets(n, lb, reps)}


BLOCK = {
    "block_id": "TEST-B01", "start_date": "2026-10-12", "weeks": 5,
    "week_phases": {"5": {"label": "DELOAD"}},
    "prescriptions": [
        {"week": 1, "day": "D1", "exercises": [
            _ex("Comp Bench", 4, "primary", 255, 3), _ex("Chest Fly (Machine)", 2, lb=105, reps=12),
            _ex("Iso Row", 2)]},
        {"week": 1, "day": "D3", "exercises": [
            _ex("Reverse Pec Deck", 2, lb=105, reps=15), _ex("Face Pull", 2, lb=45, reps=15),
            _ex("Leg Extension", 2), _ex("Dead Bug", 3, "core", 0, 10)]},
        {"week": 1, "day": "D4", "exercises": [
            _ex("Concentration Curl", 3, lb=40), _ex("CS Row", 2, lb=55, reps=12)]},
    ],
}

SWAPS = {
    "FLY_M": {"home": "Chest Fly (Dumbbell)", "class": "saturday-only", "load": "log",
              "default_lb": 25},
    "PEC": {"home": "Rear Delt Reverse Fly (Dumbbell)", "class": "priority", "load": "log",
            "default_lb": 25, "also_counts": ["Rear Delt Reverse Fly (Dumbbell)"]},
    "FACE": {"home": "Band Pullaparts", "class": "priority", "load": "none", "reps": 15},
    "LEGEXT": {"class": "never", "why": "Monday is squat."},
    "CURL": {"home": "Concentration Curl", "class": "standard", "load": "plan"},
    "DEADBUG": {"home": "Dead Bug", "class": "core", "load": "none"},
    "CSROW": {"home": "CS Row", "class": "standard", "load": "plan"},
    "ISOROW": {"home": "CS Row", "class": "standard", "load": "plan", "also_counts": ["CS Row"]},
}
EQUIPMENT = {"dumbbell_min_lb": 5, "dumbbell_max_lb": 50, "dumbbell_step_lb": 5}


def session(day_iso, *exercises, title="W1-D1 x"):
    return {"start_time": f"{day_iso}T10:48:00+00:00", "title": title,
            "exercises": [{"title": t, "exercise_template_id": TIDS.get(t), "sets": _sets(n)}
                          for t, n in exercises]}


def run(sessions, today):
    geo = wmx.geometry(BLOCK, today)
    statuses = wm.day_statuses(BLOCK, geo, today, sessions)
    rows = wm.diff_week(BLOCK, geo["week_no"], statuses, sessions, resolve, SWAPS)
    items, excluded = wm.plan_makeup(rows, statuses, SWAPS, EQUIPMENT, resolve,
                                     lambda tid: None)
    return statuses, {r["name"]: r for r in rows}, items, excluded


FULL_D1 = session("2026-10-12", ("Comp Bench", 4), ("Chest Fly (Machine)", 2), ("Iso Row", 2))
FULL_D3 = session("2026-10-15", ("Reverse Pec Deck", 2), ("Face Pull", 2), ("Leg Extension", 2),
                  ("Dead Bug", 3), title="W1-D3 x")
FULL_D4 = session("2026-10-16", ("Concentration Curl", 3), ("CS Row", 2), title="W1-D4 x")
FRIDAY = date(2026, 10, 16)


class Owed(unittest.TestCase):
    def test_full_week_owes_nothing(self):
        _, rows, items, excluded = run([FULL_D1, FULL_D3, FULL_D4], FRIDAY)
        self.assertEqual(items, [])
        self.assertEqual(excluded, [])
        self.assertTrue(all(r["status"] == "done" for r in rows.values()))

    def test_one_set_short_is_ignored(self):
        d4 = session("2026-10-16", ("Concentration Curl", 2), ("CS Row", 2), title="W1-D4 x")
        _, rows, items, _ = run([FULL_D1, FULL_D3, d4], FRIDAY)
        self.assertEqual(rows["Concentration Curl"]["status"], "one short")
        self.assertEqual(items, [])

    def test_two_sets_short_owes_the_missing_sets(self):
        d4 = session("2026-10-16", ("Concentration Curl", 1), ("CS Row", 2), title="W1-D4 x")
        _, rows, items, _ = run([FULL_D1, FULL_D3, d4], FRIDAY)
        self.assertEqual(rows["Concentration Curl"]["status"], "short")
        self.assertEqual([(i["home"], i["sets"]) for i in items], [("Concentration Curl", 2)])

    def test_missed_exercise_is_owed_in_full(self):
        d3 = session("2026-10-15", ("Face Pull", 2), ("Leg Extension", 2), ("Dead Bug", 3),
                     title="W1-D3 x")
        _, _, items, _ = run([FULL_D1, d3, FULL_D4], FRIDAY)
        self.assertEqual([(i["home"], i["sets"], i["load_lb"]) for i in items],
                         [("Rear Delt Reverse Fly (Dumbbell)", 2, 25)])

    def test_a_logged_equivalent_counts_as_done(self):
        """The machine was taken, he did the DB fly at the gym (`equipment-fallbacks`)."""
        d3 = session("2026-10-15", ("Rear Delt Reverse Fly (Dumbbell)", 2), ("Face Pull", 2),
                     ("Leg Extension", 2), ("Dead Bug", 3), title="W1-D3 x")
        _, rows, items, _ = run([FULL_D1, d3, FULL_D4], FRIDAY)
        self.assertEqual(rows["Reverse Pec Deck"]["status"], "done")
        self.assertEqual(items, [])

    def test_an_equivalent_planned_on_its_own_does_not_cover_another_slot(self):
        """D4's CS row is the CS row's sets. It must not hide a missed D1 Iso Row."""
        d1 = session("2026-10-12", ("Comp Bench", 4), ("Chest Fly (Machine)", 2))
        _, rows, items, _ = run([d1, FULL_D3, FULL_D4], FRIDAY)
        self.assertEqual(rows["Iso Row"]["status"], "missed")
        self.assertEqual([i["for"] for i in items], ["Iso Row"])


class Days(unittest.TestCase):
    def test_todays_unlogged_day_is_pending_not_missed(self):
        """Friday noon, D4 not in the app yet: report it, don't dump D4 into the routine."""
        statuses, rows, items, excluded = run([FULL_D1, FULL_D3], FRIDAY)
        self.assertEqual(statuses["D4"], "pending")
        self.assertEqual(rows["Concentration Curl"]["status"], "pending")
        self.assertEqual(items, [])
        self.assertEqual(excluded, [])

    def test_a_past_unlogged_day_is_skipped_and_owed(self):
        statuses, _, items, excluded = run([FULL_D1, FULL_D4], FRIDAY)
        self.assertEqual(statuses["D3"], "skipped")
        self.assertEqual([i["home"] for i in items],
                         ["Rear Delt Reverse Fly (Dumbbell)", "Band Pullaparts", "Dead Bug"])
        self.assertEqual([e["name"] for e in excluded], ["Leg Extension"])

    def test_the_d4_routine_title_counts_a_day_trained_off_its_weekday(self):
        d4_on_thursday = session("2026-10-15", ("Concentration Curl", 3), ("CS Row", 2),
                                 title="W1-D4 x")
        statuses, _, _, _ = run([FULL_D1, d4_on_thursday], FRIDAY)
        self.assertEqual(statuses["D4"], "logged")


class Eligibility(unittest.TestCase):
    def test_big5_and_never_and_unknown_are_excluded_with_reasons(self):
        block = json.loads(json.dumps(BLOCK))
        block["prescriptions"][0]["exercises"].append(_ex("Mystery Machine", 2))
        geo = wmx.geometry(block, FRIDAY)
        statuses = wm.day_statuses(block, geo, FRIDAY, [])
        rows = wm.diff_week(block, 1, statuses, [], resolve, SWAPS)
        _, excluded = wm.plan_makeup(rows, statuses, SWAPS, EQUIPMENT, resolve, lambda t: None)
        why = {e["name"]: e["why"] for e in excluded}
        self.assertIn("Big-5", why["Comp Bench"])
        self.assertEqual(why["Leg Extension"], "Monday is squat.")
        self.assertIn("No home swap", why["Mystery Machine"])

    def test_fill_order_and_cap(self):
        """Everything missed: priority first, SAT ONLY after standard, core last, cap 5."""
        _, _, items, excluded = run([], date(2026, 10, 17))
        self.assertEqual([i["class"] for i in items],
                         ["priority", "priority", "standard", "standard", "standard"])
        overflow = [e["name"] for e in excluded if "cap" in e["why"]]
        self.assertEqual(overflow, ["Chest Fly (Machine)", "Dead Bug"])

    def test_loads_snap_down_onto_the_home_rack(self):
        self.assertEqual(wm.snap_dumbbell(26.5, EQUIPMENT), 25)
        self.assertEqual(wm.snap_dumbbell(55, EQUIPMENT), 50)   # heaviest at home
        self.assertEqual(wm.snap_dumbbell(40.0000001, EQUIPMENT), 40)
        self.assertEqual(wm.snap_dumbbell(2, EQUIPMENT), 5)

    def test_plan_loads_use_this_weeks_prescription(self):
        _, _, items, _ = run([FULL_D1, FULL_D3], date(2026, 10, 17))
        loads = {i["home"]: i["load_lb"] for i in items}
        self.assertEqual(loads["Concentration Curl"], 40)
        self.assertEqual(loads["CS Row"], 50)


class Deload(unittest.TestCase):
    def test_a_deload_reports_its_misses_and_makes_nothing_up(self):
        """B6 W5: "Nothing to make up" went out with Leg Extension and the curl unlogged."""
        d3 = session("2026-10-15", ("Reverse Pec Deck", 2), ("Face Pull", 2), ("Dead Bug", 3),
                     title="W1-D3 x")
        d4 = session("2026-10-16", ("CS Row", 2), title="W1-D4 x")
        week = [FULL_D1, d3, d4]
        geo = wmx.geometry(BLOCK, FRIDAY)
        statuses = wm.day_statuses(BLOCK, geo, FRIDAY, week)
        rows = wm.diff_week(BLOCK, 1, statuses, week, resolve, SWAPS)
        misses = wm.deload_misses(rows, statuses)
        self.assertEqual([(m["name"], m["where"], m["owed"]) for m in misses],
                         [("Leg Extension", "Thu D3", 2), ("Concentration Curl", "Fri D4", 3)])

        msg = wm.render_message(geo, statuses, [], misses, deload=True, synced=True)
        self.assertIn("nothing is made up", msg)
        self.assertIn("• Leg Extension (Thu D3)", msg)
        self.assertIn("• Concentration Curl (Fri D4)", msg)
        self.assertNotIn("Owed, not made up", msg)

        record = wm.render_record(geo, statuses, rows, [], misses, True,
                                  datetime(2026, 10, 16, 16, 16, tzinfo=ET), "nothing pushed")
        self.assertIn("## Missed, not made up", record)
        self.assertIn("| Concentration Curl | D4 | accessory | 3 | 0 | missed |", record)

    def test_a_clean_deload_says_rest_and_nothing_else(self):
        geo = wmx.geometry(BLOCK, FRIDAY)
        statuses = {"D1": "logged", "D3": "logged", "D4": "logged"}
        msg = wm.render_message(geo, statuses, [], [], deload=True, synced=True)
        self.assertNotIn("Missed", msg)
        self.assertIn("Rest.", msg)


class Routine(unittest.TestCase):
    def test_title_spans_the_weekend(self):
        self.assertEqual(wm.routine_title({"week_start": "2026-10-12", "week_no": 3}),
                         "Make-up · W3 · Oct 17–18")
        self.assertEqual(wm.routine_title({"week_start": "2026-10-26", "week_no": 5}),
                         "Make-up · W5 · Oct 31–Nov 1")

    def test_payload_carries_rpe_sat_only_and_rest(self):
        item = {"home": "Chest Fly (Dumbbell)", "for": "Chest Fly (Machine)", "where": "Mon D1",
                "class": "saturday-only", "tier": "accessory", "sets": 2, "reps": 12,
                "duration_seconds": None, "load_lb": 25.0, "note": "Floor."}
        ex = exercise_payload(wm.spec_exercises([item])[0], Resolver())
        self.assertTrue(ex["notes"].startswith("[2×12 @7] SAT ONLY · Missed Mon D1"))
        self.assertEqual(ex["rest_seconds"], 60)
        self.assertEqual(len(ex["sets"]), 2)
        self.assertAlmostEqual(ex["sets"][0]["weight_kg"] * 2.20462, 25, places=2)

    def test_push_overwrites_only_a_makeup_in_the_makeup_folder(self):
        client = mock.Mock()
        client.paginate.side_effect = lambda path, key: {
            "/routine_folders": [{"id": 7, "title": "Weekend Make-up"}, {"id": 1, "title": "B6"}],
            "/routines": [{"id": "a", "folder_id": 1, "title": "Make-up · W2"},
                          {"id": "b", "folder_id": 7, "title": "My own thing"},
                          {"id": "c", "folder_id": 7, "title": "Make-up · W2 · Oct 10–11"}],
        }[path]
        action, rid = wm.push(client, {"routine": {"title": "Make-up · W3"}})
        self.assertEqual((action, rid), ("updated", "c"))
        client.put.assert_called_once_with("/routines/c", {"routine": {"title": "Make-up · W3"}})

    def test_push_creates_the_folder_and_routine_the_first_time(self):
        client = mock.Mock()
        client.paginate.side_effect = lambda path, key: []
        client.post.side_effect = [{"routine_folder": {"id": 9}}, {"routine": [{"id": "new"}]}]
        self.assertEqual(wm.push(client, {"routine": {"title": "Make-up · W3"}}),
                         ("created", "new"))
        self.assertEqual(client.post.call_args.args[1]["routine"]["folder_id"], 9)


class Guard(unittest.TestCase):
    def at(self, iso, done=False, force=False):
        return wm.time_guard(force, datetime.fromisoformat(iso).replace(tzinfo=ET), done)[0]

    def test_friday_noon_onward(self):
        self.assertFalse(self.at("2026-10-16T11:59"))
        self.assertTrue(self.at("2026-10-16T12:00"))
        self.assertTrue(self.at("2026-10-16T15:40"))   # a late firing still ships

    def test_once_per_week_and_fridays_only(self):
        self.assertFalse(self.at("2026-10-16T13:00", done=True))
        self.assertFalse(self.at("2026-10-17T12:00"))
        self.assertTrue(self.at("2026-10-17T12:00", force=True))


class SharedMatching(unittest.TestCase):
    def test_makeup_sessions_stay_out_of_the_gym_week(self):
        with tempfile.TemporaryDirectory() as tmp:
            for i, title in enumerate(["W3-D4 Sumo", "Make-up · W3 · Oct 17–18"]):
                Path(tmp, f"{i}.json").write_text(json.dumps(
                    {"start_time": f"2026-10-1{6 + i}T10:00:00+00:00", "title": title}))
            with mock.patch.object(wmx, "SESSIONS_DIR", Path(tmp)):
                got = [w["title"] for w in wmx._sessions_in("2026-10-12", "2026-10-18")]
        self.assertEqual(got, ["W3-D4 Sumo"])

    def test_match_accessory_is_the_first_of_match_all(self):
        index = wmx._index_exercises([FULL_D1, FULL_D3])
        for name in ["Chest Fly (Machine)", "Face Pull", "Nope"]:
            found = wmx._match_all(name, index, resolve)
            self.assertIs(wmx._match_accessory(name, index, resolve),
                          found[0] if found else None)


class HomeGymData(unittest.TestCase):
    """data/home-gym.json is hand-edited. A typo there must fail here, not at noon Friday."""

    def test_every_swap_resolves_and_is_well_formed(self):
        home = wm.load_home()
        resolver = Resolver()
        swaps = wm.swaps_by_template(home, lambda n: resolver.resolve(n))
        for swap in swaps.values():
            self.assertIn(swap["class"], wm.CLASS_ORDER + ["never"], swap["key"])
            if swap["class"] == "never":
                self.assertTrue(swap.get("why"), swap["key"])
                continue
            resolver.resolve(swap["home"])
            self.assertIn(swap.get("load"), ("plan", "log", "none"), swap["key"])
            if swap["load"] == "log":
                self.assertIsNotNone(swap.get("default_lb"), swap["key"])
            for t in swap.get("also_counts", []):
                resolver.resolve(t)

    def test_an_unresolvable_key_fails_loud(self):
        with self.assertRaises(SystemExit):
            wm.swaps_by_template({"swaps": {"Typo Raise": {"class": "standard"}}},
                                 lambda n: None)


if __name__ == "__main__":
    unittest.main()
