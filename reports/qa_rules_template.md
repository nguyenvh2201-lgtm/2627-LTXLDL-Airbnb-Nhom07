# Khung quy tắc QA — để bạn tự hoàn thiện

Đây là bản nháp học và điền, chưa phải quy tắc đã chốt hoặc kết quả chạy QA.
Khi hoàn thiện, lưu bản bàn giao thành `reports/qa_rules.md`.

## 1. Phạm vi và căn cứ

- Phạm vi listing: lọc theo `listing_id` trong `data/data-new.csv`.
- Snapshot: 2025-09-11, 2025-12-12, 2026-03-19, 2026-06-15.
- Baseline cho tác động: dữ liệu đã lọc phạm vi nhóm, trước xử lý trùng.
- Loại phòng: kết quả đã lưu ở cell 6 của `test.ipynb` cho 2025-09-11
  có 875 `Entire home/apt` và 125 `Private room`.
  TODO: khảo sát ba snapshot còn lại, bao gồm giá trị thiếu; ghi căn cứ xác minh miền.
- Khu vực: TODO: đối chiếu bảng phân công và xác nhận danh mục A01–A08.
- Rating: TODO: xác minh thang đo nguồn trước khi chốt khoảng 1–5.

## 2. Quy tắc

| Bảng | Tên quy tắc | Điều kiện | Lý do | Hành động / trạng thái |
|---|---|---|---|---|
| listings | price_missing | Giá gốc thiếu | Không tính được KPI giá | Giữ listing, gắn cờ; không dùng cho KPI giá |
| listings | price_parse_error | Giá gốc có nhưng parse thành thiếu | Không có giá số hợp lệ | Giữ listing, gắn cờ; không dùng cho KPI giá |
| listings | price_nonpositive | Giá parse được nhưng <= 0 | Không đạt điều kiện price_valid | Giữ listing, gắn cờ; không dùng cho KPI giá |
| listings | price_outlier | Giá dương ngoài ngưỡng IQR | Cần khảo sát giá bất thường | Gắn cờ, vẫn giữ trong median đợt đầu |
| listings | room_type_invalid | Thiếu hoặc ngoài danh mục đã xác minh | Kiểm tra danh mục | Giữ dòng, kiểm tra nguồn trước khi kết luận |
| mọi bảng | exact_duplicate | Toàn bộ giá trị giống nhau trong cùng snapshot | Tránh đếm bản lặp | Đề xuất giữ một bản; code hiện tại mới gắn cờ |
| mọi bảng | conflicting_key | Sau khi bỏ trùng y hệt, vẫn có cùng khóa khác nội dung | Tránh chọn tùy tiện / cộng đôi | TODO: khảo sát và chốt cách xử lý |
| reviews | text_invalid | Comments thiếu hoặc rỗng sau strip | Không đủ nội dung cho mẫu LLM | Giữ thống kê; không dùng cho mẫu LLM |
| reviews/calendar | date_invalid | Ngày thiếu hoặc parse lỗi | Không tính được phép tính cần ngày | Gắn cờ, ghi riêng thiếu và parse lỗi |
| reviews/calendar | listing_unmatched | Không có listing cùng snapshot | Kiểm tra liên kết | Ghi số orphan; chưa ghép phân tích nếu chưa giải thích |
| calendar | available_invalid | Ngoài t/f/true/false sau strip và lower | Không xác định được trạng thái | Không tính vào mẫu số available hợp lệ |
| calendar | conflicting_available | Cùng listing/ngày có cả true và false hợp lệ | Trạng thái trong ngày mâu thuẫn | TODO: ghi rõ chính sách và số ngày bị ảnh hưởng |

TODO: thêm kiểm tra thiếu khóa, numeric, rating, khu vực, cửa sổ calendar và ID lặp giữa snapshot.

Ngưỡng ngoại lai hiện tại trong `qa.py`: Q1 - 1.5*IQR và Q3 + 1.5*IQR,
tính trên giá dương của toàn bộ snapshot đã lọc nhóm. Nếu đổi sang snapshot × room_type,
cần quy định cỡ mẫu tối thiểu, cập nhật code và chạy lại report.

Khóa kiểm tra trong snapshot:

- listings: `(snapshot_date, listing_id)`.
- reviews: `(snapshot_date, review_id)`.
- calendar: `(snapshot_date, listing_id, date)`; xác minh thêm trùng theo ngày đã parse.

## 3. Mẫu số

- Median giá: chỉ giá parse được và > 0, vẫn giữ giá dương bị gắn cờ ngoại lai.
- `availability_share = n_available / n_available_valid`; mẫu số 0 để thiếu.
- `coverage_share = n_available_valid / calendar_horizon_days`.
  TODO: đối chiếu cửa sổ dữ liệu trước khi chốt 365; không tự cắt tỷ lệ xuống 1.
- TODO: ghi rõ mẫu số của từng KPI khác khi bàn giao.
