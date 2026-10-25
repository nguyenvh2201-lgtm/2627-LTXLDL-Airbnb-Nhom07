# TV4 Toronto — Lấy và sử dụng phần LLM từ nhánh `gmnh`

Tài liệu này dành cho các bạn trong nhóm lấy code trên nhánh `gmnh`, kiểm tra, cài môi trường và sử dụng phần LLM. Chạy các lệnh tại **gốc repository**, nơi có `run_tv4.py`. Mở [LLM_FLOW.html](LLM_FLOW.html) bằng trình duyệt để xem mô phỏng luồng chạy.

Đây là hướng dẫn của mã nguồn hiện có. Việc một file có trong ZIP review chưa chứng minh file đó đã được commit/push; người bàn giao cần đối chiếu nhánh và commit trước khi gửi cho nhóm.

## 1. Lấy code và chuẩn bị môi trường

### Chưa có repository trên máy

Lấy URL từ nút **Code** của repository nhóm, rồi thay giá trị trong lệnh:

```powershell
$repoUrl = 'DAN_URL_CLONE_CUA_REPO_NHOM'
git clone --branch gmnh --single-branch $repoUrl TV4_Toronto_Git
cd TV4_Toronto_Git
git branch --show-current
git log -1 --oneline
```

Nhánh cần thấy là `gmnh`. Nếu Git báo không có nhánh, kiểm tra lại URL và việc nhánh đã được push. Tên thư mục local không quyết định nhánh Git.

### Đã clone repository

Mở PowerShell tại gốc repo của bạn:

```powershell
git status --short
```

Nếu có thay đổi đang làm, lưu chúng theo cách nhóm đang dùng trước khi chuyển nhánh. Khi working tree sạch:

```powershell
git fetch origin
git switch gmnh
git pull --ff-only origin gmnh
git branch --show-current
git log -1 --oneline
```

Nếu chỉ muốn tải ZIP: chọn đúng nhánh `gmnh` trên GitHub rồi **Download ZIP**, giải nén và mở PowerShell tại thư mục có `run_tv4.py`. Bản tải ZIP không có lịch sử Git nên bỏ qua các lệnh Git. **Không cần bộ ZIP bản vá hoặc `INSTALL_LLM.ps1`**: các module đã ở trong nhánh.

### Python và dependency

Phần LLM, audit, evaluator và các test hiện dùng **thư viện chuẩn Python**, không yêu cầu Gemini SDK hay API key để chạy demo/test.

```powershell
python --version
# Tùy chọn nếu chưa có môi trường riêng:
python -m venv .venv
# Nếu không muốn kích hoạt, có thể thay python bằng .\.venv\Scripts\python.exe
```

Các module LLM sử dụng cú pháp/API phù hợp Python 3.10 trở lên; lần review này chỉ chạy thực tế trên **Linux / Python 3.12.14**. Riêng `src/prepare.py` đang gọi `hashlib.file_digest`, nên nếu sử dụng bước `prepare` hãy dùng **Python 3.11 trở lên**. Chưa có bằng chứng chạy trên Windows hoặc Python 3.10. `requirements.txt` trong bản review đang rỗng; dependency của các phần khác do thành viên phụ trách xác nhận.

## 2. Kiểm tra ngay sau khi lấy code — không gọi API

```powershell
python -m compileall -q src tests examples
python run_tv4.py llm --help
python examples/offline_demo.py
python -m unittest discover -s tests -p "test_llm_*.py" -v
```

Demo phải hiện `DEMO PASS`, gồm **3 review giả lập, 1 cache hit, 1 cache miss, 1 lỗi QA và 0 API request**. Nó dùng cache tạm, không đọc/sửa cache của nhóm. Output demo được tạo lại tại `examples/_demo_output/`; đây không phải kết quả Toronto thật.

Ở bản nguồn được review ngày 22/10/2026: **49/49 test hiện có đạt** trên môi trường nêu trên. Chạy lại tại máy nhận code và giữ kết quả kiểm tra; test tên `windows_compat` là test BOM/JSONL/evaluator, không thay thế việc chạy trên Windows.

Xem payload mà không gửi request và không cần key/model:

```powershell
python run_tv4.py llm --input examples/reviews_demo.csv --show-request --review-id DEMO-001
```

`--show-request` chỉ in prompt/schema và review text; không gửi nhãn tay. Output có thể chứa nguyên văn review, vì vậy cần chú ý khi chia sẻ log dữ liệu thật.

