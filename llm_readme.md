# TV4 Toronto — Cách chạy LLM một file (Luna / Argon)

**Bản này chỉ có một implementation LLM đang hoạt động:** `src/llm.py` (304 dòng). File tự xử lý prompt, gọi HTTP `requests`, cache/checkpoint JSONL, baseline, đánh giá và ước tính chi phí. Không cần `run_tv4.py`, `gemini_client.py`, `llm_runner.py` hay `llm_contract.py` để chạy bản mới. Các file cũ và **đầy đủ tám file test cũ** được giữ nguyên nội dung dưới `legacy/` để tra cứu; không được coi là test pass cho thiết kế mới.

> Chạy PowerShell tại thư mục gốc repository. **Dùng cùng Python `.venv` cho tất cả lệnh.** Không được đưa ShopAIKey API key vào source, JSON, Git hoặc chat.

## 1. Kiểm tra môi trường và cấu trúc

```powershell
& .\.venv\Scripts\python.exe -m pip install -r .\requirements-llm.txt
& .\.venv\Scripts\python.exe .\src\llm.py --help
& .\.venv\Scripts\python.exe -m unittest discover -s tests -p 'test_llm_*.py' -v
```

Tham số đầu tiên bắt buộc là một trong: `run`, `baseline`, `evaluate`, `cost`.
`run_pipeline.py`, `src/qa.py`, `src/kpi.py`, `src/viz.py` ở **bản nguồn nhận được** đang rỗng hoặc chỉ chứa khoảng trắng. Nhóm cần ghép code QA/KPI/TV5 thật trước khi chạy pipeline tổng; bản sửa này không tự điền code của thành viên khác.

## 2. Input/output contract

- `configs/llm_luna.json` hoặc `configs/llm_argon.json`: cấu hình API, path CSV, snapshot, phiên bản prompt và giá tham chiếu; **không chứa key**.
- `cfg.input`: `data/processed/2026-06-15/reviews_clean.csv` sau QA. Cần các cột `snapshot_date`, `review_id`, `listing_id` và `comments` hoặc `comment_clean`. QA cờ `text_valid`, `listing_match` quyết định có gọi LLM.
- `cfg.sample_ids`: `data/samples/llm_review_ids.csv`; giữ nguyên danh sách 1.000 ID và split `dev`/`analysis`/`test`. **Không bốc mẫu lại** nếu chưa có quyết định của nhóm.
- `--output`: JSONL, mỗi review một dòng, gồm ID/snapshot/split, `sentiment` (`positive/neutral/negative`), `aspects`, `language`, `status`, `error` và metadata cache. `status=error` có thể chỉ là `not_attempted` vì giới hạn lượt gọi.
- Output cũ của Gemini hoặc phiên bản 300 dòng **không tương thích tự động** với signature của bản 304 dòng. Không sửa signature bằng tay để ép dùng lại.

## 3. Cache v1 và bản nhãn neutral v2

Cache Luna v1 (`luna_tv4_simple_v1_20260615.jsonl`, đã có 5 nhãn) phải được giữ nguyên để truy vết.
Bản v2 đổi prompt/nhãn và `prompt_version`, nên **không được dùng cache v1 làm checkpoint v2**.

Với v2, dùng file kết quả mới. Nếu file chưa tồn tại, `--skip-llm` sẽ báo thiếu file (đúng thiết kế).
Chỉ dùng `--skip-llm` sau khi đã tạo kết quả v2; thao tác này không gọi API.

```powershell
$llmOut = '.\data\processed\llm\luna_tv4_simple_v2_20260615.jsonl'
& .\.venv\Scripts\python.exe .\src\llm.py run `
  --config .\configs\llm_luna.json `
  --output $llmOut `
  --skip-llm
```

Khi có ít nhất một review chưa xử lý, CLI có thể trả mã 1; đây không phải lỗi import.

## 4. Baseline, kiểm tra API nhỏ và chạy tiếp

```powershell
& .\.venv\Scripts\python.exe .\src\llm.py baseline --config .\configs\llm_luna.json

$secret = Read-Host 'ShopAIKey API key' -AsSecureString
$env:SHOPAIKEY_API_KEY = [System.Net.NetworkCredential]::new('', $secret).Password

& .\.venv\Scripts\python.exe .\src\llm.py run `
  --config .\configs\llm_luna.json `
  --output $llmOut `
  --max-new-requests 15
```

Lệnh cuối **có thể tốn phí API**. Hãy đọc 5 review đã có, rồi mới chạy tiếp 15 dev. Kiểm tra kết quả thực tế và chốt prompt trước khi chạy batch 1.000. Muốn chạy nốt thì bỏ `--max-new-requests` nhưng giữ **cùng đường dẫn output**, model và prompt/version.

## 5. Đánh giá và ước tính chi phí

Cần ít nhất **100 nhãn tay độc lập, đã điền đủ** của split `test`, file mặc định `data/samples/reviews_test_labels.csv`. Khi chưa có nhãn tay, không được công bố Accuracy/Macro-F1 thực tế. Baseline là từ khóa tiếng Anh, không phải SBERT/VADER.

```powershell
& .\.venv\Scripts\python.exe .\src\llm.py evaluate `
  --config .\configs\llm_luna.json `
  --output $llmOut `
  --labels .\data\samples\reviews_test_labels.csv

& .\.venv\Scripts\python.exe .\src\llm.py cost `
  --config .\configs\llm_luna.json `
  --output $llmOut
```

Đơn giá là tham chiếu theo config, chưa đối soát hóa đơn ShopAIKey. `cost` chỉ dựa trên `usage` được ghi nhận. Không suy ra phí thực tế của những lần gọi lỗi/mất metadata.

## 6. File cũ và pipeline nhóm

- `legacy/src/`: các module Gemini, cache audit, evaluator cũ và hai placeholder rỗng `baseline.py`/`evaluate.py` **được lưu trữ**. Chúng thuộc hợp đồng cache, provider và nhãn của kiến trúc cũ; không thay thế chúng bằng việc đổi tên kết quả Luna.
- `legacy/tests/`: 8 test cũ còn nguyên source; các test này **không thuộc lệnh test kiến trúc mới** và có thể không chạy độc lập sau khi di chuyển vì import API cũ.
- `legacy/run_tv4.py`, `legacy/examples/offline_demo.py`, `legacy/llm_readme_gemini.md`: router, demo, README phiên bản cũ để truy vết.
- `src/prepare.py` và `src/common.py` vẫn giữ, phục vụ chuẩn bị mẫu/QA theo mã hiện có. Có thể gọi `python -m src.prepare --help` bằng `.venv`.
- **Không xóa hoặc tự sửa** `run_pipeline.py`, `src/kpi.py`, `src/qa.py`, `src/download.py`, `src/viz.py`, `configs/toronto.json` vì thuộc hợp đồng chung hoặc phiên bản của thành viên khác.
- Các lệnh cũ `python run_tv4.py llm ...`, `--list-models`, `--show-request`, `--refresh` không được hỗ trợ trong bản LLM này. Chỉ dùng CLI mới được mô tả ở trên.

Xem `docs/LLM_MIGRATION.md` để biết nội dung thay đổi, rủi ro còn lại và cách xác minh.
