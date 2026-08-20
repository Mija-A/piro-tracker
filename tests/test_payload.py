import unittest

from tracker import payload


class TestPayload(unittest.TestCase):
    def test_suborders_are_dropped(self):
        self.assertTrue(payload.is_sub("JO-123-1"))
        self.assertFalse(payload.is_sub("JO-123"))
        data = payload.build([{"code": "JO-123"}, {"code": "JO-123-1"}],
                             {"orders": {}}, generated_at="2026-08-20T12:00:00Z")
        self.assertEqual([o["code"] for o in data["orders"]], ["JO-123"])

    def test_journey_is_attached_from_history(self):
        hist = {"orders": {"JO-1": {"journey": [{"stage": "QA", "since": "2026-08-01 10:00"}],
                                    "last_seen": "2026-08-20 12:00"}}}
        data = payload.build([{"code": "JO-1", "currentService": "QA"}], hist,
                             generated_at="2026-08-20T12:00:00Z")
        self.assertEqual(data["orders"][0]["journey"][0]["stage"], "QA")

    def test_fields_and_sku_dedup(self):
        o = {"code": "JO-9", "customerName": "Smith", "currentService": "CADing",
             "daysInCurrentService": 4, "dueDate": "2026-10-01T00:00:00",
             "metals": "18k White; Platinum", "serviceAssignedUser": "Ana",
             "items": [{"itemSKU": "R-1", "itemTypeSKU": "Ring"},
                       {"itemSKU": "R-1", "itemTypeSKU": "Ring"}]}
        row = payload.build([o], {"orders": {}}, generated_at="x")["orders"][0]
        self.assertEqual(row["due"], "2026-10-01")
        self.assertEqual(row["sku"], "R-1")
        self.assertEqual(row["skutype"], "Ring")
        self.assertEqual(row["assigned"], "Ana")


if __name__ == "__main__":
    unittest.main()
