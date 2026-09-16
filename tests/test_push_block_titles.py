"""Routine titles: per-session overrides, and reclaiming a routine renamed in the app.

Hevy has no DELETE for routines, so a title that stops matching the plan is a routine the
athlete has to clear by hand. Both behaviours here exist to stop that happening.
"""
import unittest

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