## 3. File nào thuộc phần LLM và liên quan tới các phần khác?

| File | Trách nhiệm / cách sử dụng |
| --- | --- |
| `run_tv4.py` | Định tuyến lệnh; `python run_tv4.py llm ...` là cách chạy LLM của nhóm |
| `src/llm.py` | CLI và wrapper `classify`; truyền request function cho runner để test được |
| `src/llm_contract.py` | Validate 5 trường mô hình; tạo fingerprint; chọn bản cache hợp lệ cuối khi trùng |
| `src/gemini_client.py` | Tạo payload, gọi REST Gemini, timeout/retry, chuẩn hóa và che key trong chẩn đoán HTTP |
| `src/llm_runner.py` | Kiểm tra cờ QA, chọn cache/API, lưu checkpoint và thống kê batch |
| `src/cache_audit.py` | Đối chiếu marking + dữ liệu sau QA + cache; chạy bằng `python -m src.cache_audit ...` |
| `src/tv4_evaluation.py` | So sánh dự đoán với nhãn người; chạy bằng `python -m src.tv4_evaluation ...` |
| `src/common.py` | Đường dẫn gốc, CSV/JSONL, chuẩn hóa text, taxonomy và nhãn tay |
| `src/prepare.py` | Parser marking và bước ghép nguồn review; audit import parser của file này |
| `configs/toronto.json` | Config được LLM dùng: prompt, schema, cache, model, retry; không phải `city.yaml` |
| `prompts/review_v1.txt`, `prompts/review_schema.json` | Prompt và schema để các lần chạy dùng cùng quy tắc |
| `docs/LLM_ANNOTATION_CONTRACT.md` | Quy tắc gán nhãn độc lập cho người |
| `tests/test_llm_*.py`, `examples/` | Regression test và ví dụ giả lập |

Giữ nguyên các file phụ trợ trong `src/`, không chỉ chép mỗi `llm.py`. Không chạy `python src/llm.py` vì file dùng relative imports.

**Ranh giới công việc:** người phụ trách QA cung cấp review và cờ chất lượng; LLM tạo **dự đoán**; người gán tay tạo gold label độc lập; evaluator đối chiếu hai nguồn; KPI/viz tiêu thụ kết quả đã lọc. Cấu trúc module hiện tại được giữ nguyên.

Trong bản review, `src/qa.py`, `baseline.py`, `evaluate.py`, `kpi.py`, `viz.py`, `download.py` và `run_pipeline.py` đang rỗng hoặc chỉ có khoảng trắng. Điều này chỉ mô tả bản nguồn này, **không kết luận tiến độ của các bạn ở nhánh khác**. Evaluator TV4 nằm ở `tv4_evaluation.py`. Router đã nối `python run_tv4.py evaluate` tới evaluator này và đã thêm `python run_tv4.py cache_audit`. Hai cách gọi trực tiếp `python -m ...` ở bảng trên vẫn dùng được.

## 4. Dữ liệu không tự xuất hiện sau khi checkout nhánh

| Thành phần | Có trong ZIP nguồn review? | Cần lấy/tạo ở đâu? |
| --- | --- | --- |
| Module, config, prompt/schema, test, demo | Có | Nhánh `gmnh` sau khi người bàn giao đã push |
| CSV review thật đã qua QA | Không | Người phụ trách QA cung cấp đường dẫn/file cụ thể |
| Bảng marking ID/mẫu LLM/mẫu nhãn tay | Không | Bảng phân công mẫu chính thức của nhóm |
| Cache Gemini đã chạy | Không | Nhận bản cache đã lưu, hoặc bắt đầu không có cache |
| 100 nhãn người đã điền | Không | Người gán độc lập hoàn tất theo contract |
| Output/metric Toronto thật | Không | Nhận bản đã chạy hoặc tạo sau khi đủ input |

Không suy ra “checkout là có data/cache”. Các đường dẫn trong config là vị trí dự kiến, không phải bằng chứng file tồn tại. Thiếu cache thì cache-only sẽ miss; chạy API với cache trống có thể gọi lại toàn bộ review đủ điều kiện.

### Contract CSV đầu vào của LLM

CSV **UTF-8 hoặc UTF-8-BOM**, phân cách bằng dấu phẩy, chưa nén:

