"""P3 duplicate-cache regression tests: synthetic data; no Gemini calls."""
import contextlib
import csv
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.cache_audit import audit
from src.common import read_jsonl, write_jsonl
from src.llm import cache_key, classify


class DuplicateFingerprintCacheTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.prompt = self.root / 'prompt.txt'
        self.schema = self.root / 'schema.json'
        self.prompt.write_text('SYNTHETIC prompt', encoding='utf-8')
        self.schema.write_text('{}', encoding='utf-8')
        self.cache = self.root / 'cache.jsonl'
        self.config = {
            'snapshot_date': '2026-06-15', 'model': 'fixture',
            'prompt_version': 'fixture', 'prompt_file': str(self.prompt),
            'schema_file': str(self.schema), 'cache': str(self.cache),
            'temperature': 0, 'max_output_tokens': 1024,
            'request_interval_seconds': 0,
        }
        self.row = {
            'snapshot_date': '2026-06-15', 'review_id': '001234',
            'listing_id': '000056', 'comments': 'Good room',
            'text_valid': 'True', 'listing_match': 'True', 'date': '2026-01-01',
        }
        key = cache_key(self.row, self.config, 'fixture', self.prompt.read_text(), {})
        self.valid = {
            'snapshot_date': self.row['snapshot_date'],
            'review_id': self.row['review_id'], 'listing_id': self.row['listing_id'],
            'cache_key': key, 'model': 'fixture',
            'sentiment': 'positive', 'aspects': [], 'language': 'en',
            'status': 'ok', 'error': None, 'usage': {}, 'api_requests': 1,
        }
        self.marking = self.root / 'marking.csv'
        self.marking.write_text('SYNTHETIC fixture', encoding='utf-8')
        self.qa = self.root / 'qa.csv'
        with self.qa.open('w', newline='', encoding='utf-8') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(self.row))
            writer.writeheader()
            writer.writerow(self.row)
        self.marks = {self.row['review_id']: {
            'review_id': self.row['review_id'],
            'listing_id': self.row['listing_id'],
            'is_llm': True, 'is_manual_test': True,
        }}

    def _classify(self, entries):
        write_jsonl(self.cache, entries)
        before = self.cache.read_bytes()
        with patch.dict(os.environ, {}, clear=True), patch('src.llm.gemini_request') as network, contextlib.redirect_stdout(io.StringIO()):
            result = classify([self.row], self.config, str(self.root / 'run.jsonl'), skip_llm=True)
        network.assert_not_called()
        self.assertEqual(before, self.cache.read_bytes())
        self.assertEqual(len(read_jsonl(self.root / 'run.jsonl')), 1)
        return result[0]

    def _audit(self):
        with patch('src.cache_audit.read_marking', return_value=({}, self.marks, {}, None, 0)):
            return audit(self.qa, self.cache, self.marking, self.config, 'fixture', self.root / 'audit')

    def test_last_invalid_schema_does_not_shadow_previous_valid(self):
        result = self._classify([self.valid, {**self.valid, 'sentiment': 'unknown'}])
        self.assertEqual((result['status'], result['sentiment'], result['from_cache']), ('ok', 'positive', True))

    def test_last_missing_schema_field_does_not_shadow_previous_valid(self):
        invalid = {k: v for k, v in self.valid.items() if k != 'language'}
        result = self._classify([self.valid, invalid])
        self.assertEqual((result['status'], result['from_cache']), ('ok', True))

    def test_last_invalid_aspects_does_not_shadow_previous_valid(self):
        invalid = {**self.valid, 'aspects': [{'aspect': 'unknown', 'polarity': 'positive'}]}
        result = self._classify([self.valid, invalid])
        self.assertEqual((result['status'], result['from_cache']), ('ok', True))

    def test_latest_valid_wins_when_both_are_valid(self):
        result = self._classify([self.valid, {**self.valid, 'sentiment': 'negative'}])
        self.assertEqual((result['sentiment'], result['from_cache']), ('negative', True))

    def test_single_invalid_cache_preserves_old_schema_error_and_no_api_call(self):
        result = self._classify([{**self.valid, 'sentiment': 'unknown'}])
        self.assertEqual(result['status'], 'error')
        self.assertEqual(result['error'], 'schema: dòng ok cần sentiment hợp lệ và error=null')
        self.assertFalse(result['from_cache'])

    def test_all_invalid_duplicates_preserve_last_schema_error(self):
        first = {**self.valid, 'sentiment': 'unknown'}
        last = {**self.valid, 'language': 'INVALID'}
        result = self._classify([first, last])
        self.assertEqual(result['status'], 'error')
        self.assertEqual(result['error'], 'schema: language không hợp lệ')
        self.assertFalse(result['from_cache'])

    def test_valid_needs_review_is_still_reusable(self):
        review = {**self.valid, 'status': 'needs_review', 'sentiment': None,
                  'aspects': [], 'error': 'ambiguous source'}
        result = self._classify([review, {**review, 'sentiment': 'positive'}])
        self.assertEqual((result['status'], result['error'], result['from_cache']),
                         ('needs_review', 'ambiguous source', True))

    def test_cache_audit_agrees_with_runner_on_valid_fallback(self):
        result = self._classify([self.valid, {**self.valid, 'sentiment': 'unknown'}])
        summary = self._audit()
        self.assertTrue(result['from_cache'])
        self.assertEqual(summary['reused_selected_model'], 1)
        self.assertEqual(read_jsonl(self.root / 'audit' / 'llm_reused.jsonl')[0]['sentiment'], 'positive')

    def test_cache_audit_still_selects_latest_valid_for_model(self):
        newest = {**self.valid, 'sentiment': 'negative'}
        other_model = {**self.valid, 'model': 'different-model', 'sentiment': 'mixed'}
        write_jsonl(self.cache, [self.valid, newest, other_model])
        summary = self._audit()
        self.assertEqual(summary['reused_selected_model'], 1)
        self.assertEqual(read_jsonl(self.root / 'audit' / 'llm_reused.jsonl')[0]['sentiment'], 'negative')


if __name__ == '__main__':
    unittest.main()
