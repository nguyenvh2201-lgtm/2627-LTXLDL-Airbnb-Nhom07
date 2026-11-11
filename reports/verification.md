# Biên bản kiểm tra — 11/11/2026

Cập nhật sau yêu cầu dọn gọn: đã xóa clone kiểm thử, ảnh preview và các bản
CSV/KPI trùng; gộp requirements-lock vào requirements.txt. Sau sửa bộ xuất
file: pytest vẫn 27 passed, có kiểm tra không tái tạo ba bảng trùng.
clean_reproduction.json là biên bản lần kiểm trước; bản clone tạm đã được xóa.

Đã chạy trên Python 3.13.7, dữ liệu thật trong data/raw. Không gọi Gemini thật.

| Lệnh / kiểm tra | Kết quả thực tế |
|---|---|
| `python tools/inspect_ids.py` | 12/12 kiểm tra; 1.000 listing, 5.000 review, 8 vùng; mẫu LLM 1.000, mẫu gold 100 |
| `python run_pipeline.py --config configs/city.yaml --skip-download --skip-llm` | Exit 0; xác thực 12 gzip, filter → QA → KPI → baseline → viz → summary → report |
| `python -m pytest -q --junitxml=reports/test_results.xml` | 27 passed; có mock Gemini, retry/cache, smoke tới PDF |
| `python tools/check_config_swap.py` | Không có tên thành phố/ngày ghi cứng trong src; 7 tests passed với bốn mốc fixture khác |
| `python tools/check_report_numbers.py` | PASS, 15 giá trị chính khớp nguồn và xuất hiện trong PDF |
| Render PDF bằng `pdftoppm` | 6 trang, đã xem tất cả trang; sửa nhãn bản đồ sau lần render đầu |
| `python tools/check_security.py` | Không có raw/.env/.venv tracked; không thấy mẫu khóa hỗ trợ trong source và patch lịch sử |
| Clone local + working source + venv sạch | Toàn pipeline exit 0; 6 bảng đối chiếu bằng nhau, xem clean_reproduction.json |

Kết quả dữ liệu:

| Snapshot | Listing | Calendar | Review mẫu |
|---|---:|---:|---:|
| 2025-09-11 | 1.000 | 365.000 | 5.000 |
| 2026-03-19 | 1.000 | 365.000 | 5.000 |
| 2026-06-15 | 1.000 | 365.000 | 5.000 |
| 2026-09-16 | 928 | 338.720 | 4.765 |

Mốc cuối theo xác nhận người dùng: thiếu 72 listing, 235 review so với bộ ID.
Các sai lệch số lượng được báo warning; không bù dữ liệu. Mốc cuối thiếu 114
giá, median hợp lệ 210 CAD/đêm. Mỗi listing hiện diện có đủ 365 ngày calendar.

Baseline chạy đủ 1.000 review (langdetect nhận toàn bộ là en). Chưa có khóa
GEMINI_API_KEY, chưa có cache thật, chưa có hand_labels.csv. Vì vậy chưa có
K7, accuracy/F1 thực, phân tích lỗi thực hoặc 5 hình LLM. Template chỉ có ô trống.
6 hình không gian/thời gian đã được tạo. Processed khoảng 8,15 MB, dưới 50 MB.

Chi phí chỉ là kịch bản từ giá chính thức và token giả định, không phải hóa đơn.
Ngày/model/giá/giả định ghi rõ trong config và llm_cost_estimate.csv.

Giới hạn kiểm tra máy sạch: clone **local không checkout**, phủ bản source
đang làm việc chưa commit; venv không kế thừa system-site-packages. Raw được
hardlink chỉ để đọc/xác thực, không tải lại qua mạng. Chưa phải clone commit final
từ GitHub; đường tải HTTP và API được kiểm bằng mock, chưa gọi thực trong phiên.

Không commit/tag/push. Repo ban đầu có thay đổi và file bị xóa từ trước;
không khôi phục/ghi đè các thay đổi đó. Nhánh hiện tại: feature/download-script.

## Sau gộp cấu trúc theo ảnh — 11/11/2026

Các lệnh/đường dẫn ở biên bản phía trên thuộc cấu trúc trước khi gộp.
Hướng dẫn hiện hành: README.md. Cấu trúc src hiện có đúng bảy tệp theo đề.

- `python -m pytest -c notebooks/pytest.ini -q --junitxml=reports/test_results.xml`: 27 tests đạt.
- `python notebooks/tools/check_config_swap.py`: 7 tests đạt, không có thành phố/ngày ghi cứng trong src.
- `python run_pipeline.py --config configs/city.yaml --skip-download --skip-llm`: exit 0 trên dữ liệu thật, xuất lại hình và báo cáo.
- `python notebooks/tools/check_report_numbers.py`: 15 giá trị đạt.
- `python notebooks/tools/check_security.py`: không phát hiện mẫu khóa hoặc tệp nhạy cảm tracked trong phạm vi kiểm.
- Prompt/từ điển chuyển vào configs/city.yaml; data-new.csv chuyển vào data/samples.
- `reports/report.md` cùng PDF được tạo bởi src/viz.py; không tạo thư mục report ở gốc.
- Chưa chạy lại clone môi trường sạch sau lần gộp này; clean_reproduction.json là bằng chứng lần trước.
- Chưa gọi API thật và chưa có gold; các phần đó vẫn chưa hoàn thành.