| Cột | Bắt buộc? | Ý nghĩa |
| --- | --- | --- |
| `snapshot_date` | Có | Mốc dữ liệu, ví dụ `2026-06-15` |
| `review_id`, `listing_id` | Có | ID dạng chuỗi, giữ nguyên chữ số |
| `comments` | Có | Văn bản review; trống sẽ thành lỗi đầu vào |
| `split` | Không | `analysis` mặc định; giữ riêng `dev` và `test` nếu có |
| `text_valid`, `listing_match` | Không ở code; nên có trong dữ liệu nhóm | Khi thiếu cột, runner mặc định `true` |
| `exclude_from_llm_sample` | Không | Khi thiếu cột, runner mặc định `false` |

Cặp `(snapshot_date, review_id)` phải duy nhất. Cờ đúng nhận `true`, `1`, `yes`, `x` (không phân biệt hoa/thường); cờ để trống không đồng nghĩa thiếu cột. LLM **chỉ đọc cờ QA, không tự làm lại QA**. Runner và chế độ xem request kiểm tra bốn cột bắt buộc trước khi xử lý; thiếu cột sẽ báo `ValueError` kèm tên cột, không gọi API.

`src/common.path` tính đường dẫn tương đối theo **gốc repo**, kể cả đường dẫn nằm trong bản config sao chép, không theo thư mục chứa config đó.

## 5. Luồng xử lý và ý nghĩa kết quả

Trước vòng review, chương trình kiểm tra trùng ID/đầu vào rỗng, đọc model/prompt/schema/cache và kiểm tra key nếu không dùng `--skip-llm`. `GEMINI_MODEL` ghi đè `model` trong config. `model=null` nghĩa là phải đặt model, kể cả khi cache-only; `--help` và `--show-request` không cần model.

Với từng review: **fingerprint → cờ QA → cache nếu không refresh → skip/giới hạn/dừng batch → Gemini nếu được phép → validate → lưu cache → ghi output**. Cuối batch mới ghi `.run.json`.

| Trạng thái | Ý nghĩa | Cách dùng downstream |
| --- | --- | --- |
| `ok` | Dự đoán đúng schema, sentiment thuộc `positive/mixed/negative` | Có thể dùng cho phân tích, vẫn là dự đoán LLM |
| `needs_review` | JSON hợp lệ nhưng mô hình chưa kết luận; sentiment null, aspects rỗng, có lý do | Giữ riêng để xem lại; cũng được lưu cache |
| `error` | QA không hợp lệ, cache miss offline, giới hạn, API hoặc output sai | Không ép thành nhãn sentiment |

Schema có 7 aspects: `location`, `cleanliness`, `host`, `value`, `amenities`, `noise`, `safety`; mỗi aspect có polarity `positive/mixed/negative`. Không có nhãn neutral. Mô hình chỉ trả 5 khóa `sentiment/aspects/language/status/error`; runner thêm ID và metadata. Tùy chọn `--labels` của lệnh LLM chỉ được giữ để tương thích CLI cũ, không đọc nhãn tay và không chạy đánh giá.

Cache key phụ thuộc model, prompt/version, schema, tham số sinh, snapshot, ID và text chuẩn hóa. `split` và các cờ QA không nằm trong key; QA vẫn được kiểm tra trước khi tái sử dụng cache. `--refresh` bỏ qua cache; không dùng chung với `--skip-llm`.

## 6. Dùng dữ liệu thật: audit tùy chọn và cache-only

Nếu đã có CSV đúng contract sau QA, có thể dùng trực tiếp. Audit hữu ích khi cần đối chiếu marking/cache và tạo mẫu nhãn tay, không phải bước tạo QA.

Thay các giá trị dưới đây bằng nguồn nhóm đã cung cấp; tên minh họa không phải file đã có sẵn:

```powershell
$qaPath = 'DUONG_DAN_CSV_SAU_QA.csv'
$markingPath = 'DUONG_DAN_BANG_MARKING.csv'
$cachePath = 'data/processed/llm_cache.jsonl'
$modelId = 'ID_MODEL_DA_TAO_CACHE'
if (!(Test-Path $qaPath)) { throw 'Chưa có CSV sau QA' }
if (!(Test-Path $markingPath)) { throw 'Chưa có bảng marking' }
$runId = Get-Date -Format 'yyyyMMdd_HHmmss_fff'
$auditDir = "reports/cache_audit_$runId"
python -m src.cache_audit `
  --qa-reviews $qaPath --marking $markingPath --cache $cachePath `
  --model $modelId --output-dir $auditDir
```

