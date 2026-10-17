"""Gemini REST thật: JSON, kiểm schema, cache, retry và giữ mọi dòng lỗi."""
from __future__ import annotations

import argparse
import collections
import json
import os
import re
import time
import urllib.error
import urllib.request
from urllib.parse import urlencode
from copy import deepcopy

from .common import (ASPECTS, LABELS, digest, key, load_config, manual_labels,
                     normalize_text, now, path, read_csv, read_jsonl,
                     require_unique, truth, write_json, write_jsonl)

MODEL_FIELDS = {"sentiment", "aspects", "language", "status", "error"}
API_ROOT = "https://generativelanguage.googleapis.com/v1beta"


def validate_response(value):
    if not isinstance(value, dict) or set(value) != MODEL_FIELDS:
        raise ValueError("schema: cần đúng 5 khóa sentiment/aspects/language/status/error")
    if value["status"] not in ("ok", "needs_review"):
        raise ValueError("schema: status không hợp lệ")
    if not isinstance(value["language"], str) or not re.fullmatch(r"[a-z]{2,3}|unknown", value["language"]):
        raise ValueError("schema: language không hợp lệ")
    if not isinstance(value["aspects"], list) or len(value["aspects"]) > len(ASPECTS):
        raise ValueError("schema: aspects không hợp lệ")
    seen = set()
    for aspect in value["aspects"]:
        if not isinstance(aspect, dict) or set(aspect) != {"aspect", "polarity"}:
            raise ValueError("schema: cấu trúc aspect sai")
        if aspect["aspect"] not in ASPECTS or aspect["polarity"] not in LABELS:
            raise ValueError("schema: aspect hoặc polarity ngoài danh mục")
        if aspect["aspect"] in seen:
            raise ValueError("schema: aspect trùng")
        seen.add(aspect["aspect"])
    if value["status"] == "ok":
        if value["sentiment"] not in LABELS or value["error"] is not None:
            raise ValueError("schema: dòng ok cần sentiment hợp lệ và error=null")
    elif value["sentiment"] is not None or value["aspects"] or not isinstance(value["error"], str) or not value["error"].strip():
        raise ValueError("schema: needs_review cần sentiment=null, aspects=[] và lý do")
    return value


def cache_key(row, config, model, prompt, schema):
    return digest({"provider": "gemini", "model": model,
                   "prompt_version": config["prompt_version"], "prompt": prompt,
                   "schema": schema, "temperature": config["temperature"],
                   "max_output_tokens": config["max_output_tokens"],
                   "snapshot_date": row["snapshot_date"], "review_id": row["review_id"],
                   "listing_id": row["listing_id"], "text": normalize_text(row["comments"])})


class ProviderError(RuntimeError):
    def __init__(self, message, attempts, details=None):
        super().__init__(message)
        self.attempts = attempts
        self.details = details or {}


def http_details(error, api_key):
    """Keep provider diagnostics, never request headers or credentials."""
    raw = error.read(65536).decode("utf-8", errors="replace")
    raw = raw.replace(api_key, "[REDACTED]") if api_key else raw
    raw = re.sub(r"AIza[A-Za-z0-9_-]+", "[REDACTED]", raw)
    try:
        body = json.loads(raw).get("error", {})
    except (ValueError, AttributeError):
        body = {}
    if not isinstance(body, dict):
        body = {}
    return {"http_status": error.code, "status": body.get("status"),
            "message": str(body.get("message", raw))[:12000],
            "details": body.get("details", []),
            "retry_after": error.headers.get("Retry-After") if error.headers else None}


