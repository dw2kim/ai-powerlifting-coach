"""superset-same-equipment: a superset only pairs exercises done on the same equipment.

He can't hold the chest fly machine while he's on the leg curl. Dumbbell + dumbbell and
cable + cable are fine; a machine pairs with nothing.
"""
import unittest

from scripts.hevy.exercise_map import Resolver
from scripts.hevy.push_block import check_supersets, superset_station


def _ex(name, ss):
    return {"name": name, "superset_id": ss, "sets": []}


class StationTests(unittest.TestCase):
    def test_cable_is_one_station_even_though_hevy_calls_it_machine(self):
        self.assertEqual(superset_station({"equipment": "machine", "title": "Lat Pulldown (Cable)"}), "cable")
        self.assertEqual(superset_station({"equipment": "machine", "title": "Face Pull"}), "cable")

    def test_each_machine_is_its_own_station(self):
        a = superset_station({"equipment": "machine", "title": "Chest Fly (Machine)"})
        b = superset_station({"equipment": "machine", "title": "Seated Leg Curl (Machine)"})
        self.assertNotEqual(a, b)


class CheckSupersetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = Resolver()

    def test_two_machines_refused(self):
        with self.assertRaises(ValueError):
            check_supersets([_ex("Chest Fly (Machine)", 0), _ex("Seated Leg Curl", 0)], self.r)

    def test_machine_with_dumbbell_refused(self):
        with self.assertRaises(ValueError):
            check_supersets([_ex("Seated Leg Curl", 0), _ex("Lateral Raise (Dumbbell)", 0)], self.r)

    def test_two_dumbbells_allowed(self):
        check_supersets([_ex("Lateral Raise (Dumbbell)", 0), _ex("Chest Supported Incline Row", 0)], self.r)

    def test_two_cables_allowed(self):
        check_supersets([_ex("Tricep Pushdown", 1), _ex("Face Pull", 1)], self.r)

    def test_unpaired_machines_are_fine(self):
        check_supersets([_ex("Chest Fly (Machine)", None), _ex("Seated Leg Curl", None)], self.r)

    def test_b6_style_pair_from_b7_is_refused(self):
        with self.assertRaises(ValueError):
            check_supersets([_ex("Tricep Pushdown", 0), _ex("Chest Fly (Machine)", 0)], self.r)


if __name__ == "__main__":
    unittest.main()