Audit nhận CSV/CSV.GZ có `review_id` (hoặc `id`), `listing_id`, `comments`, `text_valid`, `listing_match`. Nếu có `snapshot_date`, nó lọc theo config; nếu không có, cần xác nhận nguồn đúng snapshot. Parser marking yêu cầu header 15 cột chính xác theo `src/prepare.py::read_marking`; không dùng một CSV ID tùy ý thay thế.

Các đầu ra chính:

| File trong thư mục audit | Nội dung |
| --- | --- |
| `reviews_llm_after_qa.csv` | Review được marking chọn và qua QA để chạy LLM |
| `sample_qa_audit.csv`, `cache_qa_audit.csv` | Đối chiếu mẫu/QA/cache; bảng cache chỉ được ghi khi có cache record |
| `llm_reused.jsonl` | Chỉ các dự đoán tái sử dụng được |
| `llm_reconciled_all_samples.jsonl` | Đủ ID mẫu LLM; thiếu dự đoán/không đủ điều kiện vẫn là error |
| `manual_test_100.csv` | Template nhãn tay trống, số dòng theo marking, **không tự bảo đảm đúng 100** |
| `audit_summary.json` | Số mẫu thật, số cache reuse, số mẫu thiếu, nguồn/checksum |

Audit không đọc quyết định nhãn tay và không ghi đè `manual_test_100.csv` đã tồn tại. Nếu đổi QA/marking, dùng thư mục audit mới để tránh giữ nhầm template cũ. Kiểm tra `manual_test_samples` và ID mẫu trước khi gọi đây là bộ 100 test.

**Tách dev/test:** audit giữ `split=dev` từ CSV QA. Nếu cùng review đó được marking chọn làm test, audit dừng với lỗi rõ ràng để nhóm đối chiếu; không tự chuyển dev thành test. Với các dòng còn lại, cờ test trong marking quyết định test/analysis. Vẫn phải đối chiếu ID với pilot/dev đã dùng trước đó nếu nguồn QA không ghi split.

Chạy cache-only với CSV đã xác định:

```powershell
$env:GEMINI_MODEL = $modelId
$inputPath = Join-Path $auditDir 'reviews_llm_after_qa.csv'
$outputPath = "data/processed/llm_replay_$runId.jsonl"
# Đảm bảo cache trong configs/toronto.json chính là cache muốn tái sử dụng.
python run_tv4.py llm --input $inputPath --output $outputPath --skip-llm
Get-Content "$outputPath.run.json" -Raw
```

`--cache` của audit không thay đổi config của LLM. Nếu dùng cache ở vị trí khác, dùng bản config riêng trỏ tới đúng file rồi thêm `--config`. Có thể dùng `Get-FileHash $cachePath -Algorithm SHA256` trước/sau để kiểm tra cache-only giữ nguyên cache.

`cache_miss_skip_llm` là thiếu dự đoán, không phải nhãn negative. Nếu tất cả record là `error`, CLI trả mã 2 **sau khi ghi output/report**. Nếu còn `ok` hoặc `needs_review`, mã 0 không chứng minh mọi review đã thành công.

## 7. Gọi Gemini thật và chạy batch

Sau khi demo/test đạt, cần API key và ID model tài khoản được phép dùng. Không điền key vào source/config/Git:

```powershell
$env:GEMINI_API_KEY = 'DIEN_KEY_CHI_TREN_MAY_CUA_BAN'
python run_tv4.py llm --list-models
$env:GEMINI_MODEL = 'ID_MODEL_LAY_TU_DANH_SACH'
```

`--list-models` có gọi mạng; tên model trong cache cũ không bảo đảm API hiện còn hỗ trợ. Chọn model khác sẽ tạo cache key khác.

### Smoke test: tách cache thử trước khi gọi

Tạo config thử để review giả lập không bị lưu lẫn vào cache nhóm:

