"""Cửa vào phần gắn nhãn review bằng LLM (Gemini).

Lệnh chạy cho cả nhóm: ``python run_tv4.py llm --help``.
File này chỉ đọc tham số và gọi ``llm_runner.classify``:
- ``llm_contract.py`` kiểm tra nhãn và tính fingerprint cache.
- ``gemini_client.py`` thực hiện HTTP Gemini, retry và báo lỗi.
- ``llm_runner.py`` duyệt review, tận dụng cache, ghi JSONL và thống kê.
- ``cache_audit.py`` là lệnh RIÊNG kiểm tra tương thích cache/QA.

Không cần hiểu các module phụ để chạy CLI; nhưng PHẢI giữ chúng cùng
thư mục ``src/`` vì Python import chúng. Xem ``llm_readme.md`` và
``LLM_FLOW.html`` để học từng bước. File này không đọc nhãn người.
"""
import argparse
import json
import os
from .common import load_config, path, read_csv
from .gemini_client import ProviderError, build_payload, gemini_request, list_models
from .llm_contract import MODEL_FIELDS, cache_key, validate_response, validate_review_rows
from .llm_runner import classify as _classify


def classify(rows, config, output, skip_llm=False, refresh=False, max_new_requests=None):
    """Điểm gọi batch cho CLI và test; hành vi thật nằm trong llm_runner.

    ``skip_llm=True``: không gửi request, chỉ lấy dự đoán khớp cache.
    ``refresh=True``: bỏ qua cache (có thể tốn quota API).
    """
    # Giữ API cũ cho run_tv4.py và unit test; client có thể được giả lập trong test.
    return _classify(rows, config, output, skip_llm, refresh, max_new_requests, request_fn=gemini_request)


def main(argv=None):
    """Xử lý tham số dòng lệnh; không ghi dữ liệu khi dùng --help/--show-request."""
    # Đường dẫn --input/--output nhận CSV review và trả JSONL có status.
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/toronto.json")
    parser.add_argument("--input", default="data/samples/reviews_pilot.csv")
    parser.add_argument("--output", default="data/processed/llm_pilot.jsonl")
    parser.add_argument("--labels", default="data/samples/reviews_pilot_labels.csv", help="Giữ tương thích CLI cũ; llm không đọc nhãn tay. Dùng evaluate để đối chiếu.")
    parser.add_argument("--skip-llm", action="store_true", help="Chỉ đọc cache, không gọi API")
    parser.add_argument("--refresh", action="store_true", help="Gọi lại thật, bỏ qua cache")
    parser.add_argument("--list-models", action="store_true")
    parser.add_argument("--max-new-requests", type=int, help="Giới hạn review chưa cache được gọi API (retry tính riêng)")
    parser.add_argument("--max-retries", type=int)
    parser.add_argument("--interval", type=float, help="Số giây nghỉ giữa các review gọi API")
    parser.add_argument("--show-request", action="store_true", help="In payload không kèm khóa; không gọi API")
    parser.add_argument("--review-id", help="Chọn review khi dùng --show-request")
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
    if not args.show_request:
        targets = {path(args.output).resolve(), path(args.output + ".run.json").resolve()}
        if targets & {path(args.input).resolve(), path(args.config).resolve()}:
            raise ValueError("Output/báo cáo không được ghi đè CSV đầu vào hoặc cấu hình.")
    rows = read_csv(args.input)
    if args.show_request:
        validate_review_rows(rows)
        selected = [r for r in rows if args.review_id is None or r["review_id"] == args.review_id]
        if not selected:
            raise ValueError("Không tìm thấy review để xem payload.")
        prompt = path(config["prompt_file"]).read_text(encoding="utf-8")
        schema = json.loads(path(config["schema_file"]).read_text(encoding="utf-8"))
        print(json.dumps(build_payload(selected[0], config, prompt, schema), ensure_ascii=False, indent=2))
        return
    # Nhãn người chỉ được đọc ở evaluate, không dùng để chọn/giữ dự đoán LLM.
    records = classify(rows, config, args.output, args.skip_llm, args.refresh, args.max_new_requests)
    if all(r["status"] == "error" for r in records):
        raise RuntimeError("Không có review xử lý thành công; xem JSONL và run.json đã lưu để sửa nguyên nhân.")

if __name__ == "__main__":
    main()
