"""P4 regression tests for malformed Gemini HTTP responses (all fixtures synthetic)."""
import contextlib
import http.client
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from src.common import read_jsonl
from src.gemini_client import ProviderError, gemini_request, http_details
from src.llm import classify


class _BrokenBody:
    def close(self):
        pass

    def read(self, *_args):
        raise ConnectionResetError("synthetic server reset during error body read")


class ProviderEdgeRegressionTests(unittest.TestCase):
    def setUp(self):
        self.row = {"comments": "A nice room", "review_id": "123", "listing_id": "456"}
        self.config = {"temperature": 0, "max_output_tokens": 128,
                       "timeout_seconds": 1, "max_retries": 0}
        self.api_key = "SYNTHETIC_API_SECRET"
        self.label = {"sentiment": "positive", "aspects": [], "language": "en",
                      "status": "ok", "error": None}
        self.valid = {
            "candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": json.dumps(self.label)}]}}],
            "usageMetadata": {"totalTokenCount": 10},
        }

    def request(self):
        return gemini_request(self.row, self.config, "fixture", "SYNTHETIC prompt", {}, self.api_key)

    def response(self):
        return io.BytesIO(json.dumps(self.valid).encode("utf-8"))

    def error(self, code, body=b'{}', headers=None):
        return HTTPError("https://example.invalid", code, "Synthetic error", headers or {}, io.BytesIO(body))

    def test_invalid_utf8_response_is_provider_invalid_json_not_batch_crash(self):
        with patch("urllib.request.urlopen", return_value=io.BytesIO(b"\xff\xfe")):
            with self.assertRaises(ProviderError) as caught:
                self.request()
        self.assertEqual(str(caught.exception), "provider_invalid_json")
        self.assertEqual(caught.exception.attempts, 1)

    def test_connection_reset_retries_and_counts_real_requests(self):
        self.config["max_retries"] = 1
        with patch("urllib.request.urlopen", side_effect=[ConnectionResetError("synthetic"), self.response()]) as network, \
             patch("src.gemini_client.time.sleep") as sleep:
            value = self.request()
        self.assertEqual(network.call_count, 2)
        sleep.assert_called_once_with(1)
        self.assertEqual(value["api_requests"], 2)
        self.assertEqual(json.loads(value["text"]), self.label)

    def test_connection_reset_exhausted_keeps_network_error_taxonomy(self):
        with patch("urllib.request.urlopen", side_effect=ConnectionResetError("synthetic")):
            with self.assertRaises(ProviderError) as caught:
                self.request()
        self.assertEqual(str(caught.exception), "network_or_timeout")
        self.assertEqual(caught.exception.attempts, 1)

    def test_truncated_http_body_retries_as_network_failure(self):
        self.config["max_retries"] = 1
        truncated = http.client.IncompleteRead(b'{"candidates": [')
        with patch("urllib.request.urlopen", side_effect=[truncated, self.response()]) as network, \
             patch("src.gemini_client.time.sleep") as sleep:
            value = self.request()
        self.assertEqual(network.call_count, 2)
        sleep.assert_called_once_with(1)
        self.assertEqual(value["api_requests"], 2)

    def test_http_error_body_read_failure_preserves_http_status(self):
        error = HTTPError("https://example.invalid", 429, "Synthetic error", {"Retry-After": "120"}, _BrokenBody())
        with patch("urllib.request.urlopen", side_effect=error), \
             patch("src.gemini_client.time.sleep") as sleep:
            with self.assertRaises(ProviderError) as caught:
                self.request()
        self.assertEqual(str(caught.exception), "http_429")
        self.assertEqual(caught.exception.attempts, 1)
        self.assertEqual(caught.exception.details["http_status"], 429)
        sleep.assert_not_called()

    def test_http_nested_diagnostics_redact_exact_and_key_pattern(self):
        body = {"error": {"status": "INVALID_ARGUMENT", "message": f"key={self.api_key}",
                          "details": [{"note": f"leak:{self.api_key}",
                                       "nested": ["AIza1234567890abcdef1234567890abcdef12345"]}]}}
        error = self.error(400, json.dumps(body).encode("utf-8"))
        details = http_details(error, self.api_key)
        self.assertEqual(details["status"], "INVALID_ARGUMENT")
        self.assertEqual(details["http_status"], 400)
        diagnostics = json.dumps(details)
        self.assertNotIn(self.api_key, diagnostics)
        self.assertNotIn("AIza1234567890abcdef1234567890abcdef12345", diagnostics)
        self.assertEqual(details["details"][0]["note"], "leak:[REDACTED]")

    def test_http_unicode_escaped_key_is_redacted_after_json_parse(self):
        encoded = json.dumps({"error": {"details": [{"debug": self.api_key}]}}).replace("SYNTHETIC", "\\u0053YNTHETIC")
        details = http_details(self.error(403, encoded.encode("utf-8")), self.api_key)
        self.assertNotIn(self.api_key, json.dumps(details))

    def test_non_retriable_400_keeps_http_error_and_attempts(self):
        with patch("urllib.request.urlopen", side_effect=self.error(400)) as network, \
             patch("src.gemini_client.time.sleep") as sleep:
            with self.assertRaises(ProviderError) as caught:
                self.request()
        self.assertEqual(str(caught.exception), "http_400")
        self.assertEqual(caught.exception.attempts, 1)
        self.assertEqual(network.call_count, 1)
        sleep.assert_not_called()

    def run_batch(self, network_effects):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "prompt.txt").write_text("SYNTHETIC prompt", encoding="utf-8")
            (root / "schema.json").write_text("{}", encoding="utf-8")
            config = {**self.config, "prompt_file": str(root / "prompt.txt"),
                      "schema_file": str(root / "schema.json"), "cache": str(root / "cache.jsonl"),
                      "prompt_version": "fixture", "model": "fixture", "request_interval_seconds": 0}
            rows = [{"snapshot_date": "2026-06-15", "review_id": str(i),
                     "listing_id": "456", "comments": "A nice room"} for i in range(1, 3)]
            out = str(root / "out.jsonl")
            with patch.dict(os.environ, {"GEMINI_API_KEY": self.api_key}, clear=True), \
                 patch("urllib.request.urlopen", side_effect=network_effects) as network, \
                 contextlib.redirect_stdout(io.StringIO()):
                records = classify(rows, config, out)
            report = json.loads(Path(out + ".run.json").read_text(encoding="utf-8"))
            output = read_jsonl(out)
            cache = read_jsonl(config["cache"])
            return records, report, output, cache, network.call_count

    def test_batch_invalid_utf8_marks_error_then_processes_next_review(self):
        # Using the valid provider HTTP body, not a simplified fake request_fn.
        records, report, output, cache, calls = self.run_batch([
            io.BytesIO(b"\xff"), self.response()])
        self.assertEqual(calls, 2)
        self.assertEqual([r["status"] for r in records], ["error", "ok"])
        self.assertEqual([r["error"] for r in output], ["provider_invalid_json", None])
        self.assertEqual(report["api_requests"], 2)
        self.assertEqual(len(cache), 1)
        self.assertEqual(cache[0]["review_id"], "2")

    def test_batch_http_429_still_blocks_following_new_requests_and_redacts(self):
        body = {"error": {"message": "rate limit", "details": [{"hint": self.api_key}]}}
        records, report, output, cache, calls = self.run_batch([
            self.error(429, json.dumps(body).encode("utf-8"), {"Retry-After": "120"})])
        self.assertEqual(calls, 1)
        self.assertEqual([r["error"] for r in records], ["http_429", "not_attempted_after_http_429"])
        self.assertEqual(report["api_requests"], 1)
        self.assertEqual(len(output), 2)
        self.assertEqual(cache, [])
        self.assertNotIn(self.api_key, json.dumps(report))
        self.assertNotIn(self.api_key, json.dumps(output))

    def test_batch_connection_reset_does_not_abort_remaining_reviews(self):
        records, report, output, _, calls = self.run_batch([
            ConnectionResetError("synthetic"), self.response()])
        self.assertEqual(calls, 2)
        self.assertEqual(records[0]["error"], "network_or_timeout")
        self.assertEqual(len(output), 2)
        self.assertEqual(report["new_reviews_attempted"], 2)
        self.assertEqual(report["api_requests"], 2)
        self.assertEqual(records[1]["status"], "ok")

    def test_malformed_candidate_still_provider_invalid_response(self):
        body = {"candidates": "not a list"}
        with patch("urllib.request.urlopen", return_value=io.BytesIO(json.dumps(body).encode("utf-8"))):
            with self.assertRaises(ProviderError) as caught:
                self.request()
        self.assertEqual(str(caught.exception), "provider_invalid_response")


if __name__ == "__main__":
    unittest.main()
