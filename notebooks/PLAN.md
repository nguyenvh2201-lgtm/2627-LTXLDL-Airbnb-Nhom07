phân tích theo cái datanew thì giảng viên yêu cầu ctoi phân tích theo mốc đấy 
• Xuất 4 sheet từ bảng tính của giảng viên ra CSV: «Phân công» (dòng của nhóm), «Listing» (1.000 id), «Review» (5.000 id + cột Mẫu LLM + cột Nhãn tay), «Vùng» (8 hình chữ nhật của thành phố). Đặt vào data/samples/ (chúng nhỏ nên commit được) với tên assignment.csv, listing_ids.csv, review_ids.csv, areas.csv. Lọc đúng dòng của nhóm theo cặp Lớp + Nhóm.
• Ghi lại: tên thành phố, tiền tệ, bốn ngày snapshot, URL gốc Inside Airbnb. Dán vào đầu configs/<city>.yaml.
• Lấy khoá Gemini API (gói miễn phí), đặt vào file .env cục bộ (đã gitignore), biến GEMINI_API_KEY.
• Tự gán nhãn tay 100 review (cảm xúc: positive / mixed / negative; có thể thêm khía cạnh). Codex chỉ dựng công cụ hỗ trợ (CSV mẫu), không được tạo nhãn thay bạn, vì nhãn là "chuẩn vàng" để đo chất lượng. Nhãn tạo bằng AI mà khai là nhãn tay là vi phạm chính sách.
• Chọn bên đặt hàng (ví dụ chính quyền thành phố, hiệp hội du lịch, quỹ đầu tư) và gắn mỗi KPI với một bên liên quan.
• Ghi vào AI_USAGE.md ngay từ đầu mọi prompt then chốt và mọi chỗ AI sai.
2. Nguyên tắc bắt buộc cho Codex
• Python 3.x, ghi phiên bản đã chạy thử vào .python-version (một dòng 3.x.y). requirements.txt ghim ==. Thư viện gợi ý (ít, dễ giải thích): pandas, pyarrow (tuỳ chọn), pyyaml, requests, python-dotenv, matplotlib, scikit-learn, langdetect (hoặc lingua-language-detector), geopandas/shapely (chỉ nếu cần ranh giới), pytest, tqdm, SDK Gemini (google-genai) hoặc gọi REST bằng requests.
• Không ghi cứng thành phố, snapshot, đường dẫn, ngưỡng QA, kích thước mẫu: tất cả nằm trong configs/<city>.yaml.
• Một lệnh chạy toàn bộ: python run_pipeline.py --config configs/<city>.yaml, có cờ --skip-llm (dùng cache, hoặc bỏ bước LLM), --skip-download (dùng data/raw/ có sẵn), --only <bước>.
• Giảng viên có thể đổi chỉ tệp cấu hình sang mốc chụp khác (chưa từng xử lý) và chạy lại. Vì vậy: không giả định ngày cụ thể trong code; đọc danh sách snapshots từ config; mọi đường ra dựng từ config.
• Khoá API chỉ đọc từ biến môi trường (os.environ), chạy được với khoá bất kỳ; không in khoá ra log; .env.example chỉ có tên biến.
• Ngẫu nhiên: dùng seed trong config cho mọi thao tác chọn mẫu để tái lập.
• Tệp calendar rất lớn: đọc bằng pd.read_csv(..., usecols=[...], chunksize=...), lọc theo listing_id trong từng khối, không nạp cả tệp.
• Kiểm tra đầu vào/đầu ra bằng assert hoặc hàm validate có thông báo rõ ràng; lỗi mạng/tải thì thử lại (retry) rồi báo lỗi dễ hiểu.
• Log ra console và reports/run_log.txt.
3. Cấu trúc repo (theo đề)
configs/<city>.yaml
data/raw/            # gitignore, do download.py sinh ra
data/processed/      # dữ liệu sạch, kpi_*.csv, llm_cache.jsonl, kết quả LLM (commit nếu <50MB)
data/samples/        # assignment.csv, listing_ids.csv, review_ids.csv, areas.csv, hand_labels.csv (>=100 nhãn: review_id, nhãn)
src/{download,filter,qa,kpi,llm,baseline,evaluate,viz}.py  (+ utils.py, config.py)
figures/  reports/  notebooks/  tests/
run_pipeline.py  .python-version  .env.example  .gitignore
AI_USAGE.md  README.md  requirements.txt
.gitignore phải loại: data/raw/, .venv/, .env, mọi tệp có khoá.
4. Cấu hình configs/<city>.yaml
Các khoá tối thiểu: city, data_root (dạng country/region/city), currency, snapshots (4 ngày), paths (raw, processed, samples, figures, reports), inputs (đường dẫn 4 CSV trong data/samples/), qa (ngưỡng giá tối đa theo tiền tệ, min_nights_cap, dedupe_keys, ngưỡng tỷ lệ thiếu…), kpi (area_col: analysis_area/neighbourhood_cleansed), llm (provider: gemini, model, sample_size: 1000, aspects, cache: data/processed/llm_cache.jsonl, api_key_env: GEMINI_API_KEY, rate_limit_per_min, batch_size), seed: 42. Có một khoá expected (số kỳ vọng: 875/125, số listing không review 50/30/25/25, 20 thiếu giá ở mốc cuối, 120–130 listing mỗi vùng) để kiểm tra, nhưng khi đổi sang mốc khác mà không có số kỳ vọng thì chỉ cảnh báo, không dừng.
5. Đặc tả từng mô-đun
5.1 download.py + filter.py (thu thập và lọc)
• Với mỗi snapshot, dựng URL: https://data.insideairbnb.com/<data_root>/<snapshot>/data/{listings,calendar,reviews}.csv.gz. Tải bằng requests (stream) về data/raw/<snapshot>/. Chỉ tải từ Inside Airbnb, không cào airbnb.com.
• Bỏ qua nếu tệp đã có và hợp lệ. Kiểm: tệp tồn tại, kích thước > 0, mở được gzip, có cột khoá (id / listing_id / date…). Ghi reports/download_manifest.csv: snapshot, tệp, URL, bytes, sha256, thời điểm tải. Đây cũng là nguồn cho phần ghi nguồn/ngày snapshot trong báo cáo.
• Lọc đúng phần của nhóm:
    ◦ listings: giữ id trong listing_ids.csv; gắn cột analysis_area từ sheet Listing; thêm cột snapshot. Kết quả: 1.000 dòng/mốc.
    ◦ calendar: đọc theo khối, giữ listing_id trong danh sách; 365.000 dòng/mốc. Chỉ giữ cột cần: listing_id, date, available, price, adjusted_price, minimum_nights, maximum_nights.
    ◦ reviews: giữ id trong review_ids.csv; 5.000 dòng/mốc (cùng 5.000 review lặp lại ở 4 mốc); thêm cờ in_llm_sample, in_hand_label từ sheet Review.
    ◦ Vùng: 8 hình chữ nhật trong areas.csv (min/max vĩ độ-kinh độ) chỉ để vẽ và tham chiếu; không phải ranh giới hành chính. Không cần geojson ranh giới nếu không dùng, nhưng có thể tải thêm visualisations/neighbourhoods.geojson làm lớp phụ.
