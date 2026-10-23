"""Regression tests for the TV4 Windows Git-clone compatibility fix.

The test inputs are synthetic. No provider credentials or real cache involved.
"""
import json
import tempfile
import unittest
from pathlib import Path

from src.common import read_jsonl
from src.tv4_evaluation import evaluate


class TV4WindowsCompatTests(unittest.TestCase):
    def test_broken_fourth_line_rejected_with_physical_line_number(self):
        with tempfile.TemporaryDirectory() as temp:
            filename = Path(temp) / "synthetic.jsonl"
            filename.write_text('{"x":1}\n{"x":2}\n{"x":3}\n{"broken":', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "dòng 4"):
                read_jsonl(filename)
            self.assertIn('"broken":', filename.read_text(encoding='utf-8'))

    def test_nonobject_jsonl_record_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            filename = Path(temp) / "synthetic.jsonl"
            filename.write_text('{"ok":true}\n[1,2,3]\n', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "dòng 2"):
                read_jsonl(filename)

    def test_bom_jsonl_supports_utf8_sig(self):
        with tempfile.TemporaryDirectory() as temp:
            filename = Path(temp) / "synthetic.jsonl"
            filename.write_bytes(b'\xef\xbb\xbf{"x":1}\n')
            self.assertEqual(read_jsonl(filename), [{"x": 1}])

    def test_tv4_evaluator_keeps_disagreement_as_error(self):
        labels = [{"snapshot_date": "2026-06-15", "review_id": "1", "split": "test",
                   "manual_sentiment": "negative", "needs_review": "false", "note": "synthetic"}]
        predictions = [{"snapshot_date": "2026-06-15", "review_id": "1", "status": "ok",
                        "sentiment": "positive"}]
        metrics, rows = evaluate(labels, predictions, "synthetic")
        self.assertEqual(metrics["accuracy"], 0.0)
        self.assertEqual(rows[0]["correct"], "false")


if __name__ == "__main__":
    unittest.main()
