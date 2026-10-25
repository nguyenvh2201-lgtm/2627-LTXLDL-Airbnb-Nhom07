"""Giao tiếp Gemini qua REST (Python standard library, không cần SDK).

``build_payload`` chỉ đưa review_text vào dữ liệu người dùng; không gửi
nhãn tay. ``gemini_request`` gọi API với timeout/retry; lỗi chuẩn hóa thành
``ProviderError`` để runner ghi trạng thái error, không bịa dự đoán.
``list_models`` chỉ dùng khi người dùng chủ động yêu cầu --list-models.
"""
import http.client
import json
import re
import time
import urllib.error
import urllib.request
from urllib.parse import urlencode
from .common import normalize_text

API_ROOT = "https://generativelanguage.googleapis.com/v1beta"

class ProviderError(RuntimeError):
    def __init__(self, message, attempts, details=None):
        super().__init__(message)
        self.attempts = attempts
        self.details = details or {}

def _redact(value, api_key):
    """Remove credentials from provider-controlled nested diagnostics."""
    if isinstance(value, str):
        value = value.replace(api_key, "[REDACTED]") if api_key else value
        return re.sub(r"AIza[A-Za-z0-9_-]+", "[REDACTED]", value)
    if isinstance(value, list):
        return [_redact(item, api_key) for item in value]
    if isinstance(value, dict):
        return {_redact(key, api_key): _redact(item, api_key)
                for key, item in value.items()}
    return value


def http_details(error, api_key):
    """Keep HTTP status even if the error response is unreadable; never leak keys."""
    try:
        raw = (error.read(65536) or b"").decode("utf-8", errors="replace")
    except (OSError, http.client.IncompleteRead):
        raw = ""
    raw = _redact(raw, api_key)
    try:
        parsed = json.loads(raw)
    except ValueError:
        parsed = None
    safe = _redact(parsed, api_key)
    # JSON unicode escapes may hide keys from string replacement on raw bytes.
    # Only change the diagnostic fallback when nested values required redaction.
    if safe != parsed:
        raw = json.dumps(safe, ensure_ascii=False)
    body = safe.get("error", {}) if isinstance(safe, dict) else {}
    if not isinstance(body, dict):
        body = {}
    return {"http_status": error.code, "status": body.get("status"),
            "message": str(body.get("message", raw))[:12000],
            "details": body.get("details", []),
            "retry_after": _redact(error.headers.get("Retry-After"), api_key) if error.headers else None}


def build_payload(row, config, prompt, schema):
    """Tạo payload JSON: prompt/schema ở systemInstruction, chỉ gửi review_text.

    responseMimeType=application/json KHÔNG thay cho validate_response phía Python.
    """
    payload = {
        "systemInstruction": {"parts": [{"text": prompt + "\nOUTPUT JSON SCHEMA:\n" + json.dumps(schema)}]},
        "contents": [{"role": "user", "parts": [{"text": json.dumps({
            "review_text": normalize_text(row["comments"])
        }, ensure_ascii=False)}]}],
        "generationConfig": {"responseMimeType": "application/json",
                             "temperature": config["temperature"],
                             "maxOutputTokens": config["max_output_tokens"]}
    }
    return payload


def gemini_request(row, config, model, prompt, schema, api_key):
    """Thực hiện 1 review; retry HTTP/mạng theo config, trả text/usage/calls.

    Retry có thể tạo thêm request; max_new_requests ở runner chỉ giới hạn
    số review mới, không phải số lần HTTP khi mạng có lỗi.
    """
    if not re.fullmatch(r"[A-Za-z0-9._-]+", model):
        raise ValueError("Tên model không hợp lệ; dùng ID model, bỏ tiền tố models/.")
    payload = build_payload(row, config, prompt, schema)
    request = urllib.request.Request(API_ROOT + f"/models/{model}:generateContent",
              data=json.dumps(payload).encode("utf-8"), method="POST",
              headers={"Content-Type": "application/json", "x-goog-api-key": api_key})
    max_retries = int(config["max_retries"])
    for attempt in range(max_retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=config["timeout_seconds"]) as response:
                body = json.load(response)
            if not isinstance(body, dict):
                raise ProviderError("provider_invalid_response", attempt + 1)
            candidates = body.get("candidates", [])
            if not candidates:
                raise ProviderError("empty_or_blocked_response", attempt + 1)
            if not isinstance(candidates, list) or not isinstance(candidates[0], dict):
                raise ProviderError("provider_invalid_response", attempt + 1)
            candidate = candidates[0]
            if candidate.get("finishReason") != "STOP":
                raise ProviderError("finish_reason_" + str(candidate.get("finishReason", "missing")), attempt + 1)
            content = candidate.get("content", {})
            parts = content.get("parts", []) if isinstance(content, dict) else None
            if not isinstance(parts, list) or any(not isinstance(p, dict) or not isinstance(p.get("text", ""), str) for p in parts):
                raise ProviderError("provider_invalid_response", attempt + 1)
            text = "".join(p.get("text", "") for p in parts if not p.get("thought", False))
            usage = body.get("usageMetadata")
            if not isinstance(usage, dict):
                usage = {}
            return {"text": text, "usage": usage,
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
        except (urllib.error.URLError, TimeoutError, OSError, http.client.IncompleteRead) as error:
            if attempt == max_retries:
                raise ProviderError("network_or_timeout", attempt + 1) from None
            time.sleep(min(60, 2 ** attempt))
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise ProviderError("provider_invalid_json", attempt + 1) from None
    raise AssertionError("unreachable")

def list_models(api_key):
    """Liệt kê ID model tài khoản được phép generateContent (có gọi API)."""
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
