# Dữ liệu kiểm thử

Fixtures tổng hợp được tạo bởi tests/conftest.py trong thư mục tạm pytest:
bốn snapshot khác các mốc thật, hai listing được chọn, ba review mẫu và
calendar ba ngày. Một review ID dài kiểm tra tránh làm tròn số nguyên.

Gold tổng hợp và phản hồi API mock chỉ dùng trong test_smoke.py/test_llm.py.
Không chép chúng sang data/samples hoặc data/processed của dự án thật.

## Phạm vi bộ test

Bộ pytest tập trung vào các hành vi ảnh hưởng lần chạy pipeline: cấu hình sai,
tải/lọc dữ liệu, QA, KPI, Gemini/cache, đánh giá và sinh hình end-to-end.
Không giữ test riêng cho alias cấu hình cũ, lỗi copy khóa API cụ thể, hay
helper đối chiếu tài liệu. Kiểm báo cáo bằng lệnh riêng:

```bash
python notebooks/tools/check_report_numbers.py
```

Test lỗi neighbourhood thiếu và parse_error vẫn được giữ vì chúng bảo vệ
kết quả tính toán khi dữ liệu đầu vào thay đổi.

### Thu gọn lần hai

- Gộp bốn cấu hình sai vào một test; gộp retry HTTP 429/timeout, cache theo prompt/model, và skip/thiếu khóa theo hành vi chung.
- Bỏ test chunk-equivalence riêng: smoke test kiểm luồng lọc, test exact-ID giữ kiểm ID lớn/leading zero và bổ sung no-match/empty.
- Gộp kỳ vọng theo snapshot và cảnh báo snapshot mới; chuyển kiểm cấu trúc qa_report vào smoke test.
- Bỏ kiểm rating trùng; giữ IQR/schema trong test numeric.
- Bỏ hai test chỉ kiểm cách hiển thị HTTP 400 và hai test QA riêng cho khóa listing trùng/assignment vùng mâu thuẫn; vẫn giữ các guard trong mã nguồn, không còn kiểm riêng những nhánh này.
- Giữ test KPI bằng tay, neighbourhood thiếu, parse_error, gold/metrics/baseline, tải/gzip, QA đầu vào và chạy pipeline end-to-end.

Đây là giảm số test riêng và setup trùng; các tình huống độc lập về cấu hình, retry và cache vẫn được chạy bên trong các test đã gộp.
