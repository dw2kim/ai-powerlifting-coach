"""accessory-rotation floor: >=4 real rotations, >=1 on every training day (FB 2026-11-11).

A rotation is a dropped accessory replaced by a new one for the same muscle. Additions,
re-entries and drops don't count — B7 had two of each and zero rotations.
"""
import unittest

from scripts.hevy.exercise_map import Resolver
from scripts.review.rotation_check import compare

DAYS = [{"label": d} for d in ("D1", "D2", "D3", "D4")]


def _block(bid, by_day, weeks=1):
    pres = [{"week": w, "day": d, "exercises": [{"name": n, "tier": "accessory"} for n in names]}
            for w in range(1, weeks + 1) for d, names in by_day.items()]
    return {"block_id": bid, "weeks": weeks, "days": DAYS, "prescriptions": pres}


PRIOR = _block("B1", {
    "D1": ["Chest Fly (Machine)", "Tricep Pushdown"],
    "D2": ["Lateral Raise (Dumbbell)", "Seated Leg Curl"],
    "D3": ["Reverse Pec Deck", "Leg Extension (Machine)"],
    "D4": ["Chest Supported Incline Row", "Concentration Curl"],
})


class RotationCheckTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = Resolver()

    def test_identical_block_has_zero_rotations_and_fails(self):
        rep = compare(_block("B2", {d: [e["name"] for e in p["exercises"]]
                                    for p in PRIOR["prescriptions"] for d in [p["day"]]}), PRIOR, self.r)
        self.assertEqual(len(rep.rotations), 0)
        self.assertTrue(rep.failures())

    def test_one_swap_per_day_passes(self):
        new = _block("B2", {
            "D1": ["Cable Fly Crossovers", "Tricep Pushdown"],
            "D2": ["Lateral Raise (Cable)", "Seated Leg Curl"],
            "D3": ["Rear Delt Reverse Fly (Dumbbell)", "Leg Extension (Machine)"],
            "D4": ["Chest Supported Incline Row", "Hammer Curl (Dumbbell)"],
        })
        rep = compare(new, PRIOR, self.r)
        self.assertEqual(len(rep.rotations), 4)
        self.assertEqual(rep.per_day(), {"D1": 1, "D2": 1, "D3": 1, "D4": 1})
        self.assertEqual(rep.failures(), [])

    def test_four_rotations_but_an_empty_day_fails(self):
        new = _block("B2", {
            "D1": ["Cable Fly Crossovers", "Triceps Extension (Dumbbell)"],
            "D2": ["Lateral Raise (Cable)", "Lying Leg Curl (Machine)"],
            "D3": ["Reverse Pec Deck", "Leg Extension (Machine)"],
            "D4": ["Chest Supported Incline Row", "Concentration Curl"],
        })
        rep = compare(new, PRIOR, self.r)
        self.assertEqual(len(rep.rotations), 4)
        self.assertIn("no rotation on D3, D4", "; ".join(rep.failures()))

    def test_addition_and_drop_are_not_a_rotation(self):
        # Curl (biceps) out, hip adduction (adductors) in: different muscles, so no pair.
        new = _block("B2", {
            "D1": ["Chest Fly (Machine)", "Tricep Pushdown"],
            "D2": ["Lateral Raise (Dumbbell)", "Seated Leg Curl"],
            "D3": ["Reverse Pec Deck", "Leg Extension (Machine)"],
            "D4": ["Chest Supported Incline Row", "Hip Adduction (Machine)"],
        })
        rep = compare(new, PRIOR, self.r)
        self.assertEqual(rep.rotations, [])
        self.assertEqual([l.name for l in rep.additions], ["Hip Adduction (Machine)"])
        self.assertEqual([l.name for l in rep.drops], ["Concentration Curl"])

    def test_non_accessory_tiers_are_ignored(self):
        new = _block("B2", {"D1": ["Chest Fly (Machine)"]})
        new["prescriptions"][0]["exercises"].append({"name": "Low-bar Squat", "tier": "primary"})
        rep = compare(new, PRIOR, self.r)
        self.assertNotIn("Low-bar Squat", [l.name for l in rep.additions])


if __name__ == "__main__":
    unittest.main()
