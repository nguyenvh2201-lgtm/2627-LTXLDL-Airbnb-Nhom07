# Từ điển dữ liệu Toronto

Dữ liệu nguồn là [Inside Airbnb](https://insideairbnb.com/get-the-data/), giấy
phép CC BY 4.0. Bốn mốc của nhóm được ghi trong `configs/city.yaml`.
`data/data-new.csv` chứa ID listing và review đã phân công cho nhóm.

| Bảng | Đơn vị một dòng | Cột chính và ý nghĩa |
| --- | --- | --- |
| `listings.csv.gz` | Listing tại mốc chụp | `id` là ID listing. `price` là giá niêm yết mỗi đêm bằng CAD. `room_type` là loại phòng. `neighbourhood_cleansed` là khu vực do nguồn chuẩn hóa. `review_scores_rating` là điểm đánh giá của listing. |
| `calendar.csv.gz` | Ngày lịch của listing | `listing_id` nối với `listings.id`. `date` là ngày trên lịch. `available` cho biết ngày mở lịch. Ngày không mở có thể đã được đặt hoặc do chủ nhà chặn. |
| `reviews.csv.gz` | Review tại mốc chụp | `id` là ID review, `listing_id` là listing được đánh giá, `date` là ngày viết và `comments` là nội dung. |
| `neighbourhoods.geojson` | Vùng địa lý | Hình học và thuộc tính khu vực từ Inside Airbnb. |
| `listings_clean.csv` | Listing thuộc mẫu tại một mốc | Khóa `snapshot_date, listing_id`. `price_cad` là giá đã đọc sang số. `price_valid`, `price_outlier_flag`, `room_type_valid` và `rating_valid` là cờ QA dùng trong KPI. |
| `reviews_clean.csv` | Review thuộc mẫu tại một mốc | Khóa `snapshot_date, review_id`. `text_valid` đánh dấu nội dung có chữ. `listing_match` đánh dấu listing khớp ở cùng mốc. |
| `calendar_listing_summary.csv` | Lịch tổng hợp theo listing và mốc | `n_calendar_days` đếm ngày có dòng lịch. `n_available_valid` đếm ngày có trạng thái xác định. `n_available` đếm ngày mở. `availability_share` và `coverage_share` lần lượt chia số ngày mở cho số ngày xác định và số ngày xác định cho số ngày có dòng lịch. |
| JSONL LLM | Dự đoán của một review | Khóa `snapshot_date, review_id`. `sentiment` là positive, mixed hoặc negative. `aspects` là danh sách khía cạnh và sắc thái. `language` là ngôn ngữ. `status` phân biệt ok, needs_review và error. |
| CSV nhãn tay | Nhãn đã chốt của một review | `manual_sentiment` là nhãn người đọc. `split` phân biệt dev và test. Giữ ID dạng văn bản. |

## Quy tắc QA và tác động

| Quy tắc | Điều kiện và lý do | Xử lý |
| --- | --- | --- |
| Phạm vi phân công | ID ngoài mẫu nhóm làm thay đổi tổng thể phân tích | Lọc theo ID phân công, ghi số dòng trước và sau |
| Thiếu và sai kiểu | Ô thiếu, giá không đọc được, ngày không phân tích được, nội dung trống hoặc trạng thái lịch ngoài danh mục | Ghi số bị ảnh hưởng. Các giá trị không hợp lệ được loại khỏi mẫu số tương ứng |
| Ngoại lai giá | Giá hợp lệ nằm ngoài hàng rào 1,5 IQR, có thể làm kết quả nhạy với vài listing | Gắn cờ. Mặc định KPI giữ giá dương đọc được. Cấu hình `kpi.exclude_price_outliers` bật phân tích loại ngoại lai |
| Trùng trong mốc | Dòng giống hệt hoặc khóa listing, review, ngày lịch lặp có thể làm tăng trọng số | Gắn cờ. Tổng hợp lịch theo một ngày mỗi listing. Khi trạng thái lịch xung đột, ngày đó không được tính là ngày xác định. Kiểm tra khóa ở LLM và KPI trước khi tính |
| Trùng giữa các mốc | Cặp listing và lần scrape hoặc review xuất hiện lại ở mốc khác | Ghi số dòng lặp. Giữ mỗi mốc để phân tích thay đổi theo thời gian |
| Danh mục lệch | Loại phòng ngoài hai nhóm phân tích, khu phân tích ngoài A01–A08 hoặc trạng thái lịch ngoài miền đã biết | Gắn cờ và loại giá trị ngoài miền khỏi phép tính dựa trên cờ |
| Điểm đánh giá | Điểm thiếu hoặc ngoài 1–5 làm sai trung vị trên listing đã được đánh giá | Gắn `rating_valid`, giữ dòng và loại điểm không hợp lệ khỏi trung vị |

`reports/qa_report.csv` ghi mốc, bảng, phép kiểm tra, số dòng ảnh hưởng và
giá trị trước/sau. Các dòng trung vị giá và điểm dùng số đã đọc được trước
khi áp cờ hợp lệ. Công thức và đơn vị từng KPI nằm trong `src/kpi.py`.
