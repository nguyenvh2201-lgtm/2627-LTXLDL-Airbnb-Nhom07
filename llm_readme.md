# Phân tích review Toronto bằng LLM

**Inside Airbnb · Nhóm 07 · TV4**

[Sơ đồ workflow](LLM_FLOW.html) · [README toàn dự án](README.md) · [Quy tắc gán nhãn](docs/LLM_ANNOTATION_CONTRACT.md)

Phần LLM lấy review đã qua QA, gán nhãn cảm xúc và khía cạnh, rồi lưu kết quả
để đánh giá trên nhãn tay và tính KPI. `run_pipeline.py` điều phối toàn bộ quy
trình. `python -m src.llm` cung cấp các lệnh chạy riêng phần LLM.

## 1. Chạy trên Windows

Mở PowerShell tại thư mục gốc repo. Dùng Python 3.12 theo phiên bản trong
`.python-version`. Nếu đã cài môi trường dự án, dùng lại `.venv` hiện có.

```powershell
python -m venv .venv
$python = ".\.venv\Scripts\python.exe"
& $python -m pip install -r requirements.txt
```

**Chạy từ dữ liệu nguồn.** Khi cần gọi API, nhập khóa ShopAIKey ở PowerShell.
Lệnh sau đặt khóa cho phiên terminal hiện tại.

```powershell
$key = Read-Host "Nhap ShopAIKey" -AsSecureString
$env:SHOPAIKEY_API_KEY = [System.Net.NetworkCredential]::new("", $key).Password
& $python run_pipeline.py --config configs/city.yaml --profile luna
```

**Chạy lại từ checkpoint hoàn chỉnh.** Lệnh này cần dữ liệu thô đã tải và
checkpoint khớp cấu hình. Pipeline vẫn chạy QA, đánh giá nếu có tập test,
tính chi phí ước lượng, tính KPI và sinh biểu đồ.

```powershell
& $python run_pipeline.py --config configs/city.yaml --profile luna --skip-download --skip-llm
```

| Tham số | Dùng khi |
| --- | --- |
| `--profile luna` hoặc `--profile argon` | Chọn model. `run_pipeline.py` mặc định Luna. |
| `--skip-download` | Dữ liệu thô của các mốc cấu hình đã có trên máy. |
| `--max-new-requests 5` | Giới hạn tối đa 5 lần gửi request mới trong lượt chạy, tính cả retry. Nếu batch còn review chưa xử lý, pipeline dừng sau khi lưu checkpoint. |
| `--skip-llm` | Dùng checkpoint có sẵn và chỉ đọc ở bước LLM. Cần checkpoint hoàn chỉnh để pipeline chạy tiếp đến KPI. |

## 2. Dữ liệu đi qua những bước nào?

1. **Cấu hình và QA.** `configs/city.yaml` liệt kê bốn snapshot để tải và làm
   sạch. `snapshot_date` chọn mốc phân tích LLM. Đầu vào LLM mặc định là
   `data/processed/<mốc>/reviews_clean.csv`.
2. **Chọn mẫu.** Mốc `2026-06-15` dùng `data/samples/llm_review_ids.csv`,
   gồm 20 review dev, 880 review phân tích và 100 review test. Khi đổi
   `snapshot_date` sang mốc khác trong pipeline, mẫu được chọn theo seed.
3. **Gán nhãn.** `src/llm.py` chứa prompt, profile Luna và Argon. Hàm
   `request_review()` gửi văn bản review và prompt. Phản hồi được đọc,
   kiểm tra schema và gộp khía cạnh trùng theo quy tắc gán nhãn.
4. **Đánh giá và tổng hợp.** Pipeline so sánh sentiment của LLM và baseline
   từ khóa với nhãn tay nếu mẫu có tập test. KPI dùng kết quả JSONL để tổng
   hợp sentiment và khía cạnh, sau đó pipeline sinh biểu đồ.

