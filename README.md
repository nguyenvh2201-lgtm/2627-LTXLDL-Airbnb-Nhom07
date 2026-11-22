# BTL Inside Airbnb — UET.DSE2049 4, Nhóm 07

Phân tích thị trường Airbnb Toronto (CAD) qua 4 mốc chụp dữ liệu: **2025-09-11, 2026-03-19, 2026-06-15, 2026-09-16**.

---

## 1. Môi trường và Phiên bản Python

- **Phiên bản Python bắt buộc:** Tham chiếu tệp [`.python-version`](.python-version) ghi nhận **Python 3.13.7**.
- **Hệ điều hành hỗ trợ:** Windows (PowerShell), macOS/Linux (Bash).
- **Yêu cầu tài nguyên tối thiểu:** RAM ≥ 4 GB, dung lượng đĩa trống ≥ 3 GB (xử lý dữ liệu bảng lịch lớn đọc theo chunk).
- **Thư viện phụ thuộc:** Đã được khóa phiên bản chính xác tại [`requirements.txt`](requirements.txt) (gồm `pandas`, `pyarrow`, `matplotlib`, `scikit-learn`, `requests`, `reportlab`, `pypdf`, `pytest`, `pyyaml`, `langdetect`).

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

Theo yêu cầu của đề bài, toàn bộ quy trình xử lý dữ liệu từ đầu đến cuối được khởi chạy chỉ bằng **một lệnh duy nhất**. `Toronto.yaml` là cấu hình mặc định:

```powershell
python run_pipeline.py
```

Có thể truyền rõ đường dẫn tương đương bằng `python run_pipeline.py --config configs/Toronto.yaml`.

Luồng chạy tự động bao gồm 8 công đoạn tuần tự:
$$\text{download (gồm filter)} \longrightarrow \text{qa} \longrightarrow \text{kpi} \longrightarrow \text{llm} \longrightarrow \text{baseline} \longrightarrow \text{evaluate} \longrightarrow \text{kpi} \longrightarrow \text{viz}$$

> [!NOTE]
> Bước `kpi` được gọi 2 lần có chủ đích: lần 1 (sau `qa`) tính trước các bảng `kpi_area.csv` và `kpi_time.csv` (K1–K6, K8) ngay cả khi chưa chạy LLM; lần 2 (sau `llm` và `evaluate`) cập nhật bổ sung bảng `kpi_llm.csv` (K7) từ kết quả dự đoán hợp lệ của LLM trước khi bước `viz` dựng biểu đồ.

### Các tùy chọn chạy linh hoạt:
1. **Chạy toàn bộ nhưng không gọi API LLM** (vẫn tải dữ liệu thô nếu máy chưa có):
   ```powershell
   python run_pipeline.py --config configs/Toronto.yaml --skip-llm
   ```
2. **Bỏ qua tải lại dữ liệu thô khi đã có sẵn trên đĩa:**
   ```powershell
   python run_pipeline.py --config configs/Toronto.yaml --skip-download
   ```
   Tùy chọn này chỉ dùng khi `data/raw/` đã có đủ tệp; trên máy sạch hãy bỏ `--skip-download` để script tải dữ liệu từ Inside Airbnb.
3. **Chạy từng bước độc lập bằng cờ `--only`:**
   ```powershell
   # Khảo sát ID phân công:
   python notebooks/tools/inspect_ids.py --config configs/Toronto.yaml

   # Chỉ chạy QA làm sạch dữ liệu:
   python run_pipeline.py --config configs/Toronto.yaml --only qa

   # Chỉ chạy tính toán 8 KPI:
   python run_pipeline.py --config configs/Toronto.yaml --only kpi

   # Chỉ sinh 11 biểu đồ trực quan vào figures/:
   python run_pipeline.py --config configs/Toronto.yaml --only viz

   ```

4. **Chạy thử LLM/baseline trên mẫu nhỏ mà không ghi đè kết quả chuẩn:**
   ```powershell
   python run_pipeline.py --config configs/Toronto.yaml --only llm,baseline --limit 20
   ```
   Chế độ này ghi các artifact riêng như `llm_sample_limit_20.parquet`,
   `llm_results_limit_20.parquet` và `baseline_results_limit_20.parquet`.
   `--limit` bắt buộc đi cùng `--only` và không được ghép với `evaluate`, `kpi`
   hoặc `viz`, nhờ đó lượt chạy thử không thể làm hỏng bộ kết quả 1.000 dòng.

