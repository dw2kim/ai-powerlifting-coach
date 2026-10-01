"""Warm-up ramps (`primary-warmup-ramp`): scaled to the top set, never a lone BW set."""
import unittest

from scripts.hevy.units import kg_to_lb, lb_to_kg
from scripts.hevy.warmups import apply_to_spec, barbell_ramp, bodyweight_ramp


def _lb(sets):
    return [(round(kg_to_lb(s["weight_kg"])), s["reps"]) for s in sets]


class BarbellRampTests(unittest.TestCase):
    def test_every_barbell_lift_opens_at_135_for_8(self):
        for kind in ("squat", "deadlift", "bench"):
            for top in range(185, 600, 5):
                self.assertEqual(barbell_ramp(kind, top)[0], (135, 8), (kind, top))

    def test_squat_and_sumo_climb_one_plate_a_side(self):
        """+90 per step, as he loads it: 135 → 225 → 315 → 405."""
        self.assertEqual([l for l, _ in barbell_ramp("squat", 455)], [135, 225, 315, 405])
        self.assertEqual([l for l, _ in barbell_ramp("deadlift", 285)], [135, 225])

    def test_bench_climbs_185_then_225(self):
        self.assertEqual([l for l, _ in barbell_ramp("bench", 275)], [135, 185, 225])

    def test_last_warmup_is_always_clear_of_the_top_set(self):
        for kind in ("squat", "deadlift", "bench"):
            for top in range(155, 600, 5):
                self.assertLessEqual(barbell_ramp(kind, top)[-1][0], top - 20, (kind, top))


class BodyweightRampTests(unittest.TestCase):
    def test_bodyweight_is_logged_as_1_lb(self):
        self.assertEqual(bodyweight_ramp("dip", 70)[0], (1, 8))
        self.assertEqual(bodyweight_ramp("pullup", 60)[0], (1, 8))

    def test_dip_bridges_at_35_then_45_above_a_70_top(self):
        """B6 W1: plan said BW×8 only; he added +35×8 himself before 70×5."""
        self.assertEqual(bodyweight_ramp("dip", 70)[1][0], 35)
        self.assertEqual(bodyweight_ramp("dip", 85)[1][0], 45)

    def test_pullup_bridges_at_45_and_adds_70_from_a_90_top(self):
        self.assertEqual(bodyweight_ramp("pullup", 60), [(1, 8), (45, 3)])
        self.assertEqual(bodyweight_ramp("pullup", 90), [(1, 8), (45, 3), (70, 1)])

    def test_bridge_never_sits_on_a_light_top_set(self):
        self.assertEqual(bodyweight_ramp("pullup", 45)[1][0], 35)


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
        self.assertEqual(_lb(dip), [(1, 8), (35, 5)] + [(70, 5)] * 4)

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
