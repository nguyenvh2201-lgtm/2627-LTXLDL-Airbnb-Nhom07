# BTL Inside Airbnb — UET.DSE2049 4, nhóm 7

Phân tích Toronto (CAD) với bốn snapshot: **2025-09-11, 2026-03-19,
2026-06-15, 2026-09-16**. Giữ mốc cuối theo lựa chọn ngày 11/11/2026;
mốc này thiếu 72 listing và 235 review so với danh sách được giao.

## Cấu trúc theo đề

```text
.
├── configs/
│   └── city.yaml
├── data/
│   ├── raw/                 # dữ liệu tải, không commit
│   ├── processed/           # Parquet, KPI, cache và kết quả LLM
│   └── samples/             # CSV phân công, ID, vùng và nhãn tay
├── src/
│   ├── download.py          # cấu hình, tiện ích, tải, xác thực và lọc
│   ├── qa.py                # làm sạch, cờ QA và từ điển dữ liệu
│   ├── kpi.py               # KPI vùng, thời gian và LLM
│   ├── llm.py               # Gemini, JSON schema, retry, cache
│   ├── baseline.py          # đối chứng từ điển đa ngôn ngữ
│   ├── evaluate.py          # mẫu nhãn trống, đánh giá và phân tích lỗi
│   └── viz.py               # hình, bảng tổng hợp và báo cáo PDF/Markdown
├── figures/
├── reports/
├── notebooks/               # tài liệu, kiểm thử và công cụ kiểm tra tùy chọn
├── run_pipeline.py
├── .python-version
├── .env.example
├── .gitignore
├── AI_USAGE.md
├── README.md
└── requirements.txt
```

Prompt nằm trong `llm.prompt_text`, từ điển en/fr/es/pt nằm trong
`baseline.lexicons` của `configs/city.yaml`. CSV gốc được giữ tại
`data/samples/data-new.csv`. Không còn thư mục `tools`, `tests`, `prompts`,
`report` ở gốc hoặc các mô-đun phụ trong `src`.

`notebooks/tests/` và `notebooks/tools/` giữ bộ kiểm chứng, không tham gia
pipeline chính. Kế hoạch gốc giữ trong `notebooks/PLAN.md` để đối chiếu lịch sử;
đường dẫn chạy hiện hành lấy theo README này.
`.git`, `.venv`, `.vscode` và cache Python là thành phần cục bộ, không thuộc bộ tệp nộp.

## Cài đặt và chạy

Phiên bản đã kiểm thử: **Python 3.13.7**, ghi tại `.python-version`.
`requirements.txt` ghim phiên bản thư viện. Nên có 4 GB RAM và 2 GB đĩa trống;
calendar đọc từng khối theo `io.chunksize` trong cấu hình.

