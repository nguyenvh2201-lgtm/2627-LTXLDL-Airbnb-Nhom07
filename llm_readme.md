# TV4 Toronto — Hướng dẫn chạy LLM (Luna / Argon)

> **Dành cho các thành viên nhóm tải nhánh `gmnh` về máy để cài đặt, chạy lại và kiểm tra.**  
> Phiên bản tài liệu: 26/10/2026 · Code tham chiếu: `src/llm.py` v2, commit `e6dd724` · Nhãn: `positive / neutral / negative`.

**Đọc nhanh (2 phút):** TV4 hiện chỉ dùng **một file xử lý chính `src/llm.py`**. Trong đó có cả gọi LLM bằng `requests`, checkpoint JSONL, baseline theo từ khóa, evaluation và ước tính chi phí. **Không chạy `run_tv4.py`, `src/baseline.py`, `llm_runner.py` hay `gemini_client.py` cũ.** Các file cũ đã chuyển vào `legacy/` để lưu vết. Xem thêm [LLM_FLOW.html](LLM_FLOW.html) để hiểu luồng hoạt động.


### Bắt đầu nhanh — chọn đúng việc mình cần làm

| Bạn muốn… | Làm ngay | Phải có trước |
| --- | --- | --- |
| **Hiểu code / kiểm tra cài đặt** | Chạy `--help`, 19 unit tests; mở `LLM_FLOW.html` | Clone nhánh, Python và thư viện LLM; **không cần CSV QA, API key** |
| **Thử baseline, không tốn API** | Lệnh `baseline` ở mục 4 | CSV review sau QA và danh sách ID mẫu |
| **Gắn nhãn bằng Luna / Argon** | Lệnh `run` ở mục 5 | CSV QA, danh sách ID, biến môi trường chứa API key, ngân sách API |
| **Xem cache đã có, không gọi API** | Lệnh `run --skip-llm` ở mục 6 | Các nguồn input tương ứng và file JSONL **cùng signature** |
| **So sánh chất lượng hoặc chi phí** | `evaluate` / `cost` ở mục 7–8 | JSONL v2; riêng `evaluate` cần tối thiểu 100 nhãn tay test độc lập |
| **Dùng kết quả trong KPI** | Gửi JSONL v2 cho TV3 qua `--llm-file` | Bản KPI thật của TV3 và các bảng QA listings/calendar |

**Luồng tổng quan:** CSV review sau QA + danh sách mẫu + config → `src/llm.py` (`run` / `baseline`) → JSONL kết quả hoặc báo cáo → đối chiếu 100 nhãn tay (`evaluate`) và bàn giao JSONL cho KPI TV3. **KPI không được tính lại trong TV4.**

**Lưu ý:** Ngay sau khi clone, bạn **chưa thể chạy baseline, run, evaluate hoặc cost** nếu chưa nhận CSV QA TV2. Nhưng `--help` và unit tests có thể chạy ngay sau bước cài thư viện.

## 1. Cài đặt trên máy Windows

Mở **PowerShell tại thư mục gốc repository** (nơi có `src/`, `configs/`, `tests/`). Nếu chưa tải code:

```powershell
git clone --branch gmnh --single-branch https://github.com/nguyenvh2201-lgtm/2627-LTXLDL-Airbnb-Nhom07.git
cd .\2627-LTXLDL-Airbnb-Nhom07
```

Tạo môi trường riêng, cài đúng các thư viện phần LLM và kiểm tra CLI:

```powershell
py -3 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -r .\requirements-llm.txt
& .\.venv\Scripts\python.exe .\src\llm.py --help
```

Nếu Windows không có lệnh `py`, thay dòng tạo môi trường bằng `python -m venv .venv`. **Dùng `.venv\Scripts\python.exe` cho các lệnh bên dưới**, tránh nhầm sang Python ngoài môi trường. `requirements-llm.txt` phục vụ TV4 (đặc biệt `requests`); **KPI TV3 còn cần `numpy`, `pandas`**, không phải dependency của `llm.py`.

## 2. Các file cần biết