def gemini_request(row, config, model, prompt, schema, api_key):
    if not re.fullmatch(r"[A-Za-z0-9._-]+", model):
        raise ValueError("Tên model không hợp lệ; dùng ID model, bỏ tiền tố models/.")
    payload = {
        "systemInstruction": {"parts": [{"text": prompt + "\nOUTPUT JSON SCHEMA:\n" + json.dumps(schema)}]},
        "contents": [{"role": "user", "parts": [{"text": json.dumps({
            "review_text": normalize_text(row["comments"])
        }, ensure_ascii=False)}]}],
        "generationConfig": {"responseMimeType": "application/json",
                             "temperature": config["temperature"],
                             "maxOutputTokens": config["max_output_tokens"]}
    }
    request = urllib.request.Request(API_ROOT + f"/models/{model}:generateContent",
              data=json.dumps(payload).encode("utf-8"), method="POST",
              headers={"Content-Type": "application/json", "x-goog-api-key": api_key})
    max_retries = int(config["max_retries"])
    for attempt in range(max_retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=config["timeout_seconds"]) as response:
                body = json.load(response)
            candidates = body.get("candidates", [])
            if not candidates:
                raise ProviderError("empty_or_blocked_response", attempt + 1)
            candidate = candidates[0]
            if candidate.get("finishReason") != "STOP":
                raise ProviderError("finish_reason_" + str(candidate.get("finishReason", "missing")), attempt + 1)
            text = "".join(p.get("text", "") for p in candidate.get("content", {}).get("parts", [])
                           if not p.get("thought", False))
            return {"text": text, "usage": body.get("usageMetadata", {}),
                    "model_version": body.get("modelVersion"), "api_requests": attempt + 1}
        except urllib.error.HTTPError as error:
            details = http_details(error, api_key)
            retryable = error.code in (408, 429, 500, 502, 503, 504)
            if not retryable or attempt == max_retries:
                raise ProviderError(f"http_{error.code}", attempt + 1, details) from None
            delay = min(60, 2 ** attempt)
            retry_after = error.headers.get("Retry-After", "") if error.headers else ""
            if retry_after.isdigit():
                # Dừng nếu server yêu cầu chờ lâu; không retry sớm hơn yêu cầu.
                if int(retry_after) > 60:
                    raise ProviderError(f"http_{error.code}", attempt + 1, details) from None
                delay = max(delay, int(retry_after))
            time.sleep(delay)
        except (urllib.error.URLError, TimeoutError) as error:
            if attempt == max_retries:
                raise ProviderError("network_or_timeout", attempt + 1) from None
            time.sleep(min(60, 2 ** attempt))
        except json.JSONDecodeError:
            raise ProviderError("provider_invalid_json", attempt + 1) from None
    raise AssertionError("unreachable")


def list_models(api_key):
    result, token = [], None
    while True:
        suffix = "?" + urlencode({"pageSize": 1000, **({"pageToken": token} if token else {})})
        request = urllib.request.Request(API_ROOT + "/models" + suffix,
                                         headers={"x-goog-api-key": api_key})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                body = json.load(response)
        except urllib.error.HTTPError as error:
            raise RuntimeError(f"Không lấy được model: HTTP {error.code}.") from None
        result.extend(m["name"].removeprefix("models/") for m in body.get("models", [])
                      if "generateContent" in m.get("supportedGenerationMethods", []))
        token = body.get("nextPageToken")
        if not token:
            return result


