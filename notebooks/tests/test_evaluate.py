import pandas as pd
import pytest
from src.evaluate import sentiment_metrics, validate_labels, bootstrap
from src.baseline import predict


def test_known_metric(cfg):
    truth = ["positive", "negative", "mixed"]
    pred = ["positive", "positive", "mixed"]
    result = sentiment_metrics(truth, pred, cfg["evaluation"]["labels"])
    assert result["accuracy"] == pytest.approx(2 / 3)
    assert result["macro_f1"] == pytest.approx(5 / 9)
    assert (bootstrap(truth, pred, cfg)["accuracy"] == bootstrap(truth, pred, cfg)["accuracy"]).all()


def test_label_validation(cfg):
    gold = pd.DataFrame({"review_id": ["1", "2", "3"], "sentiment": ["positive", "mixed", "negative"]})
    assert len(validate_labels(gold, pd.DataFrame({"id": ["1", "2", "3"]}), cfg)) == 3
    with pytest.raises(ValueError):
        validate_labels(gold, pd.DataFrame({"id": ["1", "2"]}), cfg)
    with pytest.raises(ValueError):
        validate_labels(gold.iloc[:1], pd.DataFrame({"id": ["1", "2", "3"]}), cfg)
    gold["label_source"] = ["user_manual", "user_manual", "AI_draft"]
    with pytest.raises(ValueError, match="AI"):
        validate_labels(gold, pd.DataFrame({"id": ["1", "2", "3"]}), cfg)


def test_negation_and_mixed(cfg):
    lexicon = cfg["baseline"]["lexicons"]["en"]
    assert predict("not clean", "en", lexicon, cfg)["sentiment"] == "negative"
    assert predict("great location but dirty room", "en", lexicon, cfg)["sentiment"] == "mixed"
    assert predict("text", "und", None, cfg)["no_lexicon"]


def test_parse_error_invalidates_all_prediction_fields(clean_fixture):
    from src.download import save, path
    from src.evaluate import run
    cfg = clean_fixture
    save(cfg, pd.DataFrame({"id": ["a", "b", "c"], "comments": ["long review"] * 3}), "llm_sample")
    gold = pd.DataFrame({"review_id": ["a", "b", "c"], "sentiment": ["positive"] * 3,
                         "aspects_praise": ['["host"]'] * 3, "aspects_complaint": ['[]'] * 3, "language": ["en"] * 3})
    gold.to_csv(cfg["_root"] / cfg["inputs"]["hand_labels"], index=False)
    predictions = pd.DataFrame({"review_id": ["a", "b", "c"], "sentiment": ["positive"] * 3,
                                "aspects_praise": [["host"]] * 3, "aspects_complaint": [[]] * 3, "language": ["en"] * 3})
    save(cfg, predictions, "baseline_results")
    predictions["parse_error"] = [True, False, False]
    save(cfg, predictions, "llm_results")
    run(cfg)
    metrics = pd.read_csv(path(cfg, "reports", "eval_metrics.csv"))
    def value(task, metric):
        return metrics.loc[metrics.method.eq("llm") & metrics.task.eq(task) & metrics.metric.eq(metric), "value"].iloc[0]
    assert value("sentiment", "accuracy") == pytest.approx(2 / 3)
    assert value("coverage", "valid_prediction_rate") == pytest.approx(2 / 3)
    assert value("aspects_praise", "f1_micro") == pytest.approx(0.8)
    assert value("language", "accuracy") == pytest.approx(2 / 3)
    summary = path(cfg, "reports", "error_summary.md").read_text()
    assert "3 `positive`, 0 `mixed`, 0 `negative`" in summary
    assert "positive -> missing_or_error: 1" in summary
    assert "93 `positive`" not in summary