Ba nhãn cảm xúc là `positive`, `mixed`, `negative`. `mixed` nghĩa là có cả
khen và chê đáng kể. Một review chỉ kể sự kiện hoặc thiếu căn cứ có thể nhận
`needs_review` với sentiment rỗng. Nếu API trả cùng một khía cạnh với các
polarity khác nhau, bộ đọc gộp thành một khía cạnh có polarity `mixed`.

## 3. Checkpoint, lỗi và cách chạy tiếp

Checkpoint là JSONL lưu một bản ghi cho mỗi review trong mẫu. Signature
nhận diện model, prompt, tham số request và mẫu đầu vào. Để tiếp tục batch
đang dở, chạy lại cùng mốc, profile và cấu hình, bỏ `--skip-llm` nếu đã dùng.

| Dấu hiệu | Ý nghĩa |
| --- | --- |
| `ok` | Dự đoán hợp lệ. Lượt chạy tiếp dùng lại kết quả này. |
| `needs_review` | Model đã trả về kết quả hợp lệ nhưng review thiếu căn cứ gán nhãn. Lượt chạy tiếp cũng dùng lại bản ghi này. |
| `error: not_attempted` | Review còn trong mẫu và chưa được xử lý. Bộ đếm `status_counts.error` bao gồm cả những review này. |
| `http_502`, `http_503`, `http_504` | Lỗi gateway. Runner có thể thử lại tối đa hai lần, chờ 5 rồi 10 giây, trong giới hạn request còn lại. |
| `http_429` | API trả 429. Runner lưu checkpoint và dừng. Kiểm tra hạn mức dịch vụ trước khi tiếp tục. |

Sau khi chạy lại bằng checkpoint, xem `cache_hits`, `api_requests_this_run` và
`status_counts`. Một lượt đọc lại đủ 1.000 bản ghi của mẫu cố định sẽ báo
`cache_hits: 1000` và `api_requests_this_run: 0`.

## 4. Các đầu ra cần đọc

| File mặc định | Nội dung |
| --- | --- |
| `data/processed/llm/<mốc>_<profile>_<signature>.jsonl` | Checkpoint từ `run_pipeline.py`. |
| `reports/llm/<mốc>_<profile>_<signature>/metrics.json` | Coverage, accuracy, Macro-F1 và F1 từng lớp cho LLM và baseline trên tập test. |
| `reports/llm/<mốc>_<profile>_<signature>/error_analysis.csv` | Review có dự đoán LLM hoặc baseline khác nhãn tay. |
| `reports/llm/<mốc>_<profile>_<signature>/cost.json` | Chi phí ước lượng từ usage đã lưu. |
| `reports/kpi_checks.csv` và `figures/` | Kết quả kiểm tra KPI và biểu đồ. |

`evaluate` đo chất lượng **sentiment**. Các khía cạnh được tổng hợp thành KPI.
Baseline dùng từ khóa tiếng Anh và xử lý phủ định đơn giản. Dự đoán thiếu hoặc
`unclassified` vẫn nằm trong mẫu số khi tính accuracy.

## 5. Chạy riêng phần LLM và kiểm thử

Các lệnh dưới đây chạy từ gốc repo. `baseline` cần review đã qua QA.
`run` cần API key nếu có review phải gọi mới. `evaluate` và `cost` đọc JSONL
đã lưu. Hãy giữ cùng profile, cấu hình và `--output` cho cả ba lệnh.
Ở CLI chạy riêng, đặt `--profile` rõ ràng vì mặc định của `src.llm` là Argon.

```powershell
$output = "data/processed/llm/luna_standalone.jsonl"
& $python -m src.llm baseline --config configs/city.yaml --profile luna
& $python -m src.llm run --config configs/city.yaml --profile luna --output $output
& $python -m src.llm evaluate --config configs/city.yaml --profile luna --output $output
& $python -m src.llm cost --config configs/city.yaml --profile luna --output $output
& $python -m unittest discover -s tests
```

`evaluate` mặc định dùng `data/samples/reviews_test_labels.csv`.
Thêm `--city-reviews <tổng_review>` vào lệnh `cost` để ước tính chi phí cho
toàn thành phố. Bộ unit test chạy với phản hồi API giả lập.
