"""Warm-up ramps (`primary-warmup-ramp`): scaled to the top set, never a lone BW set."""
import unittest

from scripts.hevy.units import kg_to_lb, lb_to_kg
from scripts.hevy.warmups import apply_to_spec, barbell_ramp, bodyweight_ramp


def _lb(sets):
    return [(round(kg_to_lb(s["weight_kg"])), s["reps"]) for s in sets]


class BarbellRampTests(unittest.TestCase):
    def test_matches_his_logged_315_ramp(self):
        self.assertEqual(barbell_ramp(315), [(135, 8), (225, 3), (275, 2)])

    def test_last_warmup_stays_close_to_a_heavy_top_set(self):
        """The old static ramp leapt 275 → 405."""
        ramp = barbell_ramp(405)
        self.assertEqual(ramp[-1][0], 365)
        self.assertGreaterEqual(len(ramp), 4)

    def test_last_warmup_is_always_clear_of_the_top_set(self):
        for top in range(150, 600, 5):
            last = barbell_ramp(top)[-1][0]
            self.assertLessEqual(last, top - 20, top)
            self.assertLessEqual(last, top * 0.92, top)

    def test_jumps_shrink_toward_the_top(self):
        loads = [l for l, _ in barbell_ramp(455)]
        gaps = [b - a for a, b in zip(loads, loads[1:])]
        self.assertLessEqual(gaps[-1], gaps[0])

    def test_opener_is_never_a_triple(self):
        for top in range(150, 600, 5):
            self.assertGreaterEqual(barbell_ramp(top)[0][1], 5, top)


class BodyweightRampTests(unittest.TestCase):
    def test_dip_gets_a_loaded_bridge(self):
        """B6 W1: plan said BW×8 only; he added +35×8 himself before 70×5."""
        self.assertEqual(bodyweight_ramp("dip", 70), [(0.0, 8), (40.0, 3)])

    def test_heavy_top_gets_two_bridges(self):
        self.assertEqual(bodyweight_ramp("pullup", 90), [(0.0, 6), (40.0, 3), (65.0, 3)])

    def test_light_top_is_bodyweight_only(self):
        self.assertEqual(bodyweight_ramp("dip", 15), [(0.0, 8)])


class ApplyToSpecTests(unittest.TestCase):
    def spec(self):
        return {"prescriptions": [{"week": 1, "day": "D3", "exercises": [
            {"name": "Weighted Dip", "tier": "primary",
             "sets": [{"type": "warmup", "weight_kg": 0.0, "reps": 8}]
             + [{"type": "normal", "weight_kg": lb_to_kg(70), "reps": 5, "rpe": 7}] * 4},
            {"name": "CGB", "tier": "secondary",
             "sets": [{"type": "normal", "weight_kg": lb_to_kg(185), "reps": 5}] * 3},
        ]}]}

    def test_rewrites_primary_warmups_and_keeps_working_sets(self):
        spec = self.spec()
        apply_to_spec(spec)
        dip = spec["prescriptions"][0]["exercises"][0]["sets"]
        self.assertEqual(_lb(dip), [(0, 8), (40, 3)] + [(70, 5)] * 4)

    def test_leaves_secondaries_alone(self):
        spec = self.spec()
        apply_to_spec(spec)
        cgb = spec["prescriptions"][0]["exercises"][1]["sets"]
        self.assertTrue(all(s["type"] == "normal" for s in cgb))

    def test_idempotent(self):
        spec = self.spec()
        apply_to_spec(spec)
        self.assertEqual(apply_to_spec(spec), [])


if __name__ == "__main__":
    unittest.main()
