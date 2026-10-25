"""Dữ liệu trong unit test là giả lập, không phải nhãn người của dự án."""
import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.common import write_jsonl
from src.tv4_evaluation import evaluate
from src.gemini_client import build_payload
from src.llm import cache_key, classify


class LLMReviewTests(unittest.TestCase):
    def test_payload_contains_only_review_text_as_user_data(self):
        row = {"comments": "Good room", "review_id": "123", "manual_sentiment": "negative"}
        payload = build_payload(row, {"temperature": 0, "max_output_tokens": 2048}, "SYNTHETIC prompt", {})
        user = json.loads(payload["contents"][0]["parts"][0]["text"])
        self.assertEqual(user, {"review_text": "Good room"})
        self.assertNotIn("manual_sentiment", json.dumps(payload))

    def test_manual_disagreement_stays_in_metrics_and_error_table(self):
        labels = [{"snapshot_date": "2026-06-15", "review_id": "1", "split": "test",
                   "manual_sentiment": "negative", "needs_review": "false", "note": "synthetic"}]
        predictions = [{"snapshot_date": "2026-06-15", "review_id": "1", "status": "ok", "sentiment": "positive"}]
        result, checks = evaluate(labels, predictions, "synthetic")
        self.assertEqual(result["valid_gold"], 1)
        self.assertEqual(result["accuracy"], 0)
        self.assertEqual(len(checks), 1)
        self.assertEqual(checks[0]["correct"], "false")

    def test_skip_uses_capitalized_qa_flags_and_never_changes_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            prompt, schema, cache = directory / "prompt.txt", directory / "schema.json", directory / "cache.jsonl"
            prompt.write_text("SYNTHETIC prompt")
            schema.write_text('{"type":"object"}')
            config = {"prompt_file": str(prompt), "schema_file": str(schema), "prompt_version": "fixture",
                      "cache": str(cache), "temperature": 0, "max_output_tokens": 1024,
                      "max_retries": 0, "timeout_seconds": 1, "request_interval_seconds": 0, "model": "fixture"}
            row = {"snapshot_date": "2026-06-15", "review_id": "1", "listing_id": "2",
                   "comments": "Good room", "text_valid": "True", "listing_match": "True"}
            record = {**row, "cache_key": cache_key(row, config, "fixture", prompt.read_text(), json.loads(schema.read_text())),
                      "status": "ok", "sentiment": "mixed", "aspects": [], "language": "en", "error": None,
                      "usage": {}, "api_requests": 1}
            write_jsonl(cache, [record])
            before = cache.read_bytes()
            with patch.dict(os.environ, {}, clear=True), patch("src.llm.gemini_request") as network, contextlib.redirect_stdout(io.StringIO()):
                output = classify([row], config, str(directory / "out.jsonl"), skip_llm=True)
            network.assert_not_called()
            self.assertEqual(cache.read_bytes(), before)
            self.assertEqual(output[0]["sentiment"], "mixed")
            self.assertTrue(output[0]["from_cache"])

    def test_invalidated_qa_row_does_not_reuse_old_prediction(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            p, s = directory / "prompt.txt", directory / "schema.json"
            p.write_text("SYNTHETIC"); s.write_text("{}")
            config = {"prompt_file": str(p), "schema_file": str(s), "prompt_version": "fixture", "model": "fixture",
                      "cache": str(directory / "absent.jsonl"), "temperature": 0, "max_output_tokens": 1024,
                      "request_interval_seconds": 0}
            row = {"snapshot_date": "2026-06-15", "review_id": "1", "listing_id": "2",
                   "comments": "Text", "text_valid": "False", "listing_match": "True"}
            with patch.dict(os.environ, {}, clear=True), patch("src.llm.gemini_request") as network, contextlib.redirect_stdout(io.StringIO()):
                output = classify([row], config, str(directory / "out.jsonl"), skip_llm=True)
            network.assert_not_called()
            self.assertEqual(output[0]["error"], "input_empty_or_invalid_text")
            self.assertIsNone(output[0]["sentiment"])
            self.assertFalse((directory / "absent.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
