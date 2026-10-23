"""Quy tắc dữ liệu LLM: phân loại hợp lệ, cache key, cache trùng.

``validate_response``: chỉ chấp nhận đúng schema nhãn đã chốt.
``cache_key``: hash đầu vào + cấu hình; đổi prompt/model => cache miss.
``index_cache_records``: khi trùng fingerprint, ưu tiên dòng hợp lệ cuối.
Không được thay đổi hàm băm/taxonomy tùy tiện: cache cũ phải tái dùng được.
"""
import re
from .common import ASPECTS, LABELS, digest, normalize_text

MODEL_FIELDS = {"sentiment", "aspects", "language", "status", "error"}


def validate_review_rows(rows):
    """Báo rõ trường bắt buộc còn thiếu trước khi hash hoặc gọi API.

    Không sửa dữ liệu hay cờ QA; comments rỗng vẫn do runner xử lý.
    """
    required = {"snapshot_date", "review_id", "listing_id", "comments"}
    for number, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            raise ValueError(f"Review thứ {number} phải là một bản ghi dạng object.")
        missing = sorted(required - row.keys())
        if missing:
            raise ValueError(f"Review thứ {number} thiếu cột bắt buộc: {', '.join(missing)}.")


def validate_response(value):
    """Kiểm tra JSON do mô hình trả; raises ValueError nếu sai contract.

    ``needs_review`` = mô hình không chắc, KHÔNG phải lỗi kỹ thuật ``error``.
    """
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
    """Fingerprint SHA-256: review + snapshot + model + prompt/schema/params.

    Nếu bất cứ đầu vào quan trọng nào đổi, kết quả cache cũ không được reuse.
    """
    return digest({"provider": "gemini", "model": model,
                   "prompt_version": config["prompt_version"], "prompt": prompt,
                   "schema": schema, "temperature": config["temperature"],
                   "max_output_tokens": config["max_output_tokens"],
                   "snapshot_date": row["snapshot_date"], "review_id": row["review_id"],
                   "listing_id": row["listing_id"], "text": normalize_text(row["comments"])})



def index_cache_records(records):
    """Giữ bản cuối; riêng fingerprint trùng ưu tiên bản hợp lệ cuối.

    Nếu không có bản hợp lệ, giữ dòng cuối như trước để caller tiếp tục
    báo lỗi schema ban đầu. Cache chỉ được đọc, không bị sửa.
    """
    index = {}
    duplicate_valid = {}
    for record in records:
        if record.get("status") not in ("ok", "needs_review"):
            continue
        fingerprint = record.get("cache_key")
        if fingerprint in index:
            if fingerprint not in duplicate_valid:
                previous = index[fingerprint]
                try:
                    validate_response({field: previous[field] for field in MODEL_FIELDS})
                    duplicate_valid[fingerprint] = previous
                except (ValueError, KeyError, TypeError):
                    duplicate_valid[fingerprint] = None
            try:
                validate_response({field: record[field] for field in MODEL_FIELDS})
                duplicate_valid[fingerprint] = record
            except (ValueError, KeyError, TypeError):
                pass
        index[fingerprint] = record
    for fingerprint, valid in duplicate_valid.items():
        if valid is not None:
            index[fingerprint] = valid
    return index
