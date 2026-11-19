# BTL Inside Airbnb — UET.DSE2049 4, Nhóm 07

Phân tích thị trường Airbnb Toronto (CAD) qua 4 mốc chụp dữ liệu: **2025-09-11, 2026-03-19, 2026-06-15, 2026-09-16**.

---

## 1. Môi trường và Phiên bản Python

- **Phiên bản Python bắt buộc:** Tham chiếu tệp [`.python-version`](file:///.python-version) ghi nhận **Python 3.13.7**.
- **Hệ điều hành hỗ trợ:** Windows (PowerShell), macOS/Linux (Bash).
- **Yêu cầu tài nguyên tối thiểu:** RAM ≥ 4 GB, dung lượng đĩa trống ≥ 3 GB (xử lý dữ liệu bảng lịch lớn đọc theo chunk).
- **Thư viện phụ thuộc:** Đã được khóa phiên bản chính xác tại [`requirements.txt`](file:///requirements.txt) (gồm `pandas`, `pyarrow`, `matplotlib`, `scikit-learn`, `requests`, `reportlab`, `pypdf`, `pytest`, `pyyaml`, `langdetect`).

---

## 2. Hướng dẫn Cài đặt Môi trường (Setup)

### Trên Windows (PowerShell):
```powershell
# 1. Tạo môi trường ảo theo phiên bản Python 3.13.7
python -m venv .venv

# 2. Kích hoạt môi trường ảo
.\.venv\Scripts\Activate.ps1

# 3. Nâng cấp pip và cài đặt toàn bộ thư viện phụ thuộc
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Trên macOS / Linux (Bash):
```bash
# 1. Tạo môi trường ảo
python3 -m venv .venv

# 2. Kích hoạt môi trường ảo
source .venv/bin/activate

# 3. Cài đặt thư viện phụ thuộc
pip install --upgrade pip
pip install -r requirements.txt
```

> [!IMPORTANT]
> **Lưu ý trên Windows (PowerShell):** Nếu máy có cài sẵn Miniconda/Anaconda hoặc Python hệ thống, bạn **bắt buộc phải kích hoạt `.venv`** trước (`.\.venv\Scripts\Activate.ps1`) hoặc gọi trực tiếp `.\.venv\Scripts\python.exe` khi chạy các lệnh bên dưới để tránh lỗi thiếu thư viện (`pyarrow`, `pytest`, `pypdf`).

---

## 3. Cấu hình Khóa API (Dành cho phân tích LLM)

Bước gọi LLM đọc khóa API trực tiếp từ biến môi trường của hệ điều hành `GEMINI_API_KEY` (không ghi cứng trong code hay tệp cấu hình):

- **Trên Windows (PowerShell):**
  ```powershell
  $env:GEMINI_API_KEY="DÁN_KHÓA_API_GEMINI_TẠI_ĐÂY"
  ```
- **Trên Linux / macOS (Bash):**
  ```bash
  export GEMINI_API_KEY="DÁN_KHÓA_API_GEMINI_TẠI_ĐÂY"
  ```

> [!NOTE]
> Dự án áp dụng cơ chế tự động lưu đệm (`cache`) tại `data/processed/llm_cache.jsonl`. Khi chạy lại, các review đã có kết quả hợp lệ sẽ được lấy ngay từ cache mà không tốn thêm quota gọi API.

---

## 4. Cách Chạy và Quy trình Tái lập Toàn bộ (Quy trình 1 lệnh)

Theo yêu cầu của đề bài, toàn bộ quy trình xử lý dữ liệu từ đầu đến cuối được khởi chạy chỉ bằng **một lệnh duy nhất**:

```powershell
python run_pipeline.py --config configs/city.yaml
```

Luồng chạy tự động bao gồm 9 công đoạn tuần tự:
$$\text{download (gồm filter)} \longrightarrow \text{qa} \longrightarrow \text{kpi} \longrightarrow \text{llm} \longrightarrow \text{baseline} \longrightarrow \text{evaluate} \longrightarrow \text{kpi} \longrightarrow \text{viz} \longrightarrow \text{report}$$

> [!NOTE]
> Bước `kpi` được gọi 2 lần có chủ đích: lần 1 (sau `qa`) tính trước các bảng `kpi_area.csv` và `kpi_time.csv` (K1–K6, K8) ngay cả khi chưa chạy LLM; lần 2 (sau `llm` và `evaluate`) cập nhật bổ sung bảng `kpi_llm.csv` (K7) từ kết quả dự đoán hợp lệ của LLM trước khi bước `viz` dựng biểu đồ và bước `report` xuất báo cáo PDF/Markdown.

### Các tùy chọn chạy linh hoạt:
1. **Chạy kiểm thử nhanh toàn bộ (Offline / Không gọi API LLM):**
   ```powershell
   python run_pipeline.py --config configs/city.yaml --skip-llm
   ```
2. **Bỏ qua tải lại dữ liệu thô khi đã có sẵn trên đĩa:**
   ```powershell
   python run_pipeline.py --config configs/city.yaml --skip-download
   ```
3. **Chạy từng bước độc lập bằng cờ `--only`:**
   ```powershell
   # Khảo sát ID phân công:
   python notebooks/tools/inspect_ids.py --config configs/city.yaml

   # Chỉ chạy QA làm sạch dữ liệu:
   python run_pipeline.py --config configs/city.yaml --only qa

   # Chỉ chạy tính toán 8 KPI:
   python run_pipeline.py --config configs/city.yaml --only kpi

   # Chỉ sinh 11 biểu đồ trực quan vào figures/:
   python run_pipeline.py --config configs/city.yaml --only viz

   # Chỉ tổng hợp số liệu và xuất báo cáo Markdown (reports/report.md):
   python run_pipeline.py --config configs/city.yaml --only report
   ```

---

## 5. Quy trình Chấm lại và Kiểm tra Tự động (Dành cho Giảng viên & Nhóm)

Giảng viên và người chấm có thể tái lập toàn bộ kết quả kiểm thử và đánh giá độc lập bằng bộ công cụ có sẵn trong repo:

```powershell
# 1. Chạy toàn bộ bộ bài kiểm thử tự động (33 bài pytest bao gồm mock LLM và pipeline smoke)
python -m pytest -c notebooks/pytest.ini -q --junitxml=reports/test_results.xml

# 2. Kiểm tra tính độc lập cấu hình (không hardcode thành phố/mốc ngày trong src/)
python notebooks/tools/check_config_swap.py

# 3. Kiểm tra tính nhất quán số liệu giữa báo cáo PDF/Markdown và bảng số liệu gốc
python notebooks/tools/check_report_numbers.py

# 4. Kiểm tra bảo mật (không lưu tệp nhạy cảm, không lộ secret key)
python notebooks/tools/check_security.py

# 5. Xuất bảng thẩm định tiêu chuẩn nộp bài hoàn chỉnh
python notebooks/tools/check_submission.py
```

---

## 6. Cấu trúc Dự án

```text
.
├── .python-version          # Tham chiếu phiên bản Python 3.13.7
├── requirements.txt         # Danh mục thư viện cố định phiên bản
├── run_pipeline.py          # Điểm thực thi 1 lệnh chạy toàn bộ quy trình
├── configs/
│   └── city.yaml            # Tệp cấu hình tham số thành phố, ngưỡng QA, KPI, LLM
├── data/
│   ├── raw/                 # Dữ liệu Inside Airbnb tải về (đã gitignore)
│   ├── processed/           # Dữ liệu sạch Parquet, cache LLM (< 50 MB)
│   └── samples/             # Bảng phân công, danh sách ID, 100 nhãn tay thật
├── src/
│   ├── download.py          # Tải, kiểm tra mã SHA256/CRC và lọc sơ bộ
│   ├── qa.py                # Quy tắc QA, làm sạch, gắn cờ và xuất từ điển
│   ├── kpi.py               # Tính toán bộ 8 chỉ số KPI (K1–K8)
│   ├── llm.py               # Gọi Gemini API, JSON schema, xử lý batch & cache
│   ├── baseline.py          # Mô hình đối chứng từ điển đa ngôn ngữ (en/fr/es/pt)
│   ├── evaluate.py          # Đánh giá Accuracy/F1, ma trận nhầm lẫn, phân tích lỗi
│   ├── viz.py               # Chỉ thực hiện vẽ và xuất 11 biểu đồ trực quan vào figures/
│   └── report.py            # Tổng hợp số liệu, kể chuyện dữ liệu & xuất báo cáo Markdown (report.md)
├── figures/                 # Đủ 11 biểu đồ trực quan (Không gian, Thời gian, LLM)
├── reports/                 # Báo cáo PDF, Markdown, từ điển dữ liệu, checklist
├── AI_USAGE.md              # Báo cáo minh bạch sử dụng AI
└── README.md
```

---

## 7. Sản phẩm Đầu ra Chính

- **Báo cáo hoàn chỉnh:** [`reports/report.md`](file:///reports/report.md) (theo cấu trúc kể chuyện bằng dữ liệu và thẩm định 4 bước của Bài 14).
- **Bộ biểu đồ phân tích:** [`figures/`](file:///figures) gồm 11 hình độ phân giải cao theo 3 góc độ:
  - *Không gian:* Bản đồ phân bố listing, giá theo vùng, tỷ lệ lấp đầy phòng.
  - *Thời gian:* Biến động công suất theo quý, xu hướng KPI, số lượng đánh giá theo thời gian.
  - *LLM & Đối chứng:* Tỷ lệ cảm xúc theo vùng, phân tích khía cạnh khen/chê, so sánh LLM vs Baseline, ma trận nhầm lẫn.
- **Báo cáo chất lượng & dữ liệu:** [`reports/qa_report.csv`](file:///reports/qa_report.csv), [`reports/data_dictionary.csv`](file:///reports/data_dictionary.csv), [`reports/eval_metrics.csv`](file:///reports/eval_metrics.csv), [`reports/submission_checklist.csv`](file:///reports/submission_checklist.csv).
