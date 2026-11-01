"""weekly_metrics: the days a week expects come from the plan, not a fixed weekday map.

B5 W6 is a two-day travel deload (D1 + D2). With expected days hardcoded to D1–D4, the
Sep 19 review would have reported D3 and D4 as missed while the athlete was in Korea.
"""
import unittest
from datetime import date

from scripts.review import weekly_metrics
from scripts.review.weekly_metrics import geometry, readiness

FULL = ["D1", "D2", "D3", "D4"]


def block(days_by_week: dict) -> dict:
    return {"block_id": "t", "weeks": 6, "start_date": "2026-08-10",
            "prescriptions": [{"week": w, "day": d, "exercises": []}
                              for w, days in days_by_week.items() for d in days]}


def session(day: str) -> dict:
    return {"start_time": f"{day}T11:00:00Z", "exercises": []}


class ExpectedDaysFromPlan(unittest.TestCase):
    def test_travel_week_expects_only_the_prescribed_days(self):
        geo = geometry(block({5: FULL, 6: ["D1", "D2"]}), date(2026, 9, 19))  # Sat, W6
        self.assertEqual(geo["week_no"], 6)
        self.assertEqual(geo["expected_days"], ["D1", "D2"])
        r = readiness([session("2026-09-14"), session("2026-09-15")], geo["expected_days"])
        self.assertEqual(r["missing"], [])
        self.assertTrue(r["all_in"])

    def test_a_full_week_is_unchanged(self):
        geo = geometry(block({5: FULL}), date(2026, 9, 12))  # Sat, W5
        self.assertEqual(geo["expected_days"], FULL)

    def test_midweek_still_expects_only_the_days_so_far(self):
        geo = geometry(block({6: ["D1", "D2"]}), date(2026, 9, 14))  # Mon, W6
        self.assertEqual(geo["expected_days"], ["D1"])

    def test_a_week_with_no_prescriptions_falls_back_to_the_full_split(self):
        geo = geometry(block({5: FULL}), date(2026, 9, 19))  # W6 has nothing written
        self.assertEqual(geo["expected_days"], FULL)

    def test_a_dropped_day_that_is_trained_anyway_is_not_flagged_missing(self):
        geo = geometry(block({6: ["D1", "D2"]}), date(2026, 9, 19))
        r = readiness([session("2026-09-14"), session("2026-09-15"), session("2026-09-17")],
                      geo["expected_days"])
        self.assertEqual(r["missing"], [])


if __name__ == "__main__":
    unittest.main()


def _sets(*rpes, warmup=False):
    out = [{"type": "warmup", "weight_kg": 60, "reps": 5, "rpe": None}] if warmup else []
    return out + [{"type": "normal", "weight_kg": 100, "reps": 5, "rpe": r} for r in rpes]


def test_blank_rpe_trailing_sets_carry_the_last_logged():
    from scripts.review.weekly_metrics import effective_rpes
    assert effective_rpes(_sets(7, 7.5, None)) == [(7, "logged"), (7.5, "logged"), (7.5, "carried")]


def test_blank_rpe_all_sets_blank_is_the_floor():
    from scripts.review.weekly_metrics import effective_rpes
    assert effective_rpes(_sets(None, None, None, warmup=True)) == [(5.0, "floor")] * 3


def test_blank_rpe_leading_blank_takes_the_next_logged():
    from scripts.review.weekly_metrics import effective_rpes
    assert effective_rpes(_sets(None, 7)) == [(7, "carried"), (7, "logged")]


def test_blank_rpe_blank_backoff_under_a_rated_top_is_the_floor():
    from scripts.review.weekly_metrics import effective_rpes
    sets = [{"type": "normal", "weight_kg": 143, "reps": 3, "rpe": 7},
            {"type": "normal", "weight_kg": 125, "reps": 4, "rpe": None},
            {"type": "normal", "weight_kg": 125, "reps": 4, "rpe": None}]
    assert effective_rpes(sets) == [(7, "logged"), (5.0, "floor"), (5.0, "floor")]


class PlannedTopSkipsWarmupsTests(unittest.TestCase):
    """The RPE-cap flag was dead for a whole block, and this is the reason.

    `primary-warmup-ramp` (2026-10-02) put a real ramp in front of every Big-5 primary.
    `_planned_top` took `sets[0]`, so from that day the plan read as 135x8 @None for every
    barbell lift — no planned RPE, so `rpe_flag` could only ever be "none". B6 W4's pull-up
    went @9.5 against an @8.5 cap and the deterministic flag said nothing about it.
    """

    BLOCK = {
        "block_id": "T", "start_date": "2026-09-28", "weeks": 5,
        "prescriptions": [{
            "week": 4, "day": "D2", "exercises": [{
                "name": "Weighted Pull-up", "tier": "primary", "sets": [
                    {"type": "warmup", "weight_kg": 0.45, "reps": 8},
                    {"type": "warmup", "weight_kg": 20.4, "reps": 3},
                    {"type": "normal", "weight_kg": 43.09, "reps": 3, "rpe": 8.5},
                    {"type": "normal", "weight_kg": 27.2, "reps": 5, "rpe": 7},
                ]}]}],
    }

    def test_the_warmup_is_not_the_plan(self):
        plan = weekly_metrics._planned_top(self.BLOCK, 4, "Weighted Pull-up", True, 180.0)
        self.assertEqual(plan["reps"], 3)
        self.assertEqual(plan["rpe"], 8.5)      # was None — the whole bug

    def test_an_exercise_of_only_warmups_has_no_plan(self):
        block = {"prescriptions": [{"week": 1, "day": "D1", "exercises": [
            {"name": "X", "sets": [{"type": "warmup", "weight_kg": 60, "reps": 8}]}]}]}
        self.assertIsNone(weekly_metrics._planned_top(block, 1, "X", False, 180.0))

    def test_a_plan_with_no_ramp_still_reads_its_first_working_set(self):
        block = {"prescriptions": [{"week": 1, "day": "D1", "exercises": [
            {"name": "X", "sets": [{"type": "normal", "weight_kg": 100, "reps": 3, "rpe": 7}]}]}]}
        plan = weekly_metrics._planned_top(block, 1, "X", False, 180.0)
        self.assertEqual(plan["rpe"], 7)
