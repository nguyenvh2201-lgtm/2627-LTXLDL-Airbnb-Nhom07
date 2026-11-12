# Tổng hợp và phân tích lỗi (Error Analysis)

## Thống kê nhóm lỗi gợi ý

```
error_type_hint
mixed_confusion    9
```

## Nhận định nguyên nhân lỗi trên mẫu đối chứng
- **Nhầm lẫn giữa `positive` và `mixed` (`mixed_confusion`):** Toàn bộ các trường hợp lệch nhãn giữa LLM, baseline và nhãn tay đều rơi vào ranh giới giữa đánh giá tích cực (`positive`) và hỗn hợp (`mixed`).
- **Cơ chế gây lỗi của LLM:** Khi khách hàng đánh giá tổng thể rất tốt (ví dụ kết luận *Overall a great stay*, *10/10 would recommend*) nhưng đề cập thêm một lưu ý nhỏ mang tính thông tin hoặc hạn chế nhẹ (như trần nhà hơi thấp với người cao trên 6'2, nghe tiếng bước chân tầng trên nhưng không gây phiền hà lớn, phí đỗ xe thành phố cao, hoặc lưu ý kẹt xe giờ cao điểm), LLM có xu hướng nhạy cảm với chi tiết tiêu cực phụ và phân loại thành `mixed`, hoặc bỏ qua chi tiết giảm nhẹ khi lời khen chiếm ưu thế.
- **So sánh với đối chứng từ điển (Baseline):** Bộ quy tắc từ điển có ngưỡng đếm từ cảm xúc cố định và fallback `positive`, nên phù hợp với quy ước gán nhãn ưu tiên cảm xúc tổng thể ở câu kết; đổi lại, LLM trích xuất đa khía cạnh (`aspects_praise` và `aspects_complaint`) chính xác và giàu ngữ cảnh hơn hẳn bộ từ khóa tĩnh.