```powershell
$runId = Get-Date -Format 'yyyyMMdd_HHmmss_fff'
$config = Get-Content configs/toronto.json -Raw | ConvertFrom-Json
$config.cache = "data/processed/llm_smoke_cache_$runId.jsonl"
$smokeConfig = "configs/toronto_smoke_$runId.json"
$smokeJson = $config | ConvertTo-Json -Depth 20
[System.IO.File]::WriteAllText((Join-Path (Get-Location).Path $smokeConfig), $smokeJson, (New-Object System.Text.UTF8Encoding($false)))
python run_tv4.py llm --config $smokeConfig `
  --input examples/reviews_demo.csv `
  --output "data/processed/llm_api_smoke_$runId.jsonl" `
  --max-new-requests 1 --max-retries 0
```

Lệnh này có thể gọi API thật, nhưng nhiều nhất một review mới và không tự retry. Kiểm tra output/report; đây vẫn là review giả lập, không dùng để báo cáo accuracy Toronto.

### Batch dữ liệu thật

Đặt `$inputPath` tới CSV sau QA, model và config tới cache nhóm đúng fingerprint. Dùng output mới cho mỗi lần:

```powershell
$runId = Get-Date -Format 'yyyyMMdd_HHmmss_fff'
$outputPath = "data/processed/llm_batch_$runId.jsonl"
python run_tv4.py llm --input $inputPath --output $outputPath `
  --max-new-requests 10 --max-retries 0
Get-Content "$outputPath.run.json" -Raw
```

Mức 10 là lượt thử có giới hạn; tăng sau khi kiểm tra kết quả hoặc bỏ `--max-new-requests` khi muốn xử lý mọi cache miss. Hạn mức đếm **review được thử gọi**, còn retry có thể tạo thêm HTTP request. Các cache hit vẫn được đọc khi hết hạn mức hoặc sau lỗi dừng quota. HTTP 401/403/404/429 sau xử lý retry sẽ dừng thử request mới trong batch.

Chạy lại với cùng input/model/prompt/schema/config sẽ tái dùng cache đã lưu, không tiếp tục append vào output cũ. Kết thúc phiên:

```powershell
Remove-Item Env:GEMINI_API_KEY -ErrorAction SilentlyContinue
```

## 8. Nhãn tay, evaluation và bàn giao KPI

Người gán đọc [contract](docs/LLM_ANNOTATION_CONTRACT.md), điền độc lập trước khi xem dự đoán. `manual_sentiment` nhận `positive/mixed/negative`; nếu chưa chốt được thì để trống nhãn, `needs_review=true`, `note` ghi lý do. Không đổi nhãn tay chỉ để trùng LLM.

Khi đủ nhãn test, chạy **evaluator TV4 thật**, truyền rõ prediction để không bị yêu cầu baseline chưa có:

```powershell
$labelsPath = Join-Path $auditDir 'manual_test_100.csv'
python -m src.tv4_evaluation --labels $labelsPath `
  --predictions $outputPath --split test
