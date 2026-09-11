"""Regression coverage for amended blocks losing sets or retaining old phases."""
import copy
import unittest

from scripts.sheets.export_block import build_plan


class AmendedPlanTests(unittest.TestCase):
    def block(self):
        def exercise(name, weight, note=""):
            return {"name": name, "notes": note,
                    "sets": [{"type": "normal", "weight_kg": weight,
                              "reps": 3, "rpe": 6}]}
        return {"block_id": "test", "weeks": 6, "start_date": "2026-08-10",
                "days": [{"label": "D1", "focus": "Squat"}],
                "prescriptions": [
                    {"week": 1, "day": "D1", "exercises": [
                        exercise("Low-bar Squat", 100), exercise("Comp Bench", 80)]},
                    {"week": 5, "day": "D1", "exercises": [
                        exercise("Low-bar Squat", 165, "Top set"),
                        exercise("Low-bar Squat", 125, "Backoff")]}]}

    def test_equal_length_amendment_keeps_new_occurrence(self):
        block = self.block()
        before = copy.deepcopy(block)
        rows, _, _ = build_plan(block)
        backoff = next(r for r in rows if r[2] == "Low-bar Squat (backoff)")
        self.assertEqual(backoff[31:35], ["1", "3", "@6", "275"])
        self.assertEqual(backoff[3:9], [""] * 6)
        self.assertEqual(block, before)

    def test_explicit_phases_override_both_header_and_subtitle(self):
        block = self.block()
        block["week_phases"] = {
            "5": {"label": "PEAK", "description": "Peak before travel."},
            "6": {"label": "DELOAD", "description": "Travel recovery."}}
        rows, _, _ = build_plan(block)
        header = next(r for r in rows if r[3].startswith("WEEK 1"))
        self.assertIn("CALIBRATION", header[3])
        self.assertIn("WEEK 5 — PEAK", header[31])
        self.assertIn("WEEK 6 — DELOAD", header[38])
        subtitle = rows[rows.index(header) + 1]
        self.assertEqual(subtitle[31], "Peak before travel.")
        self.assertEqual(subtitle[38], "Travel recovery.")

    def test_legacy_five_week_phase_is_unchanged(self):
        block = self.block()
        block["weeks"] = 5
        rows, _, _ = build_plan(block)
        header = next(r for r in rows if r[3].startswith("WEEK 1"))
        self.assertIn("WEEK 5 — DELOAD", header[31])


class RowRoleTests(unittest.TestCase):
    """Role labels must come from structure, not from coaching prose."""

    def block(self, top_note, backoff_note, extra=()):
        def exercise(name, weight, note=""):
            return {"name": name, "notes": note,
                    "sets": [{"type": "normal", "weight_kg": weight,
                              "reps": 3, "rpe": 6}]}
        exercises = [exercise("Low-bar Squat", 165, top_note),
                     exercise("Low-bar Squat", 125, backoff_note)]
        exercises += [exercise(n, 50, nt) for n, nt in extra]
        return {"block_id": "test", "weeks": 5, "start_date": "2026-08-10",
                "days": [{"label": "D1", "focus": "Squat"}],
                "prescriptions": [{"week": 1, "day": "D1", "exercises": exercises}]}

    def labels(self, block):
        rows, _, _ = build_plan(block)
        # r[2] also carries the "Exercise" column header; only exercise rows are of interest.
        return [r[2] for r in rows if r[2] and r[2] != "Exercise"]

    def test_top_set_note_mentioning_backoff_is_not_labelled_backoff(self):
        # B5 W5: the 365 peak carries the hard stop "squat is DONE for the day, no backoff".
        # A prose scan labelled that row "(backoff)", right above the real backoff.
        labels = self.labels(self.block(
            "PEAK - TOP SET 365x3 @7 CAP. Any bar-speed loss: squat is DONE "
            "for the day, no backoff. Do not exceed 365.",
            "Backoff - 2 sets of 3 at 275 @6."))
        self.assertEqual(labels[:2],
                         ["Low-bar Squat (top set)", "Low-bar Squat (backoff)"])

    def test_pair_is_labelled_even_when_no_note_says_so(self):
        labels = self.labels(self.block("225 flat, medical cap.", "Second set of threes."))
        self.assertEqual(labels[:2],
                         ["Low-bar Squat (top set)", "Low-bar Squat (backoff)"])

    def test_single_row_lifts_stay_unlabelled(self):
        labels = self.labels(self.block(
            "Top set.", "Backoff.",
            extra=[("Face Pull", "Shoulder health. Stop on any painful arc."),
                   ("Seated Calf Raise", "Seated on purpose: no spinal load.")]))
        self.assertIn("Face Pull", labels)
        self.assertIn("Seated Calf Raise", labels)

    def test_amrap_note_still_wins_over_position(self):
        labels = self.labels(self.block("Top set.", "AMRAP to failure."))
        self.assertEqual(labels[1], "Low-bar Squat (AMRAP)")
