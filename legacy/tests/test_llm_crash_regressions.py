"""Regression tests for defensive Gemini metadata and error recording.

All data and responses here are SYNTHETIC. No live requests are performed.
"""
import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.common import read_jsonl
from src.gemini_client import gemini_request
from src.llm import classify


class LLMCrashRegressionTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        prompt = self.root / "prompt.txt"
        schema = self.root / "schema.json"
        prompt.write_text("SYNTHETIC prompt", encoding="utf-8")
        schema.write_text("{}", encoding="utf-8")
        self.config = {
            "model": "fixture-model", "prompt_version": "fixture-v1",
            "prompt_file": str(prompt), "schema_file": str(schema),
            "cache": str(self.root / "cache.jsonl"),
            "temperature": 0, "max_output_tokens": 1024,
            "max_retries": 0, "timeout_seconds": 1,
            "request_interval_seconds": 0,
        }
        self.row = {
            "snapshot_date": "2026-06-15", "review_id": "1", "listing_id": "2",
            "comments": "A clean room", "text_valid": "true", "listing_match": "true",
        }
        self.label = {
            "sentiment": "positive", "aspects": [], "language": "en",
            "status": "ok", "error": None,
        }
        self.output = self.root / "out.jsonl"

    def classify_with(self, provider_response, rows=None):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "SYNTHETIC_KEY"}, clear=True), \
                patch("src.llm.gemini_request", return_value=provider_response) as network, \
                contextlib.redirect_stdout(io.StringIO()):
            result = classify(rows or [self.row], self.config, str(self.output))
        return result, network.call_count

    def provider(self, *, text=None, usage=None):
        return {
            "text": json.dumps(self.label) if text is None else text,
            "usage": usage, "model_version": "fixture", "api_requests": 1,
        }

    def test_http_null_usage_metadata_has_empty_mapping(self):
        body = {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": json.dumps(self.label)}]}}],
                "usageMetadata": None}
        with patch("urllib.request.urlopen", return_value=io.BytesIO(json.dumps(body).encode("utf-8"))):
            result = gemini_request(self.row, self.config, "fixture-model", "SYNTHETIC", {}, "SYNTHETIC_KEY")
        self.assertEqual(result["usage"], {})
        self.assertEqual(result["api_requests"], 1)

    def test_http_malformed_usage_metadata_has_empty_mapping(self):
        body = {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": json.dumps(self.label)}]}}],
                "usageMetadata": ["not a token count"]}
        with patch("urllib.request.urlopen", return_value=io.BytesIO(json.dumps(body).encode("utf-8"))):
            result = gemini_request(self.row, self.config, "fixture-model", "SYNTHETIC", {}, "SYNTHETIC_KEY")
        self.assertEqual(result["usage"], {})

    def test_runner_null_usage_does_not_abort_reporting_or_cache(self):
        records, calls = self.classify_with(self.provider(usage=None))
        self.assertEqual(calls, 1)
        self.assertEqual(records[0]["status"], "ok")
        self.assertEqual(records[0]["usage"], {})
        self.assertEqual(read_jsonl(self.config["cache"])[0]["status"], "ok")
        report = json.loads(Path(str(self.output) + ".run.json").read_text(encoding="utf-8"))
        self.assertEqual(report["api_requests"], 1)
        self.assertEqual(report["prompt_tokens_new_calls"], 0)
        self.assertEqual(report["total_tokens_new_calls"], 0)
        with patch.dict(os.environ, {}, clear=True), patch("src.llm.gemini_request") as network, \
                contextlib.redirect_stdout(io.StringIO()):
            reused = classify([self.row], self.config, str(self.output), skip_llm=True)
        network.assert_not_called()
        self.assertTrue(reused[0]["from_cache"])

    def test_runner_invalid_token_counters_do_not_abort_report(self):
        records, _ = self.classify_with(self.provider(usage={"promptTokenCount": None, "totalTokenCount": "invalid"}))
        self.assertEqual(records[0]["status"], "ok")
        report = json.loads(Path(str(self.output) + ".run.json").read_text(encoding="utf-8"))
        self.assertEqual(report["prompt_tokens_new_calls"], 0)
        self.assertEqual(report["total_tokens_new_calls"], 0)

    def test_missing_provider_text_is_recorded_and_batch_continues(self):
        bad = {"usage": {}, "model_version": "fixture", "api_requests": 1}
        good = self.provider(usage={"promptTokenCount": 3, "totalTokenCount": 5})
        rows = [self.row, {**self.row, "review_id": "2"}]
        with patch.dict(os.environ, {"GEMINI_API_KEY": "SYNTHETIC_KEY"}, clear=True), \
                patch("src.llm.gemini_request", side_effect=[bad, good]) as network, \
                contextlib.redirect_stdout(io.StringIO()):
            records = classify(rows, self.config, str(self.output))
        self.assertEqual(network.call_count, 2)
        self.assertEqual([r["status"] for r in records], ["error", "ok"])
        self.assertEqual(records[0]["error"], "'text'")
        self.assertNotIn("raw_response", records[0])
        self.assertEqual([r["review_id"] for r in read_jsonl(self.config["cache"])], ["2"])
        self.assertEqual([r["review_id"] for r in read_jsonl(self.output)], ["1", "2"])
        report = json.loads(Path(str(self.output) + ".run.json").read_text(encoding="utf-8"))
        self.assertEqual(report["status_counts"], {"error": 1, "ok": 1})

    def test_nonstring_provider_text_cannot_crash_error_handler(self):
        response = self.provider(usage={})
        response["text"] = 123
        records, calls = self.classify_with(response)
        self.assertEqual(calls, 1)
        self.assertEqual(records[0]["status"], "error")
        self.assertNotIn("raw_response", records[0])
        self.assertTrue(Path(str(self.output) + ".run.json").exists())

    def test_invalid_json_still_records_raw_response_for_diagnostics(self):
        records, calls = self.classify_with(self.provider(text="not-json", usage={}))
        self.assertEqual(calls, 1)
        self.assertEqual(records[0]["status"], "error")
        self.assertEqual(records[0]["raw_response"], "not-json")
        self.assertTrue(Path(str(self.output) + ".run.json").exists())


if __name__ == "__main__":
    unittest.main()
