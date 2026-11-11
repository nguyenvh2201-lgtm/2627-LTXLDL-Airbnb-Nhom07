import json
import os
from unittest.mock import Mock
import pytest
import pandas as pd
from src import llm
from src.download import read, path


def result(review_id):
    return {"review_id": review_id, "sentiment": "positive", "aspects_praise": ["cleanliness"], "aspects_complaint": [], "language": "en"}


def test_validation(cfg):
    assert llm.validate_results([result("1")], ["1"], cfg["llm"]["aspects"])
    for bad in ([], [result("2")], [{**result("1"), "language": "english"}], [{**result("1"), "aspects_praise": ["invented"]}], [{**result("1"), "extra": 1}]):
        with pytest.raises(ValueError):
            llm.validate_results(bad, ["1"], cfg["llm"]["aspects"])


def test_retry(cfg, monkeypatch):
    bad = Mock(status_code=429, headers={"Retry-After": "0"})
    good = Mock(status_code=200)
    good.json.return_value = {"candidates": [{"content": {"parts": [{"text": json.dumps([result("1")])}]}}]}
    post = Mock(side_effect=[bad, good])
    monkeypatch.setattr(llm.requests, "post", post)
    monkeypatch.setattr(llm.time, "sleep", lambda _: None)
    assert llm.GeminiClient(cfg, "test-key").generate([{"review_id": "1"}], "prompt")[0]["review_id"] == "1"
    assert post.call_count == 2
    assert post.call_args.kwargs["headers"]["x-goog-api-key"] == "test-key"


def test_cache_and_env(clean_fixture, monkeypatch):
    cfg = clean_fixture
    cfg["_options"]["skip_llm"] = False
    cfg["llm"]["api_key_env"] = "TEST_ARBITRARY_KEY"
    monkeypatch.setenv("TEST_ARBITRARY_KEY", "test-value")
    calls = []
    def generate(self, batch, prompt):
        assert self.key == "test-value"
        calls.append(batch)
        return [result(r["review_id"]) for r in batch]
    monkeypatch.setattr(llm.GeminiClient, "generate", generate)
    llm.run(cfg)
    assert len(calls) == 2
    llm.run(cfg)
    assert len(calls) == 2
    assert read(cfg, "llm_results").sentiment.eq("positive").all()
    cfg["llm"]["prompt_version"] = "changed"
    llm.run(cfg)
    assert len(calls) == 4


@pytest.mark.parametrize("skip", [True, False])
def test_skip_and_missing_key(clean_fixture, monkeypatch, skip):
    cfg = clean_fixture
    cfg["_options"]["skip_llm"] = skip
    monkeypatch.delenv(cfg["llm"]["api_key_env"], raising=False)
    monkeypatch.setattr(llm.requests, "post", Mock(side_effect=AssertionError("network forbidden")))
    llm.run(cfg)
    assert read(cfg, "llm_results").sentiment.isna().all()


def test_bad_json_becomes_parse_error(clean_fixture, monkeypatch):
    cfg = clean_fixture
    cfg["_options"]["skip_llm"] = False
    monkeypatch.setenv(cfg["llm"]["api_key_env"], "test-value")
    response = Mock(status_code=200)
    response.json.return_value = {"candidates": [{"content": {"parts": [{"text": "not-json"}]}}]}
    monkeypatch.setattr(llm.requests, "post", Mock(return_value=response))
    monkeypatch.setattr(llm.time, "sleep", lambda _: None)
    llm.run(cfg)
    assert read(cfg, "llm_results").parse_error.all()
