"""Synthetic regression checks for incremental LLM output checkpoints.

No live requests, human annotations, or modified cache fixtures.
"""
import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, wraps

from src.common import read_jsonl
from src.llm import classify
from src.llm_contract import cache_key
import src.llm_runner as runner


class IncrementalCheckpointTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / 'prompt.txt').write_text('SYNTHETIC prompt', encoding='utf-8')
        (self.root / 'schema.json').write_text('{}', encoding='utf-8')
        self.config = {
            'model': 'fixture', 'prompt_version': 'fixture-v1',
            'prompt_file': str(self.root / 'prompt.txt'),
            'schema_file': str(self.root / 'schema.json'),
            'cache': str(self.root / 'cache.jsonl'),
            'temperature': 0, 'max_output_tokens': 1024,
            'max_retries': 0, 'timeout_seconds': 1,
            'request_interval_seconds': 0,
        }
        self.output = self.root / 'out.jsonl'
        self.valid = {'sentiment': 'positive', 'aspects': [], 'language': 'en',
                      'status': 'ok', 'error': None}

    def rows(self, count):
        return [{'snapshot_date': '2026-06-15', 'review_id': str(i),
                 'listing_id': '2', 'comments': 'Clean room ' + str(i),
                 'text_valid': 'true', 'listing_match': 'true'}
                for i in range(1, count + 1)]

    def provider(self, *_args):
        return {'text': json.dumps(self.valid), 'usage': {},
                'model_version': 'fixture', 'api_requests': 1}

    def classify(self, rows, skip_llm=False):
        env = {} if skip_llm else {'GEMINI_API_KEY': 'SYNTHETIC_KEY'}
        with patch.dict(os.environ, env, clear=True), \
             patch('src.llm.gemini_request', side_effect=self.provider) as network, \
             contextlib.redirect_stdout(io.StringIO()):
            records = classify(rows, self.config, str(self.output), skip_llm=skip_llm)
        return records, network.call_count

    def test_one_atomic_initial_checkpoint_not_full_rewrite_for_each_review(self):
        original = runner.write_jsonl
        with patch.object(runner, 'write_jsonl', wraps=original) as writer:
            records, requests = self.classify(self.rows(15))
        self.assertEqual(requests, 15)
        self.assertEqual(writer.call_count, 1)
        self.assertEqual(read_jsonl(self.output), records)
        self.assertEqual(len(read_jsonl(self.config['cache'])), 15)
        self.assertEqual(json.loads(Path(str(self.output) + '.run.json').read_text())['rows'], 15)

    def test_ctrl_c_after_third_completed_checkpoint_then_replays_cache(self):
        import builtins
        actual_print = builtins.print
        count = 0

        def interrupt_after_third(*args, **kwargs):
            nonlocal count
            count += 1
            if count == 3:
                raise KeyboardInterrupt('SYNTHETIC Ctrl+C after checkpoint')
            return actual_print(*args, **kwargs)

        rows = self.rows(5)
        with patch.dict(os.environ, {'GEMINI_API_KEY': 'SYNTHETIC_KEY'}, clear=True), \
             patch('src.llm.gemini_request', side_effect=self.provider), \
             patch('builtins.print', side_effect=interrupt_after_third), \
             contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(KeyboardInterrupt):
                classify(rows, self.config, str(self.output))
        self.assertEqual(len(read_jsonl(self.output)), 3)
        self.assertEqual(len(read_jsonl(self.config['cache'])), 3)
        self.assertFalse(Path(str(self.output) + '.run.json').exists())
        records, requests = self.classify(rows, skip_llm=True)
        self.assertEqual(requests, 0)
        self.assertEqual(len(read_jsonl(self.output)), 5)
        self.assertEqual(sum(r['from_cache'] for r in records), 3)
        self.assertEqual([r['error'] for r in records[3:]], ['cache_miss_skip_llm'] * 2)

    def test_write_error_during_second_checkpoint_rolls_back_partial_record(self):
        actual_fsync = runner.os.fsync
        times = 0
        def fail_once(fd):
            nonlocal times
            times += 1
            # Cache is now fsynced once per successful review. Fail during
            # the *second output checkpoint* (cache1, cache2, output2).
            if times == 3:
                raise OSError('SYNTHETIC disk synchronization error')
            return actual_fsync(fd)

        with patch.dict(os.environ, {'GEMINI_API_KEY': 'SYNTHETIC_KEY'}, clear=True), \
             patch('src.llm.gemini_request', side_effect=self.provider), \
             patch.object(runner.os, 'fsync', side_effect=fail_once), \
             contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(OSError):
                classify(self.rows(2), self.config, str(self.output))
        self.assertGreaterEqual(times, 4)
        self.assertEqual(len(read_jsonl(self.output)), 1)
        self.assertEqual(len(read_jsonl(self.config['cache'])), 2)
        records, _ = self.classify(self.rows(2), skip_llm=True)
        self.assertEqual(len(records), 2)
        self.assertTrue(all(r['from_cache'] for r in records))

    def test_simulated_torn_last_line_is_rebuilt_from_cache_on_next_run(self):
        rows = self.rows(4)
        self.classify(rows)
        cache_before = Path(self.config['cache']).read_bytes()
        self.output.write_bytes(self.output.read_bytes()[:-12])  # SYNTHETIC hard kill mid-record
        with self.assertRaisesRegex(ValueError, 'dòng 4'):
            read_jsonl(self.output)
        records, requests = self.classify(rows, skip_llm=True)
        self.assertEqual(requests, 0)
        self.assertEqual(len(read_jsonl(self.output)), 4)
        self.assertTrue(all(r['from_cache'] for r in records))
        self.assertEqual(Path(self.config['cache']).read_bytes(), cache_before)

    def test_existing_output_replaced_not_duplicated_on_new_run(self):
        rows = self.rows(4)
        self.classify(rows)
        original_cache = Path(self.config['cache']).read_bytes()
        self.output.write_text('{"old":"SYNTHETIC"}\n', encoding='utf-8')
        records, requests = self.classify(rows, skip_llm=True)
        self.assertEqual(requests, 0)
        self.assertEqual(read_jsonl(self.output), records)
        self.assertEqual(len(records), 4)
        self.assertEqual(Path(self.config['cache']).read_bytes(), original_cache)

    def test_skip_llm_error_and_cache_hit_contract(self):
        rows = self.rows(3)
        self.classify(rows[:2])
        cache_before = Path(self.config['cache']).read_bytes()
        records, requests = self.classify(rows, skip_llm=True)
        self.assertEqual(requests, 0)
        self.assertEqual([r['status'] for r in records], ['ok', 'ok', 'error'])
        self.assertEqual(records[2]['error'], 'cache_miss_skip_llm')
        self.assertEqual(Path(self.config['cache']).read_bytes(), cache_before)
        self.assertEqual(read_jsonl(self.output), records)

    def test_output_is_protected_from_being_same_as_cache(self):
        rows = self.rows(2)
        self.classify(rows[:1])
        previous_cache = Path(self.config['cache']).read_bytes()
        with self.assertRaisesRegex(ValueError, 'Output'):
            with patch.dict(os.environ, {}, clear=True):
                classify(rows, self.config, self.config['cache'], skip_llm=True)
        self.assertEqual(Path(self.config['cache']).read_bytes(), previous_cache)

    def test_thousand_records_not_thousand_full_file_rewrites(self):
        with patch.object(runner, 'write_jsonl', wraps=runner.write_jsonl) as writer, \
             patch.object(runner.os, 'fsync', wraps=runner.os.fsync) as sync:
            records, requests = self.classify(self.rows(1000), skip_llm=True)
        self.assertEqual(requests, 0)
        self.assertEqual(writer.call_count, 1)
        self.assertEqual(sync.call_count, 999)
        self.assertEqual(len(records), 1000)
        self.assertEqual(len(read_jsonl(self.output)), 1000)


if __name__ == '__main__':
    unittest.main()
