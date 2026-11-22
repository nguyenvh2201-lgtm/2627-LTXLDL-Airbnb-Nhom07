"""Recalculate declared report numbers; check Markdown and PDF displays.

Only values declared in report_numbers.json are covered. String presence does
not verify the surrounding interpretation or the visual layout of the PDF.
"""
import argparse
import json
import math
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import numpy as np
import pandas as pd
from pypdf import PdfReader
from sklearn.metrics import f1_score
from src.download import load_config, path, read
from src.kpi import compute
from src.evaluate import read_hand_labels, validate_labels, sentiment_metrics


def live_values(cfg: dict, keys: set[str]) -> dict:
    """Read current clean data/predictions, never the saved summary table."""
    listings, calendar, reviews = [read(cfg, name + "_clean") for name in ("listings", "calendar", "reviews")]
    _, times = compute(cfg, listings, calendar, reviews)
    values = {}
    for name, frame in (("listings", listings), ("calendar", calendar), ("reviews", reviews)):
        for snapshot, group in frame.groupby("snapshot"):
            values[f"{name}.{snapshot}.after"] = len(group)
    latest = listings.loc[listings.snapshot.eq(cfg["snapshots"][-1])]
    prices = latest.loc[~latest.flag_outlier_price & latest.price.notna()]
    values.update({
        "latest.entire_home_pct": latest.room_type.eq("Entire home/apt").mean() * 100,
        "latest.median_price": prices.price.median(),
        "latest.valid_price_count": len(prices),
        "latest.mean_price_before": latest.price.mean(),
        "latest.median_price_before": latest.price.median(),
        "latest.missing_price": latest.missing_price.sum(),
        "latest.entire_median_price": prices.loc[prices.room_type.eq("Entire home/apt"), "price"].median(),
        "latest.annex_median_price": prices.loc[prices.neighbourhood_cleansed.eq("Annex"), "price"].median(),
        "latest.private_median_price": prices.loc[prices.room_type.eq("Private room"), "price"].median(),
        "llm.actual_spend": cfg["llm"].get("actual_spend_usd"),
    })
    k2 = times.loc[times.kpi_id.eq("K2"), "value"]
    first_month = times.loc[times.kpi_id.eq("K3")].sort_values("period").groupby("snapshot").first()["value"]
    values.update({"kpi_time.K2.min": k2.min(), "kpi_time.K2.max": k2.max(),
                   "kpi_time.K3.first_month_min": first_month.min(),
                   "kpi_time.K3.first_month_max": first_month.max()})
    if any(key.startswith(("eval.", "error.")) for key in keys):
        gold = validate_labels(read_hand_labels(cfg), read(cfg, "llm_sample"), cfg)
        for method in ("llm", "baseline"):
            frame = read(cfg, method + "_results")
            merged = gold.merge(frame, on="review_id", how="left", suffixes=("_gold", "_pred"), validate="one_to_one")
            valid = merged.sentiment_pred.isin(cfg["evaluation"]["labels"])
            if method == "llm":
                valid &= ~merged.parse_error.fillna(True)
            prediction = merged.sentiment_pred.where(valid, "missing_or_error")
            values[f"error.{method}_wrong"] = prediction.ne(merged.sentiment_gold).sum()
            for metric, value in sentiment_metrics(merged.sentiment_gold, prediction, cfg["evaluation"]["labels"]).items():
                values[f"eval.{method}.sentiment.{metric}"] = value
            for task in ("aspects_praise", "aspects_complaint"):
                if task + "_gold" not in merged:
                    continue
                subset = merged.loc[merged[task + "_gold"].notna()]
                if subset.empty:
                    continue
                actual = [[a in v for a in cfg["llm"]["aspects"]] for v in subset[task + "_gold"]]
                predicted = [[bool(valid.loc[i]) and isinstance(v, (list, tuple, np.ndarray)) and a in v
                              for a in cfg["llm"]["aspects"]]
                             for i, v in subset[task + "_pred"].items()]
                values[f"eval.{method}.{task}.f1_micro"] = f1_score(actual, predicted, average="micro", zero_division=0)
    return values


def check(cfg: dict) -> int:
    manifest = json.loads(path(cfg, "reports", "report_numbers.json").read_text(encoding="utf-8"))
    values = live_values(cfg, {row["key"] for row in manifest})
    documents = {"report.md": path(cfg, "reports", "report.md").read_text(encoding="utf-8"),
                 "report.pdf": "\n".join(page.extract_text(extraction_mode="layout") or "" for page in PdfReader(path(cfg, "reports", "report.pdf")).pages)}
    documents = {name: re.sub(r"\s+", " ", text) for name, text in documents.items()}
    for row in manifest:
        key = row["key"]
        if key not in values:
            raise ValueError(f"Unsupported report number: {key}")
        actual, expected = values[key], row["value"]
        matches = pd.isna(actual) if expected is None else actual is not None and math.isclose(float(actual), expected, rel_tol=0, abs_tol=1e-8)
        if not matches:
            raise ValueError(f"{key}: current data={actual}, report declaration={expected}")
        rendered = re.sub(r"\s+", " ", row["rendered"])
        # Numeric boundaries prevent e.g. 90.5 matching 190.50.
        pattern = r"(?<![\d.,])" + re.escape(rendered) + r"(?!\d|[.,]\d)"
        for name, text in documents.items():
            if not re.search(pattern, text):
                raise ValueError(f"{key}: display {row['rendered']!r} missing from {name}")
    return len(manifest)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/Toronto.yaml")
    args = parser.parse_args()
    print("PASS report numbers (current data + Markdown + PDF):", check(load_config(args.config)))
