"""Rest timers: the athlete's numbers, and the light-week drop on the primaries.

FB 2026-10-29: in the warm-up week and the deload the primary timer drops 1:15 → 1:00.
Nothing else moves.
"""
import unittest

from scripts.hevy.push_block import build_routine_payload
from scripts.hevy.rest_times import is_light_week, rest_seconds_for


class _StubResolver:
    def resolve(self, name):
        return f"tpl-{name}"


PRIMARY = {"name": "Weighted Dip", "tier": "primary"}
SECONDARY = {"name": "CGB", "tier": "secondary"}
ACCESSORY = {"name": "Face Pull", "tier": "accessory"}
CORE = {"name": "Dead Bug", "tier": "core"}


class LightWeekTests(unittest.TestCase):
    def test_week_one_is_the_warm_up_week(self):
        self.assertTrue(is_light_week(1, {"label": "CALIBRATION"}))
        self.assertTrue(is_light_week(1))

    def test_deload_is_light_whatever_week_it_lands_in(self):
        self.assertTrue(is_light_week(5, {"label": "DELOAD"}))
        self.assertTrue(is_light_week(6, {"label": "Deload"}))

    def test_working_weeks_are_not(self):
        self.assertFalse(is_light_week(4, {"label": "PEAK"}))
        self.assertFalse(is_light_week(2))

    def test_explicit_flag_wins(self):
        """A block that opens straight into work (no calibration after a deload) says so."""
        self.assertFalse(is_light_week(1, {"label": "ESTABLISH", "light": False}))
        self.assertTrue(is_light_week(3, {"label": "TRAVEL", "light": True}))


class RestSecondsTests(unittest.TestCase):
    def test_normal_week_keeps_the_athletes_table(self):
        self.assertEqual(rest_seconds_for(PRIMARY), 75)
        self.assertEqual(rest_seconds_for(SECONDARY), 60)
        self.assertEqual(rest_seconds_for(ACCESSORY), 60)
        self.assertEqual(rest_seconds_for(CORE), 30)

    def test_light_week_drops_only_the_primary(self):
        self.assertEqual(rest_seconds_for(PRIMARY, light_week=True), 60)
        self.assertEqual(rest_seconds_for(SECONDARY, light_week=True), 60)
        self.assertEqual(rest_seconds_for(ACCESSORY, light_week=True), 60)
        self.assertEqual(rest_seconds_for(CORE, light_week=True), 30)

    def test_explicit_rest_still_overrides(self):
        self.assertEqual(rest_seconds_for({**PRIMARY, "rest_seconds": 120}, light_week=True), 120)

    def test_routine_payload_carries_the_light_week_timer(self):
        pres = {"week": 5, "day": "D3", "exercises": [
            {**PRIMARY, "sets": [{"type": "normal", "weight_kg": 27.2, "reps": 5}]},
            {**ACCESSORY, "sets": [{"type": "normal", "weight_kg": 15.9, "reps": 15}]},
        ]}
        day = {"label": "D3", "focus": "Dip + Upper Back"}
        light = build_routine_payload("B", 5, day, pres, None, _StubResolver(), True)
        heavy = build_routine_payload("B", 4, day, pres, None, _StubResolver())
        self.assertEqual([e["rest_seconds"] for e in light["routine"]["exercises"]], [60, 60])
        self.assertEqual([e["rest_seconds"] for e in heavy["routine"]["exercises"]], [75, 60])


if __name__ == "__main__":
    unittest.main()
