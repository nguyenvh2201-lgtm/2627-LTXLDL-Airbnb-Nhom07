"""Đánh giá trên gold do con người gán; không tạo score khi thiếu gold."""
import json
import logging
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score, precision_recall_fscore_support, confusion_matrix
from .download import read, path, csv_report, cli

METRIC_COLUMNS = ["method", "task", "metric", "value", "ci_low", "ci_high", "n"]


def validate_labels(labels: pd.DataFrame, sample: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Kiểm số nhãn tối thiểu, uniqueness, sentiment và membership."""
    if not {"review_id", "sentiment"}.issubset(labels.columns):
        raise ValueError("hand_labels cần review_id, sentiment")
    if len(labels) < cfg["evaluation"]["min_hand_labels"]:
        raise ValueError("Chưa đủ nhãn tay theo evaluation.min_hand_labels")
    if labels.review_id.isna().any() or labels.review_id.duplicated().any():
        raise ValueError("Nhãn tay thiếu/trùng review_id")
    if not set(labels.review_id) <= set(sample.id):
        raise ValueError("ID nhãn tay nằm ngoài mẫu LLM hiện tại")
    if not labels.sentiment.isin(cfg["evaluation"]["labels"]).all():
        raise ValueError("Nhãn cảm xúc thiếu/không hợp lệ")
    if "label_source" in labels and labels.label_source.ne("user_manual").any():
        raise ValueError("Gợi ý AI chưa được người gán xác nhận không phải nhãn tay")
    for column in ("aspects_praise", "aspects_complaint"):
        if column in labels:
            def parse(value):
                if pd.isna(value) or not str(value).strip():
                    return None
                decoded = json.loads(value)
                if not isinstance(decoded, list) or any(a not in cfg["llm"]["aspects"] for a in decoded):
                    raise ValueError(f"Nhãn {column} phải là mảng JSON khía cạnh trong config")
                return decoded
            labels[column] = labels[column].map(parse)
    return labels


def sentiment_metrics(truth, prediction, labels: list) -> dict:
    """Cố định ba lớp khi tính macro-F1, kể cả mẫu bootstrap thiếu lớp."""
    result = {"accuracy": accuracy_score(truth, prediction), "macro_f1": f1_score(truth, prediction, labels=labels, average="macro", zero_division=0)}
    precision, recall, f1, _ = precision_recall_fscore_support(truth, prediction, labels=labels, zero_division=0)
    for i, label in enumerate(labels):
        for name, values in (("precision", precision), ("recall", recall), ("f1", f1)):
            result[f"{name}_{label}"] = values[i]
    return result


def bootstrap(truth, prediction, cfg: dict) -> dict:
    """Khoảng tin cậy percentile, tái lấy mẫu review độc lập với seed."""
    truth, prediction = np.asarray(truth), np.asarray(prediction)
    rng = np.random.default_rng(cfg["seed"])
    values = []
    for _ in range(cfg["evaluation"]["bootstrap_iterations"]):
        index = rng.integers(0, len(truth), len(truth))
        values.append(sentiment_metrics(truth[index], prediction[index], cfg["evaluation"]["labels"]))
    alpha = (1 - cfg["evaluation"]["confidence"]) / 2
    return {key: np.quantile([v[key] for v in values], [alpha, 1 - alpha]) for key in values[0]}


def read_hand_labels(cfg: dict) -> pd.DataFrame | None:
    """Đọc nhãn tay; dùng 100 dòng đã xác nhận trong template khi chưa có file riêng."""
    source = cfg["_root"] / cfg["inputs"]["hand_labels"]
    if not source.exists():
        source = path(cfg, "samples", "hand_labels_template.csv")
        if not source.exists():
            return None
    labels = pd.read_csv(source, dtype={"review_id": str})
    if "label_source" in labels:
        labels = labels.loc[labels.label_source.eq("user_manual")].copy()
    return labels


def run(cfg: dict) -> None:
    """So sánh công bằng trên cùng gold; lỗi/thiếu LLM được tính là sai."""
    empty_error_columns = ["review_id", "text", "hand_label", "llm", "baseline", "error_type_hint"]
    labels = read_hand_labels(cfg)
    if labels is None or labels.empty:
        logging.warning("Chưa có nhãn tay thật: không thể tính accuracy/F1")
        csv_report(cfg, [], "eval_metrics.csv", METRIC_COLUMNS)
        path(cfg, "reports", "error_summary.md").write_text("# Chưa có nhãn tay\nKhông có số liệu đánh giá. Nhóm gán nhãn tay rồi chạy lại.\n", encoding="utf-8")
        return
    sample = read(cfg, "llm_sample")
    gold = validate_labels(labels, sample, cfg)
    frames = {method: read(cfg, method + "_results") for method in ("llm", "baseline")}
    valid_llm = frames["llm"].sentiment.notna() & ~frames["llm"].parse_error
    if not valid_llm.any():
        logging.warning("Chưa có dự đoán Gemini hợp lệ: chưa thể đánh giá LLM so với baseline")
        csv_report(cfg, [], "eval_metrics.csv", METRIC_COLUMNS)
        path(cfg, "reports", "error_summary.md").write_text("# Chưa có kết quả Gemini\nĐã có nhãn tay, nhưng chưa có dự đoán Gemini hợp lệ để so sánh.\n", encoding="utf-8")
        return
    rows, predictions = [], {}
    for method, frame in frames.items():
        if frame.review_id.duplicated().any():
            raise ValueError(f"{method} có review_id trùng")
        merged = gold.merge(frame, on="review_id", how="left", suffixes=("_gold", "_pred"), validate="one_to_one")
        prediction = merged.sentiment_pred.fillna("missing_or_error")
        predictions[method] = prediction.to_numpy()
        metrics = sentiment_metrics(merged.sentiment_gold, prediction, cfg["evaluation"]["labels"])
        ci = bootstrap(merged.sentiment_gold, prediction, cfg)
        for name, value in metrics.items():
            rows.append({"method": method, "task": "sentiment", "metric": name, "value": value, "ci_low": ci[name][0], "ci_high": ci[name][1], "n": len(merged)})
        rows.append({"method": method, "task": "coverage", "metric": "valid_prediction_rate", "value": prediction.ne("missing_or_error").mean(), "n": len(merged)})
        matrix_labels = [*cfg["evaluation"]["labels"], "missing_or_error"]
        matrix = pd.DataFrame(confusion_matrix(merged.sentiment_gold, prediction, labels=matrix_labels), index=matrix_labels, columns=matrix_labels)
        matrix.index.name = "true_label"
        matrix.to_csv(path(cfg, "reports", f"confusion_{method}.csv"))
        for aspect_task in ("aspects_praise", "aspects_complaint"):
            gold_column, pred_column = aspect_task + "_gold", aspect_task + "_pred"
            if gold_column not in merged:
                continue
            subset = merged.loc[merged[gold_column].notna()]
            if subset.empty:
                continue
            actual = np.array([[a in values for a in cfg["llm"]["aspects"]] for values in subset[gold_column]])
            predicted = np.array([[a in values if isinstance(values, (list, np.ndarray)) else False for a in cfg["llm"]["aspects"]] for values in subset[pred_column]])
            for average in ("micro", None):
                precision, recall, score, _ = precision_recall_fscore_support(actual, predicted, average=average, zero_division=0)
                for metric_name, values in (("precision", precision), ("recall", recall), ("f1", score)):
                    if average == "micro":
                        rows.append({"method": method, "task": aspect_task, "metric": metric_name + "_micro", "value": values, "n": len(subset)})
                    else:
                        rows.extend({"method": method, "task": aspect_task, "metric": metric_name + "_" + a, "value": v, "n": len(subset)} for a, v in zip(cfg["llm"]["aspects"], values))
        if "language_gold" in merged:
            subset = merged.loc[merged.language_gold.notna() & merged.language_gold.ne("")]
            if len(subset):
                rows.append({"method": method, "task": "language", "metric": "accuracy", "value": subset.language_gold.eq(subset.language_pred).mean(), "n": len(subset)})
    # Bootstrap ghép cặp cho chênh lệch accuracy, không so hai mẫu khác nhau.
    truth = gold.sentiment.to_numpy()
    differences = (predictions["llm"] == truth).astype(float) - (predictions["baseline"] == truth).astype(float)
    rng = np.random.default_rng(cfg["seed"])
    samples = [rng.choice(differences, len(differences), replace=True).mean() for _ in range(cfg["evaluation"]["bootstrap_iterations"])]
    alpha = (1 - cfg["evaluation"]["confidence"]) / 2
    low, high = np.quantile(samples, [alpha, 1 - alpha])
    rows.append({"method": "llm_minus_baseline", "task": "paired_comparison", "metric": "accuracy_difference", "value": differences.mean(), "ci_low": low, "ci_high": high, "n": len(gold)})
    errors = gold[["review_id", "sentiment"]].rename(columns={"sentiment": "hand_label"}).merge(sample[["id", "comments"]], left_on="review_id", right_on="id")
    errors["llm"], errors["baseline"] = predictions["llm"], predictions["baseline"]
    errors = errors.loc[errors.llm.ne(errors.hand_label) | errors.baseline.ne(errors.hand_label)].rename(columns={"comments": "text"})
    errors["error_type_hint"] = errors.apply(lambda r: "parse_error_or_missing" if r.llm == "missing_or_error" else ("short_review" if len(r.text) < cfg["evaluation"]["short_review_chars"] else ("mixed_confusion" if "mixed" in [r.llm, r.baseline, r.hand_label] else "human_review_required")), axis=1)
    csv_report(cfg, errors, "error_analysis.csv", empty_error_columns)
    csv_report(cfg, rows, "eval_metrics.csv", METRIC_COLUMNS)
    text = "# Gợi ý phân tích lỗi\n\n" + errors.error_type_hint.value_counts().to_string() + "\n\nNhóm tự đọc và nhận xét mỉa mai, ngôn ngữ ít gặp, nội dung không liên quan. Không tự coi gợi ý là nguyên nhân thật.\n"
    path(cfg, "reports", "error_summary.md").write_text(text, encoding="utf-8")

if __name__ == "__main__":
    cli(run)
