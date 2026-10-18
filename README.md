# 2627-LTXLDL-Airbnb-Nhom07

## Chạy QA

Trong thư mục dự án, cài các thư viện mà `src/qa.py` sử dụng:

```bash
python -m pip install pandas numpy
```

Đặt dữ liệu theo cấu trúc dưới đây. Mỗi snapshot cần đủ ba file raw:

```text
data/
  data-new.csv
  2025-09-11/
    listings.csv.gz
    reviews.csv.gz
    calendar.csv.gz
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
