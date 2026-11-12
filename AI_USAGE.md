# Nhật ký sử dụng AI

## Công cụ đã dùng (vào việc gì)

- 11/11/2026: Codex đọc yêu cầu/mã, viết pipeline Python, config, tests, tài liệu,
  công cụ nhãn trống, hình và báo cáo nháp từ số liệu thật.
- Python 3.13.7, pandas/pyarrow, matplotlib, scikit-learn, pytest, ReportLab,
  pypdf, Poppler dùng để chạy/kiểm số liệu và render/kiểm PDF.
- Skill PDF áp dụng để dựng, render và kiểm bố cục báo cáo.
- Tra tài liệu chính thức Google structured output/pricing; URL/ngày tra trong
  config/README. Chưa gọi Gemini thật vì môi trường không có khóa.
- Không dùng sub-agent; không gán gold hay tạo kết quả LLM giả trong dữ liệu thật.

## Prompt then chốt (5-10): bước nào, vào tệp nào

Mục 1-7 là yêu cầu trong kế hoạch đã đưa, được thực hiện khi người dùng nhắn
“làm hết đi”; không phải bảy lượt hội thoại riêng.

1. “phân tích theo cái datanew…” và mục 12.2: tách cột trùng tên, lọc lớp/nhóm
   → notebooks/tools/inspect_ids.py, data/samples/*.csv.
2. Mục 12.3-12.4: config, CLI, tải stream/lọc chunk → src/download.py,
   run_pipeline.py.
3. Mục 12.5-12.6: QA gắn cờ/tác động, KPI vùng/thời gian → src/qa.py, kpi.py.
4. Mục 12.7: JSON schema/retry/cache, thiếu key vẫn chạy → src/llm.py,
   configs/city.yaml (llm.prompt_text).
5. Mục 12.8: baseline, gold do người gán, CI/lỗi → src/baseline.py,
   evaluate.py, notebooks/tools/.
6. Mục 12.9-12.10: hình, tests/smoke/đổi mốc → src/viz.py, notebooks/tests/,
   notebooks/tools/check_config_swap.py, notebooks/tools/clean_reproduce.py.
7. Mục 12.11-12.12: không bịa báo cáo, checklist, không tự push/tag →
   src/viz.py, notebooks/tools/check_report_numbers.py, README.
8. Người dùng: “Giữ 16/09/2026, báo rõ thiếu 72 listing” → giữ mốc, xuất
   missing_ids.csv, không áp kỳ vọng tháng 12/2025 cho tháng 9/2026.

## AI sai ở đâu (ví dụ thật)

- Đã giữ quá nhiều file phụ sau triển khai: clone kiểm thử chứa cả dependency,
  ảnh preview và CSV trùng Parquet. Người dùng yêu cầu dọn; đã xóa các bản dư,
  gộp requirements và sửa nơi xuất file để không tái tạo chúng.

- Kiểm phiên bản pytest như thể đã có, nhận PackageNotFoundError; sau đó tạo
  venv/cài pytest và thực sự chạy tests.
- QA đầu tính metric available trước chuyển t/f gây ValueError chuyển 'f'
  sang float. Sửa metric nhận chuỗi/bool, thêm regression test.
- Lệnh marker PDF gọi node nhưng PATH không có; chạy đúng script qua Node
  runtime sẵn có, nhận exitCode=0.
- Bản đồ đầu đặt nhãn ở góc vùng làm nhãn gần nhau; sửa vào tâm có nền trắng
  sau khi xem render PDF.
- pip sandbox bị chặn mạng WinError 10013; chạy lại bằng quyền mạng được
  phê duyệt, không khai rằng lần đầu thành công.
- Config ban đầu chưa tăng dần và kỳ vọng cũ lệch mốc; kiểm dữ liệu thật,
  hỏi lựa chọn và giữ mốc mới theo người dùng.
- Một lần apply_patch thay README/AI_USAGE dùng Delete+Add cùng đường dẫn bị
  tool từ chối. Không có file bị đổi; chuyển sang Update File.
- Sau khi tạo clone kiểm thử trong tmp, pytest ban đầu thu thập cả hai bản
  tests và báo import file mismatch. Thêm pytest.ini giới hạn testpaths=tests
  và bỏ tmp/.venv khỏi đệ quy; chạy lại bộ kiểm thử.

## Nhóm kiểm chứng thế nào

- Theo yêu cầu dọn gọn của người dùng: gộp requirements, bỏ CSV kết quả trùng
  Parquet, bỏ kpi_summary trùng ba bảng KPI, xóa bản clone/ảnh preview dùng kiểm
  thử. Sửa pipeline để không sinh lại các bản dư; kiểm lại pytest.

- Agent chạy GĐ0: 12/12 kiểm tra đạt, ID dài giữ text.
- Ba mốc đầu 1.000 listing/5.000 review, cuối 928/4.765; không bù dòng giả.
- Template 100 review có ô nhãn trống. LLM lấy 1.000 review unique từ hợp các mốc.
- Tests có công thức tính tay, schema/retry/cache/key tùy biến/skip, smoke tới
  PDF. Xem reports/verification.md cho kết quả chạy cuối.
- Kiểm số PDF với summary_numbers.csv, render và nhìn từng trang; số chưa có
  ghi thiếu. Chi phí output khi chưa có API là giả định rõ trong config.
- Kiểm mẫu khóa trong working source và lịch sử Git; không chứng nhận mọi
  định dạng bí mật ngoài các mẫu đã kiểm.
- TODO (nhóm): đọc mã, xác nhận bên đặt hàng/ngưỡng, gán gold, chạy Gemini,
  tự viết/kiểm nhận định, ghi người/ngày và lỗi nhóm phát hiện.

## Gộp cấu trúc theo ảnh yêu cầu — 11/11/2026

- Người dùng yêu cầu chỉ giữ các thư mục và bảy mô-đun src giống ảnh đề bài.
- Gộp config/utils/filter vào download.py; summary/report vào viz.py;
  công cụ tạo mẫu nhãn trống vào llm.make_label_template.
- Prompt và bốn từ điển được giữ nguyên nội dung trong city.yaml. CSV nguồn
  chuyển vào data/samples; báo cáo Markdown chuyển vào reports.
- Giữ bộ kiểm thử/công cụ trong notebooks; cập nhật import, CLI và README.
  Không tạo gold, không gọi Gemini, không commit/tag/push.
- Lỗi phát hiện: một test còn đọc từ điển từ đường dẫn cũ, gây TypeError khi
  lexicons đã chuyển thành dictionary trong config. Đã sửa cách lấy fixture;
  các kiểm tra phủ định/cảm xúc hỗn hợp được giữ nguyên.
- Kiểm chứng: 27 tests đạt, kiểm đổi cấu hình 7 tests đạt, pipeline dữ liệu thật
  với --skip-download --skip-llm exit 0, 15 số báo cáo khớp, kiểm mẫu khóa đạt.

## Đối chiếu toàn bộ đề — 12/11/2026

- Codex đọc đề bài người dùng gửi, sửa giao diện QA/KPI với lệnh một lần,
  chuyển dữ liệu sạch theo mốc vào KPI, thống nhất 8 KPI hoạt động của pipeline,
  và cập nhật test QA theo API hiện tại. Bộ 27 test chạy đạt trong thư mục tạm;
  chưa chạy lại toàn pipeline trên dữ liệu thật trong lượt này để tránh tạo file mới.
- Chưa có 100 nhãn tay đã điền, dự đoán Gemini thật, K7 có giá trị, hình LLM
  hay PDF cuối. Không khai các phần này là đã hoàn thành.
- `data/processed/` hiện có khoảng 220 MiB file đã được Git theo dõi, vượt
  giới hạn 50 MB. Đã thêm ignore cho output mới; thao tác bỏ theo dõi file cũ
  trong Git chưa thực hiện vì cơ chế duyệt tự động từ chối thay đổi index.
- Theo yêu cầu chọn thêm review để gán nhãn tay: Codex dùng dự đoán baseline
  và dấu hiệu phàn nàn trong văn bản để chọn 50 review ngoài 100 review ban đầu.
  `selection_hint` chỉ là gợi ý cách chọn; 50 dòng được gán nhãn AI nháp và
  đánh dấu `label_source=AI_draft`. Không biến dự đoán máy thành nhãn đúng.
- Theo yêu cầu tiếp theo, Codex đã chuẩn hóa cú pháp khía cạnh của 100 nhãn
  người dùng đã điền sang JSON cho bảy mục cấu hình; tên mục cũ/ngoài danh mục
  được giữ ở `original_aspects_*` và `other_aspects_*`. Codex cũng điền
  `suggested_*` và nhãn nháp cho 50 review mới. Các dòng đó vẫn có
  `label_source=AI_draft`, chưa được tính là nhãn tay và cần người dùng tự xác nhận.
- Sau phản hồi của người dùng, phần tạo template được chuyển từ `evaluate.py`
  sang `llm.py`. `evaluate.py` chỉ đọc, kiểm tra và chấm trên nhãn tay; 50 nhãn
  AI nháp trong CSV không được đưa vào mẫu chấm khi chưa được người dùng xác nhận.
