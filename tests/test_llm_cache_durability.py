"""P5 regression: protect Gemini cache from interrupted writes (synthetic, offline)."""
import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import src.llm_runner as runner
from src.llm import classify
from src.common import read_jsonl


class _FailingAppend:
    """Simulate an interrupted append after the first half reached the file."""
    def __init__(self, stream, kind):
        self.stream = stream
        self.kind = kind

    def __enter__(self):
        self.stream.__enter__()
        return self

    def __exit__(self, *args):
        return self.stream.__exit__(*args)

    def __getattr__(self, name):
        return getattr(self.stream, name)

    def write(self, data):
        self.stream.write(data[:max(1, len(data) // 2)])
        self.stream.flush()
        if self.kind == 'interrupt':
            raise KeyboardInterrupt('SYNTHETIC interruption while writing cache')
        raise OSError('SYNTHETIC partial cache append')


class CacheDurabilityTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        prompt = self.root / 'prompt.txt'
        schema = self.root / 'schema.json'
        prompt.write_text('SYNTHETIC prompt', encoding='utf-8')
        schema.write_text('{}', encoding='utf-8')
        self.config = {
            'model': 'fixture', 'prompt_version': 'fixture-v1',
            'prompt_file': str(prompt), 'schema_file': str(schema),
            'cache': str(self.root / 'cache.jsonl'),
            'temperature': 0, 'max_output_tokens': 1024,
            'max_retries': 0, 'timeout_seconds': 1,
            'request_interval_seconds': 0,
        }
        self.cache = Path(self.config['cache'])
        self.out = self.root / 'output.jsonl'

    def rows(self, n):
        return [dict(snapshot_date='2026-06-15', review_id=str(i),
                     listing_id='42', comments=f'SYNTHETIC clean room {i}',
                     text_valid='true', listing_match='true')
                for i in range(1, n + 1)]

    @staticmethod
    def provider(*_args):
        return dict(text=json.dumps(dict(sentiment='positive', aspects=[],
                                         language='en', status='ok', error=None)),
                    usage={}, model_version='fixture', api_requests=1)

    def run_batch(self, rows, skip_llm=False):
        env = {} if skip_llm else {'GEMINI_API_KEY': 'SYNTHETIC_KEY'}
        with patch.dict(os.environ, env, clear=True), \
             patch('src.llm.gemini_request', side_effect=self.provider) as network, \
             contextlib.redirect_stdout(io.StringIO()):
            result = classify(rows, self.config, str(self.out), skip_llm=skip_llm)
        return result, network.call_count

    def inject_partial_cache_write(self, rows, kind):
        actual_open = Path.open
        def patched_open(path, mode='r', *args, **kwargs):
            stream = actual_open(path, mode, *args, **kwargs)
            if path == self.cache and mode in ('a', 'ab'):
                return _FailingAppend(stream, kind)
            return stream
        with patch.dict(os.environ, {'GEMINI_API_KEY': 'SYNTHETIC_KEY'}, clear=True), \
             patch('src.llm.gemini_request', side_effect=self.provider), \
             patch.object(Path, 'open', patched_open), \
             contextlib.redirect_stdout(io.StringIO()):
            classify(rows, self.config, str(self.out))

    def test_partial_cache_write_rolls_back_and_can_be_reused(self):
        self.run_batch(self.rows(1))
        saved = self.cache.read_bytes()
        with self.assertRaisesRegex(OSError, 'SYNTHETIC partial cache'):
            self.inject_partial_cache_write(self.rows(2), 'oserror')
        self.assertEqual(self.cache.read_bytes(), saved)
        result, calls = self.run_batch(self.rows(2), skip_llm=True)
        self.assertEqual(calls, 0)
        self.assertEqual([r['status'] for r in result], ['ok', 'error'])
        self.assertEqual(result[1]['error'], 'cache_miss_skip_llm')

    def test_ctrl_c_during_cache_append_preserves_earlier_entries(self):
        self.run_batch(self.rows(1))
        saved = self.cache.read_bytes()
        with self.assertRaises(KeyboardInterrupt):
            self.inject_partial_cache_write(self.rows(2), 'interrupt')
        self.assertEqual(self.cache.read_bytes(), saved)
        self.assertEqual(len(read_jsonl(self.cache)), 1)

    def test_cache_is_synced_for_each_successful_new_prediction(self):
        actual_fsync = runner.os.fsync
        with patch.object(runner.os, 'fsync', wraps=actual_fsync) as sync:
            result, calls = self.run_batch(self.rows(3))
        self.assertEqual(calls, 3)
        self.assertEqual(len(read_jsonl(self.cache)), 3)
        self.assertEqual([r['status'] for r in result], ['ok'] * 3)
        # 3 committed cache rows + 2 output append checkpoints.
        self.assertEqual(sync.call_count, 5)

    def test_cache_fsync_error_rolls_back_new_record(self):
        self.run_batch(self.rows(1))
        saved = self.cache.read_bytes()
        fsync_real = runner.os.fsync
        attempts = 0
        def interrupted_sync(fd):
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise OSError('SYNTHETIC cache fsync failure')
            return fsync_real(fd)
        with patch.object(runner.os, 'fsync', side_effect=interrupted_sync):
            with self.assertRaisesRegex(OSError, 'SYNTHETIC cache fsync'):
                self.run_batch(self.rows(2))
        self.assertGreaterEqual(attempts, 2)  # rollback itself is synced
        self.assertEqual(self.cache.read_bytes(), saved)
        self.assertEqual(len(read_jsonl(self.cache)), 1)
        with patch.dict(os.environ, {}, clear=True):
            reused, calls = self.run_batch(self.rows(2), skip_llm=True)
        self.assertEqual(calls, 0)
        self.assertEqual([r['status'] for r in reused], ['ok', 'error'])

    def test_cache_unchanged_in_skip_llm_replay(self):
        self.run_batch(self.rows(2))
        saved = self.cache.read_bytes()
        with patch.object(runner.os, 'fsync', wraps=runner.os.fsync) as sync:
            result, calls = self.run_batch(self.rows(3), skip_llm=True)
        self.assertEqual(calls, 0)
        self.assertEqual([r['status'] for r in result], ['ok', 'ok', 'error'])
        self.assertEqual(self.cache.read_bytes(), saved)
        # Only output checkpoints synced, never cache reads.
        self.assertEqual(sync.call_count, 2)


if __name__ == '__main__':
    unittest.main()
