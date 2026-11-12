"""Đối chứng từ khóa đa ngôn ngữ, không dùng nhãn tay để dự đoán."""
import json
import logging
import re
import pandas as pd
from langdetect import detect, DetectorFactory, LangDetectException
from .download import path, read, save, csv_report, cli


def detect_language(text: str, cfg: dict) -> str:
    """Seed cố định, câu quá ngắn được đánh dấu không xác định."""
    DetectorFactory.seed = cfg["seed"]
    if len(text.strip()) < cfg["baseline"]["language_min_chars"]:
        return "und"
    try:
        language = detect(text)
        return language.split("-")[0]
    except LangDetectException:
        return "und"


def predict(text: str, language: str, lexicon: dict | None, cfg: dict) -> dict:
    """Phủ định trong cửa sổ trái; khía cạnh dùng cảm xúc gần trong ±window."""
    base = {"language": language, "aspects_praise": [], "aspects_complaint": [], "no_lexicon": lexicon is None}
    if lexicon is None:
        return {**base, "sentiment": cfg["baseline"]["fallback_sentiment"]}
    tokens = re.findall(r"[^\W\d_]+", text.lower(), flags=re.UNICODE)
    scores = []
    for index, token in enumerate(tokens):
        score = int(token in lexicon["positive"]) - int(token in lexicon["negative"])
        if any(t in lexicon["negations"] for t in tokens[max(0, index - cfg["baseline"]["negation_window"]):index]):
            score *= -1
        scores.append(score)
    positive, negative = sum(s > 0 for s in scores), sum(s < 0 for s in scores)
    contrast = any(t in lexicon["contrast"] for t in tokens)
    if positive and negative and (contrast or abs(positive - negative) <= cfg["baseline"]["mixed_max_difference"]):
        sentiment = "mixed"
    elif positive or negative:
        sentiment = "positive" if positive >= negative else "negative"
    else:
        sentiment = cfg["baseline"]["fallback_sentiment"]
    window = cfg["baseline"]["aspect_window"]
    for aspect in cfg["llm"]["aspects"]:
        indices = [i for i, t in enumerate(tokens) if t in lexicon["aspects"].get(aspect, [])]
        nearby = [score for i in indices for score in scores[max(0, i - window):i + window + 1]]
        if any(s > 0 for s in nearby):
            base["aspects_praise"].append(aspect)
        if any(s < 0 for s in nearby):
            base["aspects_complaint"].append(aspect)
    return {**base, "sentiment": sentiment}


def run(cfg: dict) -> None:
    """Cùng sample LLM, báo độ phủ ngôn ngữ chưa có từ điển."""
    from .llm import select_sample
    sample = select_sample(cfg)
    lexicons = cfg["baseline"]["lexicons"]
    results = []
    for row in sample.itertuples():
        language = detect_language(row.comments, cfg)
        results.append({"review_id": row.id, **predict(row.comments, language, lexicons.get(language), cfg), "method": "lexicon"})
    frame = pd.DataFrame(results, columns=["review_id", "sentiment", "aspects_praise", "aspects_complaint", "language", "no_lexicon", "method"])
    save(cfg, frame, "baseline_results")
    coverage = frame.groupby("language").agg(n=("review_id", "size"), no_lexicon=("no_lexicon", "all")).reset_index()
    coverage["share"] = coverage.n / len(frame) if len(frame) else 0
    csv_report(cfg, coverage, "baseline_language_coverage.csv")
    missing = coverage.loc[coverage.no_lexicon & coverage.share.ge(cfg["baseline"]["language_share_min"])]
    if len(missing):
        logging.warning("Ngôn ngữ >= ngưỡng chưa có từ điển: %s", missing.language.tolist())


if __name__ == "__main__":
    cli(run)