| File/thư mục | Công dụng | Có được commit / cần chuyển khi đổi máy? |
| --- | --- | --- |
| `src/llm.py` | **Một điểm vào duy nhất** cho `run`, `baseline`, `evaluate`, `cost` | Có, nằm trong Git |
| `configs/llm_luna.json` | Cấu hình `gpt-6-luna` qua ShopAIKey; prompt v2 | Có; **không chứa API key thật** |
| `configs/llm_argon.json` | Cấu hình `gemini-4-argon` qua ShopAIKey; prompt v2 | Có; không chứa API key thật |
| `data/samples/llm_review_ids.csv` | Danh sách **1.000 review** cố định và split dùng cho TV4 | Có, đã commit |
| `data/processed/2026-06-15/reviews_clean.csv` | Dữ liệu review **sau QA**; cần có trên từng máy | Phải nhận từ TV2/nhóm; không tự sinh bởi `llm.py` |
| `data/samples/reviews_test_labels.csv` | Ít nhất 100 nhãn tay **test** để tính accuracy/F1 | Cần chuẩn bị riêng, kiểm tra quy định chia sẻ dữ liệu |
| `data/processed/llm/*.jsonl` | Kết quả LLM kiêm **checkpoint/cache** | File chạy cục bộ, **được Git ignore**, sao lưu riêng nếu chuyển máy |
| `reports/llm/` | Baseline, báo cáo evaluation và cost | Đầu ra cục bộ, **được Git ignore** |
| `tests/test_llm_simple.py` | Unit test cho kiến trúc một file | Có, chạy bằng `unittest` |
| `legacy/` | Code/demo/test Gemini cũ (lưu trữ để truy vết) | Có, **không chạy làm pipeline mới** |

**Không nhầm:** `src/kpi.py` ở snapshot nhánh `gmnh` từng là placeholder; KPI đầy đủ nằm ở nhánh **`tv3-kpi-analysis`** của thành viên TV3. Tài liệu này không yêu cầu ghi đè hay sửa KPI của TV3. Pipeline tích hợp cần đúng phiên bản của nhóm.

## 3. Dữ liệu đầu vào và quy ước nhãn

Trong cả hai config, đường dẫn đầu vào đang là `data/processed/2026-06-15/reviews_clean.csv`, snapshot `2026-06-15`, và danh sách mẫu `data/samples/llm_review_ids.csv`.

- CSV QA phải có `snapshot_date`, `review_id`, `listing_id`, cùng ít nhất một cột `comment_clean` **hoặc** `comments`. Nếu có `comment_clean`, code ưu tiên dùng cột đó; review phải có chuỗi văn bản hợp lệ. ID nên giữ ở dạng chuỗi, không ép qua số thực.
- Nếu có `text_valid` và `listing_match`, chương trình chỉ gọi API khi cả hai cờ nằm trong tập được chấp nhận: `true`, `1`, `yes`, `x` (không phân biệt hoa/thường). Nếu **không có hai cột này**, code mặc định xem là hợp lệ; do đó phải bảo đảm file thật sự đã QA.
- File `sample_ids` cố định thứ tự và `split`; không tự chọn lại 1.000 review nếu không thống nhất với nhóm. `sample_size` và `seed` chỉ dùng để chọn mẫu ngẫu nhiên khi **không cấu hình `sample_ids`**.
- `sentiment` hợp lệ: `positive`, `neutral`, `negative`. Trong prompt v2, **`neutral` dùng cho review có cả khen lẫn chê đáng kể**; review thuần mô tả, mơ hồ hoặc không đủ thông tin là `needs_review`, **không tự ép thành neutral**.
- `aspects` chỉ gồm: `location`, `cleanliness`, `host`, `value`, `amenities`, `noise`, `safety`. `polarity` trên từng aspect cũng thuộc `positive / neutral / negative`. Không gán aspect nếu văn bản không nói rõ.

### Định dạng JSONL bàn giao cho KPI

Mỗi dòng là một JSON object đại diện một review. **Ví dụ cấu trúc minh họa, không phải nhãn thật** (đã lược bỏ một số metadata):

