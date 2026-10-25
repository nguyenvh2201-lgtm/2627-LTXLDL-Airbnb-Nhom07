"""Regression tests for the four handoff fixes and command routing.

All inputs/responses/credentials are synthetic. No live API is called.
"""
import contextlib
import csv
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

from src import common, cache_audit, llm_runner as runner
from src.llm_contract import cache_key


class HandoffFixTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.prompt = self.root / 'prompt.txt'
        self.schema = self.root / 'schema.json'
        self.prompt.write_text('SYNTHETIC handoff regression', encoding='utf-8')
        self.schema.write_text('{}', encoding='utf-8')
        self.config = dict(snapshot_date='2026-06-15', snapshots=['2026-06-15'], model='fixture',
                           prompt_version='fixture-v1', prompt_file=str(self.prompt),
                           schema_file=str(self.schema), cache=str(self.root / 'cache.jsonl'),
                           temperature=0, max_output_tokens=128, max_retries=0,
                           timeout_seconds=1, request_interval_seconds=0)
        self.rows = [dict(snapshot_date='2026-06-15', review_id=str(i), listing_id='100',
                          date='2026-06-01', comments=f'SYNTHETIC clean room {i}',
                          split=split, text_valid='true', listing_match='true')
                     for i, split in enumerate(('dev', 'test', 'analysis'), start=1)]
        self.qa = self.root / 'qa.csv'
        self.marking = self.root / 'marking.csv'
        self.cache = Path(self.config['cache'])
        self.output = self.root / 'output.jsonl'
        self.report = Path(str(self.output) + '.run.json')
        self.audit_dir = self.root / 'audit'
        self._write_qa()
        self._write_marking()
        environment = patch.dict(os.environ, {'GEMINI_API_KEY': 'SYNTHETIC_KEY', 'GEMINI_MODEL': 'fixture'})
        environment.start()
        self.addCleanup(environment.stop)
        guard = patch('urllib.request.urlopen', side_effect=AssertionError('Live API forbidden'))
        guard.start()
        self.addCleanup(guard.stop)
        quiet = contextlib.redirect_stdout(io.StringIO())
        quiet.__enter__()
        self.addCleanup(quiet.__exit__, None, None, None)

    def _write_qa(self):
        common.write_csv(self.qa, self.rows, list(self.rows[0]))

    def _write_marking(self, dev_is_test=False):
        header = ['Lớp', 'Nhóm', 'Mã dữ liệu', 'listing_id', 'analysis_area', 'review_id',
                  'listing_id', 'Mẫu LLM', 'Nhãn tay', 'Thành phố', 'analysis_area',
                  'lon_min', 'lat_min', 'lon_max', 'lat_max']
        with self.marking.open('w', encoding='utf-8', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow(header)
            for index, row in enumerate(self.rows):
                first = index == 0
                writer.writerow(['fixture' if first else '', '7' if first else '',
                                 'fixture-code' if first else '', '100' if first else '',
                                 'A' if first else '', row['review_id'], '100', 'x',
                                 'x' if index == 1 or (first and dev_is_test) else '',
                                 'Toronto' if first else '', 'A' if first else '',
                                 '-80' if first else '', '43' if first else '',
                                 '-79' if first else '', '44' if first else ''])

    @staticmethod
    def provider(*_args):
        return dict(text=json.dumps(dict(sentiment='positive', aspects=[], language='en', status='ok', error=None)),
                    usage={}, model_version='fixture', api_requests=1)

    def record(self, row):
        return {**row, 'sentiment': 'positive', 'aspects': [], 'language': 'en',
                'status': 'ok', 'error': None, 'usage': {}, 'api_requests': 1,
                'model': 'fixture', 'from_cache': False,
                'cache_key': cache_key(row, self.config, 'fixture', self.prompt.read_text(), {}),
                'text_sha256': common.digest(common.normalize_text(row['comments']))}

    def run_batch(self, rows=None, **kwargs):
        return runner.classify(self.rows if rows is None else rows, self.config, self.output,
                               request_fn=kwargs.pop('request_fn', self.provider), **kwargs)

    def audit(self):
        return cache_audit.audit(self.qa, self.cache, self.marking, self.config, 'fixture', self.audit_dir)

    def cli(self, *arguments):
        project = self.root / 'project'
        if not project.exists():
            project.mkdir()
            source = Path(runner.__file__).resolve().parent
            shutil.copytree(source, project / 'src', ignore=shutil.ignore_patterns('__pycache__'))
            shutil.copy2(source.parent / 'run_tv4.py', project / 'run_tv4.py')
        config_path = self.root / 'config.json'
        config_path.write_text(json.dumps(self.config), encoding='utf-8')
        env = os.environ.copy()
        env.pop('GEMINI_API_KEY', None)
        env.pop('GEMINI_MODEL', None)
        return subprocess.run([sys.executable, 'run_tv4.py', *arguments], cwd=project,
                              env=env, capture_output=True, text=True, timeout=10)

    def test_append_handles_no_newline_lf_crlf_and_bom(self):
        raw = json.dumps(self.record(self.rows[0])).encode('utf-8')
        for initial in (raw, raw + b'\n', raw + b'\r\n', b'\xef\xbb\xbf' + raw):
            with self.subTest(initial=initial[-4:]):
                self.cache.write_bytes(initial)
                records = self.run_batch(self.rows[:2])
                saved = common.read_jsonl(self.cache)
                self.assertEqual(len(saved), 2)
                self.assertTrue(records[0]['from_cache'])
                self.assertEqual(saved[0]['cache_key'], self.record(self.rows[0])['cache_key'])
                self.assertTrue(self.cache.read_bytes().startswith(initial))

    def test_skip_does_not_add_a_newline_to_cache(self):
        initial = json.dumps(self.record(self.rows[0])).encode('utf-8')
        self.cache.write_bytes(initial)
        request = Mock(side_effect=AssertionError('No API'))
        records = self.run_batch(self.rows[:1], skip_llm=True, request_fn=request)
        self.assertTrue(records[0]['from_cache'])
        request.assert_not_called()
        self.assertEqual(self.cache.read_bytes(), initial)

    def test_failed_append_rolls_back_the_added_separator_too(self):
        initial = json.dumps(self.record(self.rows[0])).encode('utf-8')
        self.cache.write_bytes(initial)
        original_sync = runner.os.fsync
        calls = 0
        def fail_once(fd):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise OSError('SYNTHETIC fsync failure')
            return original_sync(fd)
        with patch.object(runner.os, 'fsync', side_effect=fail_once):
            with self.assertRaises(OSError):
                self.run_batch(self.rows[:2])
        self.assertEqual(self.cache.read_bytes(), initial)
        self.assertEqual(len(common.read_jsonl(self.cache)), 1)
        self.assertGreaterEqual(calls, 2)

    def test_interruption_removes_previous_report(self):
        self.report.write_text('{"rows":999,"started_at":"old"}')
        request = Mock(side_effect=[self.provider(), KeyboardInterrupt('SYNTHETIC interruption')])
        with self.assertRaises(KeyboardInterrupt):
            self.run_batch(request_fn=request)
        self.assertEqual(len(common.read_jsonl(self.output)), 1)
        self.assertFalse(self.report.exists())

    def test_interruption_before_first_result_does_not_claim_completion(self):
        common.write_jsonl(self.output, [{'old_output': True}])
        previous = self.output.read_bytes()
        self.report.write_text('{"rows":999}')
        with self.assertRaises(KeyboardInterrupt):
            self.run_batch(request_fn=Mock(side_effect=KeyboardInterrupt()))
        self.assertEqual(self.output.read_bytes(), previous)
        self.assertFalse(self.report.exists())

    def test_preflight_failure_preserves_previous_output_and_report(self):
        common.write_jsonl(self.output, [{'old_output': True}])
        self.report.write_text('{"rows":999}')
        before = self.output.read_bytes(), self.report.read_bytes()
        bad = {k: value for k, value in self.rows[0].items() if k != 'comments'}
        request = Mock(side_effect=AssertionError('No API'))
        with self.assertRaises(ValueError):
            self.run_batch([bad], request_fn=request)
        with patch.dict(os.environ, {'GEMINI_API_KEY': ''}):
            with self.assertRaises(RuntimeError):
                self.run_batch(request_fn=request)
        self.assertEqual((self.output.read_bytes(), self.report.read_bytes()), before)
        request.assert_not_called()

    def test_success_replaces_previous_report(self):
        self.report.write_text('{"rows":999,"started_at":"old"}')
        self.run_batch(self.rows[:1])
        report = json.loads(self.report.read_text())
        self.assertEqual(report['rows'], 1)
        self.assertNotEqual(report['started_at'], 'old')

    def test_each_missing_required_column_is_reported_before_api(self):
        request = Mock(side_effect=AssertionError('No API'))
        for field in ('snapshot_date', 'review_id', 'listing_id', 'comments'):
            with self.subTest(field=field):
                row = {key: value for key, value in self.rows[0].items() if key != field}
                with self.assertRaisesRegex(ValueError, field):
                    self.run_batch([row], request_fn=request)
        request.assert_not_called()
        self.assertFalse(self.cache.exists())
        self.assertFalse(self.output.exists())

    def test_missing_comments_in_later_row_does_not_start_partial_batch(self):
        rows = [dict(row) for row in self.rows]
        del rows[1]['comments']
        request = Mock(side_effect=AssertionError('No API'))
        with self.assertRaisesRegex(ValueError, 'Review thứ 2.*comments'):
            self.run_batch(rows, request_fn=request)
        request.assert_not_called()
        self.assertFalse(self.output.exists())

    def test_empty_comments_still_produces_original_qa_error(self):
        row = {**self.rows[0], 'comments': ''}
        result = self.run_batch([row], skip_llm=True)
        self.assertEqual((result[0]['status'], result[0]['error']), ('error', 'input_empty_or_invalid_text'))

    def test_cli_missing_comments_gives_exit_2_without_traceback(self):
        bad = [{k: value for k, value in self.rows[0].items() if k != 'comments'}]
        common.write_csv(self.qa, bad, list(bad[0]))
        result = self.cli('llm', '--config', str(self.root / 'config.json'), '--input', str(self.qa), '--skip-llm')
        self.assertEqual(result.returncode, 2)
        self.assertIn('comments', result.stderr)
        self.assertNotIn('Traceback', result.stderr)

    def test_show_request_missing_comments_gives_exit_2(self):
        bad = [{k: value for k, value in self.rows[0].items() if k != 'comments'}]
        common.write_csv(self.qa, bad, list(bad[0]))
        result = self.cli('llm', '--config', str(self.root / 'config.json'), '--input', str(self.qa), '--show-request')
        self.assertEqual(result.returncode, 2)
        self.assertIn('comments', result.stderr)
        self.assertNotIn('Traceback', result.stderr)

    def test_audit_keeps_dev_in_ready_reused_and_complete_outputs(self):
        common.write_jsonl(self.cache, [self.record(row) for row in self.rows])
        previous = self.cache.read_bytes()
        self.audit()
        for name in ('reviews_llm_after_qa.csv', 'llm_reused.jsonl', 'llm_reconciled_all_samples.jsonl'):
            data = common.read_csv(self.audit_dir / name) if name.endswith('.csv') else common.read_jsonl(self.audit_dir / name)
            self.assertEqual(next(row for row in data if row['review_id'] == '1')['split'], 'dev')
        template = common.read_csv(self.audit_dir / 'manual_test_100.csv')
        self.assertEqual([row['review_id'] for row in template], ['2'])
        self.assertEqual(self.cache.read_bytes(), previous)

    def test_audit_rejects_dev_marked_as_test_before_writing_outputs(self):
        self._write_marking(dev_is_test=True)
        with self.assertRaisesRegex(ValueError, 'split=dev.*test'):
            self.audit()
        self.assertFalse(self.audit_dir.exists())

    def test_audit_keeps_dev_identity_even_when_qa_rejects_review(self):
        self.rows[0]['text_valid'] = 'false'
        self._write_qa()
        self.audit()
        complete = common.read_jsonl(self.audit_dir / 'llm_reconciled_all_samples.jsonl')
        self.assertEqual((complete[0]['split'], complete[0]['status']), ('dev', 'error'))

    def test_audit_without_source_split_preserves_marking_selection(self):
        for row in self.rows:
            row.pop('split')
        self._write_qa()
        self.audit()
        ready = common.read_csv(self.audit_dir / 'reviews_llm_after_qa.csv')
        self.assertEqual([row['split'] for row in ready], ['analysis', 'test', 'analysis'])

    def test_router_evaluate_runs_actual_metrics(self):
        labels = [{**row, 'manual_sentiment': gold, 'needs_review': 'false', 'note': 'SYNTHETIC', 'split': 'test'}
                  for row, gold in zip(self.rows, ('positive', 'negative', 'mixed'))]
        gold_path = self.root / 'gold.csv'
        common.write_csv(gold_path, labels, list(labels[0]))
        common.write_jsonl(self.output, [self.record(row) for row in self.rows])
        result = self.cli('evaluate', '--labels', str(gold_path), '--predictions', str(self.output), '--allow-partial')
        self.assertEqual(result.returncode, 0, result.stderr)
        metrics = json.loads(result.stdout)[0]
        self.assertEqual(metrics['valid_gold'], 3)
        self.assertAlmostEqual(metrics['accuracy'], 1 / 3)
        self.assertTrue((self.root / 'project/reports/llm_test_checks.csv').exists())

    def test_router_cache_audit_runs_actual_audit(self):
        result = self.cli('cache_audit', '--qa-reviews', str(self.qa), '--cache', str(self.cache),
                          '--marking', str(self.marking), '--config', str(self.root / 'config.json'),
                          '--model', 'fixture', '--output-dir', str(self.audit_dir))
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual((report['marked_llm_samples'], report['api_requests']), (3, 0))
        ready = common.read_csv(self.audit_dir / 'reviews_llm_after_qa.csv')
        self.assertEqual(ready[0]['split'], 'dev')

    def test_router_help_and_unknown_command(self):
        for name in ('llm', 'evaluate', 'cache_audit'):
            result = self.cli(name, '--help')
            self.assertEqual(result.returncode, 0, result.stderr)
        result = self.cli('unknown-command')
        self.assertEqual(result.returncode, 2)
        self.assertIn('cache_audit', result.stdout)


if __name__ == '__main__':
    unittest.main(verbosity=2)
