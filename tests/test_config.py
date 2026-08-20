import json
import os
import unittest

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "site", "config.json")


class TestConfig(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(CONFIG_PATH, encoding="utf-8") as f:
            cls.cfg = json.load(f)

    def test_department_names_unique(self):
        names = [d["name"] for d in self.cfg["departments"]]
        self.assertEqual(len(names), len(set(names)))

    def test_no_stage_in_two_departments(self):
        seen = {}
        for d in self.cfg["departments"]:
            for s in d["stages"]:
                self.assertNotIn(s, seen, f"stage '{s}' in both '{seen.get(s)}' and '{d['name']}'")
                seen[s] = d["name"]

    def test_person_grouped_stages_exist_in_some_department(self):
        all_stages = {s for d in self.cfg["departments"] for s in d["stages"]}
        for s in self.cfg["personGroupedStages"]:
            self.assertIn(s, all_stages, f"personGroupedStages entry '{s}' is not a known stage")

    def test_metal_order_entries_have_colors(self):
        for m in self.cfg["metalOrder"]:
            self.assertIn(m, self.cfg["metalColors"], f"'{m}' in metalOrder but has no color")

    def test_thresholds_are_sane(self):
        self.assertGreater(self.cfg["stuckDays"], 0)
        self.assertGreaterEqual(self.cfg["staleDays"], 0)
        self.assertGreaterEqual(self.cfg["refreshSeconds"], 30)


if __name__ == "__main__":
    unittest.main()
