# AI_USAGE

## Công cụ đã dùng cho phần tích hợp

ChatGPT/Codex hỗ trợ đối chiếu cấu trúc nhánh `main`, xác nhận danh sách ID,
đồng bộ cấu hình và kiểm thử giao tiếp giữa LLM với KPI.

Mã phân tích review có hai profile dùng API ShopAIKey. Khi chạy thực nghiệm,
nhóm ghi lại profile, model được trả về, mốc dữ liệu và căn cứ tính chi phí.

## Prompt phân tích review

Prompt nằm ở `PROMPT` trong `src/llm.py` với phiên bản `tv4-simple-v3-mixed`.
Prompt yêu cầu trả JSON có cảm xúc, khía cạnh, ngôn ngữ, trạng thái và lý do
khi cần xem lại. Quy tắc gán nhãn được ghi trong `docs/LLM_ANNOTATION_CONTRACT.md`.

## Sai sót phát hiện khi kiểm chứng

Hướng dẫn gói LLM trước đây dùng `--llm-file`, nhưng `kpi.py` trong ZIP `main`
chưa hỗ trợ cờ này. Nhóm kiểm tra bằng lệnh KPI và bộ test tích hợp, rồi ghép
bản KPI có phần đọc JSONL với contract `positive`, `mixed`, `negative`.

Trong lượt kiểm thử API thật do thành viên chạy trên mốc 2025-09-11, review
1447946422410222540 được model trả amenities positive và amenities negative
thành hai mục. Validator phát hiện khía cạnh trùng và runner giữ bốn kết quả
đã hoàn thành trong checkpoint. Phản hồi JSON gốc được dùng để tái hiện lỗi
offline. Codex hỗ trợ bổ sung bước chuẩn hóa thành một mục amenities mixed
và kiểm thử việc giữ nguyên kết quả đã lưu khi chạy tiếp. Kết quả chạy API
thật sau bản sửa cần được ghi nhận từ lượt chạy của nhóm.

## Cách kiểm chứng

Đối chiếu 1.000 cặp `review_id` và `listing_id` với cột đánh dấu mẫu trong
`data/data-new.csv`. Kiểm tra 100 ID test khớp nhóm được chỉ định gán nhãn.
Dùng test offline cho validate, checkpoint, đánh giá và phép tính KPI.

## Các yêu cầu dùng AI trong phần tích hợp

- Kiểm tra bộ ID được phân công và ghép đầu vào giữa QA, LLM và KPI.
- Rút gọn luồng gọi API, giữ checkpoint và chữ ký cấu hình.
- Sửa xử lý khía cạnh lặp khi API trả cả hai sắc thái cho cùng một mục.
- Đối chiếu nhãn tay xuất từ công cụ gán nhãn với các ID Test và dev.
- Nối tải dữ liệu, QA, LLM, đánh giá, KPI và biểu đồ trong một lệnh chạy.

Nhóm đã chạy thử API trên 5 review mốc 2025-09-11. Sau khi sửa khía cạnh lặp,
lượt đọc lại kết quả qua kiểm tra KPI và sinh đủ ba bảng KPI LLM. Lượt kiểm
thử toàn pipeline dùng dữ liệu thô bốn mốc thật và phản hồi API giả lập.
Các chỉ số LLM từ phản hồi giả lập không dùng làm kết quả thực nghiệm.