```json
{"snapshot_date":"2026-06-15","review_id":"demo-001","listing_id":"demo-100","split":"analysis","sentiment":"neutral","aspects":[{"aspect":"location","polarity":"positive"},{"aspect":"cleanliness","polarity":"negative"}],"language":"en","status":"ok","error":null,"provider":"shopaikey","model":"gpt-6-luna","prompt_version":"tv4-simple-v2"}
```

Quy ước `status`:

| `status` | Ý nghĩa | KPI/evaluation xử lý |
| --- | --- | --- |
| `ok` | Có nhãn hợp lệ và `error = null` | KPI TV3 dùng nếu sentiment hợp lệ |
| `needs_review` | Văn bản chưa đủ bằng chứng để phân loại; sentiment `null` | Không tính là nhãn dùng được |
| `error` | Chưa thử (`not_attempted`), QA không đạt hoặc lỗi API/định dạng | Không tính là nhãn dùng được; **không xóa khỏi file kết quả** |

Các trường cache/truy vết bổ sung thường gồm `run_signature`, `usage`, `model_version` (khi có), `provider`, `model` và `prompt_version`. Bản ghi `error` không bắt buộc có response/usage.

## 4. Chạy baseline — không cần API

Baseline hiện là hàm `baseline(text)` **bên trong `src/llm.py`**, dùng từ khóa tích cực/tiêu cực tiếng Anh và xử lý phủ định đơn giản (2 từ trước). Không phải SBERT, VADER hay một LLM khác.

```powershell
& .\.venv\Scripts\python.exe .\src\llm.py baseline --config .\configs\llm_luna.json
```

Đầu ra nằm trong thư mục `reports/llm/<ten-lan-chay>_<hash>/baseline.jsonl`; CLI sẽ **in đường dẫn thực tế**. Có cả nhãn `unclassified` khi không nhận thấy bằng chứng từ khóa; đây là giới hạn của baseline, không phải một sentiment hợp lệ cho KPI. `baseline` **không gọi API và không cần file kết quả LLM**.

## 5. Chạy LLM thật với Luna (có thể phát sinh phí)

**Chỉ làm bước này sau khi đã có CSV QA và danh sách mẫu đúng.** Đặt API key dưới dạng biến môi trường trong phiên PowerShell hiện tại; **không lưu key vào Git, config, ảnh chụp hoặc README**:

```powershell
$secret = Read-Host 'ShopAIKey API key' -AsSecureString
$env:SHOPAIKEY_API_KEY = [System.Net.NetworkCredential]::new('', $secret).Password

$llmOut = '.\data\processed\llm\luna_tv4_simple_v2_20260615.jsonl'
& .\.venv\Scripts\python.exe .\src\llm.py run `
  --config .\configs\llm_luna.json `
  --output $llmOut `
  --max-new-requests 5
```

- `--max-new-requests 5` giới hạn **tối đa 5 lần gọi HTTP mới** ở lần chạy này, không phải 5 review chắc chắn thành công. Trên máy khác có thể chọn giới hạn nhỏ hơn để kiểm tra trước.
- Mỗi lần chạy, chương trình ghi **toàn bộ danh sách mẫu** vào JSONL; bản ghi chưa thử mang `status=error, error=not_attempted` (không phải kết quả phân loại sai). Nếu còn bản ghi `error`, lệnh `run` có thể trả **exit code 1** dù một phần đã thành công.
- Nếu request/response lỗi, chương trình **ghi checkpoint rồi dừng ở review đó**. Code hiện tại **không tự retry HTTP trong cùng lần chạy**; kiểm tra nguyên nhân rồi chạy lại cùng config và output để thử lại các bản ghi `error`.
- Signature hiện hash **`base_url`, `model`, `prompt_version`, `request_options`, nội dung `PROMPT` và các trường dữ liệu mẫu** (`snapshot_date`, ID, text, QA, split). Khi các giá trị này đổi, cache cũ bị **từ chối**. **API key và chuỗi `provider` không nằm trong signature**; việc đổi riêng API key không làm mất hiệu lực cache, nhưng **không được dùng lại kết quả giữa các nhà cung cấp/endpoint khác nhau**. Khi đổi provider, dùng config/đường dẫn output riêng; kiểm tra kỹ `base_url`. Không tự sửa `run_signature`.

Để chạy tiếp sau lần đầu, giữ **cùng** `$llmOut`, config và nguồn dữ liệu; có thể tăng giới hạn hoặc bỏ hẳn `--max-new-requests` sau khi đã kiểm tra đầu ra và hạn mức API:

```powershell
& .\.venv\Scripts\python.exe .\src\llm.py run `
  --config .\configs\llm_luna.json `
  --output $llmOut `
  --max-new-requests 20
```

