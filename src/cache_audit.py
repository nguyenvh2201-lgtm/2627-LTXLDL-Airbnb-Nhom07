"""Lệnh phụ trợ độc lập: kiểm tra cache có khớp dữ liệu sau QA không.

Đối chiếu review_id/listing_id/văn bản/snapshot/fingerprint, xuất mẫu đánh
giá và CSV nhãn tay 100 review (để TRỐNG, không tự gán nhãn).
Không gọi Gemini, không đọc nhãn người để quyết định dự đoán.
Chạy qua: ``python run_tv4.py cache_audit --help``.
"""
from __future__ import annotations

import argparse
import collections
import csv
import gzip
import json

from .common import digest, file_sha256, load_config, normalize_text, path, read_jsonl, truth, write_csv, write_json, write_jsonl
from .llm_contract import MODEL_FIELDS, cache_key, index_cache_records, validate_response
from .prepare import REVIEW_FIELDS, read_marking


def audit(qa_file, cache_file, marking_file, config, model, output_dir):
    """Tạo báo cáo QA-cache và danh sách review đủ điều kiện.

    Nguồn đầu vào: QA CSV + cache JSONL + marking CSV; không sửa các nguồn.
    Đầu ra: thư mục report, bao gồm review sau QA và template nhãn tay.
    """
    model = model.removeprefix("models/")
    output_dir = path(output_dir)
    output_names = ("sample_qa_audit.csv", "cache_qa_audit.csv", "reviews_llm_after_qa.csv",
                    "manual_test_100.csv", "llm_reused.jsonl", "llm_reconciled_all_samples.jsonl", "audit_summary.json")
    sources = {path(name).resolve() for name in (qa_file, cache_file, marking_file, config["prompt_file"], config["schema_file"])}
    if sources & {(output_dir / name).resolve() for name in output_names}:
        raise ValueError("Thư mục audit làm đầu ra trùng nguồn/cache; chọn --output-dir khác.")
    _, marks, _, _, _ = read_marking(marking_file)
    snapshot = config["snapshot_date"]
    qa_by_id = {}
    duplicates = set()
    opener = gzip.open if str(qa_file).endswith(".gz") else open
    with opener(path(qa_file), "rt", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        id_col = "review_id" if "review_id" in (reader.fieldnames or []) else "id"
        required = {id_col, "listing_id", "comments", "text_valid", "listing_match"}
        if not required <= set(reader.fieldnames or []):
            raise ValueError(f"QA thiếu cột: {sorted(required - set(reader.fieldnames or []))}")
        for row in reader:
            if None in row or any(value is None for value in row.values()):
                raise ValueError("CSV QA có dòng không khớp số cột.")
            if row.get("snapshot_date", snapshot) != snapshot:
                continue
            rid = row[id_col]
            if rid in qa_by_id:
                duplicates.add(rid)
            qa_by_id[rid] = row

    prompt = path(config["prompt_file"]).read_text(encoding="utf-8")
    schema = json.loads(path(config["schema_file"]).read_text(encoding="utf-8"))
    cache = read_jsonl(cache_file)
    index = index_cache_records(r for r in cache if r.get("model") == model)
    sample_audit, ready, predictions, template = [], [], [], []
    sample_by_id = {}
    for rid, mark in marks.items():
        if not mark["is_llm"]:
            continue
        qa = qa_by_id.get(rid)
        reasons = []
        if qa is None:
            reasons.append("missing_after_qa")
        else:
            if rid in duplicates:
                reasons.append("duplicate_review_id_after_qa")
            if qa["listing_id"] != mark["listing_id"]:
                reasons.append("listing_id_mismatch")
            if not truth(qa["text_valid"]) or not normalize_text(qa["comments"]):
                reasons.append("qa_invalid_text")
            if not truth(qa["listing_match"]):
                reasons.append("qa_listing_mismatch")
            if truth(qa.get("exclude_from_llm_sample", "false")):
                reasons.append("qa_exclude_from_llm_sample")
        is_dev = qa is not None and qa.get("split", "").strip() == "dev"
        if is_dev and mark["is_manual_test"]:
            raise ValueError(f"Review {rid}: QA ghi split=dev nhưng marking chọn test; đối chiếu lại dev/test trước khi audit.")
        row = {
            "snapshot_date": snapshot, "review_id": rid, "listing_id": mark["listing_id"],
            "date": qa.get("date", "") if qa else "", "comments": qa["comments"] if qa else "",
            "analysis_area": "", "is_llm": "true", "is_manual_test": str(mark["is_manual_test"]).lower(),
            "split": "test" if mark["is_manual_test"] else ("dev" if is_dev else "analysis"),
            "text_valid": "true" if not reasons else "false", "listing_match": "true" if not reasons else "false",
        }
        sample_by_id[rid] = row
        candidate = index.get(cache_key(row, config, model, prompt, schema)) if not reasons else None
        if candidate:
            try:
                validate_response({field: candidate[field] for field in MODEL_FIELDS})
            except (ValueError, KeyError, TypeError):
                candidate = None
        state = ";".join(reasons) or ("reusable_cache" if candidate else "cache_missing_or_different_fingerprint")
        sample_audit.append({"snapshot_date": snapshot, "review_id": rid, "listing_id": row["listing_id"],
                             "qa_present": qa is not None, "qa_eligible": not reasons,
                             "cache_reusable": bool(candidate), "is_manual_test": mark["is_manual_test"], "reason": state})
        if not reasons:
            ready.append(row)
        if candidate:
            record = dict(candidate)
            record.update(split=row["split"], from_cache=True, api_requests=0)
            predictions.append(record)
        if mark["is_manual_test"]:
            template.append({k: row[k] for k in ("snapshot_date", "review_id", "listing_id", "date", "comments", "split")})
            template[-1].update(manual_sentiment="", manual_aspects="", needs_review="", note="", qa_eligible=not reasons)

    cache_audit = []
    for record in cache:
        rid = record.get("review_id")
        in_scope = record.get("snapshot_date") == snapshot
        qa = qa_by_id.get(rid) if in_scope else None
        same_text = qa is not None and digest(normalize_text(qa["comments"])) == record.get("text_sha256")
        same_listing = qa is not None and qa["listing_id"] == record.get("listing_id")
        eligible = bool(qa and truth(qa["text_valid"]) and truth(qa["listing_match"])
                        and not truth(qa.get("exclude_from_llm_sample", "false")) and rid not in duplicates)
        cache_audit.append({"snapshot_date": record.get("snapshot_date"), "review_id": rid,
                            "listing_id": record.get("listing_id"), "model": record.get("model"),
                            "status": record.get("status"), "qa_present": qa is not None,
                            "qa_snapshot_in_scope": in_scope,
                            "listing_matches_qa": same_listing, "normalized_text_matches_qa": same_text,
                            "qa_eligible": eligible, "in_marked_llm_sample": rid in sample_by_id})

    output_dir.mkdir(parents=True, exist_ok=True)
    if not sample_audit:
        raise ValueError("Bảng đánh dấu không có mẫu LLM.")
    write_csv(output_dir / "sample_qa_audit.csv", sample_audit, list(sample_audit[0]))
    if cache_audit:
        write_csv(output_dir / "cache_qa_audit.csv", cache_audit, list(cache_audit[0]))
    write_csv(output_dir / "reviews_llm_after_qa.csv", ready, REVIEW_FIELDS)
    # Không đọc quyết định của người để chọn mẫu, và không ghi đè file có thể đã được gán tay.
    manual_target = output_dir / "manual_test_100.csv"
    manual_template_written = not manual_target.exists()
    if manual_template_written:
        write_csv(manual_target, template,
                  ["snapshot_date", "review_id", "listing_id", "date", "comments", "manual_sentiment", "manual_aspects", "needs_review", "note", "split", "qa_eligible"])
    write_jsonl(output_dir / "llm_reused.jsonl", predictions)
    # Keep all 1,000 sample identities in the companion output; missing results stay errors.
    by_id = {r["review_id"]: r for r in predictions}
    audit_by_id = {r["review_id"]: r for r in sample_audit}
    complete = []
    for rid, row in sample_by_id.items():
        complete.append(by_id.get(rid) or {
            "snapshot_date": snapshot, "review_id": rid, "listing_id": row["listing_id"],
            "split": row["split"], "sentiment": None, "aspects": [], "language": "unknown",
            "status": "error", "error": audit_by_id[rid]["reason"], "model": model,
            "provider": "gemini", "prompt_version": config["prompt_version"],
            "from_cache": False, "api_requests": 0})
    write_jsonl(output_dir / "llm_reconciled_all_samples.jsonl", complete)
    report = {
        "snapshot_date": snapshot, "model": model, "qa_file": str(path(qa_file)),
        "cache_file": str(path(cache_file)), "qa_rows_unique": len(qa_by_id),
        "qa_duplicate_ids": len(duplicates), "marked_llm_samples": len(sample_audit),
        "qa_eligible_samples": len(ready), "qa_ineligible_or_missing_samples": len(sample_audit) - len(ready),
        "cache_rows_all_models": len(cache),
        "cache_rows_by_model": dict(collections.Counter(r.get("model") for r in cache)),
        "cache_unique_review_ids": len({(r.get("snapshot_date"), r.get("review_id")) for r in cache}),
        "reused_selected_model": len(predictions), "still_missing_selected_model": len(ready) - len(predictions),
        "manual_test_samples": len(template),
        "manual_template_written": manual_template_written,
        "manual_template_note": "new blank template" if manual_template_written else "existing file preserved; use a new output directory if QA changed",
        "manual_test_predictions_available": sum(r.get("split") == "test" for r in predictions),
        "sentiment_counts_reused": dict(collections.Counter(r["sentiment"] for r in predictions)),
        "cache_rows_outside_qa_snapshot": sum(not r["qa_snapshot_in_scope"] for r in cache_audit),
        "cache_rows_missing_after_qa": sum(r["qa_snapshot_in_scope"] and not r["qa_present"] for r in cache_audit),
        "cache_rows_changed_normalized_text": sum(r["qa_present"] and not r["normalized_text_matches_qa"] for r in cache_audit),
        "cache_rows_ineligible_after_qa": sum(r["qa_present"] and not r["qa_eligible"] for r in cache_audit),
        "api_requests": 0, "manual_label_values_read": False,
        "qa_file_sha256": file_sha256(qa_file),
        "cache_file_sha256": file_sha256(cache_file) if path(cache_file).exists() else None,
        "scope": "Only the supplied QA export and saved cache. No claim about newer remote branches or current local cache.",
    }
    write_json(output_dir / "audit_summary.json", report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qa-reviews", required=True)
    parser.add_argument("--cache", default="data/processed/llm_cache.jsonl")
    parser.add_argument("--marking", default="data/data-new.csv")
    parser.add_argument("--config", default="configs/toronto.json")
    parser.add_argument("--model", required=True)
    parser.add_argument("--output-dir", default="reports/cache_audit")
    args = parser.parse_args(argv)
    report = audit(args.qa_reviews, args.cache, args.marking, load_config(args.config), args.model, path(args.output_dir))
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
