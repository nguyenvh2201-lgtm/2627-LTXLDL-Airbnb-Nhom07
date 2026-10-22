# 2627-LTXLDL-Airbnb-Nhom07

## Chạy QA

Trong thư mục dự án, cài các thư viện mà `src/qa.py` sử dụng:

```bash
python -m pip install pandas numpy pyyaml
```

Đặt dữ liệu theo cấu trúc dưới đây. Mỗi snapshot cần đủ ba file raw:

```text
data/
  data-new.csv
  raw/
    2025-09-11/
      listings.csv.gz
      reviews.csv.gz
      calendar.csv.gz
      neighbourhoods.geojson
    2025-12-12/
      ...
    2026-03-19/
      ...
    2026-06-15/
      ...
```

Chạy từ thư mục dự án:

```bash
python src/qa.py
```

QA tính đường dẫn từ vị trí `src/qa.py`, nên có thể chuyển cả thư mục dự án
sang vị trí khác mà không sửa đường dẫn trong code. Nếu terminal đang ở nơi khác,
truyền đường dẫn đầy đủ đến `qa.py` (đặt trong dấu nháy nếu có khoảng trắng).

Kết quả được ghi vào `data/processed/<snapshot>/`. Mã hiện tại ghi đè các file
đầu ra cùng tên khi chạy lại. Việc dùng đường dẫn linh hoạt không thay thế
bước kiểm chứng chất lượng dữ liệu và đầu ra QA.

Danh sách mốc, đường dẫn raw/processed và thư mục báo cáo được đọc từ
`configs/city.yaml`. Sau khi xử lý tất cả các mốc, `qa.py` xuất một lần vào
`reports/qa_report.csv` (theo `reports_dir` trong config), gồm các cờ QA của
listings/reviews/calendar và so sánh reviews giữa từng cặp mốc.

Các phép so sánh ngày, listing và comments chỉ dùng review_id không thiếu,
xuất hiện đúng một lần trong mỗi mốc; ngày/listing phải hợp lệ hoặc không
thiếu tương ứng, còn cặp thiếu comments bị loại khỏi so sánh nội dung.
Review xuất hiện lại được ghi nhận, không tự coi là lỗi hoặc xóa dòng.

Metric trước/sau được tính trên cùng dữ liệu đã lọc theo phân công: số dòng
của ba bảng, giá trung vị numeric và độ dài bình luận trung bình trước/sau
làm sạch HTML. Giá trung vị bỏ giá không chuyển được sang số, nhưng không
tự loại giá không dương/ngoại lai. Bình luận thiếu tính là 0 ký tự.
Pipeline hiện giữ dòng nên số dòng trước/sau bằng nhau; việc tổng hợp calendar
theo listing không được tính là xóa dòng. Chi tiết công thức nằm trong cột
`note` của báo cáo. Đây là CSV QA, không phải báo cáo kỹ thuật PDF.

