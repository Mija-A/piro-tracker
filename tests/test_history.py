import unittest

from tracker import history


def order(code, stage):
    return {"code": code, "currentService": stage}


class TestMigration(unittest.TestCase):
    def test_old_flat_format_is_migrated(self):
        hist = history._migrate({"JO-1": [{"stage": "QA", "since": "2026-08-01 10:00"}]})
        rec = hist["orders"]["JO-1"]
        self.assertEqual(rec["journey"][0]["stage"], "QA")
        self.assertEqual(rec["last_seen"], "2026-08-01 10:00")

    def test_load_missing_file_gives_empty(self):
        self.assertEqual(history.load("does-not-exist.json"), {"orders": {}})


class TestUpdate(unittest.TestCase):
    def test_first_sighting_starts_journey(self):
        hist = {"orders": {}}
        moved = history.update(hist, [order("JO-1", "CADing")], now="2026-08-20 12:00")
        self.assertEqual(moved, 0)
        self.assertEqual(hist["orders"]["JO-1"]["journey"],
                         [{"stage": "CADing", "since": "2026-08-20 12:00"}])

    def test_stage_change_appends_and_counts(self):
        hist = {"orders": {"JO-1": {"journey": [{"stage": "CADing", "since": "2026-08-01 09:00"}],
                                    "last_seen": "2026-08-19 09:00"}}}
        moved = history.update(hist, [order("JO-1", "QA")], now="2026-08-20 12:00")
        self.assertEqual(moved, 1)
        self.assertEqual([e["stage"] for e in hist["orders"]["JO-1"]["journey"]], ["CADing", "QA"])
        self.assertEqual(hist["orders"]["JO-1"]["last_seen"], "2026-08-20 12:00")

    def test_same_stage_does_not_append(self):
        hist = {"orders": {"JO-1": {"journey": [{"stage": "QA", "since": "2026-08-01 09:00"}],
                                    "last_seen": "2026-08-19 09:00"}}}
        moved = history.update(hist, [order("JO-1", "QA")], now="2026-08-20 12:00")
        self.assertEqual(moved, 0)
        self.assertEqual(len(hist["orders"]["JO-1"]["journey"]), 1)
        self.assertEqual(hist["orders"]["JO-1"]["last_seen"], "2026-08-20 12:00")

    def test_missing_code_or_stage_is_skipped(self):
        hist = {"orders": {}}
        history.update(hist, [order(None, "QA"), order("JO-2", None)], now="2026-08-20 12:00")
        self.assertEqual(hist["orders"], {})


class TestPrune(unittest.TestCase):
    def test_old_unseen_orders_are_pruned(self):
        hist = {"orders": {
            "JO-old": {"journey": [], "last_seen": "2026-01-01 00:00"},
            "JO-new": {"journey": [], "last_seen": "2026-08-19 00:00"},
        }}
        pruned = history.prune(hist, now="2026-08-20 12:00", keep_days=60)
        self.assertIn("JO-old", pruned)
        self.assertNotIn("JO-old", hist["orders"])
        self.assertIn("JO-new", hist["orders"])

    def test_bad_stamp_is_kept(self):
        hist = {"orders": {"JO-x": {"journey": [], "last_seen": "garbage"}}}
        pruned = history.prune(hist, now="2026-08-20 12:00")
        self.assertEqual(pruned, {})
        self.assertIn("JO-x", hist["orders"])


if __name__ == "__main__":
    unittest.main()
