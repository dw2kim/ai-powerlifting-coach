"""Routine titles: per-session overrides, and reclaiming a routine renamed in the app.

Hevy has no DELETE for routines, so a title that stops matching the plan is a routine the
athlete has to clear by hand. Both behaviours here exist to stop that happening.
"""
import json
import unittest

from scripts.hevy import push_block
from scripts.hevy.push_block import build_routine_payload


class _StubResolver:
    def resolve(self, name):
        return f"tpl-{name}"


class RoutineTitleTests(unittest.TestCase):
    day = {"label": "D3", "focus": "Dip + Glutes + Upper Back"}

    def payload(self, prescription):
        return build_routine_payload(
            "2026-Q3-B05", 6, self.day, prescription, None, _StubResolver()
        )

    def prescription(self, **extra):
        return {"week": 6, "day": "D3", "exercises": [
            {"name": "Incline DB Press", "tier": "secondary",
             "sets": [{"type": "normal", "weight_kg": 27.2, "reps": 8, "rpe": 7}]}
        ], **extra}

    def test_title_defaults_to_the_shared_day_focus(self):
        title = self.payload(self.prescription())["routine"]["title"]
        self.assertEqual(title, "W6-D3 Dip + Glutes + Upper Back")

    def test_prescription_focus_overrides_only_that_session(self):
        """The `days` list is block-wide — editing it would rename D3 in every week."""
        title = self.payload(
            self.prescription(focus="Incline + Upper Back (added)")
        )["routine"]["title"]
        self.assertEqual(title, "W6-D3 Incline + Upper Back (added)")
        # The shared day is untouched, so W1-D3..W5-D3 keep their titles and their routines.
        self.assertEqual(self.day["focus"], "Dip + Glutes + Upper Back")

    def test_replaces_title_is_not_what_gets_pushed(self):
        """It's a lookup key for the live routine, never the title written to the app."""
        routine = self.payload(self.prescription(
            focus="Incline + Upper Back (added)",
            replaces_title="W6-D3 — DROPPED (travel week, nothing to train)",
        ))["routine"]
        self.assertEqual(routine["title"], "W6-D3 Incline + Upper Back (added)")
        self.assertNotIn("replaces_title", routine)


if __name__ == "__main__":
    unittest.main()


class SupersetIdMustBeNumericTests(unittest.TestCase):
    """B7's first push died here, after the routine folder had already been created.

    The block JSON used readable superset labels ("d1a", "d2b"). Hevy's `superset_id` is a
    NUMBER, so a string is coerced to NaN and the routine is rejected with
    `400 Expected number, received nan` — twice, once per exercise in W1-D1's superset pair.
    The dry run printed loads and rest timers and never looked at the field, so it passed
    clean 20/20 while being unpushable.
    """

    def _ex(self, ss):
        return {"name": "Tricep Pushdown", "tier": "accessory", "superset_id": ss,
                "sets": [{"type": "normal", "weight_kg": 22.7, "reps": 12}]}

    def test_int_passes_through(self):
        self.assertEqual(
            push_block.exercise_payload(self._ex(0), _StubResolver(), False)["superset_id"], 0)

    def test_none_passes_through(self):
        self.assertIsNone(
            push_block.exercise_payload(self._ex(None), _StubResolver(), False)["superset_id"])

    def test_missing_key_is_none(self):
        ex = self._ex(0); del ex["superset_id"]
        self.assertIsNone(
            push_block.exercise_payload(ex, _StubResolver(), False)["superset_id"])

    def test_digit_string_is_coerced(self):
        self.assertEqual(
            push_block.exercise_payload(self._ex("2"), _StubResolver(), False)["superset_id"], 2)

    def test_the_actual_bug_is_refused_at_build_time(self):
        """'d1a' must fail loudly here, not as a 400 after the folder exists."""
        with self.assertRaises(SystemExit) as cm:
            push_block.exercise_payload(self._ex("d1a"), _StubResolver(), False)
        self.assertIn("superset_id", str(cm.exception))

    def test_the_shipped_block_is_clean(self):
        """Guards the real file: every superset_id in current-block.json is numeric."""
        spec = json.loads(push_block.SPEC_PATH.read_text())
        offenders = [
            (p["week"], p["day"], e.get("name"), e["superset_id"])
            for p in spec["prescriptions"] for e in p["exercises"]
            if e.get("superset_id") is not None and not isinstance(e["superset_id"], int)
        ]
        self.assertEqual(offenders, [])
