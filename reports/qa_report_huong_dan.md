# Tự làm QA report từ qa.py

Đây là khung thực hành, chưa phải báo cáo kết quả. Không có số lỗi được điền sẵn.
Các cell dưới đây chỉ minh họa listings của một snapshot; chưa bao phủ toàn bộ yêu cầu bàn giao.
Không cần sửa `src/qa.py` để thử. Tạo notebook tại thư mục gốc dự án rồi chạy lần lượt.
Python của notebook cần có pandas và numpy như môi trường bạn đang chạy QA.

## 1. Tạo dữ liệu và cờ QA

```python
from pathlib import Path
import pandas as pd
from src.qa import prepare_listings, run_qa_listings, clean_price

root = Path.cwd()
snapshot = "2025-09-11"

phan_cong = pd.read_csv(
    root / "data/data-new.csv", dtype={"listing_id": "string"}
)
raw = pd.read_csv(
    root / "data" / snapshot / "listings.csv.gz",
    dtype={"id": "string"},
)
prepared = prepare_listings(raw, phan_cong, snapshot)
qa = run_qa_listings(prepared)
flags = qa["row_flags"]

# Xem số đếm trước khi viết report.
print("Dòng sau lọc và ghép phân công:", len(prepared))
print("Giá thiếu:", int(flags["price_missing"].sum()))
print("Loại phòng thiếu/ngoài danh mục:", int((~flags["room_type_valid"]).sum()))
```

Baseline tác động ở đây là `prepared`, sau lọc và ghép phân công.
Đối chiếu số dòng trước/sau merge để chắc chắn bảng phân công không nhân số dòng.
`price_missing=True` là có vấn đề; `room_type_valid=False` là không đạt quy tắc.
Không đảo cờ lẫn lộn. Nếu cờ có giá trị thiếu thì phải giải thích/xử lý trước khi đếm,
vì `sum()` mặc định bỏ qua giá trị thiếu.

## 2. Viết hai dòng report đầu tiên

Schema bắt buộc có 10 cột. Chưa tính được để `None` (xuất CSV thành ô trống),
ghi lý do trong `note`; không thay số chưa biết bằng 0.

```python
columns = [
    "snapshot_date", "table", "rule", "action",
    "rows_flagged", "rows_removed", "metric_name",
    "metric_before", "metric_after", "note",
]
rows = []  # Khi mở rộng bốn snapshot, đặt dòng này trước vòng lặp.

rows.append({
    "snapshot_date": snapshot,
    "table": "listings",
    "rule": "price_missing",
    "action": "flag_only",
    "rows_flagged": int(flags["price_missing"].sum()),
    "rows_removed": 0,
    "metric_name": None,
    "metric_before": None,
    "metric_after": None,
    "note": "Giữ listing; không dùng giá thiếu cho KPI giá. Chưa bỏ dòng.",
})

rows.append({
    "snapshot_date": snapshot,
    "table": "listings",
    "rule": "room_type_invalid",
    "action": "flag_and_review",
    "rows_flagged": int((~flags["room_type_valid"]).sum()),
    "rows_removed": 0,
    "metric_name": None,
    "metric_before": None,
    "metric_after": None,
    "note": "Gồm thiếu và ngoài danh mục hiện tại; cần xác minh miền. Giữ dòng.",
})
```

Bạn thử tự thêm `price_parse_error`, `price_nonpositive`, `price_outlier_flag` trước.
Chỉ gắn cờ thì `rows_removed=0` là số thật. Loại khỏi một KPI không đồng nghĩa bỏ khỏi bảng.

## 3. Thêm tác động trước/sau

Ví dụ hiện tại chỉ giữ dòng và thêm cờ nên số dòng trước/sau bằng nhau là đúng.
Khi bạn thực sự xử lý trùng, thay `after` bằng bảng sau xử lý, không dùng bản sao này nữa.
Chạy lại cell 2 trước cell 3 nếu muốn tránh append lặp các dòng report.

```python
before = prepared
after = prepared.copy()  # Bản thực hành: chưa loại dòng nào.

def listing_metrics(df):
    price = clean_price(df["price"])
    valid = price.notna() & (price > 0)
    return {
        "row_count": len(df),
        "unique_listing_count": df["listing_id"].nunique(),
        "valid_price_count": int(valid.sum()),
        "median_price_cad": price.loc[valid].median() if valid.any() else None,
    }

before_metrics = listing_metrics(before)
after_metrics = listing_metrics(after)

for name in before_metrics:
    rows.append({
        "snapshot_date": snapshot,
        "table": "listings",
        "rule": "impact_summary",
        "action": "compare_before_after",
        "rows_flagged": None,
        "rows_removed": None,
        "metric_name": name,
        "metric_before": before_metrics[name],
        "metric_after": after_metrics[name],
        "note": (
            "Baseline: sau lọc nhóm và ghép phân công, trước xử lý trùng. "
            "Bản thực hành chưa loại dòng. Median dùng giá parse được >0, "
            "giữ ngoại lai; mẫu số ở valid_price_count. "
            "Unique listing bỏ qua ID thiếu. Median trống nếu không có giá hợp lệ."
        ),
    })
```