PowerShell, chạy trong thư mục gốc dự án:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run_pipeline.py --config configs/city.yaml
```

Nếu raw đã có và chưa cần gọi API:

```powershell
.\.venv\Scripts\python.exe run_pipeline.py --config configs/city.yaml --skip-download --skip-llm
```

`--skip-download` vẫn kiểm gzip/CRC, cột bắt buộc và SHA256. `--skip-llm` dùng
cache thật nếu có; phần chưa có dự đoán để trống. Pipeline hoàn thành không
đồng nghĩa phần LLM và đánh giá đã đủ dữ liệu.

Luồng đầy đủ:
`download (gồm filter) → qa → kpi → llm → baseline → evaluate → kpi → viz (gồm summary/report)`.

Linux/macOS thay đường dẫn Python bằng `.venv/bin/python`.

## Nhãn tay và Gemini

Tạo/cập nhật mẫu gán nhãn (pipeline đầy đủ cũng gọi bước này):

```powershell
.\.venv\Scripts\python.exe run_pipeline.py --config configs/city.yaml --only labels
```

`data/samples/hand_labels_template.csv` hiện có 100 review ban đầu và 50 review
bổ sung được ưu tiên vì baseline hoặc câu chữ gợi ý `negative`/`mixed`. Cột
`selection_hint` chỉ ghi cách chọn mẫu, **không phải nhãn đúng**. 100 dòng đầu do
người dùng tự gán đã được chuẩn hóa cú pháp khía cạnh; giá trị gốc giữ trong
`original_aspects_*`, mục ngoài bảy khía cạnh cấu hình giữ trong `other_aspects_*`.
50 dòng cuối đã được AI điền bản nháp vào `sentiment`, khía cạnh và ngôn ngữ;
các cột `suggested_*` giữ lại gợi ý gốc để đối chiếu. Chúng có
`label_source=AI_draft`, không tính là nhãn tay. Nhóm cần đọc và xác nhận từng
review rồi đổi `label_source` thành `user_manual`. Sau khi kiểm tra toàn bộ, lưu thành
`data/samples/hand_labels.csv`. Giữ ID dạng Text khi
dùng Excel để tránh làm tròn. Chạy lại bước `labels` giữ các nhãn và 50 dòng bổ
sung trong template; tệp `hand_labels.csv` không bị ghi đè. Không dùng dự đoán
baseline/LLM làm gold. Mẫu bổ sung được chọn có chủ đích nên tỷ lệ lớp trong 150
review không đại diện cho toàn bộ review thành phố.
Nếu chưa tạo `hand_labels.csv`, bước đánh giá dùng 100 dòng `user_manual` trong
template; 50 dòng `AI_draft` không được tính. Chỉ xuất chỉ số so sánh khi đã có
dự đoán Gemini hợp lệ.

Khía cạnh trong `aspects_praise`/`aspects_complaint` dùng mảng JSON như
`["cleanliness"]`; `[]` nghĩa đã kiểm và không có khía cạnh, trống nghĩa chưa gán.
Language tùy chọn: mã hai chữ hoặc `und`. Mã đánh giá từ chối dòng
`label_source=AI_draft` để không khai dự đoán AI thành nhãn tay.

Khóa chỉ đọc từ biến môi trường; pipeline **không tự đọc `.env`**:

Trước khi chạy Gemini, cần có `data/processed/<mốc>/reviews_clean.csv`
do `python src/qa.py` tạo ra. Dùng Python trong `.venv` vì môi trường
`(base)` có thể thiếu `pyarrow` và `langdetect`.

Nhập hàm dưới đây vào PowerShell **trước khi** sao chép khóa. Sau đó bấm
**Copy** trên chính khóa trong Google AI Studio, trở lại PowerShell và **gõ tay**
`Set-GeminiKey` rồi Enter; copy thêm lệnh khác sẽ ghi đè clipboard.

```powershell
function Set-GeminiKey {
    $copied = (Get-Clipboard -Raw).Trim()
    if ($copied -notmatch '^[\x21-\x7E]+$') { throw "Clipboard không chứa khóa API nguyên vẹn" }
    $env:GEMINI_API_KEY = $copied
    Write-Host "Đã nạp khóa, độ dài: $($copied.Length)"
}
```

Khi đã nạp khóa, thử một review, rồi tăng lên 20. Chỉ chạy toàn bộ khi mẫu thử
có dự đoán Gemini hợp lệ:

```powershell
.\.venv\Scripts\python.exe run_pipeline.py --config configs/city.yaml --only llm --limit 1
.\.venv\Scripts\python.exe run_pipeline.py --config configs/city.yaml --only llm --limit 20
.\.venv\Scripts\python.exe run_pipeline.py --config configs/city.yaml --only llm,baseline,evaluate,kpi,figures
```

Lần chạy thử chỉ xuất mẫu giới hạn; lần tiếp theo không có `--limit` sẽ xử lý
đủ mẫu và dùng lại cache hợp lệ. Không đưa khóa thật vào Git hoặc nhật ký AI.
Với cấu hình lô 10 và 5 request/phút, 1.000 review cần khoảng 20 phút trở lên,
chưa kể retry/quota. Model và giá là cấu hình đã ghi ngày tham khảo; kiểm lại
trước khi gọi API. Chi phí trong báo cáo là ước tính, không phải hóa đơn.

Có thể chạy từng mô-đun, ví dụ:

```powershell
.\.venv\Scripts\python.exe -m src.qa --config configs/city.yaml
```

`--only` nhận danh sách bước theo đúng thứ tự nhập. Ngoài bảy mô-đun chính,
còn các bước phụ `filter`, `labels`, `figures`, `summary`, `report` để chạy riêng
chức năng đã gộp. Chạy riêng cần có dữ liệu từ các bước trước.

## Đầu ra và giới hạn phân tích

- `data/processed/*_raw_filtered.parquet`: bảng đã lọc, đầu vào QA.
- `data/processed/<snapshot>/listings_clean.csv`, `reviews_clean.csv`,
  `calendar_flagged.csv`: bảng sau QA và cờ kiểm tra. Các bước sau đọc trực tiếp
  các tệp này, không tạo thêm Parquet sạch trùng nội dung.
- `data/processed/kpi_area.csv`, `kpi_time.csv`, `kpi_llm.csv`: KPI.
- `data/processed/llm_sample.parquet`, `llm_results.parquet`, `llm_cache.jsonl`,
  `baseline_results.parquet`: mẫu và dự đoán.
- `reports/`: manifest, kiểm lọc/ID thiếu, QA, định nghĩa KPI, đánh giá, chi phí,
  số liệu tổng hợp, `report.pdf`, `report.md`, log và checklist.
- `figures/`: 3 hình không gian, 3 hình thời gian và 5 hình LLM khi đủ dữ liệu.

Chưa có gold thì chưa có đánh giá thật; chưa có API/cache thì K7 chưa có số liệu.
Xem `reports/figure_status.csv` và chạy công cụ checklist để biết phần thiếu.

Giá listing chỉ dùng mốc cuối; loại giá thiếu/ngoài ngưỡng khỏi KPI giá.
Ngày không khả dụng có thể do chủ nhà khóa lịch, không đồng nghĩa booking.
K5 chỉ mô tả review trong mẫu, không ngoại suy toàn thành phố. KPI không gian
theo `neighbourhood_cleansed`; bản đồ tám vùng mẫu là hình chữ nhật phân tích,
không phải địa giới hành chính. Không suy quốc tịch từ ngôn ngữ.
ID lặp giữa snapshot là bình thường; LLM dùng bản mới nhất của mỗi review ID.
QA chủ yếu gắn cờ; KPI trước/sau là tác động giả định loại riêng dòng bị từng cờ.
Baseline fallback positive là giả định, không học từ gold.

Đánh giá gồm accuracy, macro-F1, precision/recall/F1 từng lớp, bootstrap,
confusion matrix, coverage và so sánh ghép cặp. Nhóm tự đọc lỗi và viết nguyên nhân;
gợi ý tự động không phải kết luận nguyên nhân thật.

## Kiểm tra

```powershell
.\.venv\Scripts\python.exe -m pytest -c notebooks/pytest.ini -q --junitxml=reports/test_results.xml
.\.venv\Scripts\python.exe notebooks/tools/check_config_swap.py
.\.venv\Scripts\python.exe notebooks/tools/check_report_numbers.py
.\.venv\Scripts\python.exe notebooks/tools/check_security.py
.\.venv\Scripts\python.exe notebooks/tools/check_submission.py
```

Fixtures/API mock không tốn quota và chỉ ghi dữ liệu tổng hợp trong thư mục tạm.
Công cụ `notebooks/tools/inspect_ids.py` kiểm và xuất lại bốn CSV phân công.
`notebooks/tools/clean_reproduce.py --prepare` chuẩn bị clone local trong
`notebooks/.work/clean-repro`; `--compare` đối chiếu sau khi chạy pipeline ở đó.
Đây là kiểm mã làm việc, không thay việc clone bản nộp cuối từ GitHub.

Đổi thành phố/mốc bằng config; `expected.by_snapshot` chỉ giữ kỳ vọng đã xác minh.
Mốc chưa có kỳ vọng chỉ cảnh báo số lượng; lỗi ID trùng/ngày sai vẫn dừng.

## Phần nhóm phải hoàn thiện và nộp

1. Xác nhận bên đặt hàng, KPI và lý do chọn ngưỡng QA.
2. Tự gán 100 nhãn tay, chạy Gemini thật đủ mẫu, kiểm kết quả và lỗi.
3. Viết nhận định, giải thích hạn chế và hoàn thiện báo cáo tối đa 10 trang.
4. Cập nhật AI_USAGE, chạy kiểm tra, xác nhận quyền repo/mời giảng viên và nộp liên kết.
5. Kiểm nhánh bằng `git branch --show-current`, kiểm `git status`, rồi commit,
   tạo tag final và push đúng nhánh theo quy trình nhóm.

`reports/report.pdf` và `reports/report.md` là đầu ra tự động từ `src/viz.py`.
Markdown không phải đầu vào dựng PDF. Nếu sửa tay Markdown, giữ bản riêng trước
khi chạy lại `viz`/`report`, hoặc sửa nội dung bộ sinh báo cáo. Bản hiện tại còn TODO.
HEAD ghi trong báo cáo là commit tại lúc dựng, không tự động là commit/tag final.
Checklist có mục xác nhận thủ công, cần đối chiếu thực tế trên GitHub.
Không commit raw, `.env`, khóa, `.venv`; processed chỉ commit nếu dưới 50 MB.
Hiện các CSV calendar sau QA đã được Git theo dõi và toàn bộ `data/processed/`
vượt 50 MB. `.gitignore` chặn tệp mới nhưng không bỏ theo dõi tệp cũ; cần bỏ
theo dõi chúng trước khi nộp, vẫn giữ tệp trên máy để chạy lại.

Nguồn dữ liệu: Inside Airbnb, CC BY 4.0. URL, SHA256 và thời điểm xác thực
nằm trong `reports/download_manifest.csv`; file có sẵn không bịa thời điểm tải.

## Báo cáo tác động QA

Bước QA xuất `reports/qa_impact.csv`, so sánh trung vị và trung bình giá
khi giữ toàn bộ giá hợp lệ với khi loại giá bị cờ `price_outlier` khỏi phép tính.
Hai phía chỉ dùng giá hữu hạn và > 0; giá thiếu/sai không thuộc mẫu tham chiếu.
Bảng có kết quả theo mốc, khu vực `kpi.area_col` và loại phòng. Ngưỡng IQR
vẫn lấy theo loại phòng trong từng mốc, không tính lại theo khu vực.

`n_before`/`n_after` là cỡ mẫu tính giá, `n_excluded` là số giá ngoại lai bị
loại khỏi phép tính, `n_invalid_or_missing` là số giá không đủ điều kiện ban đầu.
`n_iqr_uncheckable` là số giá hợp lệ chưa đủ căn cứ xét IQR và vẫn được giữ.
`delta = value_after - value_before`; `delta_pct = delta / value_before * 100`.
Nhóm không có giá hợp lệ có kết quả trống; không thay bằng 0. Đây là phép so sánh
tác động, không xóa dòng khỏi listings và không kết luận giá ngoại lai là sai.

K4 theo vùng và toàn thành phố dùng `minimum_nights_valid` của QA làm điều kiện
chọn mẫu: số nguyên dương hữu hạn, không min > max và không vượt
`qa.min_nights_cap`. Listing không đủ điều kiện không thuộc mẫu số K4.
