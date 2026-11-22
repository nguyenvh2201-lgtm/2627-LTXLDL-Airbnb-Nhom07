import json
from unittest.mock import Mock
import pytest
from src import llm
from src.download import read


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


def test_api_retries_stop_after_limit(clean_fixture, monkeypatch):
    cfg = clean_fixture
    cfg["llm"].update({"retries": 2, "batch_size": 3})
    cfg["_options"]["skip_llm"] = False
    monkeypatch.setenv(cfg["llm"]["api_key_env"], "test-key")
    monkeypatch.setattr(llm.time, "sleep", lambda _: None)
    for failure in (Mock(status_code=429, headers={"Retry-After": "0"}), llm.requests.Timeout("mock timeout")):
        post = Mock(side_effect=failure) if isinstance(failure, Exception) else Mock(return_value=failure)
        monkeypatch.setattr(llm.requests, "post", post)
        with pytest.raises(ConnectionError):
            llm.run(cfg)
        assert post.call_count == 2


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
    cfg["llm"]["model"] = "a-different-model"
    llm.run(cfg)
    assert len(calls) == 6
    assert read(cfg, "llm_results").model.eq("a-different-model").all()


def test_limit_writes_separate_artifacts(clean_fixture, monkeypatch):
    cfg = clean_fixture
    cfg["_options"]["skip_llm"] = False
    monkeypatch.setenv(cfg["llm"]["api_key_env"], "test-value")
    monkeypatch.setattr(
        llm.GeminiClient,
        "generate",
        lambda self, batch, prompt: [result(r["review_id"]) for r in batch],
    )
    llm.run(cfg)
    canonical = read(cfg, "llm_results")
    cfg["_options"]["limit"] = 2
    llm.run(cfg)
    assert len(read(cfg, "llm_results")) == len(canonical) == 3
    assert len(read(cfg, "llm_results_limit_2")) == 2
    assert len(read(cfg, "llm_sample_limit_2")) == 2
    assert (cfg["_root"] / cfg["paths"]["reports"] / "llm_cost_estimate_limit_2.csv").exists()


def test_skip_and_missing_key(clean_fixture, monkeypatch):
    cfg = clean_fixture
    monkeypatch.setattr(llm.requests, "post", Mock(side_effect=AssertionError("network forbidden")))
    for skip in (True, False):
        cfg["_options"]["skip_llm"] = skip
        if skip:
            monkeypatch.setenv(cfg["llm"]["api_key_env"], "test-key")
        else:
            monkeypatch.delenv(cfg["llm"]["api_key_env"], raising=False)
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
    with pytest.raises(ValueError, match="không trả dự đoán hợp lệ nào"):
        llm.run(cfg)
    assert read(cfg, "llm_results").parse_error.all()
