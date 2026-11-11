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
   → tools/inspect_ids.py, data/samples/*.csv.
2. Mục 12.3-12.4: config, CLI, tải stream/lọc chunk → src/config.py, utils.py,
   download.py, filter.py, run_pipeline.py.
3. Mục 12.5-12.6: QA gắn cờ/tác động, KPI vùng/thời gian → src/qa.py, kpi.py.
4. Mục 12.7: JSON schema/retry/cache, thiếu key vẫn chạy → src/llm.py,
   prompts/extract_v1.txt (giữ nguyên nội dung prompt yêu cầu).
5. Mục 12.8: baseline, gold do người gán, CI/lỗi → src/baseline.py,
   evaluate.py, tools/make_label_template.py.
6. Mục 12.9-12.10: hình, tests/smoke/đổi mốc → src/viz.py, tests/,
   tools/check_config_swap.py, tools/clean_reproduce.py.
7. Mục 12.11-12.12: không bịa báo cáo, checklist, không tự push/tag →
   src/report.py, summary.py, tools/check_report_numbers.py, README.
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
  công cụ mẫu nhãn trống vào evaluate.make_label_template.
- Prompt và bốn từ điển được giữ nguyên nội dung trong city.yaml. CSV nguồn
  chuyển vào data/samples; báo cáo Markdown chuyển vào reports.
- Giữ bộ kiểm thử/công cụ trong notebooks; cập nhật import, CLI và README.
  Không tạo gold, không gọi Gemini, không commit/tag/push.
- Lỗi phát hiện: một test còn đọc từ điển từ đường dẫn cũ, gây TypeError khi
  lexicons đã chuyển thành dictionary trong config. Đã sửa cách lấy fixture;
  các kiểm tra phủ định/cảm xúc hỗn hợp được giữ nguyên.
- Kiểm chứng: 27 tests đạt, kiểm đổi cấu hình 7 tests đạt, pipeline dữ liệu thật
  với --skip-download --skip-llm exit 0, 15 số báo cáo khớp, kiểm mẫu khóa đạt.