```

Bản cuối yêu cầu ít nhất 100 nhãn test đã chốt. `--allow-partial` chỉ dành cho kiểm tra tạm trên file nhãn hợp lệ; nó **không cho phép bỏ qua ô nhãn còn trống mà chưa đánh dấu needs_review**. Dev cần `--split dev --allow-dev` và không được gọi là test độc lập.

Evaluator xuất `reports/llm_test_checks.csv`, `reports/llm_test_metrics.json` và `.csv` (dev dùng prefix `llm_pilot`). Nó ghi đè báo cáo cùng prefix ở lần sau, nên giữ bản kết quả đang bàn giao trước khi đánh giá lại.

Prediction thiếu/error/needs_review được tính là unavailable với gold đã chốt; vẫn nằm trong mẫu số metric chính. `accuracy_on_available_only` là chỉ số phụ, cần đọc cùng `coverage`. Evaluator hiện chỉ chấm sentiment, chưa chấm aspects/language. Metric từ fixture/demo không phải metric dự án.

Người làm KPI/viz nhận JSONL cùng `.run.json`, config/model/prompt version và thông tin QA. Dùng `status=ok` khi cần sentiment, thống kê riêng `needs_review/error`, join theo `(snapshot_date, review_id)` và đối chiếu `listing_id`. LLM không tạo đầy đủ metadata khu vực hoặc chuỗi thời gian; phải join nguồn tương ứng. Chưa có bằng chứng tích hợp KPI/viz thật trong ZIP review.

## 9. Đọc output và xử lý lỗi

Mỗi dòng JSONL là một record. Với kết quả API mới, runner thêm ID, model, version/hash, thời gian, usage, số request; cache hit giữ metadata của bản cache và thêm thông tin replay, nên cache cũ/demo có thể thiếu một số metadata tùy chọn.

| Trường report | Cách hiểu |
| --- | --- |
| `rows`, `status_counts`, `error_counts` | Số review và trạng thái thực tế; đọc ngay cả khi CLI trả 0 |
| `cache_hits`, `new_reviews_attempted` | Bao nhiêu review reuse / được thử gọi mới |
| `api_requests` | Số lần thử HTTP được client ghi nhận, gồm retry; không phải số request được server xác nhận tính phí |
| `prompt_tokens_new_calls`, `total_tokens_new_calls` | Token metadata đã ghi nhận; thiếu/sai metadata được tính 0, không đủ để tự kết luận chi phí |
| `started_at`, `finished_at`, `skip_llm` | Kiểm tra đúng lần chạy và chế độ |

| Tình huống | Kiểm tra / cách xử lý |
| --- | --- |
| Import thiếu module | Lấy đủ code của nhánh; giữ `src/common.py`, các module LLM và prompt/schema |
| Thiếu CSV mặc định `reviews_pilot.csv` | Truyền `--input` tới CSV có thật; demo dùng file trong `examples/` |
| Thiếu model trong cache-only | Đặt đúng `GEMINI_MODEL`, hoặc model trong config riêng |
| Cache miss | Kiểm tra đường dẫn cache, model, ID/text, prompt/schema và tham số sinh |
| HTTP 429 | Đọc chẩn đoán/quota; không xóa cache để chữa lỗi |
| JSONL hỏng | Sao lưu nguyên trạng và phục hồi có kiểm soát; reader từ chối dòng JSON sai, không tự bỏ qua |
| Input thiếu cột | Báo `ValueError` nêu trường bắt buộc còn thiếu trước khi gọi API; sửa header theo contract |
| Batch bị ngắt | Output có thể mới chỉ là một phần; cache thành công có thể giúp chạy lại |

**Các giới hạn đã tìm thấy khi review:**

- Khi preflight đạt và bắt đầu batch mới, runner xóa report cũ cùng output prefix. Report hoàn tất chỉ được ghi ở cuối; batch bị ngắt không giữ report của lần trước. Nếu preflight thất bại thì output/report cũ được giữ nguyên. Nên dùng output mới và đối chiếu timestamp/số dòng.
- Khi append vào file thiếu newline cuối, writer thêm dấu phân cách cùng record mới; nếu ghi thất bại thì rollback cả dấu phân cách và record. Cache-only giữ nguyên từng byte. JSONL đã hỏng vẫn bị reader từ chối, không tự sửa nội dung.
- Không có file lock cho hai writer; không chạy đồng thời cùng cache/output. Hard kill/mất điện vẫn có thể tạo đuôi JSONL dở; rollback/fsync không phải giao dịch nguyên tử.
- Cache trùng fingerprint dùng bản hợp lệ cuối, không chứng minh nhãn đó đúng hơn. Schema hợp lệ cũng không đồng nghĩa phân loại chính xác.

## 10. Checklist bàn giao nhánh

- [ ] Người bàn giao đã commit/push các file cần thiết và gửi commit để nhóm đối chiếu.
- [ ] Máy nhận lấy đúng `gmnh`, chạy lại help/demo/toàn bộ regression test hiện có.
- [ ] Xác định nguồn CSV QA, marking, cache và model; không coi đường dẫn minh họa là file có sẵn.
- [ ] Kiểm tra số lượng/ID bộ test và dev/test không chồng lấn trước khi tune/evaluate.
- [ ] Chạy cache-only, đối chiếu checksum cache và báo cáo; không dùng cache miss làm nhãn.
- [ ] Nếu gọi thật: smoke dùng cache riêng, batch dùng cache/model đúng và output mới.
- [ ] Hoàn tất nhãn người độc lập, chạy evaluator, bàn giao coverage/metric kèm prediction.
- [ ] Phần KPI/viz nhận đúng contract và được kiểm chứng tích hợp bằng dữ liệu thật.

Không commit API key, môi trường `.venv`, `__pycache__`, cấu hình smoke hay kết quả thử không thuộc dữ liệu nhóm. Những mục trong checklist cần người bàn giao/máy nhận xác nhận; kết quả offline trong một ZIP chưa thay thế việc nghiệm thu nhánh remote và dữ liệu thật.
