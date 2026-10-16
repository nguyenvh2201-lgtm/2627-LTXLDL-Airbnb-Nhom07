# Định nghĩa 5 KPI phân tích thị trường Airbnb

 5 KPI cốt lõi dùng để trả lời các câu hỏi về cơ cấu loại phòng, giá cả, mức độ sẵn sàng và chất lượng đánh giá của thị trường.

## 1. Số lượng listing (`n_listings`)
* **Câu hỏi phục vụ:** Quy mô thị trường và sự phân bổ số lượng chỗ ở giữa các mốc, khu vực là bao nhiêu?
* **Công thức:** Đếm tổng số lượng ID chỗ ở (`listing_id`) duy nhất.
* **Đơn vị:** Số nguyên (listing).
* **Dữ liệu đầu vào:** Cột `id` trong bảng listings sạch.
* **Điều kiện hợp lệ:** Áp dụng cho tất cả các ID có trong bảng.
* **Mẫu số/Số mẫu xuất kèm:** Không có mẫu số. 
* **Hạn chế:** Chỉ cho biết quy mô đăng ký trên nền tảng, không phản ánh việc căn hộ đó có đang kinh doanh hiệu quả hay không.

## 2. Giá trung vị (`median_price_cad`)
* **Câu hỏi phục vụ:** Mức giá niêm yết phổ biến nhất khác nhau thế nào giữa các loại phòng và khu vực?
* **Công thức:** Tính giá trị trung vị (median) của giá niêm yết. Không dùng giá trị trung bình (mean) để tránh bị nhiễu bởi các căn hộ giá quá cao/thấp.
* **Đơn vị:** Nội tệ / đêm (ví dụ CAD/đêm).
* **Dữ liệu đầu vào:** Cột `price` trong bảng listings.
* **Điều kiện hợp lệ:** Chỉ tính các listing có giá trị `price` hợp lệ (`price` không bị thiếu và > 0).
* **Mẫu số/Số mẫu xuất kèm:** Xuất kèm `n_price_valid` (số lượng listing có giá hợp lệ). Nhóm nào `n_price_valid` = 0 thì giá trung vị để trống (NaN).
* **Hạn chế:** Đây chỉ là mức giá niêm yết của chủ nhà, không chắc chắn là giá khách hàng thực sự giao dịch.

## 3. Tỷ lệ Entire home/apt (`entire_home_share`)
* **Câu hỏi phục vụ:** Cơ cấu nhà nguyên căn/căn hộ chiếm bao nhiêu phần trăm trong tổng số nguồn cung?
* **Công thức:** (Số lượng listing có `room_type` = 'Entire home/apt') / `n_room_type_valid`.
* **Đơn vị:** Tỷ lệ (0.0 - 1.0).
* **Dữ liệu đầu vào:** Cột `room_type` trong bảng listings.
* **Điều kiện hợp lệ:** Listing phải có thông tin loại phòng.
* **Mẫu số/Số mẫu xuất kèm:** `n_room_type_valid` (tổng số listing có loại phòng hợp lệ).
* **Hạn chế:** Không áp dụng khi xuất bảng thống kê đã chia nhóm theo từng `room_type`.

## 4. Tỷ lệ mở lịch quan sát được (`availability_share_mean`)
* **Câu hỏi phục vụ:** Mức độ sẵn sàng đón khách của thị trường ra sao?
* **Công thức:** Tính tỷ lệ số ngày trống (`available` = 't') trên tổng số ngày trong lịch của từng listing. Sau đó tính trung bình (mean) của các tỷ lệ này cho toàn nhóm.
* **Đơn vị:** Tỷ lệ (0.0 - 1.0).
* **Dữ liệu đầu vào:** Cột `available` và `listing_id` trong bảng calendar.
* **Điều kiện hợp lệ:** Listing phải có dữ liệu trong bảng calendar.
* **Mẫu số/Số mẫu xuất kèm:** `n_calendar_listings` (số lượng listing có dữ liệu lịch).
* **Hạn chế:** Tỷ lệ trống thấp có thể do nhà kinh doanh tốt (được đặt nhiều) hoặc do chủ nhà chủ động khóa lịch nghỉ ngơi. Dữ liệu không phân biệt được hai trường hợp này.

## 5. Điểm đánh giá trung vị (`median_rating`)
* **Câu hỏi phục vụ:** Chất lượng dịch vụ nhìn chung thay đổi như thế nào?
* **Công thức:** Tính giá trị trung vị (median) của điểm đánh giá.
* **Đơn vị:** Điểm.
* **Dữ liệu đầu vào:** Cột điểm tổng hợp (ví dụ: `review_scores_rating`) trong bảng listings.
* **Điều kiện hợp lệ:** Listing phải có điểm đánh giá (không khuyết thiếu).
* **Mẫu số/Số mẫu xuất kèm:** `n_rating_valid` (số lượng listing có điểm đánh giá).
* **Hạn chế:** Điểm trung vị trên nền tảng thường bị dồn về mức rất cao (4.8 - 5.0), khó phản ánh rõ sự phân hóa chất lượng trừ khi có sự cố diện rộng.