Config Argon dùng cùng CLI, chỉ đổi `--config .\configs\llm_argon.json` và **đổi sang một file output riêng**. Tính khả dụng, định dạng phản hồi và giá thực tế phụ thuộc API/account; không mặc định Argon đã được test bằng request thật.

## 6. Đọc lại checkpoint mà không gọi API

`--skip-llm` chỉ đọc **file kết quả có sẵn** và kiểm tra signature; **không tự tạo một kết quả mới**. Nếu chưa chạy v2 tạo `$llmOut`, lệnh sẽ báo thiếu file — đúng thiết kế.

```powershell
& .\.venv\Scripts\python.exe .\src\llm.py run `
  --config .\configs\llm_luna.json `
  --output $llmOut `
  --skip-llm
```

Trong summary, chú ý `rows`, `status_counts`, `cache_hits` và `api_requests_this_run` (phải là **0** với `--skip-llm`). `cache_hits` đếm bản ghi `ok`/`needs_review` được giữ lại, **không** phải số request API đã tiết kiệm được tính phí.

**Cache v1 → v2:** Luna v1 đã từng có 5 review `ok`, nhưng prompt cũ dùng `mixed`. V2 dùng `neutral`, `prompt_version = tv4-simple-v2` và signature khác; **không dùng lại file v1 làm checkpoint v2**. Hãy lưu nguyên file JSONL v1 riêng để truy vết. Cache JSONL không được commit; khi chuyển máy, chép đúng file kết quả và đảm bảo config/CSV/sample/prompt tương ứng.

## 7. Đánh giá với ít nhất 100 nhãn tay

`evaluate` chỉ chạy sau khi có **file JSONL LLM v2** và ít nhất 100 review test được gán nhãn **độc lập**. CSV nhãn tay phải có tối thiểu `review_id`, `snapshot_date`, `manual_sentiment`; nếu có `split` thì phải là `test`, nếu có `needs_review` thì không được là `true`. Các nhãn trong `manual_sentiment` phải là `positive / neutral / negative`; không chuyển `mixed` sang `neutral` hàng loạt mà không rà lại ngữ nghĩa. Dùng đầy đủ các ID thuộc split test đã chọn, không lọc bỏ review khó hoặc review LLM dự đoán sai.

```powershell
& .\.venv\Scripts\python.exe .\src\llm.py evaluate `
  --config .\configs\llm_luna.json `
  --output $llmOut `
  --labels .\data\samples\reviews_test_labels.csv
```

Đầu ra trong `reports/llm/<ten-lan-chay>_<hash>/`: `metrics.json` (accuracy, coverage, macro-F1, F1 từng lớp của LLM và baseline) và `error_analysis.csv` (các trường hợp có sai khác). Review thiếu dự đoán được tính là `unclassified` và **vẫn tính là sai**, không lén bỏ khỏi mẫu số. **Chưa có 100 nhãn test hoàn chỉnh thì chưa được công bố accuracy/F1 thực tế.**

## 8. Ước tính chi phí API

```powershell
& .\.venv\Scripts\python.exe .\src\llm.py cost `
  --config .\configs\llm_luna.json `
  --output $llmOut
```

Đầu ra `cost.json` trong thư mục báo cáo tương ứng; dùng `usage` (`prompt_tokens`, `completion_tokens`) đã ghi và giá **tham khảo trong config**. Không đại diện hóa đơn thực tế, không tính chính xác các lần gọi lỗi hoặc thiếu usage. Có thể thêm `--city-reviews <so_luong>` nếu đã có tổng review thành phố đáng tin cậy; đây là ngoại suy theo giả định, không phải chi phí đo được.

