"""Điều phối vòng đời review: kiểm tra QA -> cache -> Gemini -> JSONL.

Từng review luôn có status ``ok``, ``needs_review`` hoặc ``error``.
Cache chỉ lưu kết quả LLM đã validate; output chứa cả cache hit và lỗi.
``.run.json`` là báo cáo cuối batch; chỉ có sau khi vòng lặp kết thúc.
Append checkpoint giúp giảm khối lượng ghi O(n²) -> O(n), nhưng khi mất
điện đúng lúc ghi có thể còn dòng JSONL cuối bị dở dang (xem README).
"""
import collections
import json
import os
import time
from copy import deepcopy
from .common import digest, normalize_text, now, path, read_jsonl, require_unique, truth, write_json, write_jsonl
from .llm_contract import MODEL_FIELDS, cache_key, index_cache_records, validate_response, validate_review_rows
from .gemini_client import ProviderError


def _usage_token_count(record, field):
    """Missing or malformed provider metadata must not abort a finished batch."""
    usage = record.get("usage")
    value = usage.get(field, 0) if isinstance(usage, dict) else 0
    return value if type(value) is int and value >= 0 else 0


def _append_checkpoint(output, record):
    """Append one JSONL record with fsync and best-effort rollback.

    Used for both the successful-response cache and subsequent output
    checkpoints. A hard power loss mid-write can still leave a partial tail;
    fsync and rollback do not make append an atomic transaction.
    """
    data = (json.dumps(record, ensure_ascii=False) + "\n").encode("utf-8")
    target = path(output)
    with target.open("ab", buffering=0) as stream:
        previous_size = stream.tell()
        if previous_size:
            # JSONL nhận từ nguồn khác có thể chưa có newline cuối file.
            with target.open("rb") as existing:
                existing.seek(-1, os.SEEK_END)
                if existing.read(1) != b"\n":
                    data = b"\n" + data
        try:
            if stream.write(data) != len(data):
                raise OSError("Không ghi đủ dữ liệu checkpoint JSONL.")
            os.fsync(stream.fileno())
        except BaseException:
            # Covers handled I/O errors and Ctrl+C; impossible on hard kill.
            stream.truncate(previous_size)
            os.fsync(stream.fileno())
            raise