## 4. Xem rồi lưu bản thử

```python
report_df = pd.DataFrame(rows, columns=columns)
display(report_df)

(root / "reports").mkdir(exist_ok=True)
report_df.to_csv(
    root / "reports/qa_report_thu.csv",
    index=False,
    encoding="utf-8-sig",
)
```

Đặt tên bản thử để tránh nhầm với report bàn giao hoàn chỉnh.
Sau khi đủ quy tắc, bốn snapshot và kiểm chứng, mới xuất `reports/qa_report.csv`.

## 5. Bài tập mở rộng theo code hiện tại

| Bảng | Cờ đang có | Cách đếm vi phạm |
|---|---|---|
| listings | price_parse_error, price_nonpositive, price_outlier_flag | Đếm True |
| listings | duplicate_full_row, duplicate_listing_id | Đếm True; hiện chỉ phát hiện trùng |
| listings | rating_valid, Khu phan tich hop le | Đếm False; xác minh miền trước |
| listings | Dem toi thieu <= 0, Dem toi da <= 0, Dem toi thieu > dem toi da, Out of range | Đếm True; cờ Out of range là availability_365 |
| reviews | duplicate_all, duplicate_id | Đếm True |
| reviews | text_valid, listing_match | Đếm False |
| reviews/calendar | date_missing, date_parse_error | Đếm True, ghi thành hai quy tắc riêng |
| calendar | duplicate_full_row, duplicate_listing_date | Đếm True |
| calendar | available_valid, listing_match | Đếm False |

Dùng `run_qa_reviews()` / `run_qa_calendar()` để lấy cờ tương ứng.
Các cờ trùng khóa hiện tại bao gồm cả trùng y hệt; không được gọi chúng là số xung đột nội dung.
Muốn phân biệt: bỏ bản trùng y hệt trước, rồi tìm trùng khóa còn lại.
`duplicated(keep=False).sum()` đếm mọi dòng thuộc nhóm trùng;
`duplicated(keep="first").sum()` đếm bản lặp có thể bỏ.
Chỉ ghi số đã bỏ sau khi thực sự thực hiện loại bản lặp; kiểm tra xuyên chunk khi đọc theo chunk.

Các phần cần bổ sung ngoài cờ hiện có: thiếu khóa, xung đột nội dung/trạng thái,
ID lặp giữa snapshot, cửa sổ calendar và tác động xử lý thực tế.
Report lấy từ bảng đã lọc sẽ không tự ghi nhận các dòng bị loại ở bước chuẩn bị;
muốn báo đầy đủ, thu số đếm ngay tại bước lọc, gồm ID thiếu và ngoài phạm vi.

## 6. Kiểm chứng trước bàn giao và khung nhận xét

- Kiểm tra khóa duy nhất ở đầu ra từng snapshot; nếu chưa đạt thì báo rõ chưa giải quyết.
- Đối chiếu vài ID giữa listings/reviews/calendar; vài giá và available với raw.
- Kiểm tra `n_available <= n_available_valid <= n_calendar_days`.
- Kiểm tra availability_share trong [0, 1] khi có mẫu số; coverage_share > 1 cần điều tra cửa sổ.
- Không cộng các cờ chồng lấn để kết luận số dòng bị bỏ.

Điền 5–8 câu sau bằng số chạy thật, không dùng số giả:

1. Dữ liệu QA gồm [...] snapshot và [...] listing thuộc phân công nhóm.
2. Danh mục loại phòng/khu vực được xác minh bằng [...].
3. Giá thiếu/parse lỗi/không dương có [...] dòng; giữ listing nhưng không dùng cho KPI giá.
4. Phát hiện [...] dòng thuộc nhóm trùng y hệt; thực sự bỏ [...] bản lặp.
5. Median giá trước/sau là [...] / [...], với mẫu số [...] / [...]; giữ ngoại lai dương.
6. Review/calendar không khớp listing có [...]; cách xử lý là [...].
7. Các kiểm chứng khóa, liên kết và calendar cho kết quả [...].
8. Hạn chế hoặc vấn đề chưa xử lý là [...].
