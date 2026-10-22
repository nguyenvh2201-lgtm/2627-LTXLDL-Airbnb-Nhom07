import contextlib
import io
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src.qa import process_calendar


class CalendarChunkTests(unittest.TestCase):
    def test_calendar_without_price_columns(self):
        raw = pd.DataFrame({
            "listing_id": ["001", "999", "001"],
            "date": ["2025-01-01", "2025-01-01", "2025-01-02"],
            "available": ["t", "f", "f"],
            "minimum_nights": [1] * 3,
            "maximum_nights": [30] * 3,
        })
        assigned = pd.DataFrame({"listing_id": pd.Series(["001"], dtype="string")})
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "raw" / "A").mkdir(parents=True)
            raw.to_csv(root / "raw" / "A" / "calendar.csv.gz", index=False)
            with contextlib.redirect_stdout(io.StringIO()):
                summary = process_calendar(
                    "A", assigned, assigned, raw_dir=root / "raw",
                    processed_dir=root / "processed", chunksize=1,
                )
            flagged = pd.read_csv(root / "processed" / "A" / "calendar_flagged.csv")
            self.assertEqual(len(flagged), 2)
            self.assertNotIn("price", flagged.columns)
            self.assertNotIn("adjusted_price", flagged.columns)
            self.assertEqual(summary.iloc[0]["n_available_valid"], 2)
            self.assertEqual(summary.iloc[0]["n_available"], 1)

    def test_filtering_preserves_cross_chunk_duplicates_and_conflicts(self):
        raw = pd.DataFrame({
            "listing_id": ["001", "999", "001", "001", "001"],
            "date": ["2025-01-01", "2025-01-01", "2025-01-01",
                     "2025-01-01", "2025-01-02"],
            "available": ["t", "f", "t", "f", "t"],
            "price": [100] * 5,
            "adjusted_price": [100] * 5,
            "minimum_nights": [1] * 5,
            "maximum_nights": [30] * 5,
            "unused_column": ["ignored"] * 5,
        })
        assigned = pd.DataFrame({"listing_id": pd.Series(["001"], dtype="string")})
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "raw" / "A").mkdir(parents=True)
            raw.to_csv(root / "raw" / "A" / "calendar.csv.gz", index=False)
            reports = []
            with contextlib.redirect_stdout(io.StringIO()):
                summary = process_calendar(
                    "A", assigned, assigned, raw_dir=root / "raw",
                    processed_dir=root / "processed", report_rows=reports, chunksize=2,
                )
            flagged = pd.read_csv(root / "processed" / "A" / "calendar_flagged.csv",
                                  dtype={"listing_id": "string"})
            self.assertEqual(flagged["listing_id"].tolist(), ["001"] * 4)
            self.assertNotIn("unused_column", flagged.columns)
            self.assertEqual(int(flagged["duplicate_calendar_full_row"].sum()), 2)
            self.assertEqual(int(flagged["duplicate_calendar"].sum()), 3)
            self.assertEqual(int(flagged["calendar_available_conflict"].sum()), 3)
            self.assertEqual(summary.iloc[0]["n_available_valid"], 1)
            metric = next(row for row in reports if row["metric_name"] == "row_count")
            self.assertEqual(metric["metric_before"], 4)
            self.assertEqual(metric["metric_after"], 4)


if __name__ == "__main__":
    unittest.main()
