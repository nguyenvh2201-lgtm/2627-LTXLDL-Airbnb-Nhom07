import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src.qa import (
    check_comments,
    check_date,
    check_price,
    export_qa_report,
    report_review_snapshots,
    report_table,
)


class QAReportTests(unittest.TestCase):
    def test_original_invalid_dates_are_reported_after_cleaning(self):
        before = pd.DataFrame({"date": ["bad", None, "2025-01-01"],
                               "comments": ["<b>Hi</b>", None, "Hello"]})
        flags = pd.concat([check_date(before), check_comments(before)], axis=1)
        after = before.copy()
        after["date"] = flags["date_parsed"]
        after["comment_clean"] = flags["comment_clean"]
        rows = []
        report_table(rows, "A", "reviews", before, after, flags)
        rules = {row["rule"]: row for row in rows if row["metric_name"] is None}
        self.assertEqual(rules["wrong_date_type"]["rows_flagged"], 1)
        self.assertEqual(rules["date_missing"]["rows_flagged"], 1)
        self.assertEqual(rules["comment_markup"]["rows_flagged"], 1)
        metric = next(r for r in rows if r["metric_name"] == "mean_comment_length")
        self.assertAlmostEqual(metric["metric_before"], 14 / 3)
        self.assertAlmostEqual(metric["metric_after"], 7 / 3)
        self.assertTrue(all(r["rows_removed"] == 0 for r in rows))

    def test_price_metrics_keep_same_population(self):
        before = pd.DataFrame({"price": ["$100", "$200", "bad", None, "$0"]})
        flags = check_price(before["price"])
        rows = []
        report_table(rows, "A", "listings", before, flags, flags)
        metric = next(r for r in rows if r["metric_name"] == "median_price")
        self.assertEqual(metric["metric_before"], 100)
        self.assertEqual(metric["metric_after"], 100)
        self.assertNotIn("price_valid", [r["rule"] for r in rows])

    def test_cross_snapshot_comparisons_exclude_ambiguous_and_missing_values(self):
        first = pd.DataFrame({
            "review_id": ["1", "2", "3", "3", "4", "5", None],
            "listing_id": ["10", "20", "30", "31", "40", "50", "60"],
            "date": ["2025-01-01", "bad", "2025-01-01", "2025-01-02",
                     "2025-01-01", "2025-01-01", "2025-01-01"],
            "comments": ["old", None, "a", "b", "same", "", "ignored"],
        })
        second = pd.DataFrame({
            "review_id": ["1", "2", "3", "4", "5"],
            "listing_id": ["11", "20", "30", None, "50"],
            "date": ["2025-01-02", "2025-01-01", "2025-01-01",
                     "2025-01-01 12:00:00", "2025-01-01"],
            "comments": ["new", "text", "a", "same", ""],
        })
        rows = []
        report_review_snapshots(rows, {"A": first, "B": second})
        rules = {r["rule"]: r for r in rows}
        self.assertEqual(rules["review_id_repeated"]["rows_flagged"], 5)
        self.assertEqual(rules["date_changed"]["rows_checked"], 3)
        self.assertEqual(rules["date_changed"]["rows_flagged"], 1)
        self.assertEqual(rules["listing_changed"]["rows_checked"], 3)
        self.assertEqual(rules["listing_changed"]["rows_flagged"], 1)
        self.assertEqual(rules["comments_changed"]["rows_checked"], 3)
        self.assertEqual(rules["comments_changed"]["rows_flagged"], 1)

    def test_undefined_price_metric_stays_missing_with_explanation(self):
        before = pd.DataFrame({"price": [None, "bad"]})
        flags = check_price(before["price"])
        rows = []
        report_table(rows, "A", "listings", before, flags, flags)
        metric = next(r for r in rows if r["metric_name"] == "median_price")
        self.assertTrue(pd.isna(metric["metric_before"]))
        self.assertTrue(pd.isna(metric["metric_after"]))
        self.assertIn("metric", metric["note"])

    def test_all_six_pairs_and_export(self):
        empty = pd.DataFrame({col: pd.Series(dtype="string") for col in
                              ["review_id", "listing_id", "date", "comments"]})
        rows = []
        report_review_snapshots(rows, dict.fromkeys(["A", "B", "C", "D"], empty))
        self.assertEqual(len(rows), 24)
        self.assertTrue(all(r["rows_checked"] == 0 for r in rows))
        with tempfile.TemporaryDirectory() as folder:
            output = export_qa_report(rows, Path(folder) / "reports")
            loaded = pd.read_csv(output)
            self.assertEqual(len(loaded), 24)
            self.assertEqual(len(loaded.groupby(["snapshot_date", "compared_snapshot"])), 6)


if __name__ == "__main__":
    unittest.main()
