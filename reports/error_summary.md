# Tổng hợp và phân tích lỗi (Error Analysis)

## Thống kê nhóm lỗi gợi ý

```
error_type_hint
mixed_confusion    9
```

## Nhận định nguyên nhân lỗi trên mẫu đối chứng
- **Thống kê lệch nhãn trên 100 mẫu nhãn tay:** Tổng số dòng có ít nhất một phương pháp lệch nhãn tay là **9** dòng (trong đó LLM lệch **9** dòng, Baseline từ điển lệch **1** dòng).
- **Cảm xúc (`sentiment`):** LLM Accuracy = **0.9100**, Macro-F1 = **0.7112**; Baseline Accuracy = **0.9900**, Macro-F1 = **0.9679**. Chênh lệch ghép cặp `llm_minus_baseline` = **-0.0800**, 95% CI [-0.1400, -0.0300].
- **Phân bố 100 nhãn tay:** 93 `positive`, 6 `mixed`, 1 `negative`.
- **Các hướng lệch nhãn LLM (nhãn tay -> dự đoán):** mixed -> positive: 5; positive -> mixed: 4. Nhóm lỗi ở trên chỉ là gợi ý; nguyên nhân cần đọc lại từng review.
- **Khía cạnh khen:** Micro-F1 LLM = **0.8503**, Baseline = **0.6934**.
- **Khía cạnh chê:** Micro-F1 LLM = **0.3636**, Baseline = **0.5333**; 7/100 review có nhãn chê. Chưa kiểm định ý nghĩa thống kê cho chênh lệch khía cạnh.
