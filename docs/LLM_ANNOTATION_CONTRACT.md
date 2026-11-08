# Quy tắc gán nhãn review Airbnb Toronto · Nhóm 07

Phiên bản quy tắc đang dùng trong `src/llm.py` là `tv4-simple-v3-mixed`.

## Cảm xúc tổng thể

Ba nhãn: `positive` (khen có ý nghĩa, không có chê đáng kể), `negative` (chê có ý
nghĩa, không có khen đáng kể), `mixed` (có cả khen và chê đáng kể). Câu xã giao hay
một hạn chế nhỏ không tự động làm review thành mixed. Không có nhãn neutral.
Nếu chỉ kể sự kiện hoặc không đủ cơ sở diễn giải: để sentiment trống, đánh dấu
needs_review và ghi lý do. Lỗi API không được đổi thành mixed.

## Bảy khía cạnh

| Mã | Nghĩa và ranh giới |
|---|---|
| location | Vị trí, giao thông, khoảng cách đến địa điểm |
| cleanliness | Sạch/bẩn, vệ sinh |
| host | Giao tiếp, hỗ trợ và tương tác với chủ nhà |
| value | Đánh giá rõ về đáng tiền, giá so với trải nghiệm |
| amenities | Trang bị, Wi-Fi, nội thất, sưởi và tiện ích |
| noise | Ồn hoặc yên tĩnh được nói rõ |
| safety | An toàn, an ninh hay cảm giác không an toàn được nói rõ |

Mỗi khía cạnh được nhắc có polarity positive/mixed/negative. Không nhắc thì bỏ
khía cạnh đó, không gán neutral. Mỗi khía cạnh xuất hiện tối đa một lần. Khen vị
trí không tự suy ra an toàn; khen chung không tự suy ra sạch sẽ hay tiện nghi.
Đọc phủ định và đối lập trong ngữ cảnh. Cảm xúc tổng thể không nhất thiết trùng
mọi polarity khía cạnh.

Khi nhận phản hồi API có nhiều mục cho cùng một khía cạnh, bộ đọc gộp các mục
cùng nhãn thành một mục và gộp các nhãn khác nhau thành mixed. Ví dụ amenities
positive và amenities negative trở thành một mục amenities mixed. Thứ tự khía
cạnh theo lần xuất hiện đầu tiên. Mỗi mục được kiểm tra cấu trúc và nhãn trước
khi gộp, sau đó toàn bộ kết quả được kiểm tra lại. Bước này áp dụng cho phản hồi
API mới. Bộ kiểm tra checkpoint vẫn yêu cầu mỗi khía cạnh xuất hiện một lần.

Ví dụ SAU ĐÂY LÀ GIẢ LẬP hướng dẫn, không phải nhãn người của dự án:
“Great location, but the room was filthy.” → mixed; location positive;
cleanliness negative. “Lovely stay!” → positive, không có khía cạnh cụ thể.
“Stayed two nights.” → needs_review vì không có đánh giá rõ ràng.

## Cách điền mẫu gán tay

Lấy toàn bộ ID có `split=test` từ `data/samples/llm_review_ids.csv`, ghép nội dung
review sau QA. Lưu nhãn đã chốt vào `data/samples/reviews_test_labels.csv` với
các cột `snapshot_date`, `review_id`, `manual_sentiment`, `split`; có thể thêm
`needs_review` và ghi chú. File nhãn người không chứa dự đoán LLM.

- Đọc và gán độc lập trước khi xem dự đoán; không xem đáp án LLM để quyết định nhãn.
- `manual_sentiment`: positive/mixed/negative.
- `manual_aspects`: nếu nhóm cùng gán khía cạnh, dùng JSON, ví dụ giả lập
  `[{"aspect":"cleanliness","polarity":"negative"}]`. Không bắt buộc với bộ
  đánh giá cảm xúc tổng thể hiện có; evaluator hiện chỉ tính metric sentiment.
- `needs_review=true`: chỉ khi người đọc chưa chốt được, nhãn sentiment để trống
  và note phải ghi lý do. Không đánh dấu needs_review chỉ vì LLM gán khác.
- Hai người bất đồng thì chốt bằng quy tắc và bằng chứng trong review; ghi chú
  quá trình. Giữ bản nhãn trước chỉnh sửa và phiên bản quy tắc.
- Giữ nguyên ID dạng chuỗi khi mở Excel để tránh mất chữ số.

Mọi trường hợp LLM hoặc baseline khác nhãn tay được xuất ra error_analysis.csv.
Thiếu dự đoán vẫn tính trong mẫu số, không chỉ chấm những hàng đã phân loại.
Evaluate từ chối nhãn chưa chốt, yêu cầu ít nhất 100 nhãn hợp lệ và không cho
bỏ ID trong danh sách test để cải thiện điểm. Không đổi review chỉ kể sự kiện
thành mixed để lách kiểm tra.
Số ID đã có dự đoán phải kiểm đếm từ output thực tế, không dùng con số lịch sử.

## Prompt và request thật

Prompt đang dùng là hằng `PROMPT` trong `src/llm.py`, không đọc từ `prompts/`.
`request_review()` tạo Chat Completions payload từ `request_options`, model,
system prompt và văn bản review. Khóa đọc từ biến môi trường được cấu hình
bằng `api_key_env` (mặc định `SHOPAIKEY_API_KEY`), chỉ đưa vào header HTTP.

Cả sentiment tổng thể và polarity của aspect dùng `positive/mixed/negative`.
`neutral` không thuộc contract hiện tại. Review chỉ kể sự kiện: `needs_review`,
sentiment null và aspects rỗng. API lỗi là `error`, không được đổi thành mixed.

Đổi prompt/model/tham số/văn bản/split/cờ QA tạo signature khác. Dùng output mới
cho v3; giữ checkpoint cũ riêng. Không sửa nhãn hoặc signature trong cache để
làm nó tương thích một cách giả tạo.