def classify(rows, config, output, skip_llm=False, refresh=False, max_new_requests=None):
    require_unique(rows)
    if not rows:
        raise ValueError("Không có review đầu vào; chưa gọi API.")
    model = os.environ.get("GEMINI_MODEL") or config.get("model")
    if not model:
        raise RuntimeError("Đặt GEMINI_MODEL theo model tài khoản dùng được; xem llm --list-models.")
    model = model.removeprefix("models/")
    prompt = path(config["prompt_file"]).read_text(encoding="utf-8")
    schema = json.loads(path(config["schema_file"]).read_text(encoding="utf-8"))
    cached = {r.get("cache_key"): r for r in read_jsonl(config["cache"])
              if r.get("status") in ("ok", "needs_review")}
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key and not skip_llm:
        raise RuntimeError("Thiếu GEMINI_API_KEY. Chưa gọi API, chưa tạo dự đoán giả.")
    cache_file = path(config["cache"])
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    records, started, abort_reason, new_reviews = [], now(), None, 0
    with cache_file.open("a", encoding="utf-8") as cache:
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
                if not normalize_text(row.get("comments", "")) or row.get("text_valid", "true") != "true":
                    raise ValueError("input_empty_or_invalid_text")
                if row.get("listing_match", "true") != "true":
                    raise ValueError("input_listing_mismatch")
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
                    provider = gemini_request(row, config, model, prompt, schema, api_key)
                    record.update({k: provider[k] for k in ("usage", "model_version", "api_requests")})
                    record.update(validate_response(json.loads(provider["text"])))
                    cache.write(json.dumps(record, ensure_ascii=False) + "\n")
                    cache.flush()
                    cached[fingerprint] = deepcopy(record)
            except (ValueError, ProviderError, KeyError, TypeError) as error:
                record["status"], record["sentiment"], record["aspects"] = "error", None, []
                record["error"] = str(error)[:300].replace(api_key, "[REDACTED]") if api_key else str(error)[:300]
                if isinstance(error, ProviderError):
                    record["api_requests"] = error.attempts
                    record["provider_error"] = error.details
                    if str(error) in ("http_401", "http_403", "http_404", "http_429"):
                        abort_reason = str(error)
                if provider:
                    record["raw_response"] = provider["text"][:20000]
            records.append(record)
            # Lưu sau từng review để lần chạy bị ngắt vẫn có bằng chứng và chạy tiếp bằng cache.
            write_jsonl(output, records)
            detail = "cache" if record["from_cache"] else (record["error"] or "API")
            print(f'{number}/{len(rows)} {row["review_id"]}: {record["status"]} ({detail})', flush=True)
            if record.get("provider_error"):
                print(json.dumps(record["provider_error"], ensure_ascii=False), flush=True)
            if record["api_requests"] and number < len(rows):
                time.sleep(max(0, float(config["request_interval_seconds"])))
    report = {"started_at": started, "finished_at": now(), "provider": "gemini", "model": model,
              "prompt_version": config["prompt_version"], "rows": len(records),
              "status_counts": dict(collections.Counter(r["status"] for r in records)),
              "cache_hits": sum(r["from_cache"] for r in records),
              "new_reviews_attempted": new_reviews,
              "error_counts": dict(collections.Counter(r["error"] for r in records if r["status"] == "error")),
              "provider_errors": [r["provider_error"] for r in records if r.get("provider_error")],
              "api_requests": sum(r["api_requests"] for r in records),
              "prompt_tokens_new_calls": sum(r["usage"].get("promptTokenCount", 0)
                                              for r in records if not r["from_cache"]),
              "total_tokens_new_calls": sum(r["usage"].get("totalTokenCount", 0)
                                             for r in records if not r["from_cache"]),
              "skip_llm": skip_llm}
    write_json(str(output) + ".run.json", report)
    return records


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/toronto.json")
    parser.add_argument("--input", default="data/samples/reviews_pilot.csv")
    parser.add_argument("--output", default="data/processed/llm_pilot.jsonl")
    parser.add_argument("--labels", default="data/samples/reviews_pilot_labels.csv")
    parser.add_argument("--skip-llm", action="store_true", help="Chỉ đọc cache, không gọi API")
    parser.add_argument("--refresh", action="store_true", help="Gọi lại thật, bỏ qua cache")
    parser.add_argument("--list-models", action="store_true")
    parser.add_argument("--max-new-requests", type=int, help="Giới hạn review chưa cache được gọi API (retry tính riêng)")
    parser.add_argument("--max-retries", type=int)
    parser.add_argument("--interval", type=float, help="Số giây nghỉ giữa các review gọi API")
    args = parser.parse_args(argv)
    config = load_config(args.config)
    for name, value in (("max_new_requests", args.max_new_requests), ("max_retries", args.max_retries), ("interval", args.interval)):
        if value is not None and value < 0:
            raise ValueError(name + " phải >= 0")
    if args.max_retries is not None:
        config["max_retries"] = args.max_retries
    if args.interval is not None:
        config["request_interval_seconds"] = args.interval
    if args.list_models:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("Đặt GEMINI_API_KEY trong môi trường trước; không gửi khóa vào chat.")
        print("\n".join(list_models(api_key)))
        return
    if args.skip_llm and args.refresh:
        raise ValueError("Không dùng đồng thời --skip-llm và --refresh.")
    rows = read_csv(args.input)
    dev = [r for r in rows if r.get("split") == "dev"]
    if dev and not args.skip_llm:
        labels = {key(r): r for r in manual_labels(args.labels, "dev")}
        if any(key(r) not in labels for r in dev):
            raise ValueError("Thiếu nhãn tay dev cho review pilot.")
        if any(labels[key(r)].get("comments") != r["comments"] for r in dev):
            raise ValueError("Nhãn tay dev không khớp nội dung review hiện tại.")
    records = classify(rows, config, args.output, args.skip_llm, args.refresh, args.max_new_requests)
    if all(r["status"] == "error" for r in records):
        raise RuntimeError("Không có review xử lý thành công; xem JSONL và run.json đã lưu để sửa nguyên nhân.")


if __name__ == "__main__":
    main()