---

## 5. Quy trình Chấm lại và Kiểm tra Tự động (Dành cho Giảng viên & Nhóm)

Giảng viên và người chấm có thể tái lập toàn bộ kết quả kiểm thử và đánh giá độc lập bằng bộ công cụ có sẵn trong repo:

```powershell
# 1. Chạy toàn bộ bài kiểm thử tự động, gồm mock LLM và pipeline smoke
python -m pytest -c notebooks/pytest.ini -q

# Kiểm 6 mục bàn giao, gồm security và đối chiếu số (không cần chạy lại riêng)
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
│   └── Toronto.yaml         # Tệp cấu hình tham số thành phố, ngưỡng QA, KPI, LLM
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
│   └── viz.py               # Chỉ xuất 11 biểu đồ PDF vector vào figures/
├── figures/                 # Đủ 11 biểu đồ PDF (Không gian, Thời gian, LLM)
├── reports/                 # report.pdf bản nộp, report.md nguồn và các bảng kiểm chứng
├── AI_USAGE.md              # Báo cáo minh bạch sử dụng AI
└── README.md
```

---

## 7. Sản phẩm Đầu ra Chính

- **Báo cáo:** `reports/report.pdf` là bản nộp tối đa 10 trang do nhóm hoàn thiện; [`reports/report.md`](reports/report.md) là bản nguồn được nhóm quản lý độc lập với pipeline.
- **Bộ biểu đồ phân tích:** [`figures/`](figures/) gồm 11 biểu đồ **PDF vector** để đưa vào báo cáo, theo 3 góc độ:
  - *Không gian:* Bản đồ phân bố listing, giá theo vùng, tỷ lệ ngày không khả dụng.
  - *Thời gian:* Biến động tỷ lệ ngày không khả dụng, xu hướng KPI, số lượng đánh giá theo thời gian.
  - *LLM & Đối chứng:* Tỷ lệ cảm xúc theo vùng, phân tích khía cạnh khen/chê, so sánh LLM vs Baseline, ma trận nhầm lẫn.
- **Báo cáo chất lượng & dữ liệu:** [`reports/qa_report.csv`](reports/qa_report.csv), [`reports/data_dictionary.csv`](reports/data_dictionary.csv), [`reports/eval_metrics.csv`](reports/eval_metrics.csv), `reports/error_analysis.csv` và `reports/llm_cost_estimate.csv`.

## Biên dịch báo cáo LaTeX

Nguồn chỉnh sửa nằm trong `reports/latex/` (`main.tex`, `content.tex`, `cover.tex`, `image/`). Nguồn dùng trực tiếp các PDF ở `figures/`, tránh giữ bản hình cũ trong template. Cần TeX Live/MacTeX có font T5/Latin Modern.

```bash
cd reports/latex
pdflatex -no-shell-escape -interaction=nonstopmode -halt-on-error -jobname=report main.tex
pdflatex -no-shell-escape -interaction=nonstopmode -halt-on-error -jobname=report main.tex
cp report.pdf ../report.pdf
cd ../..
python notebooks/tools/check_report_numbers.py
```

Hai lượt biên dịch cập nhật mục lục và tham chiếu bảng/hình. Báo cáo có ghi nhận lần kiểm chứng 27 test; cần cập nhật sau khi bộ test thay đổi.

Các công cụ còn lại: `inspect_ids.py` chuẩn bị ID phân công; `check_report_numbers.py` kiểm 36 giá trị duy nhất khi sửa báo cáo; `check_security.py` audit secret riêng; `check_submission.py` gọi lại hai checker và kiểm kích thước processed, đủ hình, giới hạn trang PDF, Git status. `check_submission.py` không chạy lại pytest. Trước khi nộp, nhóm tự xác nhận repo riêng tư, quyền giảng viên, liên kết nộp bài và tag final.
