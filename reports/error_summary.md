# Tổng hợp và phân tích lỗi (Error Analysis)

## Thống kê nhóm lỗi gợi ý

```
error_type_hint
mixed_confusion    9
```

## Nhận định nguyên nhân lỗi trên mẫu đối chứng
- **Thống kê lệch nhãn trên 100 mẫu nhãn tay:** Tổng số dòng có ít nhất một phương pháp lệch nhãn tay là **9** dòng (trong đó LLM lệch **9** dòng, Baseline từ điển lệch **1** dòng).
- **So sánh hiệu năng cảm xúc (`sentiment`):** Baseline từ điển đạt Accuracy = **0.9900** (Macro-F1 = **0.9679**), cao hơn LLM với Accuracy = **0.9100** (Macro-F1 = **0.7112**), chênh lệch ghép cặp `llm_minus_baseline` = **-0.0800** (95% CI: [-0.1400, -0.0300]). Nguyên nhân là mẫu 100 review nhãn tay mất cân bằng mạnh (93 `positive`, 6 `mixed`, 1 `negative`) và quy ước gán nhãn tay ưu tiên kết luận tổng thể tích cực khi chỉ có lưu ý nhỏ.
- **Cơ chế gây lỗi của LLM (`mixed_confusion`):** Khi khách hàng đánh giá tổng thể rất tốt (ví dụ *Overall a great stay*, *10/10 would recommend*) nhưng kèm theo lưu ý phụ (tiếng bước chân tầng trên, phí đỗ xe thành phố, hoặc cần bảo trì nhẹ), LLM nhạy cảm với mệnh đề nhượng bộ nên gán `mixed` (4 ca `positive -> mixed`), hoặc ngược lại gán `positive` khi lời khen áp đảo (5 ca `mixed -> positive`).
- **So sánh trích xuất khía cạnh (`aspects`):** Ở tác vụ trích xuất khía cạnh được khen (`aspects_praise`), LLM đạt Micro-F1 = **0.8503**, vượt rõ rệt so với Baseline từ điển (**0.6934**) nhờ hiểu ngữ cảnh đồng nghĩa. Tuy nhiên, ở khía cạnh bị chê (`aspects_complaint`), do số mẫu phàn nàn thực sự trong tập nhãn tay rất ít (chỉ 7/100 review có nhãn chê) và LLM hay trích xuất cả các lưu ý nhẹ thành lời chê (precision thấp), Micro-F1 của LLM đạt **0.3636** so với **0.5333** của Baseline.
