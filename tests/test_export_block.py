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


class TopBackoffSplitTests(unittest.TestCase):
    """One Hevy exercise = top set + backoffs. The Sheet must show one load per row
    (athlete feedback 2026-10-03: '5 sets, 3/4/4/4/4, 365-385' hid the 295 backoffs)."""

    LB = 0.45359237

    def sets(self, top, back, n=4, top_reps=3, back_reps=4):
        return ([{"type": "warmup", "weight_kg": 135 * self.LB, "reps": 8},
                 {"type": "normal", "weight_kg": top * self.LB, "reps": top_reps, "rpe": 7.5}]
                + [{"type": "normal", "weight_kg": back * self.LB, "reps": back_reps, "rpe": 7}] * n)

    def block(self):
        squat = {"name": "Low-bar Squat", "notes": "Floor 365. Backoffs @ 295 keyed to the floor.",
                 "display_load": "365–385", "sets": self.sets(365, 295)}
        dip_flat = {"name": "Weighted Dip", "notes": "Stop above the pinch.",
                    "sets": [{"type": "normal", "weight_kg": 70 * self.LB, "reps": 5, "rpe": 7}] * 4}
        dip_peak = {"name": "Weighted Dip", "notes": "Dip peak.",
                    "sets": self.sets(105, 85, n=3, back_reps=5)}
        return {"block_id": "test", "weeks": 2, "start_date": "2026-09-28",
                "days": [{"label": "D1", "focus": "Squat"}],
                "prescriptions": [
                    {"week": 1, "day": "D1", "exercises": [squat, dip_flat]},
                    {"week": 2, "day": "D1", "exercises": [squat, dip_peak]}]}

    def rows(self):
        rows, _, _ = build_plan(self.block())
        return {r[2]: r for r in rows if r[2] and r[2] != "Exercise"}

    def test_squat_top_and_backoffs_get_their_own_rows_and_loads(self):
        rows = self.rows()
        top, back = rows["Low-bar Squat (top set)"], rows["Low-bar Squat (backoff)"]
        self.assertEqual(top[3:7], ["1", "3", "@7.5", "365–385"])
        self.assertTrue(top[7])                       # e1RM on the top set
        self.assertIn("Floor 365", top[8])
        self.assertEqual(back[3:9], ["4", "4", "@7", "295", "", ""])

    def test_top_row_sits_above_backoff_row(self):
        names = list(self.rows())
        self.assertLess(names.index("Low-bar Squat (top set)"),
                        names.index("Low-bar Squat (backoff)"))
        self.assertLess(names.index("Weighted Dip (top set)"),
                        names.index("Weighted Dip (backoff / straight sets)"))

    def test_straight_sets_week_lands_on_volume_row_not_top_row(self):
        rows = self.rows()
        top = rows["Weighted Dip (top set)"]
        vol = rows["Weighted Dip (backoff / straight sets)"]
        self.assertEqual(top[3:7], [""] * 4)          # W1 has no dip top set
        self.assertEqual(vol[3:7], ["4", "5", "@7", "BW+70"])
        self.assertEqual(top[10:14], ["1", "3", "@7.5", "BW+105"])
        self.assertEqual(vol[10:14], ["3", "5", "@7", "BW+85"])
