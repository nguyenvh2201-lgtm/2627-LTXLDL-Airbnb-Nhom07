"""I/O giữ nguyên ID và các hợp đồng dùng chung. Chỉ dùng thư viện chuẩn."""
from __future__ import annotations

import csv
import hashlib
import json
import re
from datetime import datetime, timezone
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LABELS = ("positive", "mixed", "negative")
ASPECTS = ("location", "cleanliness", "host", "value", "amenities", "noise", "safety")


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def digest(value):
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def path(value):
    value = Path(value)
    return value if value.is_absolute() else ROOT / value


def load_config(filename="configs/toronto.json"):
    with path(filename).open(encoding="utf-8") as stream:
        config = json.load(stream)
    if config["snapshot_date"] not in config["snapshots"]:
        raise ValueError("snapshot_date phải thuộc snapshots trong cấu hình.")
    return config


def read_csv(filename):
    with path(filename).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames):
            raise ValueError("CSV cần tên cột duy nhất; bảng đánh dấu dùng parser riêng.")
        result = []
        for row in reader:
            if None in row or any(v is None for v in row.values()):
                raise ValueError("CSV có hàng không khớp số cột.")
            result.append(row)
        return result


def write_csv(filename, rows, fields):
    target = path(filename)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(target)


def write_json(filename, value):
    target = path(filename)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(target)


def read_jsonl(filename):
    """Read JSONL, preserving physical line numbers in diagnostics.

    Corrupted input is rejected rather than silently truncated or skipped.
    Other TV4 stages also consume this shared function.
    """
    target = path(filename)
    if not target.exists():
        return []
    records = []
    with target.open(encoding="utf-8-sig") as stream:
        for number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                raise ValueError(
                    f"{target}: JSON không hợp lệ ở dòng {number}; "
                    "giữ file gốc để kiểm tra/phục hồi."
                ) from None
            if not isinstance(record, dict):
                raise ValueError(f"{target}: dòng {number} phải là một JSON object.")
            records.append(record)
    return records


def write_jsonl(filename, rows):
    target = path(filename)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    temporary.replace(target)


def normalize_text(text):
    # Không bỏ phủ định, dấu câu hay dịch văn bản; chỉ bỏ markup của nguồn.
    text = re.sub(r"<br\s*/?>", "\n", text or "", flags=re.I)
    text = re.sub(r"<[^>]*>", " ", text)
    return re.sub(r"\s+", " ", unescape(text)).strip()


def key(row):
    return str(row["snapshot_date"]), str(row["review_id"])


def require_unique(rows):
    keys = [key(row) for row in rows]
    if len(keys) != len(set(keys)):
        raise ValueError("Trùng khóa (snapshot_date, review_id).")


def truth(value):
    return str(value).strip().lower() in ("true", "1", "yes", "x")


def manual_labels(filename, expected_split=None):
    rows = read_csv(filename)
    required = {"snapshot_date", "review_id", "manual_sentiment", "needs_review", "note", "split"}
    if rows and not required <= rows[0].keys():
        raise ValueError("Tệp nhãn tay thiếu cột bắt buộc.")
    require_unique(rows)
    for row in rows:
        if expected_split and row["split"] != expected_split:
            raise ValueError(f"Tệp nhãn không phải split={expected_split}.")
        flag = row["needs_review"].strip().lower()
        if flag not in ("", "true", "false", "1", "0", "yes", "no", "x"):
            raise ValueError("needs_review chỉ nhận true/false (hoặc để trống nếu đã có nhãn).")
        label = row["manual_sentiment"].strip()
        if truth(flag):
            if label or not row["note"].strip():
                raise ValueError("Ca cần xem lại: để trống nhãn, needs_review=true và ghi lý do.")
        elif label not in LABELS:
            raise ValueError(f'Review {row["review_id"]}: nhãn tay còn trống hoặc không hợp lệ.')
    return rows


def file_sha256(filename):
    """Compute SHA-256 of a file without loading it all into memory."""
    import hashlib

    checksum = hashlib.sha256()
    with path(filename).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(block)
    return checksum.hexdigest()