• Kiểm tra sau lọc (bắt buộc, in ra và ghi reports/filter_checks.csv): mỗi mốc có 875 Entire home/apt và 125 Private room; số listing number_of_reviews = 0 là 50, 30, 25, 25; mốc cuối có đúng 20 listing thiếu price; mỗi vùng 120–130 listing. Sai thì dừng với thông báo "lọc sai hoặc đọc sai ID".
• Lưu bản đã lọc vào data/processed/ (parquet hoặc csv.gz) để các bước sau dùng. Kiểm dung lượng <50MB trước khi commit.
• Lưu ý dữ liệu: price là chuỗi kiểu $1,234.00 (hoặc có ký hiệu khác): làm sạch thành số. Chỉ dùng price ở mốc cuối (các mốc trước không đồng đều giữa các thành phố). Tiền tệ lấy từ config.
5.2 qa.py (làm sạch và quy tắc QA)
Mỗi quy tắc là một bản ghi: tên → điều kiện → lý do → hành động (ưu tiên gắn cờ, hạn chế xoá). Ghi reports/qa_report.csv với cột: rule_id, rule_name, table, snapshot, condition, reason, action, rows_affected, kpi_before, kpi_after. Tối thiểu có các nhóm:
• Thiếu: price thiếu ở mốc cuối (20 listing), bedrooms, review_scores_*, comments rỗng. Hành động: gắn cờ flag_missing_*, không điền bừa.
• Ngoại lai: giá > price_max_* hoặc ≤ 0; minimum_nights > min_nights_cap; accommodates/beds bất thường; dùng thêm IQR/percentile làm cờ phụ.
• Trùng: trong một mốc (dedupe_keys: [id, last_scraped]; review trùng id) và giữa các mốc (cùng id xuất hiện ở bốn mốc là bình thường, chỉ báo cáo; còn review trùng văn bản/reviewer_id thì gắn cờ).
• Kiểu sai: available t/f → bool; date → datetime; tỷ lệ % dạng chuỗi (host_response_rate) → số; price → số.
• Danh mục lệch: room_type, property_type có biến thể chính tả/hiếm → gom nhóm "Other", cờ; chuẩn hoá analysis_area.
• Nhất quán chéo: number_of_reviews so với số review thực tế; first_review ≤ last_review; calendar thiếu ngày (phải đủ 365 ngày/listing).
Mỗi quy tắc tính KPI trước/sau (ví dụ giá trung vị, tỷ lệ lấp đầy) để chứng minh tác động. Xuất dữ liệu sạch + các cột cờ.
5.3 kpi.py (5–8 KPI, gắn với bên liên quan)
Mỗi KPI có mô tả: kpi_id, tên, bên liên quan, mục tiêu, công thức, đơn vị (ghi rõ tiền tệ); tính sau QA; lưu data/processed/kpi_*.csv (ví dụ kpi_area.csv, kpi_time.csv, kpi_llm.csv, kpi_summary.csv) và bảng định nghĩa reports/kpi_definitions.csv. Gợi ý bộ KPI (nhóm chọn và bảo vệ):
1. Giá ngủ trung vị theo vùng (mốc cuối, tiền tệ thành phố): theo khu vực.
2. Tỷ lệ lấp đầy ước tính theo tháng/mốc = 1 − available/ngày (calendar): theo thời gian và theo vùng.
3. Tỷ lệ listing "khả dụng cao" quanh năm / nghi kinh doanh chuyên nghiệp (phần trăm listing có tỷ lệ available cao + nhiều review): theo vùng.
4. Thay đổi khả dụng giữa 4 mốc (xu hướng theo quý).
5. Tỷ lệ listing có minimum_nights ≥ 30 (dấu hiệu thuê dài hạn): theo vùng.
6. Tốc độ review (review mới/tháng): theo thời gian.
7. KPI dùng LLM: tỷ lệ cảm xúc tiêu cực theo vùng, hoặc điểm khía cạnh (sạch sẽ, vị trí…) theo vùng. Bắt buộc có.
8. Tỷ trọng ngôn ngữ review (du khách quốc tế vs nội địa), dùng LLM/langdetect.
Cần ít nhất một KPI theo vùng (analysis_area/neighbourhood_cleansed) và một theo thời gian.
5.4 llm.py (trích xuất có cấu trúc bằng LLM)
• Mẫu: llm.sample_size review (1.000, đã cho sẵn bởi cột «Mẫu LLM» trong sheet; nếu mốc khác thì chọn có seed) và giải thích cách chọn (ví dụ chọn sẵn theo giảng viên, có kiểm tra phân bố theo vùng/ngôn ngữ/thời gian). Đầu ra mỗi review: review_id, sentiment ∈ {positive, mixed, negative}, aspects (danh sách khía cạnh khen/chê: khía cạnh trong config × {praise, complaint}), language (mã ISO 639-1).
• Ép JSON có cấu trúc (response schema của Gemini, response_mime_type: application/json), temperature thấp, validate đầu ra bằng schema nghiêm ngặt; giá trị lạ → thử lại, rồi gắn parse_error.
• Gửi theo lô nhỏ (ví dụ 10–20 review/lần) để tiết kiệm lượt gọi; có giới hạn tốc độ (rate_limit_per_min), retry với backoff khi gặp 429/5xx, ghi lại lỗi.
• Cache JSONL (data/processed/llm_cache.jsonl): khoá = hash của (review_id, văn bản, tên model, phiên bản prompt). Chạy lại thì dùng cache; chỉ gọi API cho review thiếu. Cache được commit để nhóm tái lập số liệu nếu không có khoá.
• --skip-llm: không gọi API; dùng cache nếu có. Nếu không có cache và không có khoá thì bỏ bước này, vẫn chạy các bước khác và cảnh báo rõ ràng. Khi giảng viên chạy với khoá của họ, bước này phải gọi thật và chạy được với khoá bất kỳ.
• Khoá chỉ từ os.environ[llm.api_key_env].
• Ước tính chi phí: đếm token (hoặc xấp xỉ theo ký tự) trung bình mỗi review trong mẫu, nhân cho tổng số review của thành phố (lấy từ bảng reviews đầy đủ của thành phố; nếu không có thì ghi giả định), nhân giá/1M token của model (ghi trong config kèm ngày tra cứu). Xuất reports/llm_cost_estimate.csv.
• Prompt lưu thành hằng số/ tệp riêng có số phiên bản (prompts/extract_v1.txt) để ghi vào AI_USAGE.md và báo cáo.
5.5 baseline.py (đối chứng không LLM)
Review có nhiều ngôn ngữ và không có điểm sao. Phương án đề xuất, đơn giản và giải thích được:
• Nhận diện ngôn ngữ bằng langdetect/lingua (đối chứng cho trường language).
• Cảm xúc: từ điển từ khoá tích cực/tiêu cực theo ngôn ngữ chính (en, và vài ngôn ngữ phổ biến của thành phố) + quy tắc (phủ định, "but/pero/mais" → mixed). Khía cạnh: từ khoá theo từng khía cạnh trong config.
• (Tuỳ chọn) mô hình TF-IDF + Logistic Regression huấn luyện với cross-validation trên chính 100 nhãn tay, không để rò rỉ (không huấn luyện và chấm trên cùng mẫu).
• Chạy baseline trên cùng mẫu LLM để so sánh công bằng.
5.6 evaluate.py (chấm LLM vs đối chứng)
• Đọc data/samples/hand_labels.csv (review_id, sentiment, tuỳ chọn aspects, language). Kiểm ≥100 nhãn, id nằm trong mẫu LLM, nhãn hợp lệ.
• Tính accuracy, macro-F1, F1 từng lớp, ma trận nhầm lẫn cho cả LLM và baseline; với khía cạnh: precision/recall/F1 mức nhãn. Xuất reports/eval_metrics.csv, reports/confusion_*.csv.
• Phân tích lỗi: xuất reports/error_analysis.csv liệt kê review sai (văn bản, nhãn tay, LLM, baseline, nhóm lỗi: mỉa mai/mixed/ngôn ngữ ít gặp/review ngắn…). Nhóm tự đọc và viết nhận định vào báo cáo.
• Báo cáo khoảng tin cậy (bootstrap) vì n=100 nhỏ.
5.7 viz.py (hình tự động vào figures/)
Luôn sinh bằng code, tên cố định, có tiêu đề, trục, đơn vị, nguồn. Tối thiểu:
• Không gian: bản đồ phân tán lat/lon các listing tô màu theo giá hoặc theo vùng, vẽ 8 hình chữ nhật; bản đồ nhiệt/bar KPI theo vùng.
• Thời gian: đường tỷ lệ lấp đầy theo ngày/tháng cho 4 mốc; xu hướng KPI giữa các mốc.
• LLM: cảm xúc theo vùng (stacked bar), khía cạnh được khen/chê nhiều nhất, so sánh F1 LLM vs baseline, ma trận nhầm lẫn.
• Hình cho QA: tác động QA trước/sau (tuỳ chọn).
5.8 run_pipeline.py
Thứ tự: download → filter → validate → qa → kpi → (llm → baseline → evaluate) → viz → tổng hợp bảng kết quả cho báo cáo. Mỗi bước độc lập, đọc đầu vào từ thư mục processed, ghi đầu ra có tên cố định, idempotent (chạy lại ra cùng kết quả). Cuối cùng in danh sách tệp đầu ra và in cảnh báo nếu thiếu tệp.
6. Tệp đầu ra kỳ vọng (giảng viên kiểm tra)
data/processed/ (listings sạch, calendar sạch, reviews sạch, kpi_*.csv, llm_cache.jsonl, kết quả LLM), reports/qa_report.csv, reports/eval_metrics.csv, reports/report.pdf, từ điển dữ liệu (reports/data_dictionary.csv), figures/*.png. Ghi danh sách này vào README để giảng viên đối chiếu. Đề bài chưa công bố tên tệp chính thức cho test chung, nên giữ đúng các tên và đường dẫn đã nêu trong đề, và theo dõi thông báo bổ sung.
7. Kiểm thử (tests/, chạy bằng pytest)
• test_config: config đọc được, đủ 4 snapshot, không có đường dẫn tuyệt đối.
• test_filter: dùng mẫu nhỏ trong data/samples/ (giả lập vài trăm dòng) kiểm tra lọc đúng, calendar đọc theo khối cho cùng kết quả với đọc một lần.
• test_qa: mỗi quy tắc có ít nhất một ca test nhỏ; qa_report.csv có đúng cột.
• test_kpi: công thức đúng trên dữ liệu tay tính được; KPI có đủ cột đơn vị/tiền tệ.
• test_llm: mock API (không gọi thật), kiểm parse JSON, retry, cache, --skip-llm, đọc khoá từ môi trường.
• test_evaluate: metric đúng trên ví dụ nhỏ.
• Một test "smoke" chạy toàn bộ trên dữ liệu mẫu nhỏ để nhanh.
8. Tài liệu bắt buộc
• README.md: giới thiệu, yêu cầu máy, cách tạo môi trường (python -m venv .venv, pip install -r requirements.txt, tham chiếu .python-version), cách đặt biến môi trường GEMINI_API_KEY, lệnh chạy (python run_pipeline.py --config configs/<city>.yaml), các cờ, danh sách tệp đầu ra, cách chạy lại với mốc khác (chỉ sửa config), cách chạy test, ghi nguồn Inside Airbnb (CC BY 4.0) và ngày 4 snapshot.
• AI_USAGE.md (đúng 4 mục của đề): Công cụ đã dùng (vào việc gì) · Prompt then chốt (5–10, ghi bước nào, tệp nào) · AI sai ở đâu (ví dụ thật) · Nhóm kiểm chứng thế nào. Cập nhật suốt quá trình, khai thật.
• Báo cáo PDF ≤10 trang (format sẽ công bố sau): bên đặt hàng và mục tiêu; dữ liệu và nguồn/ngày snapshot; QA; KPI; trực quan hoá; phần LLM (mẫu, prompt, đối chứng, accuracy/F1, phân tích lỗi, chi phí); hạn chế; ghi mã commit của tag final. Codex có thể soạn bản nháp (Markdown/LaTeX → PDF) dựa trên số liệu sinh ra, nhưng nhóm tự viết nhận định và kiểm lại mọi con số.
• Từ điển dữ liệu reports/data_dictionary.csv: cột, kiểu, ý nghĩa, ghi chú QA.
9. Các giai đoạn giao cho Codex (kèm nghiệm thu)
Vì hạn là 22/11 và hôm nay là 11/11, nên dồn theo lịch dưới đây.
GĐ 1 – Khung dự án (hôm nay): tạo cấu trúc repo, .gitignore, .env.example, requirements.txt, .python-version, configs/<city>.yaml, config.py, run_pipeline.py khung với các bước rỗng. Nghiệm thu: python run_pipeline.py --config ... chạy không lỗi và in các bước.
GĐ 2 – Tải và lọc (ngày 1–2): download.py, filter.py, kiểm tra đếm. Nghiệm thu: bốn số kiểm tra ở 5.1 đúng cho cả 4 mốc; calendar không tràn RAM.
GĐ 3 – QA (ngày 2–3): qa.py, qa_report.csv. Nghiệm thu: đủ 5 nhóm quy tắc, mỗi dòng có số dòng bị tác động và KPI trước/sau.
GĐ 4 – KPI (ngày 3–4): kpi.py, kpi_*.csv, kpi_definitions.csv. Nghiệm thu: 5–8 KPI, có theo vùng và theo thời gian.
GĐ 5 – LLM (ngày 4–6): llm.py + cache, thử trên 20 review, sau đó chạy đủ mẫu 1.000. Bạn gán xong 100 nhãn tay song song ở giai đoạn này. Nghiệm thu: JSON hợp lệ >98%, cache hoạt động, chạy lần hai không gọi API.
GĐ 6 – Baseline và đánh giá (ngày 6–7): baseline.py, evaluate.py, error_analysis.csv. Nghiệm thu: có accuracy/F1 cả hai, ma trận nhầm lẫn, danh sách lỗi.
GĐ 7 – KPI LLM và hình (ngày 7–8): bổ sung KPI LLM, viz.py. Nghiệm thu: có hình cho không gian, thời gian, LLM trong figures/.
GĐ 8 – Kiểm thử và tái lập (ngày 8–9): viết test, tự kiểm "máy sạch": clone vào thư mục mới, tạo venv theo README, chạy một lệnh, so sánh số liệu với báo cáo; thử đổi một snapshot trong config để chắc không ghi cứng.
GĐ 9 – Báo cáo và hoàn thiện (ngày 9–10): báo cáo PDF, AI_USAGE.md, README. Cả nhóm đọc lại.
GĐ 10 – Nộp (trước 23:59 22/11): git tag final, git push origin final, ghi mã commit vào báo cáo, kiểm lại repo trên GitHub (không có data/raw, không có khoá, đã mời tài khoản giảng viên).
10. Rủi ro thường gặp và cách xử lý
• Hết quota Gemini miễn phí: gọi theo lô, cache, giới hạn tốc độ, có thể chia chạy qua nhiều ngày; ghi lại trong báo cáo.
• Đọc nhầm ID/lọc sai: dựa vào 4 phép kiểm ở mục 5.1.
• Tệp calendar quá lớn: usecols + chunksize; không dùng read_csv toàn bộ.
• Giá chỉ tin cậy ở mốc cuối: không so giá giữa các mốc; dùng calendar chủ yếu cho khả dụng.
• Review đa ngôn ngữ: baseline có thể yếu; nêu rõ trong phân tích lỗi thay vì che giấu.
• Vấn đáp không dùng AI: mỗi người phải tự chạy lại và đọc từng mô-đun; chuẩn bị giải thích các lựa chọn (vì sao cỡ mẫu này, vì sao quy tắc QA này, vì sao KPI này).
• Không chắc tên tệp đầu ra khi test chung: bám tên trong đề; nếu giảng viên thông báo thêm thì đổi ngay.
11. Checklist nộp bài
[ ] Repo riêng tư, đúng tên, mời cả nhóm và tài khoản giảng viên
[ ] data/raw/ trong .gitignore, không có dữ liệu thô/khoá API trên GitHub
[ ] Một lệnh chạy được trên máy sạch, tham số từ config
[ ] Số kiểm tra 875/125, 50/30/25/25, 20 thiếu giá, 120–130 mỗi vùng
[ ] qa_report.csv, kpi_*.csv, figures/, eval_metrics.csv đủ
[ ] ≥100 nhãn tay thật trong data/samples/hand_labels.csv
[ ] Ước tính chi phí LLM
[ ] AI_USAGE.md đủ 4 mục và trung thực
[ ] README đủ, có tên biến môi trường
[ ] Báo cáo PDF ≤10 trang, có nguồn/ngày snapshot và mã commit
[ ] git tag final đã push
12. HƯỚNG DẪN GIAO CHO CODEX (dán trực tiếp)
Phần này là văn bản để bạn dán nguyên văn cho Codex. Thứ tự: tạo AGENTS.md (12.1) → chạy các prompt GĐ0 → GĐ10 lần lượt. Chỗ có dấu <...> là thông tin bạn điền (thành phố, tiền tệ, ngày snapshot, tên cột thật).
12.1 Tệp AGENTS.md (đặt ở gốc repo, Codex tự đọc mỗi lần)
# Quy tắc làm việc cho agent

Dự án: BTL Inside Airbnb (UET.DSE2049). Đọc docs/yeu_cau.txt và PLAN.md trước khi làm.

## Bắt buộc
1. Chỉ làm đúng giai đoạn được giao. Không tự thêm tính năng, không đổi cấu trúc thư mục.
2. Không ghi cứng thành phố, ngày snapshot, ngưỡng, kích thước mẫu, tên cột, đường dẫn: tất cả đọc từ configs/<city>.yaml.
3. Khoá API chỉ đọc từ os.environ (tên biến lấy từ config llm.api_key_env). Không in, không log, không commit khoá. Không tạo file .env có khoá thật.
4. Không commit data/raw/. Chỉ commit data/processed/ nếu tổng < 50 MB (kiểm bằng du trước khi commit).
5. Mã đơn giản, dễ giải thích khi vấn đáp: mỗi hàm một việc, tên biến rõ nghĩa, chú thích tiếng Việt cho mọi quyết định (vì sao chọn ngưỡng này, vì sao gắn cờ thay vì xoá). Tránh one-liner phức tạp, tránh metaprogramming, tránh thư viện không cần thiết.
6. Mỗi bước đọc đầu vào từ data/processed/ và ghi đầu ra tên cố định. Chạy lại cho cùng kết quả (idempotent, dùng seed trong config).
7. calendar rất lớn: luôn đọc bằng usecols + chunksize, lọc theo listing_id trong từng khối. Không đọc cả tệp vào RAM.
8. Mọi giả định phải được assert/validate với thông báo lỗi tiếng Việt rõ ràng. Không nuốt lỗi bằng except rỗng.
9. Không bịa số liệu, không bịa nhãn tay, không tạo dữ liệu giả trong data/processed/. Dữ liệu giả chỉ nằm trong tests/fixtures/.
10. Sau mỗi giai đoạn: chạy pytest + lệnh nghiệm thu của giai đoạn, rồi báo cáo: đã làm gì, lệnh đã chạy, kết quả, điều chưa chắc chắn.
11. Cuối mỗi giai đoạn, thêm vào AI_USAGE.md một mục ngắn: đã nhờ agent làm gì, và những chỗ agent từng sai hoặc cần sửa (nếu có).

## Phong cách
- Python 3, type hints cho hàm công khai, docstring ngắn tiếng Việt.
- Dùng pathlib, logging (không print rải rác), argparse cho CLI.
- Mỗi mô-đun có hàm run(cfg) làm điểm vào, và chạy độc lập được: python -m src.qa --config configs/<city>.yaml
12.2 Prompt GĐ0 – Khảo sát tệp ID (làm trước tiên)
Đọc AGENTS.md, PLAN.md, docs/yeu_cau.txt.
Trong data/samples/ có tệp(các tệp) chứa danh sách ID của nhóm tôi: <tên tệp>.
Việc cần làm (chưa viết pipeline):
1. Viết script tools/inspect_ids.py: in ra tên sheet/tệp, tên cột, kiểu dữ liệu, số dòng, 5 dòng đầu, số giá trị thiếu mỗi cột, số giá trị duy nhất của cột id.
2. Nếu là .xlsx thì dùng openpyxl (thêm vào requirements.txt, ghim phiên bản). Nếu có nhiều sheet thì in từng sheet.
3. Xác định và in ra: (a) sheet Phân công: dòng của nhóm lọc theo cặp Lớp + Nhóm; (b) sheet Listing: số id, cột analysis_area; (c) sheet Review: số id, cột Mẫu LLM (số dòng có x), cột Nhãn tay (số dòng có x), kiểm tra Nhãn tay ⊂ Mẫu LLM; (d) sheet Vùng: 8 hình chữ nhật của thành phố và dạng toạ độ.
4. In ra các kiểm tra kỳ vọng: 1.000 id listing, 5.000 id review, 1.000 mẫu LLM, 100 nhãn tay, 8 vùng, id không trùng.
5. Xuất ra data/samples/ bốn CSV chuẩn: listing_ids.csv (id, analysis_area), review_ids.csv (id, in_llm_sample, in_hand_label), areas.csv (area, lat_min, lat_max, lon_min, lon_max), assignment.csv (city, currency, snapshots, data_root).
6. Đề xuất khối inputs.columns để dán vào configs/<city>.yaml (ánh xạ tên cột thật).
Không đoán: nếu tên cột hay giá trị đánh dấu không rõ, dừng lại và liệt kê các khả năng để tôi chọn.
Nghiệm thu: python tools/inspect_ids.py chạy được và 4 CSV chuẩn được tạo với số dòng đúng.
12.3 Prompt GĐ1 – Khung dự án
Đọc AGENTS.md và PLAN.md. Chỉ làm GĐ1.
Tạo cấu trúc repo theo mục 3 của PLAN.md: các thư mục, src/__init__.py, tests/, notebooks/, figures/.gitkeep, reports/.gitkeep.
Tạo: .gitignore (data/raw/, .venv/, .env, __pycache__/, *.key, .pytest_cache/), .env.example (chỉ GEMINI_API_KEY=), .python-version (phiên bản đang dùng, lấy bằng python --version), requirements.txt (ghim ==; chạy pip freeze rồi giữ các gói trực tiếp và phụ thuộc cần thiết), README.md khung.
Tạo configs/<city>.yaml đầy đủ khoá như mục 4 của PLAN.md với giá trị: city=<...>, data_root=<country/region/city>, currency=<...>, snapshots=[<4 ngày>], seed=42. Thêm khối inputs (đường dẫn 4 CSV) và khối inputs.columns (ánh xạ cột).
Tạo src/config.py: hàm load_config(path) dùng yaml.safe_load, validate: đủ 4 snapshot đúng định dạng YYYY-MM-DD, không trùng, các khoá bắt buộc tồn tại; trả về dict (hoặc dataclass). Lỗi thiếu khoá phải nêu tên khoá.
Tạo src/utils.py: setup_logging, ensure_dir, snapshot_dir(cfg, snapshot), read_ids(path).
Tạo run_pipeline.py: argparse --config, --skip-download, --skip-llm, --only <bước>; danh sách bước theo thứ tự download, filter, qa, kpi, llm, baseline, evaluate, viz, summary; mỗi bước gọi src.<bước>.run(cfg); bước chưa làm thì log 'chưa cài đặt' và bỏ qua; ghi log vào reports/run_log.txt; cuối cùng liệt kê tệp đầu ra còn thiếu.
Nghiệm thu: python run_pipeline.py --config configs/<city>.yaml chạy hết không lỗi và in đủ các bước; pytest chạy được (có tests/test_config.py).
12.4 Prompt GĐ2 – Tải và lọc dữ liệu
Đọc AGENTS.md và PLAN.md mục 5.1. Chỉ làm GĐ2: src/download.py và src/filter.py.

src/download.py
- build_url(cfg, snapshot, table) -> 'https://data.insideairbnb.com/<data_root>/<snapshot>/data/<table>.csv.gz' với table ∈ {listings, calendar, reviews}.
- download_file(url, dest, retries=3): requests stream, ghi vào tệp tạm rồi đổi tên, retry có backoff, timeout. Chỉ tải từ data.insideairbnb.com.
- verify_file(path, table): tồn tại, > 0 byte, mở được gzip, đọc 1 dòng đầu, có cột khoá (listings: id; calendar: listing_id,date; reviews: id,listing_id,date,comments). Báo lỗi rõ ràng nếu thiếu.
- run(cfg): với mỗi snapshot × 3 bảng, bỏ qua nếu đã có và hợp lệ, tải nếu chưa. Ghi reports/download_manifest.csv: snapshot, table, url, bytes, sha256, downloaded_at_utc.
- Nếu không có mạng hoặc tải thất bại: dừng với thông báo nêu URL và gợi ý kiểm tra cài đặt mạng.

src/filter.py
- load_ids(cfg): đọc listing_ids.csv, review_ids.csv, areas.csv.
- filter_listings(cfg, snapshot): đọc listings.csv.gz (low_memory=False), giữ id ∈ listing_ids, merge analysis_area, thêm cột snapshot; sắp xếp theo id. Làm sạch price: bỏ ký hiệu tiền tệ và dấu phẩy, chuyển float, giữ NaN nếu thiếu (chỉ dùng price ở snapshot cuối).
- filter_calendar(cfg, snapshot): đọc theo chunksize=500_000 với usecols=[listing_id,date,available,price,adjusted_price,minimum_nights,maximum_nights] (chỉ cột có trong tệp), giữ listing_id ∈ listing_ids, gom các khối lại; thêm snapshot; available 't'/'f' -> bool.
- filter_reviews(cfg, snapshot): giữ id ∈ review_ids; thêm cờ in_llm_sample, in_hand_label từ review_ids.csv; thêm snapshot.
- validate(cfg, tables): KIỂM TRA BẮT BUỘC, ghi reports/filter_checks.csv (check, snapshot, expected, actual, passed) và dừng nếu sai:
  * listings mỗi snapshot = 1000 dòng, id duy nhất, cùng 1000 id ở cả 4 snapshot.
  * room_type: 875 'Entire home/apt' và 125 'Private room' mỗi snapshot.
  * số listing number_of_reviews == 0 lần lượt 50, 30, 25, 25 (theo thứ tự 4 snapshot).
  * snapshot cuối: đúng 20 listing thiếu price.
  * mỗi analysis_area có 120–130 listing; có đúng 8 vùng.
  * calendar: 365000 dòng mỗi snapshot (365 ngày × 1000 listing), không thiếu ngày.
  * reviews: 5000 dòng mỗi snapshot, id duy nhất, cùng 5000 id ở 4 snapshot; 1000 in_llm_sample; 100 in_hand_label và nằm trong mẫu LLM.
  Khi chạy với snapshot khác mà config.expected không có số kỳ vọng: chỉ cảnh báo, không dừng.
- Ghi ra data/processed/: listings_raw_filtered.parquet, calendar_raw_filtered.parquet, reviews_raw_filtered.parquet (nối 4 snapshot, có cột snapshot). Nếu không có pyarrow thì dùng csv.gz. Kiểm tra dung lượng.
- Xuất tools/area_assign_check.py (tuỳ chọn): kiểm lat/lon của từng listing có nằm trong hình chữ nhật của analysis_area, in số listing lệch.

Test: tests/test_filter.py dùng tests/fixtures/ (vài trăm dòng giả) kiểm lọc đúng, đọc chunk cho cùng kết quả đọc một lần, validate báo lỗi khi cố tình sai số lượng.
Nghiệm thu: python run_pipeline.py --config configs/<city>.yaml --only download,filter; reports/filter_checks.csv tất cả passed=True; bộ nhớ không tràn khi đọc calendar.
12.5 Prompt GĐ3 – QA
Đọc AGENTS.md và PLAN.md mục 5.2. Chỉ làm GĐ3: src/qa.py.

Thiết kế: mỗi quy tắc là một hàm nhận DataFrame và trả (df_đã_gắn_cờ, bản_ghi). Dùng một cấu trúc Rule(rule_id, name, table, condition, reason, action) để ghi tài liệu. ƯU TIÊN GẮN CỜ (cột flag_*), chỉ loại bỏ khi là bản ghi trùng đúng nghĩa. Đo KPI trước/sau cho mỗi quy tắc (dùng 2 KPI đơn giản: giá trung vị ở snapshot cuối, tỷ lệ lấp đầy trung bình).

Quy tắc tối thiểu (đặt mã rõ ràng):
- MISS-01 listings: price thiếu (snapshot cuối) -> gắn flag_price_missing, không điền; KPI giá loại các dòng này.
- MISS-02 listings: thiếu bedrooms/beds/review_scores_rating -> flag_missing_*.
- MISS-03 reviews: comments rỗng/chỉ khoảng trắng -> flag_empty_comment, loại khỏi mẫu LLM nếu có.
- OUT-01 listings: price <= 0 hoặc > qa.price_max (theo tiền tệ) -> flag_price_outlier.
- OUT-02 listings/calendar: minimum_nights > qa.min_nights_cap hoặc < 1 -> flag_minnights_outlier.
- OUT-03 listings: accommodates/beds/bedrooms ngoài khoảng hợp lý, hoặc vượt percentile 99.5 -> flag_capacity_outlier.
- DUP-01 listings: trùng theo qa.dedupe_keys trong cùng snapshot -> giữ bản đầu, ghi số dòng bị loại.
- DUP-02 reviews: trùng id trong cùng snapshot -> loại bản trùng; trùng nội dung (listing_id+reviewer_id+comments) -> flag_dup_review.
- DUP-03 giữa các snapshot: kiểm id listing/review xuất hiện ở cả 4 snapshot (bình thường) và nhận diện id đổi thuộc tính bất thường (ví dụ room_type đổi giữa các snapshot) -> flag_attr_changed; chỉ báo cáo, không loại.
- TYPE-01: ép kiểu date, available (bool), price (float), host_response_rate/host_acceptance_rate (%->float), các cột boolean 't/f'; đếm số giá trị không ép được -> NaN + cờ.
- CAT-01 listings: room_type chuẩn hoá (strip, thống nhất chữ hoa/thường); property_type hiếm (< 1% tổng) gom thành 'Other' trong cột mới property_type_grp, giữ cột gốc.
- CAT-02 listings: analysis_area có giá trị lạ so với 8 vùng trong areas.csv -> flag_area_unknown.
- CONS-01 listings: first_review > last_review hoặc number_of_reviews == 0 nhưng có first_review -> flag_review_inconsistent.
- CONS-02 calendar: mỗi listing phải đủ 365 ngày duy nhất mỗi snapshot -> báo cáo thiếu/trùng; trùng thì loại.
- CONS-03 listings vs calendar: listing có trong listings mà không có trong calendar và ngược lại.

Đầu ra:
- data/processed/listings_clean.parquet, calendar_clean.parquet, reviews_clean.parquet (giữ mọi cột cờ).
- reports/qa_report.csv cột: rule_id, rule_name, table, snapshot, condition, reason, action, rows_before, rows_affected, rows_after, kpi_name, kpi_before, kpi_after. Mỗi quy tắc × mỗi snapshot một dòng (hoặc 'all').
- reports/data_dictionary.csv: table, column, dtype, description, qa_notes (điền mô tả ngắn cho các cột chính; cột còn lại ghi 'từ Inside Airbnb').

Test: tests/test_qa.py: mỗi quy tắc ít nhất một ca (dữ liệu nhỏ có lỗi cố ý), kiểm cột qa_report.csv, kiểm số dòng không đổi khi chỉ gắn cờ.
Nghiệm thu: --only qa chạy được; qa_report.csv có đủ 5 nhóm: thiếu, ngoại lai, trùng (trong và giữa snapshot), kiểu sai, danh mục lệch; số dòng trong listings_clean vẫn 1000/snapshot trừ khi có trùng thật.
12.6 Prompt GĐ4 – KPI
Đọc AGENTS.md và PLAN.md mục 5.3. Chỉ làm GĐ4: src/kpi.py.
KPI tính SAU QA, từ *_clean.parquet. Mọi KPI loại các dòng có cờ chất lượng liên quan (ghi rõ trong định nghĩa). Giá chỉ lấy snapshot cuối, đơn vị <tiền tệ trong config>.

Bên đặt hàng: <điền, ví dụ 'Sở Du lịch thành phố'>. Cài đặt 7 KPI sau (điều chỉnh theo bên đặt hàng nếu tôi đổi):
K1 Giá trung vị theo vùng (snapshot cuối): median(price) nhóm theo analysis_area, loại flag_price_missing và flag_price_outlier. Đơn vị: tiền tệ/đêm. Bên liên quan: du khách, cơ quan quản lý.
K2 Tỷ lệ lấp đầy ước tính theo vùng và theo snapshot: (số ngày available=False)/(tổng ngày-listing) trong calendar. Đơn vị: %. Ghi chú: 'đã đặt' và 'chủ nhà chặn' không phân biệt được, đây là cận trên.
K3 Tỷ lệ lấp đầy theo tháng (calendar, mỗi snapshot): chuỗi thời gian theo tháng của ngày lịch. Đơn vị: %.
K4 Tỷ lệ listing thuê dài hạn: % listing có minimum_nights >= 30, theo vùng và snapshot. Đơn vị: %.
K5 Tốc độ review mới: số review có date trong từng quý chia số listing, theo snapshot hoặc theo quý (reviews). Đơn vị: review/listing/quý.
K6 Tỷ lệ listing không có review (number_of_reviews == 0) theo snapshot: kiểm chứng 50/30/25/25. Đơn vị: %.
K7 (LLM) Tỷ lệ cảm xúc tiêu cực theo vùng và điểm khía cạnh (khen − chê)/(khen + chê) mỗi khía cạnh theo vùng, tính từ kết quả LLM trên mẫu. Đơn vị: %, chỉ số [-1,1]. Nếu chưa có kết quả LLM thì bỏ qua, ghi cảnh báo.

Đầu ra:
- data/processed/kpi_area.csv (area, kpi_id, value, unit, n), kpi_time.csv (period, snapshot, kpi_id, value, unit, n), kpi_llm.csv, kpi_summary.csv.
- reports/kpi_definitions.csv: kpi_id, name, stakeholder, goal, formula, unit, currency, filters_after_qa.
Mọi KPI ghi cột n (cỡ mẫu) để người đọc biết độ tin cậy.
Test: tests/test_kpi.py: tính tay trên dữ liệu 10 dòng và so khớp.
Nghiệm thu: --only kpi chạy được; có ít nhất một KPI theo vùng và một theo thời gian; kpi_definitions.csv đủ 5 trường: tên, mục tiêu, công thức, đơn vị, tiền tệ.
12.7 Prompt GĐ5 – Trích xuất bằng LLM
Đọc AGENTS.md và PLAN.md mục 5.4. Chỉ làm GĐ5: src/llm.py và prompts/extract_v1.txt.

Đầu vào: reviews_clean.parquet, lọc in_llm_sample == True và flag_empty_comment == False, loại trùng review id (lấy một bản, vì cùng 5.000 review lặp ở 4 snapshot). Nếu số dòng khác cfg.llm.sample_size thì cảnh báo; nếu mốc khác thì chọn mẫu có seed, phân tầng theo analysis_area (qua listing) và ngôn ngữ.

Gọi API:
- Nhà cung cấp: Gemini (google-genai, hoặc REST bằng requests; chọn cách ít phụ thuộc nhất). Tên model từ cfg.llm.model. Khoá từ os.environ[cfg.llm.api_key_env]; nếu thiếu khoá và không có cache cho review nào đó: log cảnh báo rõ ràng, dừng bước LLM (không làm hỏng các bước khác).
- temperature=0, response_mime_type='application/json', truyền response schema.
- Gửi theo lô cfg.llm.batch_size review (mặc định 10), mỗi review kèm review_id; yêu cầu trả mảng JSON cùng thứ tự và cùng review_id. Kiểm khớp id; thiếu/thừa id thì gửi lại các review lỗi từng cái một.
- Giới hạn tốc độ cfg.llm.rate_limit_per_min (time.sleep), retry tối đa 5 lần với exponential backoff khi 429/5xx/timeout, đọc header Retry-After nếu có.
- Cache JSONL (cfg.llm.cache): mỗi dòng {key, review_id, model, prompt_version, result, ts}. key = sha256(review_id + comments + model + prompt_version). Ghi nối từng lô ngay sau khi nhận (không mất công khi bị ngắt). Chạy lại chỉ gọi review chưa có trong cache.
- Cờ --skip-llm: không gọi API; dùng cache sẵn có; thiếu thì để trống và cảnh báo.
- Ghi data/processed/llm_results.parquet và llm_results.csv: review_id, sentiment, aspects_praise (list), aspects_complaint (list), language, parse_error (bool), model, prompt_version.
- Truncate review dài hơn 1500 ký tự (ghi cờ truncated).
- Ước tính chi phí: src/llm.py hàm estimate_cost(cfg) -> reports/llm_cost_estimate.csv: số review mẫu, số token vào/ra trung bình (đo từ usage_metadata nếu có, nếu không thì ước theo ký tự/4), tổng số review của thành phố (tham số cfg.llm.city_total_reviews, tôi sẽ điền; nếu trống thì dùng giả định ghi rõ), giá/1M token từ cfg.llm.price_per_m_input/output và cfg.llm.price_date, kết quả ước tính USD. Không bịa giá: nếu cfg không có giá thì để trống và ghi 'cần điền'.

File prompts/extract_v1.txt (system prompt, dùng nguyên văn):
---
Bạn là hệ thống trích xuất thông tin từ đánh giá của khách Airbnb. Đánh giá có thể bằng nhiều ngôn ngữ.
Với MỖI đánh giá, trả về một đối tượng JSON gồm:
- review_id: giữ nguyên id đã cho.
- sentiment: một trong 'positive', 'mixed', 'negative'. 'mixed' khi có cả khen và chê rõ ràng. Nếu chỉ có lời khen chung chung thì 'positive'. Chỉ 'negative' khi nội dung chủ yếu là phàn nàn.
- aspects_praise: danh sách khía cạnh được KHEN, chọn trong: {aspects}. Chỉ chọn khi đánh giá nói trực tiếp.
- aspects_complaint: danh sách khía cạnh bị CHÊ, chọn trong cùng danh sách.
- language: mã ngôn ngữ ISO 639-1 của đánh giá (en, es, fr, ...). Dùng 'und' nếu không xác định.
Quy tắc: không suy diễn ngoài văn bản; không thêm khía cạnh ngoài danh sách; nếu không có khía cạnh thì trả danh sách rỗng; chỉ trả JSON, không giải thích.
---

JSON schema đầu ra: mảng các object {review_id: string, sentiment: enum[positive,mixed,negative], aspects_praise: array<enum aspects>, aspects_complaint: array<enum aspects>, language: string}. Các khía cạnh lấy từ cfg.llm.aspects (không ghi cứng); khi dùng khía cạnh tiếng Việt, đặt thêm ánh xạ sang mã tiếng Anh ngắn (location, cleanliness, host, value, amenities, noise, safety) trong config để dễ lưu trữ.

Test (mock, không gọi API thật): tests/test_llm.py: parse JSON đúng, xử lý JSON hỏng (retry rồi parse_error), cache hit/miss, --skip-llm không gọi mạng, đọc khoá từ môi trường với khoá bất kỳ, thiếu khoá không làm sập pipeline.
Nghiệm thu: chạy thử với 20 review (cờ --limit 20), kiểm tra JSON hợp lệ, chạy lại lần hai không gọi API (đếm số lần gọi mock/log), rồi chạy mẫu đầy đủ. Tỷ lệ parse_error < 2%.
12.8 Prompt GĐ6 – Đối chứng và đánh giá
Đọc AGENTS.md và PLAN.md mục 5.5, 5.6. Chỉ làm GĐ6: src/baseline.py, src/evaluate.py, tools/make_label_template.py.

tools/make_label_template.py: xuất data/samples/hand_labels_template.csv gồm 100 review (in_hand_label==True): review_id, comments, sentiment (để trống), aspects_praise (để trống), aspects_complaint (để trống), language (để trống). TUYỆT ĐỐI không điền nhãn thay tôi. Tôi tự gán rồi lưu thành data/samples/hand_labels.csv. Xác thực định dạng nhãn (hàm validate_labels): đủ >= 100 dòng, id nằm trong mẫu LLM, sentiment hợp lệ, không thiếu.

src/baseline.py (không LLM; mô hình đơn giản, giải thích được):
- language: langdetect hoặc lingua, đặt seed cố định cho langdetect (DetectorFactory.seed = cfg.seed); lỗi/ngắn -> 'und'.
- sentiment: từ điển từ khoá khen/chê theo ngôn ngữ (en + các ngôn ngữ chiếm >= 3% mẫu, đo từ kết quả langdetect); quy tắc: điểm = (#từ khen − #từ chê); có phủ định đơn giản trong cửa sổ 3 từ; 'mixed' khi cả hai phía có >= 1 từ khoá và độ lệch nhỏ; ngôn ngữ không có từ điển -> dự đoán lớp đa số, ghi cờ no_lexicon. Lưu từ điển ở data/lexicons/*.json (dễ đọc, dễ chỉnh).
- aspects: từ khoá theo từng khía cạnh (config), khen/chê dựa trên từ khoá cảm xúc gần đó (cửa sổ ±5 từ).
- (Tuỳ chọn) baseline_ml: TF-IDF (char n-gram 2–5, đa ngôn ngữ) + LogisticRegression, đánh giá bằng cross-validation phân tầng trên 100 nhãn tay (k=5, seed). Không huấn luyện và chấm trên cùng quan sát (không rò rỉ).
- Đầu ra: data/processed/baseline_results.parquet với cùng cột như llm_results (để so sánh).

src/evaluate.py:
- Ghép hand_labels với llm_results và baseline_results theo review_id.
- Với sentiment: accuracy, macro-F1, precision/recall/F1 từng lớp, ma trận nhầm lẫn; khoảng tin cậy 95% bằng bootstrap (1000 lần, seed).
- Với aspects: precision/recall/F1 micro và theo từng khía cạnh (khen và chê riêng), exact-match tuỳ chọn.
- Với language: accuracy so với nhãn tay (nếu có).
- Kiểm tra thống kê: so sánh LLM vs baseline bằng McNemar (hoặc bootstrap chênh lệch).
- Xuất: reports/eval_metrics.csv (method, task, metric, value, ci_low, ci_high, n), reports/confusion_llm.csv, reports/confusion_baseline.csv, reports/error_analysis.csv (review_id, text, hand_label, llm, baseline, error_type_hint) và reports/error_summary.md (đếm theo loại lỗi: mỉa mai, mixed bị nhầm, ngôn ngữ ít gặp, review ngắn, nội dung không liên quan, parse_error). Phần nhận định lỗi do người viết, agent chỉ gợi ý nhóm.
Test: tests/test_evaluate.py với ví dụ nhỏ biết trước metric.
Nghiệm thu: --only baseline,evaluate chạy được trên hand_labels.csv thật; có accuracy/macro-F1 cho cả hai phương pháp, ma trận nhầm lẫn và bảng lỗi.
12.9 Prompt GĐ7 – Trực quan hoá
Đọc AGENTS.md và PLAN.md mục 5.7. Chỉ làm GĐ7: src/viz.py.
Dùng matplotlib (hoặc geopandas nếu cần). Mỗi hình: tiêu đề, nhãn trục có đơn vị, chú thích nguồn 'Nguồn: Inside Airbnb (CC BY 4.0), snapshot <ngày>', dpi=200, kích thước nhất quán, bảng màu thân thiện với người mù màu (viridis / cividis), font dễ đọc. Lưu PNG vào figures/ với tên cố định:
Không gian:
- fig_space_01_listings_map.png: scatter longitude/latitude (từ listings snapshot cuối), tô màu theo giá (cắt ở percentile 95 để không bị ngoại lai làm lệch), vẽ 8 hình chữ nhật vùng kèm nhãn.
- fig_space_02_area_price.png: cột giá trung vị theo vùng (K1), có số listing n.
- fig_space_03_area_occupancy.png: lấp đầy theo vùng (K2) snapshot cuối.
Thời gian:
- fig_time_01_occupancy_by_snapshot.png: đường lấp đầy theo tháng của ngày lịch, mỗi snapshot một đường (K3).
- fig_time_02_kpi_trend.png: K2/K4/K6 qua 4 snapshot.
- fig_time_03_reviews_per_quarter.png: review mới theo quý (K5).
LLM:
- fig_llm_01_sentiment_by_area.png: cột chồng 100% cảm xúc theo vùng.
- fig_llm_02_aspects.png: top khía cạnh khen/chê (cột đôi hoặc diverging bar), hoặc heatmap vùng × khía cạnh (K7).
- fig_llm_03_model_vs_baseline.png: so sánh accuracy/macro-F1 của LLM và baseline kèm CI.
- fig_llm_04_confusion_llm.png và fig_llm_05_confusion_baseline.png: ma trận nhầm lẫn.
QA (tuỳ chọn): fig_qa_01_impact.png: số dòng bị gắn cờ theo quy tắc.
Hàm run(cfg) sinh hết; hình nào thiếu dữ liệu (ví dụ chưa có LLM) thì bỏ qua và log cảnh báo, không làm sập pipeline.
Nghiệm thu: chạy --only viz sinh đủ hình cho 3 góc độ: không gian, thời gian, LLM. Mở từng hình kiểm tra nhãn, đơn vị.
12.10 Prompt GĐ8 – Tích hợp, kiểm thử, tái lập
Đọc AGENTS.md. Chỉ làm GĐ8.
1. Hoàn thiện run_pipeline.py: thứ tự download -> filter -> qa -> kpi -> llm -> baseline -> evaluate -> kpi (cập nhật K7) -> viz -> summary. Bước summary xuất reports/summary_numbers.csv gom các con số chính cho báo cáo (số dòng trước/sau QA, KPI chính, metric LLM, chi phí ước tính) để báo cáo dùng đúng số.
2. Đảm bảo thay snapshot chỉ qua config chạy được. Viết tools/check_config_swap.py: tạo config tạm với snapshot khác (nếu có), chạy các bước filter/qa/kpi, kiểm không có chuỗi ngày hoặc tên thành phố ghi cứng trong src/ (grep tự động).
3. Viết tests đầy đủ theo PLAN.md mục 7 và tests/test_smoke.py chạy pipeline trên fixtures nhỏ với LLM mock; pytest phải xanh.
4. Kiểm tra bảo mật: grep tìm chuỗi giống khoá API trong repo và lịch sử git; xác nhận .env nằm trong .gitignore; chạy với khoá giả đặt trong biến môi trường (GEMINI_API_KEY=dummy) và đảm bảo code đọc được từ biến môi trường.
5. Viết README.md đầy đủ theo PLAN.md mục 8: cài đặt, bốn bước chạy, tên biến môi trường, danh sách tệp kết quả để đối chiếu, thời gian chạy ước tính, cách chạy chỉ bước nào, cách chấm lại bằng khoá khác, ghi nguồn Inside Airbnb (CC BY 4.0) và 4 ngày snapshot.
6. Tự kiểm 'máy sạch': trong thư mục mới, git clone, python -m venv .venv, pip install -r requirements.txt, đặt khoá, chạy một lệnh, so sánh tệp đầu ra với danh sách trong README. Báo cáo mọi chênh lệch.
Nghiệm thu: pytest xanh; tools/check_config_swap.py không phát hiện ghi cứng; quy trình chạy sạch từ đầu đến cuối.
12.11 Prompt GĐ9 – Báo cáo và AI_USAGE
Đọc AGENTS.md. Chỉ làm GĐ9. Không bịa số liệu: mọi con số lấy từ reports/summary_numbers.csv, qa_report.csv, kpi_*.csv, eval_metrics.csv.
1. Tạo khung AI_USAGE.md đúng 4 mục: '## Công cụ đã dùng (vào việc gì)', '## Prompt then chốt (5-10): bước nào, vào tệp nào', '## AI sai ở đâu (ví dụ thật)', '## Nhóm kiểm chứng thế nào'. Điền phần có thể suy ra từ lịch sử làm việc (công cụ, prompt đã dùng, tệp liên quan); để chỗ trống đánh dấu TODO cho phần chỉ con người biết (ví dụ lỗi thật đã gặp, cách nhóm kiểm). KHÔNG bịa ví dụ lỗi.
2. Tạo thư mục report/ với bản nháp báo cáo (Markdown hoặc LaTeX) <= 10 trang theo cấu trúc: tóm tắt; bên đặt hàng và mục tiêu; dữ liệu và nguồn (4 ngày snapshot, CC BY 4.0); quy trình và tái lập; QA (bảng quy tắc, tác động); KPI (bảng định nghĩa và kết quả); trực quan hoá (3 góc độ, kèm hình); phân tích LLM (mẫu, prompt, đối chứng, metric, phân tích lỗi, chi phí); hạn chế và rủi ro; phụ lục: mã commit của tag final. Chỉ chèn hình có trong figures/. Format chính thức chưa công bố, nên để khung dễ đổi.
3. Biên dịch ra reports/report.pdf (pandoc/LaTeX nếu có; nếu không có công cụ thì dùng matplotlib/reportlab theo skill pdf, hoặc báo tôi biết cần cài gì). Kiểm số trang <= 10.
4. Tạo kiểm tra tự động tools/check_report_numbers.py: các số chính trong báo cáo khớp summary_numbers.csv.
Những phần nhận định, kết luận, phân tích lỗi: để tôi viết; chỉ gợi ý dàn ý.
Nghiệm thu: report.pdf <= 10 trang, hình đúng, số khớp, AI_USAGE.md đủ 4 mục.
12.12 Prompt GĐ10 – Kiểm cuối và nộp
Đọc AGENTS.md. Chỉ làm GĐ10: kiểm tra, KHÔNG tự động push hay tạo tag nếu tôi chưa xác nhận.
1. Chạy checklist ở PLAN.md mục 11, báo từng mục Đạt/Không đạt kèm bằng chứng (lệnh và đầu ra).
2. Kiểm tra git status sạch, không có data/raw/, không có .env hay khoá, dung lượng data/processed < 50 MB, mọi tệp đầu ra có trong repo.
3. Chạy lại pytest và quy trình từ máy sạch lần cuối.
4. In ra các lệnh tôi cần chạy tay: git add -A, git commit -m 'Bản nộp cuối', git tag final, git push origin main, git push origin final, và lệnh lấy mã commit (git rev-parse HEAD) để tôi ghi vào báo cáo.
5. Nhắc tôi: mời tài khoản giảng viên vào repo, điền liên kết repo vào bảng tính.
12.13 Bảng tên cột đầu ra cố định (để Codex không đổi tên giữa các bước)
Tệp
Cột chính
listings_clean
id, snapshot, analysis_area, room_type, price (chỉ snapshot cuối), latitude, longitude, accommodates, bedrooms, beds, minimum_nights, maximum_nights, number_of_reviews, first_review, last_review, review_scores_rating, host_id, property_type, property_type_grp, flag_*
calendar_clean
listing_id, snapshot, date, available (bool), price, minimum_nights, maximum_nights, flag_*
reviews_clean
id (review_id), listing_id, snapshot, date, reviewer_id, comments, in_llm_sample, in_hand_label, flag_*
llm_results
review_id, sentiment, aspects_praise, aspects_complaint, language, parse_error, truncated, model, prompt_version
baseline_results
review_id, sentiment, aspects_praise, aspects_complaint, language, method
kpi_area
area, kpi_id, value, unit, n
kpi_time
period, snapshot, kpi_id, value, unit, n
qa_report
rule_id, rule_name, table, snapshot, condition, reason, action, rows_before, rows_affected, rows_after, kpi_name, kpi_before, kpi_after
eval_metrics
method, task, metric, value, ci_low, ci_high, n
12.14 Mẹo làm việc với Codex để tránh lỗi
• Giao đúng từng prompt, sau mỗi giai đoạn bắt Codex chạy lệnh nghiệm thu và dán kết quả thật. Không chấp nhận câu trả lời 'đã hoàn thành' mà thiếu đầu ra lệnh.
• Nếu Codex đề xuất đổi cấu trúc hay thêm thư viện lớn: từ chối, hỏi lại vì sao và có cách đơn giản hơn không.
• Sau mỗi giai đoạn, tự đọc code và nhờ Codex giải thích từng hàm cho bạn. Ghi lại các lỗi AI từng mắc vào AI_USAGE.md ngay lúc gặp (ví dụ lọc nhầm cột, ép kiểu giá sai, ghi cứng ngày).
• Commit nhỏ, thường xuyên, mỗi giai đoạn một commit có thông điệp rõ ràng. Mọi thành viên cùng đọc commit để hiểu code.
• Chuẩn bị câu trả lời vấn đáp: vì sao 8 vùng này, vì sao ngưỡng giá này, vì sao gắn cờ thay vì xoá, vì sao mẫu 1.000 review, vì sao baseline này, LLM sai ở đâu, chi phí bao nhiêu.