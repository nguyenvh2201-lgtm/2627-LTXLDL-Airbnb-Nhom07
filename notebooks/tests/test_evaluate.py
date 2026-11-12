import pandas as pd
import pytest
from src.evaluate import sentiment_metrics, validate_labels, bootstrap
from src.baseline import predict
import json


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