def classify(rows, config, output, skip_llm=False, refresh=False, max_new_requests=None, *, request_fn):
    """Duyệt batch, tái dùng cache, ghi output JSONL và báo cáo run.json.

    ``request_fn`` được inject từ CLI để dễ mock trong unit test.
    KHÔNG so sánh với nhãn người ở đây: việc đó thuộc evaluate.
    """
    output_paths = {path(output).resolve(), path(str(output) + ".run.json").resolve()}
    protected_paths = {path(config[k]).resolve() for k in ("cache", "prompt_file", "schema_file")}
    if output_paths & protected_paths:
        raise ValueError("Output/báo cáo không được trùng cache, prompt hoặc schema; chọn đường dẫn khác.")
    if not rows:
        raise ValueError("Không có review đầu vào; chưa gọi API.")
    validate_review_rows(rows)
    require_unique(rows)
    model = os.environ.get("GEMINI_MODEL") or config.get("model")
    if not model:
        raise RuntimeError("Đặt GEMINI_MODEL theo model tài khoản dùng được; xem llm --list-models.")
    model = model.removeprefix("models/")
    prompt = path(config["prompt_file"]).read_text(encoding="utf-8")
    schema = json.loads(path(config["schema_file"]).read_text(encoding="utf-8"))
    # Nạp cache trước; hàm index không sửa file gốc. Sai fingerprint => miss.
    cached = index_cache_records(read_jsonl(config["cache"]))
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if skip_llm and refresh:
        raise ValueError("Không dùng đồng thời --skip-llm và --refresh.")
    if max_new_requests is not None and max_new_requests < 0:
        raise ValueError("max_new_requests phải >= 0")
    if not api_key and not skip_llm:
        raise RuntimeError("Thiếu GEMINI_API_KEY. Chưa gọi API, chưa tạo dự đoán giả.")
    cache_file = path(config["cache"])
    report_file = path(str(output) + ".run.json")
    # Preflight đã đạt: report cũ không được đại diện cho batch sắp chạy.
    # Batch bị ngắt không có report hoàn tất; output/cache vẫn là checkpoint.
    report_file.unlink(missing_ok=True)
    records, started, abort_reason, new_reviews = [], now(), None, 0
    for number, row in enumerate(rows, start=1):
        fingerprint = cache_key(row, config, model, prompt, schema)
        record = {"snapshot_date": row["snapshot_date"], "review_id": row["review_id"],
                  "listing_id": row["listing_id"], "split": row.get("split", "analysis"),
                  "sentiment": None, "aspects": [], "language": "unknown", "status": "error",
                  "error": None, "provider": "gemini", "model": model,
                  "prompt_version": config["prompt_version"], "prompt_sha256": digest(prompt),
                  "schema_sha256": digest(schema), "text_sha256": digest(normalize_text(row["comments"])),
                  "cache_key": fingerprint, "processed_at": now(), "from_cache": False,
                  "api_requests": 0, "usage": {}}
        provider = None
        try:
            if truth(row.get("exclude_from_llm_sample", "false")):
                raise ValueError("input_qa_excluded")
            if not normalize_text(row.get("comments", "")) or not truth(row.get("text_valid", "true")):
                raise ValueError("input_empty_or_invalid_text")
            if not truth(row.get("listing_match", "true")):
                raise ValueError("input_listing_mismatch")
            # Ưu tiên cache nếu hợp lệ; --refresh chủ động bỏ qua cache.
            if fingerprint in cached and not refresh:
                old = cached[fingerprint]
                validate_response({field: old[field] for field in MODEL_FIELDS})
                record = deepcopy(old)
                record.update({"from_cache": True, "api_requests": 0, "split": row.get("split", "analysis"),
                               "read_from_cache_at": now()})
            elif skip_llm:
                raise ValueError("cache_miss_skip_llm")
            elif abort_reason:
                raise ValueError("not_attempted_after_" + abort_reason)
            elif max_new_requests is not None and new_reviews >= max_new_requests:
                raise ValueError("not_attempted_request_limit")
            else:
                new_reviews += 1
                # Chỉ gọi Gemini khi review QA hợp lệ, chưa cache và còn hạn mức.
                provider = request_fn(row, config, model, prompt, schema, api_key)
                record.update({k: provider[k] for k in ("usage", "model_version", "api_requests")})
                if not isinstance(record["usage"], dict):
                    record["usage"] = {}
                record.update(validate_response(json.loads(provider["text"])))
                cache_file.parent.mkdir(parents=True, exist_ok=True)
                _append_checkpoint(cache_file, record)
                cached[fingerprint] = deepcopy(record)
        except (ValueError, ProviderError, KeyError, TypeError) as error:
            record["status"], record["sentiment"], record["aspects"] = "error", None, []
            record["error"] = str(error)[:300].replace(api_key, "[REDACTED]") if api_key else str(error)[:300]
            if isinstance(error, ProviderError):
                record["api_requests"] = error.attempts
                record["provider_error"] = error.details
                if str(error) in ("http_401", "http_403", "http_404", "http_429"):
                    abort_reason = str(error)
            if isinstance(provider, dict) and isinstance(provider.get("text"), str):
                record["raw_response"] = provider["text"][:20000]
        records.append(record)
        # Checkpoint đầu tiên giữ atomic replace; các dòng sau append O(n).
        # Cache kết quả thành công vẫn là nguồn phục hồi độc lập nếu bị ngắt.
        if number == 1:
            write_jsonl(output, records)
        else:
            _append_checkpoint(output, record)
        detail = "cache" if record["from_cache"] else (record["error"] or "API")
        print(f'{number}/{len(rows)} {row["review_id"]}: {record["status"]} ({detail})', flush=True)
        if record.get("provider_error"):
            print(json.dumps(record["provider_error"], ensure_ascii=False), flush=True)
        if record["api_requests"] and number < len(rows):
            time.sleep(max(0, float(config["request_interval_seconds"])))
    # Thống kê run.json: cache hit, lỗi, requests và token đã ghi nhận.
    report = {"started_at": started, "finished_at": now(), "provider": "gemini", "model": model,
              "prompt_version": config["prompt_version"], "rows": len(records),
              "status_counts": dict(collections.Counter(r["status"] for r in records)),
              "cache_hits": sum(r["from_cache"] for r in records),
              "new_reviews_attempted": new_reviews,
              "error_counts": dict(collections.Counter(r["error"] for r in records if r["status"] == "error")),
              "provider_errors": [r["provider_error"] for r in records if r.get("provider_error")],
              "api_requests": sum(r["api_requests"] for r in records),
              "prompt_tokens_new_calls": sum(_usage_token_count(r, "promptTokenCount")
                                              for r in records if not r["from_cache"]),
              "total_tokens_new_calls": sum(_usage_token_count(r, "totalTokenCount")
                                             for r in records if not r["from_cache"]),
              "skip_llm": skip_llm}
    write_json(report_file, report)
    return records