## 9. Bàn giao kết quả cho KPI TV3

KPI đầy đủ của TV3 đọc JSONL bằng tùy chọn `--llm-file` và ghép review với listings theo `(snapshot_date, listing_id)`. Nhãn v2 `positive / neutral / negative` hiện tương thích với `LLM_LABELS` của **bản TV3 trên nhánh `tv3-kpi-analysis`**. `LLM_FLOW.html` minh họa rõ điểm bàn giao.

Khi thành viên phụ trách tích hợp đã đưa **bản KPI thật** vào pipeline và có đủ `listings_clean.csv`, `calendar_listing_summary.csv`, họ có thể dùng:

```powershell
& .\.venv\Scripts\python.exe .\src\kpi.py `
  --input-dir .\data\processed `
  --llm-file $llmOut
```

**Không chạy lệnh này với `src/kpi.py` placeholder 1 byte trên `gmnh`, và không tự ghi đè code TV3.** KPI có ngưỡng `MIN_N_SHARE = 30`: khi mới có 5 review hợp lệ, một số tỷ lệ sentiment/aspect sẽ để trống theo thiết kế. Bài kiểm thử offline `neutral` được KPI nhận là `usable` đã **PASS**; chạy KPI trên toàn bộ dữ liệu thật **chưa được chứng minh**.

## 10. Test và xử lý lỗi hay gặp

Chạy kiểm thử **không gọi API**:

```powershell
& .\.venv\Scripts\python.exe -m py_compile .\src\llm.py
& .\.venv\Scripts\python.exe -m unittest discover -s tests -p 'test_llm_*.py' -v
```

Ở thời điểm chốt v2, test trên Windows đã **19/19 PASS** và hợp đồng nhận nhãn `neutral` của KPI TV3 đã **PASS** trên JSONL giả lập; đây **không phải** kết quả accuracy/F1 hay kiểm thử API v2 trên 1.000 review.

| Hiện tượng | Nguyên nhân / xử lý |
| --- | --- |
| `ModuleNotFoundError: requests` | Chưa cài vào đúng `.venv`; chạy `-m pip install -r requirements-llm.txt` bằng `.venv\Scripts\python.exe` |
| `FileNotFoundError` đầu vào CSV | Chưa nhận dữ liệu QA TV2 hoặc đường dẫn `input` trong config sai; kiểm tra `Test-Path` |
| Thiếu `SHOPAIKEY_API_KEY` | Chưa đặt biến môi trường **trong phiên PowerShell đang chạy**; chỉ cần khi có request mới |
| `File kết quả khác model/prompt/dữ liệu/cấu hình` | Signature không khớp; đặt **output mới**, không ép sửa cache |
| `--skip-llm` báo thiếu file | Chưa từng tạo JSONL v2 ở đường dẫn truyền vào; chạy có kiểm soát trước |
| Exit code `1`, `error=not_attempted` | Batch chưa xử lý hết; đọc `status_counts`, xem `--max-new-requests` |
| HTTP 429/network/timeout | Chương trình lưu checkpoint và **dừng**, chưa có retry tự động; điều tra rồi chạy lại |
| `evaluate` báo nhãn không hợp lệ | Thiếu 100 nhãn `test`, còn `mixed`, thiếu/sai ID, có nhãn chưa chốt hoặc trộn split |
| `ModuleNotFoundError: numpy` từ KPI | Cài `numpy pandas` vào cùng venv **nếu cần chạy KPI**; không liên quan `run` của LLM |

**Không tự sửa** `src/kpi.py`, `src/qa.py`, `run_pipeline.py` hay các module nhóm khác khi chỉ thực hiện TV4. Không commit API key, `.venv/`, file cache JSONL, báo cáo sinh tự động hoặc dữ liệu QA chưa có quy ước chia sẻ.

**Xem sơ đồ:** mở [`LLM_FLOW.html`](LLM_FLOW.html) cùng thư mục với README để xem nhánh cache/API và định dạng JSONL trên nền tối.
