"""Đánh giá trên nhãn NGƯỜI điền; không bỏ lỗi để làm đẹp accuracy/F1."""
from __future__ import annotations

import argparse
import json

from .common import (LABELS, key, manual_labels, now, path, read_jsonl, require_unique,
                     truth, write_csv, write_json)


def scores(gold, predicted):
    if not gold or len(gold) != len(predicted):
        raise ValueError("Không có nhãn tay hợp lệ để tính metric.")
    per_class = []
    for label in LABELS:
        tp = sum(a == b == label for a, b in zip(gold, predicted))
        fp = sum(a != label and b == label for a, b in zip(gold, predicted))
        fn = sum(a == label and b != label for a, b in zip(gold, predicted))
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class.append({"label": label, "support": gold.count(label),
                          "precision": precision, "recall": recall, "f1": f1})
    return {"accuracy": sum(a == b for a, b in zip(gold, predicted)) / len(gold),
            "macro_f1": sum(r["f1"] for r in per_class) / len(LABELS),
            "weighted_f1": sum(r["f1"] * r["support"] for r in per_class) / len(gold),
            "macro_precision": sum(r["precision"] for r in per_class) / len(LABELS),
            "macro_recall": sum(r["recall"] for r in per_class) / len(LABELS),
            "per_class": per_class}


def evaluate(labels, predictions, name):
    require_unique(predictions)
    prediction_map = {key(r): r for r in predictions}
    gold, predicted, checks = [], [], []
    confusion = {label: {other: 0 for other in (*LABELS, "unavailable")} for label in LABELS}
    for label_row in labels:
        record = prediction_map.get(key(label_row))
        pred = record.get("sentiment") if record and record.get("status") == "ok" else None
        if pred not in LABELS:
            pred = None
        uncertain = truth(label_row["needs_review"])
        checks.append({"model": name, "snapshot_date": label_row["snapshot_date"],
                       "review_id": label_row["review_id"], "manual_sentiment": label_row["manual_sentiment"],
                       "predicted_sentiment": pred, "status": record.get("status") if record else "missing_prediction",
                       "needs_review": label_row["needs_review"], "note": label_row["note"],
                       "error": record.get("error") if record else "missing_prediction",
                       "correct": "" if uncertain else str(pred == label_row["manual_sentiment"]).lower(),
                       "split": label_row["split"]})
        if uncertain:
            continue
        gold.append(label_row["manual_sentiment"])
        predicted.append(pred)
        confusion[gold[-1]][pred or "unavailable"] += 1
    result = scores(gold, predicted)
    covered = [(a, b) for a, b in zip(gold, predicted) if b is not None]
    result.update({"model": name, "manual_rows": len(labels), "valid_gold": len(gold),
                   "manual_unresolved": len(labels) - len(gold), "prediction_available": len(covered),
                   "coverage": len(covered) / len(gold), "prediction_unavailable": len(gold) - len(covered),
                   "accuracy_on_available_only": scores([p[0] for p in covered], [p[1] for p in covered])["accuracy"] if covered else None,
                   "confusion_matrix": confusion, "split": labels[0]["split"]})
    return result, checks


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--labels", default="data/samples/reviews_test_labels.csv")
    parser.add_argument("--predictions", action="append", help="Lặp tùy chọn này để so sánh LLM và baseline")
    parser.add_argument("--split", choices=["dev", "test"], default="test")
    parser.add_argument("--allow-dev", action="store_true")
    parser.add_argument("--allow-partial", action="store_true", help="Chỉ kiểm tra tạm; không phải kết quả test cuối")
    args = parser.parse_args(argv)
    if args.split == "dev" and not args.allow_dev:
        raise ValueError("Metric dev không phải test độc lập; cần --allow-dev để ghi nhận rõ.")
    labels = manual_labels(args.labels, args.split)
    valid_gold = sum(not truth(row["needs_review"]) for row in labels)
    if args.split == "test" and valid_gold < 100 and not args.allow_partial:
        raise ValueError(f"Mới có {valid_gold} nhãn test hợp lệ; cần ít nhất 100 cho bản cuối.")
    files = args.predictions or ["data/processed/llm_batch.jsonl", "data/processed/baseline.jsonl"]
    reports, all_checks = [], []
    for filename in files:
        if not path(filename).exists():
            raise FileNotFoundError(filename)
        report, checks = evaluate(labels, read_jsonl(filename), path(filename).stem)
        report.update({"partial": args.allow_partial, "created_at": now(),
                       "interpretation": "dev diagnostic only" if args.split == "dev" else "held-out test"})
        reports.append(report)
        all_checks.extend(checks)
    prefix = "llm_pilot" if args.split == "dev" else "llm_test"
    write_csv(f"reports/{prefix}_checks.csv", all_checks,
              ["model", "snapshot_date", "review_id", "manual_sentiment", "predicted_sentiment",
               "status", "needs_review", "note", "error", "correct", "split"])
    write_json(f"reports/{prefix}_metrics.json", reports)
    write_csv(f"reports/{prefix}_metrics.csv", reports,
              ["model", "split", "valid_gold", "manual_unresolved", "accuracy", "macro_precision",
               "macro_recall", "macro_f1", "weighted_f1", "coverage", "prediction_unavailable",
               "accuracy_on_available_only", "partial"])
    print(json.dumps(reports, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
