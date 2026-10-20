# Định nghĩa 5 KPI Phân tích Airbnb (TV3)

Tài liệu này định nghĩa 5 KPI cốt lõi trả lời 3 câu hỏi kinh doanh về cơ cấu phòng, mức giá, và độ khả dụng/đánh giá của Airbnb Toronto.

**Danh sách cột cần TV2 (Data Engineer) đảm bảo trong dữ liệu sạch:**
- Bảng listings: `id`, `price`, `room_type`, `neighbourhood_cleansed`, `review_scores_rating`.
- Bảng calendar: `listing_id`, `date`, `available`.

---

#### 1. Tổng số lượng Listing (n_listings)
- **Câu hỏi phục vụ:** Quy mô thị trường tại mỗi thời điểm và mỗi khu vực/loại phòng thay đổi ra sao? (Phục vụ TV5 vẽ biểu đồ tổng quan).
- **Công thức:** Đếm số lượng mã `id` duy nhất.
- **Đơn vị:** Căn/Listing.
- **Dữ liệu đầu vào:** Cột `id` (listings.csv).
- **Điều kiện hợp lệ / Mẫu số:** Tất cả các dòng trong bảng listings (mỗi dòng phải là 1 id duy nhất).
- **Hạn chế:** Chỉ đếm số lượng niêm yết, không phản ánh việc căn đó có đang thực sự hoạt động hay bị bỏ hoang.

#### 2. Giá niêm yết trung vị (median_price_cad) & Phân vị (Q1, Q3)
- **Câu hỏi phục vụ:** Mức giá bình thường mà khách hàng phải trả là bao nhiêu? Giá khác nhau thế nào giữa các khu vực?
- **Công thức:** Tính giá trị trung vị (Median - 50%), Q1 (25%) và Q3 (75%) của giá niêm yết.
- **Đơn vị:** CAD/đêm.
- **Dữ liệu đầu vào:** Cột `price` (listings.csv).
- **Điều kiện hợp lệ / Mẫu số:** Yêu cầu đếm và xuất kèm `n_price_valid` (số listing có giá khác Null). Chỉ tính median trên tập hợp này.
- **Hạn chế:** Đây là giá niêm yết do chủ nhà đặt, chưa tính phí dọn dẹp, phí dịch vụ Airbnb hay các đợt giảm giá. Không phải giá giao dịch thực tế.

#### 3. Tỷ lệ Entire home/apt (entire_home_share)
- **Câu hỏi phục vụ:** Tỷ trọng căn hộ nguyên căn (mang lại không gian riêng tư) chiếm bao nhiêu phần trăm?
- **Công thức:** Số lượng listing có `room_type == 'Entire home/apt'` chia cho `n_room_type_valid`.
- **Đơn vị:** Tỷ lệ (0 - 1).
- **Dữ liệu đầu vào:** Cột `room_type` (listings.csv).
- **Điều kiện hợp lệ / Mẫu số:** Mẫu số (`n_room_type_valid`) là tổng số listing có `room_type` rõ ràng. Nếu `room_type` thiếu, gán là 'Unknown' và KHÔNG đưa vào mẫu số.
- **Hạn chế:** Phụ thuộc vào khai báo chủ quan của chủ nhà, một số chủ nhà chia nhỏ phòng nhưng vẫn khai báo là Entire home.

#### 4. Tỷ lệ mở lịch quan sát được (availability_share_mean)
- **Câu hỏi phục vụ:** Căn hộ có sẵn sàng đón khách trong 365 ngày tới không?
- **Công thức:** Tính tỷ lệ ngày trống (`available == 't'`) trên tổng số ngày quan sát được của TỪNG listing. Sau đó tính giá trị trung bình (`mean`) của các tỷ lệ này cho toàn nhóm.
- **Đơn vị:** Tỷ lệ (0 - 1).
- **Dữ liệu đầu vào:** Cột `available` (calendar.csv).
- **Điều kiện hợp lệ / Mẫu số:** Cần xuất kèm `n_calendar_listings` (số căn có dữ liệu lịch) và `calendar_coverage_mean` (số ngày trung bình thu thập được lịch của 1 căn).
- **Hạn chế:** Lịch không khả dụng (available='f') có thể do khách đã đặt (có doanh thu) hoặc do chủ nhà khóa lịch (không đón khách). Ta KHÔNG suy ra được tỷ lệ lấp đầy (occupancy rate) từ chỉ số này.

#### 5. Điểm đánh giá trung vị (median_rating)
- **Câu hỏi phục vụ:** Chất lượng lưu trú tổng thể của thị trường thế nào?
- **Công thức:** Giá trị trung vị của điểm đánh giá tổng.
- **Đơn vị:** Điểm.
- **Dữ liệu đầu vào:** Cột `review_scores_rating` (listings.csv).
- **Điều kiện hợp lệ / Mẫu số:** Xuất kèm `n_rating_valid` (số lượng listing thực sự có điểm). Bỏ qua các listing chưa từng có review (Null).
- **Hạn chế:** Điểm đánh giá của Airbnb thường rất cao (lệch phải - skewed), median thường rơi vào khoảng 4.8 - 5.0, ít phản ánh được các khác biệt nhỏ.
# ---- KPI 6. area_price_premium — Chênh lệch giá khu vực so với thành phố (theo khu vực)
    #   Mục tiêu : khu vực nào đắt hơn hoặc rẻ hơn mặt bằng chung của Toronto trong cùng mốc.
    #   Công thức: median_price_cad(khu vực) / median_price_cad(thành phố, cùng mốc) − 1.
    #              Ví dụ 0,20 nghĩa là khu vực đắt hơn trung vị thành phố 20%.
    #   Đơn vị   : tỷ lệ. Tiền gốc là CAD/đêm.
    #   Mẫu số   : n_price_valid của khu vực. Điều kiện để tính:
    #              khu vực không phải Unknown; n_price_valid >= MIN_N_SHARE (30);
    #              cả hai median đều có giá trị. Không đạt thì để NaN.
    #   Đối chiếu: cột city_median_price_cad được ghi kèm trong kpi_area.csv.
    #   Hạn chế  : so sánh thành phần listing, không phải giá của cùng một căn.
# ---------------------------------------------------------- KPI 7 (theo thời gian)
# ---- KPI 7. delta_median_price_cad — Thay đổi giá trung vị so với mốc trước
    #   Mục tiêu : hướng và độ lớn thay đổi giá niêm yết giữa hai mốc liền kề.
    #   Công thức: median_price_cad(t) − median_price_cad(t−1), đơn vị CAD/đêm.
    #     Mẫu số   : không có. Điều kiện: cả hai mốc phải có median; nếu thiếu thì để trống.
    #   Mốc đầu tiên không có mốc trước nên để trống.
    #   Không bắc cầu qua mốc thiếu giá (2025-12-12 thiếu giá thì không so 2026-03-19 với 2025-09-11).
    #   Hạn chế  : thành phần listing có thể khác giữa hai mốc; đây không phải giá của cùng một căn.
    # ------------------------------------------------------------- KPI dùng LLM
# Đầu vào: JSONL do llm.py ghi, mỗi dòng là một review với các khoá:
    #   snapshot_date, review_id, listing_id, status (ok | needs_review | error),
    #   sentiment (positive | neutral | negative | null), aspects ([{aspect, polarity}]),
    #      language, error, split (tuỳ chọn).
    # Một review chỉ được tính là "dùng được" khi status = "ok" VÀ sentiment thuộc LLM_LABELS.
