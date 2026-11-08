
# Inside Airbnb Toronto · Nhóm 07

Mã dữ liệu của nhóm là `DSE2049-C04-G07-toronto`.

## Cài đặt và kiểm thử

Chạy từ thư mục gốc repo với Python 3.12.14 trong môi trường ảo. Phiên bản
Python được ghi trong `.python-version`.

```bash
python -m pip install -r requirements.txt
python -m pip check
python -m unittest discover -s tests -p "test_llm_*.py" -v
```

Bộ test dùng phản hồi API giả lập và dữ liệu kiểm thử. Các báo cáo thực nghiệm
được tạo khi nhóm chạy trên dữ liệu Toronto với model và nhãn tay đã chọn.

## Chạy toàn bộ quy trình

Đặt `SHOPAIKEY_API_KEY` trong môi trường của terminal rồi chạy từ gốc repo.

```bash
python run_pipeline.py --config configs/city.yaml --profile luna
```

Lệnh tải và kiểm tra dữ liệu bốn mốc, chạy QA, phân tích review tại
`snapshot_date`, đánh giá trên bộ Test nếu mốc có nhãn, tính chi phí và KPI,
rồi sinh biểu đồ. Mặc định mẫu cố định gồm 1.000 review. Khi đổi
`snapshot_date` khỏi `llm.sample_snapshot_date`, pipeline chọn mẫu theo seed
từ review đã qua QA của mốc mới.

Thêm `--skip-download` khi đã có đủ dữ liệu thô. Lệnh tự dùng lại các phản hồi
đã lưu cho cùng cấu hình, mốc và mẫu. Có thể đặt `--max-new-requests 50` để giới
hạn lượt gọi mới mỗi lần. Nếu batch chưa hoàn tất, lệnh lưu checkpoint và
trả lỗi. Chạy lại cùng cấu hình để tiếp tục. Dùng `--skip-llm` khi đã có
checkpoint hoàn chỉnh và muốn sinh lại các đầu ra từ kết quả đã lưu.

Với HTTP 502, 503 hoặc 504, pipeline thử lại review hiện tại tối đa hai lần,
sau khoảng chờ 5 và 10 giây. Mỗi lần thử lại tính vào giới hạn lượt gọi.
Nếu vẫn lỗi, pipeline lưu checkpoint và báo review cần chạy tiếp.

| Đầu ra | Vị trí mặc định |
| --- | --- |
| Tác động của QA | `reports/qa_report.csv` |
| KPI và kiểm tra | `data/processed/kpi_*.csv`, `reports/kpi_checks.csv` |
| Checkpoint | `data/processed/llm/<mốc>_<profile>_<chữ ký>.jsonl` |
| Accuracy, Macro-F1, lỗi phân loại và chi phí | `reports/llm/<mốc>_<profile>_<chữ ký>/` |
| Biểu đồ khu vực, thời gian và LLM | `figures/` |

## Cấu hình và dữ liệu

`configs/city.yaml` là cấu hình chung cho tải dữ liệu, QA và LLM. `snapshots`
chứa bốn mốc của Toronto theo đề. `snapshot_date` chọn một mốc để chạy LLM.
Hai profile Luna và Argon nằm trong `src/llm.py` và được chọn bằng `--profile`.

Mốc `2026-06-15` dùng `data/samples/llm_review_ids.csv`. Danh sách này giữ
1.000 ID được đánh dấu trong `data/data-new.csv`, gồm 20 review dev,
880 review phân tích và 100 review test. Với mốc khác, đặt `llm.sample_ids`
thành `null` để lấy mẫu theo `seed` từ đầu ra QA của mốc đó.

## Chạy từng bước

```bash
python -m src.download
python -m src.qa
python -m src.llm baseline --config configs/city.yaml --profile luna
```

QA lưu `reviews_clean.csv`, `listings_clean.csv` và
`calendar_listing_summary.csv` trong `data/processed/<mốc>/`. Baseline chạy
tại chỗ và ghi dự đoán dưới `reports/llm/`.

Chạy lại QA nếu thư mục processed còn bảng lịch từ bản cũ. Cả QA và KPI dùng
`n_available_valid / n_calendar_days` cho độ phủ lịch. KPI dùng `rating_valid`
để loại điểm bị QA đánh dấu khỏi trung vị.

Để chạy LLM thật, đặt biến môi trường `SHOPAIKEY_API_KEY` bằng khóa của nhóm.
`.env.example` ghi tên biến cần đặt. Mỗi profile hiện gửi request qua ShopAIKey.

```bash
python -m src.llm run --config configs/city.yaml --profile luna --output data/processed/llm_pilot.jsonl
python -m src.kpi --input-dir data/processed --llm-file data/processed/llm_pilot.jsonl
```

Lệnh KPI ghi các bảng `kpi_*.csv` và `kpi_checks.csv` vào `data/processed/`.
Để lưu ở nơi khác, dùng `--output-dir` và `--checks-path`. Bảng LLM theo mốc
và khu vực chỉ hiện tỷ lệ khi có đủ 30 review dùng được trong nhóm tương ứng.
`mixed` được tính vào mẫu số. KPI ghi cảnh báo nếu thiếu file JSONL và báo lỗi
nếu file được truyền vào có dữ liệu nhưng không có review của mốc đã chọn.

Giữ cùng mốc, model, mẫu và `--output` khi chạy tiếp. `--skip-llm` dùng
checkpoint khớp chữ ký lần chạy. Khi đổi mốc hoặc profile, dùng đường dẫn
output riêng rồi truyền chính đường dẫn đó cho `--llm-file`.

Sau khi nhóm điền nhãn tay, dùng `python -m src.llm evaluate` cùng profile,
config và output của lượt chạy trên. Tệp mặc định là
`data/samples/reviews_test_labels.csv`. Xem quy tắc trong
`docs/LLM_ANNOTATION_CONTRACT.md`. Lệnh `cost` nhận `--city-reviews` là tổng
review thành phố của mốc đang xét để ước tính chi phí theo usage đã ghi.

## Đối chiếu trước khi nộp

Repo có 20 nhãn dev và 100 nhãn Test của mốc `2026-06-15`. Khi chạy với khóa
của nhóm, đọc `metrics.json`, `error_analysis.csv` và `cost.json` để hoàn thiện
báo cáo. Dùng cả Accuracy và Macro-F1 vì nhãn Test có 88 positive, 11 mixed
và 1 negative.

Kiểm tra lại bằng một lượt chạy trên checkout mới. Đưa mã nguồn, cấu hình,
bộ nhãn và báo cáo cuối vào Git. Dữ liệu thô, checkpoint, khóa API và kết quả
kiểm thử giả lập thuộc phạm vi máy chạy. Cập nhật `AI_USAGE.md` theo lượt
sử dụng thực tế.
