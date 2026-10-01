"""The [sets×reps @RPE] prefix on an exercise note describes the working sets only.

A warm-up ×8 ahead of 4×5 used to read "[5×8]" in the app — the warm-up's reps and an
inflated set count, the first thing the athlete sees on the exercise.
"""
import unittest

from scripts.hevy.push_block import _notes_with_scheme


def _s(reps, rpe=None, type_="normal", **extra):
    return {"type": type_, "reps": reps, "rpe": rpe, **extra}


class SchemePrefixTests(unittest.TestCase):
    def test_warmup_is_excluded_from_count_and_reps(self):
        sets = [_s(8, type_="warmup")] + [_s(5, 7)] * 4
        self.assertEqual(_notes_with_scheme(sets, "Depth first."), "[4×5 @7] Depth first.")

    def test_plain_working_sets(self):
        self.assertEqual(_notes_with_scheme([_s(6, 7.5)] * 3, ""), "[3×6 @7.5]")

    def test_top_set_plus_backoffs(self):
        sets = [_s(3, 8)] + [_s(5, 7)] * 4
        self.assertEqual(_notes_with_scheme(sets, "x"), "[1×3 @8 + 4×5 @7] x")

    def test_timed_holds(self):
        sets = [{"type": "normal", "duration_seconds": 30}] * 3
        self.assertEqual(_notes_with_scheme(sets, ""), "[3×30s]")

    def test_only_warmups_leaves_note_untouched(self):
        self.assertEqual(_notes_with_scheme([_s(8, type_="warmup")], "n"), "n")


if __name__ == "__main__":
    unittest.main()
