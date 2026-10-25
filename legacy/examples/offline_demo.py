"""Demo độc lập KHÔNG gọi Gemini / KHÔNG chạm cache thật.

Chạy tại gốc repo: python examples/offline_demo.py
Đầu ra demo: examples/_demo_output/llm_demo.jsonl và .run.json
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.common import load_config, path, read_csv, read_jsonl, write_jsonl  # noqa: E402
from src.llm import cache_key, classify  # noqa: E402


def main():
    rows = read_csv(ROOT / "examples" / "reviews_demo.csv")
    config = dict(load_config("configs/toronto.json"))
    config["model"] = "gemini-demo-offline"  # Chỉ ID giả lập, không phải model thật.
    config["request_interval_seconds"] = 0
    output = ROOT / "examples" / "_demo_output" / "llm_demo.jsonl"
    output.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="tv4_llm_offline_") as directory:
        config["cache"] = str(Path(directory) / "synthetic_cache.jsonl")
        prompt = path(config["prompt_file"]).read_text(encoding="utf-8")
        schema = json.loads(path(config["schema_file"]).read_text(encoding="utf-8"))
        first = rows[0]
        synthetic_cached = {
            "snapshot_date": first["snapshot_date"],
            "review_id": first["review_id"],
            "listing_id": first["listing_id"],
            "cache_key": cache_key(first, config, config["model"], prompt, schema),
            "status": "ok",
            "sentiment": "positive",
            "aspects": [],
            "language": "en",
            "error": None,
            "usage": {},
            "api_requests": 1,
        }
        write_jsonl(config["cache"], [synthetic_cached])
        old_hash = hashlib.sha256(Path(config["cache"]).read_bytes()).hexdigest()
        # Chạy hoàn toàn offline; ngay cả khi biến môi trường có key thật cũng không gọi API.
        with patch.dict(os.environ, {"GEMINI_MODEL": config["model"]}):
            records = classify(rows, config, str(output), skip_llm=True)
        new_hash = hashlib.sha256(Path(config["cache"]).read_bytes()).hexdigest()
        assert old_hash == new_hash, "DEMO FAILED: synthetic cache changed"

    report = json.loads(Path(str(output) + ".run.json").read_text(encoding="utf-8"))
    assert len(records) == 3
    assert report["cache_hits"] == 1 and report["api_requests"] == 0
    assert records[0]["status"] == "ok" and records[0]["from_cache"] is True
    assert records[1]["error"] == "cache_miss_skip_llm"
    assert records[2]["error"] == "input_listing_mismatch"
    assert len(read_jsonl(output)) == 3
    print("\nDEMO PASS — 3 review, 1 cache hit, 1 cache miss, 1 QA error, 0 API calls.")
    print("Output:", output)
    print("Report:", str(output) + ".run.json")
    print("Cache dự án KHÔNG bị đọc hoặc thay đổi; cache demo tạm đã tự dọn.")


if __name__ == "__main__":
    main()
