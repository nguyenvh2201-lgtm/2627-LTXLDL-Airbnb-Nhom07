# Phân tích review Toronto bằng LLM

**Inside Airbnb · Nhóm 07 · TV4**

[Sơ đồ, tra 18 hàm và các biến chính](LLM_FLOW.html) · [README toàn dự án](README.md) · [Quy tắc gán nhãn](docs/LLM_ANNOTATION_CONTRACT.md)

## Đọc code theo luồng này

| Chặng | Mở hàm nào | Dữ liệu đi tiếp |
| --- | --- | --- |
| Chọn mốc và model | `load_config()` | `cfg` ghép mặc định, profile Luna hoặc Argon và cấu hình thành phố. |
| Chọn mẫu từ review sạch | `reviews()`, `build_run_signature()` | `rows` gồm các review được chọn. `signature` nhận diện model, prompt và mẫu. |
| Dùng checkpoint hoặc gọi model | `run()`, `request_review()`, `parse_response()` | `review` là đầu vào, `prediction` là nhãn tách từ phản hồi API, `result` là bản ghi có ID và metadata để lưu JSONL. |
| Đánh giá và tổng hợp | `evaluate()`, `baseline()`, `metrics()`, `cost()` | Báo cáo sentiment và chi phí. Pipeline chuyển JSONL sang KPI để tổng hợp khía cạnh và sinh biểu đồ. |

Mốc mặc định `2026-06-15` dùng 1.000 ID cố định, gồm 20 dev, 880 analysis
và 100 test. `run_pipeline.py` gọi trực tiếp các hàm ở bảng trên.
`python -m src.llm` đi qua `main()` để chạy riêng từng tác vụ.

## Chạy nhanh trên Windows

Mở PowerShell tại gốc repo. Dùng lại `.venv` đã cài dự án hoặc xem phần cài đặt
trong [README toàn dự án](README.md).

```powershell
$python = ".\.venv\Scripts\python.exe"
$key = Read-Host "Nhap ShopAIKey" -AsSecureString
$env:SHOPAIKEY_API_KEY = [System.Net.NetworkCredential]::new("", $key).Password
& $python run_pipeline.py --config configs/city.yaml --profile luna
```

Nếu đã có đủ dữ liệu thô và checkpoint hoàn chỉnh, chạy lại với 0 request API:

```powershell
& $python run_pipeline.py --config configs/city.yaml --profile luna --skip-download --skip-llm
```

Để tiếp tục batch còn dở, dùng cùng cấu hình và profile, bỏ `--skip-llm`.
`--max-new-requests 5` giới hạn 5 lần gửi, tính cả retry. Đổi model, prompt,
tham số request hoặc mẫu có thể tạo chữ ký mới.

## Đọc kết quả

- **Checkpoint** nằm ở `data/processed/llm/<mốc>_<profile>_<chữ ký>.jsonl`.
  `ok` và `needs_review` được dùng lại khi chạy tiếp. Với `status: error`,
  xem trường `error` để phân biệt `not_attempted` với lỗi QA hoặc API.
- **Đánh giá trên nhãn tay** ghi `metrics.json` và `error_analysis.csv` trong
  `reports/llm/<mốc>_<profile>_<chữ ký>/` nếu mẫu có tập test. Điểm ở đây đo
  sentiment của LLM và baseline. KPI dùng cả sentiment lẫn khía cạnh.
- **Chi phí và KPI** xem `cost.json` trong thư mục báo cáo LLM,
  `reports/kpi_checks.csv` và các biểu đồ trong `figures/`.

Ba nhãn sentiment là `positive`, `mixed` và `negative`. Câu “Great location
but filthy room” là `mixed` với `location: positive` và
`cleanliness: negative`. Xem [workflow](LLM_FLOW.html#vidu) để lần theo ví dụ
từ text đến JSONL.

Tra tùy chọn chạy riêng bằng `python -m src.llm --help`. CLI này mặc định
Argon, còn pipeline mặc định Luna. Đặt `--profile` rõ ràng khi tái hiện kết quả.
