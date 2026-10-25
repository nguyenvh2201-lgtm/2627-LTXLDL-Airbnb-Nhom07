"""Offline regression tests for the single-file TV4 LLM runner.

No real API requests, no real annotations, and no real costs are produced here.
"""
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase, main
from unittest.mock import Mock, patch
import csv
import hashlib
import json

from src import llm


SNAPSHOT = '2026-06-15'


def csv_file(path, rows):
    with open(path, 'w', encoding='utf-8', newline='') as out:
        writer = csv.DictWriter(out, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def model_reply(label='positive', usage=None, *, text=None):
    item = {'sentiment': label, 'aspects': [], 'language': 'en', 'status': 'ok', 'error': None}
    return {
        'model': 'gpt-6-luna',
        'usage': usage if usage is not None else {'prompt_tokens': 7, 'completion_tokens': 4},
        'choices': [{'finish_reason': 'stop', 'message': {'content': text if text is not None else json.dumps(item)}}],
    }


class TV4Fixture(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        self.qa = self.work / 'reviews.csv'
        self.ids = self.work / 'ids.csv'
        self.config = self.work / 'config.json'
        self.output = self.work / 'output.jsonl'
        self.reports = self.work / 'reports'
        self.qa_rows = [
            {'snapshot_date': SNAPSHOT, 'review_id': '00010', 'listing_id': 'L1', 'comments': 'Great place', 'text_valid': 'true', 'listing_match': 'true'},
            {'snapshot_date': SNAPSHOT, 'review_id': '00020', 'listing_id': 'L2', 'comments': 'Bad and noisy', 'text_valid': 'true', 'listing_match': 'true'},
            {'snapshot_date': SNAPSHOT, 'review_id': '00030', 'listing_id': 'L3', 'comments': 'Clean room', 'text_valid': 'true', 'listing_match': 'true'},
        ]
        self.sample_rows = [
            {'review_id': '00010', 'listing_id': 'L1', 'split': 'dev'},
            {'review_id': '00020', 'listing_id': 'L2', 'split': 'dev'},
            {'review_id': '00030', 'listing_id': 'L3', 'split': 'test'},
        ]
        csv_file(self.qa, self.qa_rows)
        csv_file(self.ids, self.sample_rows)
        self.cfg = {
            'input': str(self.qa), 'sample_ids': str(self.ids), 'sample_size': 3,
            'snapshot_date': SNAPSHOT, 'seed': 42, 'provider': 'shopaikey',
            'model': 'gpt-6-luna', 'base_url': 'https://example.invalid/v1',
            'api_key_env': 'SYNTHETIC_TEST_KEY', 'prompt_version': 'tv4-simple-v1',
            'request_options': {'max_completion_tokens': 100},
            'timeout_seconds': 10, 'interval_seconds': 0,
            'output_dir': str(self.work), 'report_dir': str(self.reports),
            'input_vnd_per_million': 780, 'output_vnd_per_million': 2925,
            'price_source': 'synthetic, not a real price',
        }
        self.save_config()

    def save_config(self):
        self.config.write_text(json.dumps(self.cfg), encoding='utf-8')

    def invoke(self, action, *extra):
        with redirect_stdout(StringIO()):
            return llm.main([action, '--config', str(self.config), '--output', str(self.output), *extra])

    def read_output(self):
        with open(self.output, encoding='utf-8') as stream:
            return [json.loads(x) for x in stream if x.strip()]

    def test_cli_help_needs_no_api(self):
        with self.assertRaises(SystemExit) as err, redirect_stdout(StringIO()):
            llm.main(['--help'])
        self.assertEqual(err.exception.code, 0)

    def test_baseline_does_not_need_api(self):
        with patch.object(llm, 'request_review', side_effect=AssertionError('unexpected API')):
            self.assertEqual(self.invoke('baseline'), 0)
        self.assertEqual(list(self.reports.rglob('baseline.jsonl')) != [], True)

    def test_cache_only_missing_file_fails_before_api(self):
        with patch.object(llm, 'request_review', side_effect=AssertionError('unexpected API')):
            with self.assertRaises(FileNotFoundError):
                self.invoke('run', '--skip-llm')

    def test_resume_preserves_cached_results_and_ids(self):
        with patch.dict('os.environ', {'SYNTHETIC_TEST_KEY': 'not-a-real-key'}):
            with patch.object(llm, 'request_review', return_value=model_reply()) as api:
                with patch.object(llm.time, 'sleep'):
                    self.assertEqual(self.invoke('run', '--max-new-requests', '1'), 1)
                self.assertEqual(api.call_count, 1)
        saved = self.read_output()
        self.assertEqual([r['review_id'] for r in saved], ['00010', '00020', '00030'])
        self.assertEqual([r['status'] for r in saved], ['ok', 'error', 'error'])
        sha = hashlib.sha256(self.output.read_bytes()).digest()
        with patch.object(llm, 'request_review', side_effect=AssertionError('unexpected API')):
            self.assertEqual(self.invoke('run', '--skip-llm'), 1)
        self.assertEqual(hashlib.sha256(self.output.read_bytes()).digest(), sha)
        with patch.dict('os.environ', {'SYNTHETIC_TEST_KEY': 'not-a-real-key'}):
            with patch.object(llm, 'request_review', return_value=model_reply()) as api:
                with patch.object(llm.time, 'sleep'):
                    self.assertEqual(self.invoke('run', '--max-new-requests', '2'), 0)
                self.assertEqual(api.call_count, 2)
        self.assertEqual([r['status'] for r in self.read_output()], ['ok'] * 3)

    def test_model_change_rejects_cache_without_modification(self):
        with patch.dict('os.environ', {'SYNTHETIC_TEST_KEY': 'not-a-real-key'}):
            with patch.object(llm, 'request_review', return_value=model_reply()):
                with patch.object(llm.time, 'sleep'):
                    self.invoke('run', '--max-new-requests', '1')
        old = self.output.read_bytes()
        self.cfg['model'] = 'different-model'
        self.save_config()
        with patch.object(llm, 'request_review', side_effect=AssertionError('unexpected API')):
            with self.assertRaisesRegex(ValueError, 'khác model'):
                self.invoke('run', '--skip-llm')
        self.assertEqual(self.output.read_bytes(), old)

    def test_prompt_change_rejects_cache(self):
        with patch.dict('os.environ', {'SYNTHETIC_TEST_KEY': 'not-a-real-key'}):
            with patch.object(llm, 'request_review', return_value=model_reply()):
                with patch.object(llm.time, 'sleep'):
                    self.invoke('run', '--max-new-requests', '1')
        self.cfg['prompt_version'] = 'tv4-simple-v2'
        self.save_config()
        with self.assertRaises(ValueError):
            self.invoke('run', '--skip-llm')

    def test_unrelated_csv_column_does_not_invalidate_cache(self):
        with patch.dict('os.environ', {'SYNTHETIC_TEST_KEY': 'not-a-real-key'}):
            with patch.object(llm, 'request_review', return_value=model_reply()):
                with patch.object(llm.time, 'sleep'):
                    self.invoke('run', '--max-new-requests', '1')
        rows = [{**r, 'unused_note': 'hello'} for r in self.qa_rows]
        csv_file(self.qa, rows)
        self.assertEqual(self.invoke('run', '--skip-llm'), 1)

    def test_text_change_rejects_cache(self):
        with patch.dict('os.environ', {'SYNTHETIC_TEST_KEY': 'not-a-real-key'}):
            with patch.object(llm, 'request_review', return_value=model_reply()):
                with patch.object(llm.time, 'sleep'):
                    self.invoke('run', '--max-new-requests', '1')
        rows = [dict(x) for x in self.qa_rows]
        rows[0]['comments'] = 'changed'
        csv_file(self.qa, rows)
        with self.assertRaises(ValueError):
            self.invoke('run', '--skip-llm')

    def test_http_error_stops_and_preserves_checkpoint(self):
        import requests
        response = Mock(status_code=429)
        exc = requests.HTTPError('rate limit', response=response)
        with patch.dict('os.environ', {'SYNTHETIC_TEST_KEY': 'not-a-real-key'}):
            with patch.object(llm, 'request_review', side_effect=[model_reply(), exc]) as api:
                with patch.object(llm.time, 'sleep'):
                    self.assertEqual(self.invoke('run', '--max-new-requests', '3'), 1)
        self.assertEqual(api.call_count, 2)
        rows = self.read_output()
        self.assertEqual([r['status'] for r in rows], ['ok', 'error', 'error'])
        self.assertEqual(rows[1]['error'], 'http_429')
        self.assertEqual(rows[0]['usage'], {'prompt_tokens': 7, 'completion_tokens': 4})

    def test_failed_retry_does_not_keep_old_usage(self):
        import requests
        broken = {'model': 'gpt-6-luna', 'usage': {'prompt_tokens': 42, 'completion_tokens': 23},
                  'choices': [{'finish_reason': 'stop', 'message': {'content': '{bad json'}}]}
        with patch.dict('os.environ', {'SYNTHETIC_TEST_KEY': 'not-a-real-key'}):
            with patch.object(llm, 'request_review', return_value=broken):
                self.assertEqual(self.invoke('run', '--max-new-requests', '1'), 1)
            self.assertEqual(self.read_output()[0]['usage'], broken['usage'])
            with patch.object(llm, 'request_review', side_effect=requests.Timeout('offline')):
                self.assertEqual(self.invoke('run', '--max-new-requests', '1'), 1)
        self.assertEqual(self.read_output()[0]['usage'], {})
        self.assertIsNone(self.read_output()[0]['model_version'])

    def test_qa_flag_prevents_api(self):
        rows = [dict(x) for x in self.qa_rows]
        rows[0]['text_valid'] = 'false'
        csv_file(self.qa, rows)
        with patch.dict('os.environ', {'SYNTHETIC_TEST_KEY': 'not-a-real-key'}):
            with patch.object(llm, 'request_review', return_value=model_reply()) as api:
                with patch.object(llm.time, 'sleep'):
                    self.assertEqual(self.invoke('run', '--max-new-requests', '1'), 1)
        self.assertEqual(self.read_output()[0]['error'], 'input_failed_qa')
        self.assertEqual(api.call_count, 1)  # next eligible row still gets attempted

    def test_duplicate_review_id_in_sample_fails(self):
        csv_file(self.ids, [self.sample_rows[0], self.sample_rows[0]])
        with self.assertRaises(ValueError):
            self.invoke('baseline')

    def test_listing_id_mismatch_fails(self):
        selected = [dict(x) for x in self.sample_rows]
        selected[0]['listing_id'] = 'wrong'
        csv_file(self.ids, selected)
        with self.assertRaises(ValueError):
            self.invoke('baseline')

    def test_output_cannot_overwrite_input(self):
        with redirect_stdout(StringIO()):
            with self.assertRaisesRegex(ValueError, 'ghi đè'):
                llm.main(['run', '--config', str(self.config), '--output', str(self.qa), '--skip-llm'])

    def test_validator_rejects_invalid_aspects(self):
        with self.assertRaises(ValueError):
            llm.validate({'status': 'ok', 'sentiment': 'positive', 'aspects': [
                {'aspect': 'host', 'polarity': 'positive'}, {'aspect': 'host', 'polarity': 'negative'}],
                'language': 'en', 'error': None})
        with self.assertRaises(ValueError):
            llm.validate({'status': 'ok', 'sentiment': 'mixed', 'aspects': [], 'language': 'en', 'error': None})

    def test_neutral_contract(self):
        sample = {'status': 'ok', 'sentiment': 'neutral', 'aspects': [
            {'aspect': 'location', 'polarity': 'neutral'}], 'language': 'en', 'error': None}
        self.assertEqual(llm.validate(sample)['sentiment'], 'neutral')
        self.assertEqual(llm.baseline('Great but dirty'), 'neutral')

    def test_missing_prediction_counts_as_error_not_filtered_out(self):
        m = llm.metrics(['positive', 'negative', 'neutral'], ['positive', 'unclassified', 'unclassified'])
        self.assertEqual(m['n'], 3)
        self.assertAlmostEqual(m['coverage'], 1/3)
        self.assertAlmostEqual(m['accuracy'], 1/3)

    def test_cost_missing_usage_is_unknown(self):
        m = llm.cost([{'usage': {}}], self.cfg, city_reviews=1000)
        self.assertIsNone(m['estimated_vnd_for_reported_usage'])
        self.assertIsNone(m['estimated_city_vnd'])

    def test_validate_missing_test_labels_rejected(self):
        labels = self.work / 'labels.csv'
        csv_file(labels, [{'snapshot_date': SNAPSHOT, 'review_id': '00030', 'manual_sentiment': 'positive', 'split': 'test'}])
        with self.assertRaisesRegex(ValueError, '100 nhãn'):
            llm.evaluate(llm.reviews(self.cfg), [], str(labels), self.reports)


if __name__ == '__main__':
    main()
