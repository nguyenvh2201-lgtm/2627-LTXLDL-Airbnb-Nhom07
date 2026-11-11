# Dữ liệu kiểm thử

Fixtures tổng hợp được tạo bởi tests/conftest.py trong thư mục tạm pytest:
bốn snapshot khác các mốc thật, hai listing được chọn, ba review mẫu và
calendar ba ngày. Một review ID dài kiểm tra tránh làm tròn số nguyên.

Gold tổng hợp và phản hồi API mock chỉ dùng trong test_smoke.py/test_llm.py.
Không chép chúng sang data/samples hoặc data/processed của dự án thật.
