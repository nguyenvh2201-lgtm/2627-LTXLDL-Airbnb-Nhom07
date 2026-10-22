# Bộ quy tắc QA

Tài liệu mô tả 13 quy tắc kiểm tra chất lượng dữ liệu listings, reviews và calendar. Mỗi quy tắc gồm tên, bảng áp dụng, điều kiện, lý do và hành động.

## Quy ước

- Dùng `listing_id` làm tên mã phòng sau bước chuẩn bị dữ liệu; trong listings gốc, mã này có tên `id`.
- Cờ QA có giá trị `True` khi bản ghi vi phạm quy tắc.
- Ưu tiên gắn cờ và giữ dữ liệu gốc, chưa tự động xóa hoặc điền dữ liệu.
- Kiểm tra thiếu tách riêng với lỗi chuyển kiểu, lỗi danh mục và ngoại lai.
- Kiểm tra trùng và liên kết dưới đây được thực hiện trong cùng một mốc (`snapshot_date`).

## Danh sách quy tắc

| Tên quy tắc | Bảng áp dụng | Điều kiện | Lý do | Hành động |
| --- | --- | --- | --- | --- |
| `missing_price` | listings | Giá gốc bị thiếu. | Không đủ dữ liệu để phân tích giá. | Gắn cờ, giữ dòng và không tự điền. |
| `invalid_price` | listings | Giá sau chuyển kiểu thành công ≤ 0. | Giá phòng không hợp lý. | Gắn cờ, giữ dữ liệu gốc. |
| `price_outlier` | listings | Giá dương nằm ngoài khoảng `[Q1 - 1.5 × IQR, Q3 + 1.5 × IQR]`; Q1 và Q3 tính trên các giá dương hợp lệ trong cùng mốc. | Giá khác biệt lớn, cần kiểm tra thêm. | Gắn cờ, giữ dữ liệu gốc. |
| `missing_listing_id` | listings, reviews, calendar | Mã listing bị null, rỗng hoặc chỉ chứa khoảng trắng. | Không xác định được listing để liên kết dữ liệu. | Gắn cờ nghiêm trọng, giữ dòng để kiểm tra. |
| `duplicate_listing` | listings | `listing_id` không thiếu xuất hiện nhiều lần trong cùng mốc. | Một listing chỉ nên có một bản ghi trong mỗi mốc. | Gắn cờ tất cả các dòng thuộc nhóm trùng, chưa tự xóa. |
| `duplicate_calendar` | calendar | Cùng cặp `(listing_id, date)` hợp lệ xuất hiện nhiều lần trong cùng mốc. | Một listing tại một ngày chỉ nên có một bản ghi trong mỗi mốc. | Gắn cờ tất cả các dòng thuộc nhóm trùng, chưa tự xóa. |
| `wrong_price_type` | listings | Giá gốc không thiếu nhưng sau chuẩn hóa ký hiệu tiền tệ và dấu phân cách vẫn không chuyển được sang numeric. | Giá sai định dạng, không dùng được để tính toán. | Giữ giá gốc, tạo cột giá numeric và gắn cờ lỗi chuyển đổi. |
| `wrong_date_type` | reviews, calendar | Ngày gốc không thiếu nhưng không chuyển được sang datetime. | Không xác định được ngày để phân tích theo thời gian. | Giữ ngày gốc, tạo cột ngày đã chuyển kiểu và gắn cờ. |
| `invalid_available` | calendar | `available` không thiếu nhưng sau chuẩn hóa không thuộc tập giá trị nhóm quy định. | Trạng thái phòng không thuộc danh mục được chấp nhận. | Gắn cờ, giữ giá trị gốc. |
| `invalid_minimum_nights` | listings | `minimum_nights` sau chuyển kiểu thành công ≤ 0. | Số đêm tối thiểu không hợp lý. | Gắn cờ, giữ dữ liệu gốc. |
| `min_greater_max` | listings | `minimum_nights` và `maximum_nights` đều chuyển kiểu thành công, nhưng `minimum_nights > maximum_nights`. | Số đêm tối thiểu lớn hơn số đêm tối đa. | Gắn cờ, giữ dữ liệu gốc. |
| `listing_not_found` | reviews, calendar | `listing_id` không thiếu nhưng không tồn tại trong bảng listings của nhóm cùng mốc. | Bản ghi không liên kết được với listings trong phạm vi nhóm. | Gắn cờ, giữ dòng để kiểm tra. |
| `category_mismatch` | listings | `room_type` hoặc `analysis_area` không thiếu nhưng sau chuẩn hóa không thuộc danh sách cho phép của từng cột. | Giá trị ngoài danh mục hoặc phạm vi phân tích đã quy định. | Gắn cờ theo từng cột, giữ giá trị gốc. |

## Lưu ý triển khai

- `IQR = Q3 - Q1`. Giá thiếu, lỗi chuyển kiểu và giá không dương không được tính chung vào cờ ngoại lai theo định nghĩa trên.
- `wrong_price_type` kiểm tra lỗi chuyển đổi của từng giá trị; kiểu `object` của cả cột chưa đủ để kết luận dữ liệu sai.
- Với `available`, code hiện tại chấp nhận `t`, `f`, `true`, `false` sau khi bỏ khoảng trắng đầu/cuối và chuyển về chữ thường.
- Với `room_type`, code hiện tại chấp nhận `Entire home/apt` và `Private room`. Giá trị khác có thể nằm ngoài phạm vi phân tích, chưa chắc là dữ liệu sai.
- Với `analysis_area`, code hiện tại chấp nhận `A01` đến `A08`.
- `category_mismatch` có thể được triển khai thành hai cờ riêng: `room_type_mismatch` và `analysis_area_mismatch` để dễ xác định cột vi phạm.
- Tài liệu này mô tả quy tắc; các điều kiện và hành động phải được triển khai trong code mới có hiệu lực.
- `qa.py` tổng hợp các cờ thực tế theo từng mốc vào `qa_report.csv`, đồng thời ghi nhận review xuất hiện lại và kiểm tra thay đổi ngày, listing, comments giữa từng cặp mốc. So sánh thuộc tính chỉ dùng ID không thiếu, xuất hiện đúng một lần ở mỗi mốc; bỏ cặp thiếu giá trị cần so sánh, chuẩn hóa ngày hợp lệ trước khi đối chiếu.
- Báo cáo tính số dòng trước/sau trên cùng phạm vi phân công, trung vị giá numeric và độ dài bình luận trung bình trước/sau làm sạch. Công thức và cách xử lý giá trị thiếu được ghi trong cột `note`; các chỉ số này không thay thế toàn bộ KPI phân tích của nhóm.
