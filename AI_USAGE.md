# Khai báo chi tiết việc sử dụng AI trong bài tập lớn

**Dự án:** Phân tích dữ liệu Inside Airbnb Toronto — UET.DSE2049 4, Nhóm 07.

**Phạm vi khai báo:** Mã nguồn, cấu hình, xử lý dữ liệu, tính KPI, phân tích review, kiểm thử, trực quan hóa và tài liệu của dự án.

Trong bài tập lớn này, nhóm sử dụng **Codex** để hỗ trợ phân tích yêu cầu kỹ thuật, đề xuất cách tổ chức chương trình, viết và chỉnh sửa các phần mã, tìm nguyên nhân lỗi, xây dựng kiểm thử, đối chiếu đầu ra và soạn bản nháp tài liệu. Sự tham gia của AI có cả công việc trực tiếp tạo ra sản phẩm, như viết hàm xử lý, chỉnh prompt và viết kiểm thử, chứ không chỉ dừng ở hỏi đáp hoặc sửa câu chữ.

Phần do nhóm trực tiếp thực hiện và chịu trách nhiệm gồm xác định yêu cầu bài làm, lựa chọn và xác nhận cấu hình phân tích, quản lý dữ liệu được phân công, đọc hiểu các thay đổi, gán hoặc xác nhận nhãn đánh giá, kiểm tra kết quả, lựa chọn nhận xét và hoàn thiện sản phẩm nộp. **Trách nhiệm về toàn bộ bài làm vẫn thuộc về nhóm**, kể cả đối với phần có AI hỗ trợ.

## Công cụ đã dùng (vào việc gì)

### 1. QA — Kiểm tra và làm sạch dữ liệu

**Đồng bộ quy tắc giá giữa dữ liệu QA và dữ liệu dùng tính KPI.** Nhóm nhờ AI rà soát phần xử lý giá trong `src/qa.py`, nhất là sự khác nhau giữa giá thiếu, giá không hợp lệ và giá ngoại lai. AI hỗ trợ chỉnh đoạn tạo cờ để giá dương hợp lệ mới được xét ngoại lai theo IQR, đồng thời kết hợp các giới hạn trong cấu hình. Phần này cần giữ riêng giá trị đã chuyển kiểu và các cờ kiểm tra để các bước sau biết bản ghi bị loại khỏi phép tính vì lý do gì, thay vì xóa toàn bộ dòng.

Một lỗi thực tế là số giá trung vị trong báo cáo QA chưa khớp với KPI vì hai bước chọn tập giá khác nhau. Nhóm nhờ AI đối chiếu `report_table()` trong `src/qa.py`, phần đọc dữ liệu trong `src/download.py` và phần tính K1 trong `src/kpi.py`. Điều kiện đã được thống nhất về giá hợp lệ và không có cờ ngoại lai. Cách kiểm tra là đối chiếu cùng một mốc, cùng tập listing và cùng điều kiện lọc giữa các đầu ra.

**Xử lý trạng thái lịch phòng trước khi đưa vào phép tính.** Cột `available` có thể được đọc dưới dạng chuỗi `t/f`, trong khi công thức KPI cần giá trị boolean hoặc số. Nhóm từng gặp lỗi chuyển chuỗi `f` sang số nên nhờ AI sửa bước chuyển kiểu và bổ sung kiểm thử cho chuỗi/boolean. Điểm cần chú ý là trạng thái thiếu hoặc không hợp lệ không được tự hiểu thành phòng đã được đặt; các dòng này cần được phân biệt trước khi tính tỷ lệ.

**Giảm dung lượng đầu ra calendar mà vẫn giữ dữ liệu phục vụ phân tích.** Bản triển khai trước tạo các tệp `calendar_flagged.csv` lớn và có thông tin trùng với dữ liệu đã lưu. Nhóm nhờ AI hỗ trợ chuyển sang bảng tóm tắt theo listing và dữ liệu sạch dạng Parquet nén, đồng thời điều chỉnh nơi đọc các đầu ra này. Đây là thay đổi liên quan đến cả QA và các bước phía sau nên cần kiểm tra lại luồng đọc dữ liệu, không chỉ kiểm tra việc ghi tệp thành công.

### 2. KPI — Tính các chỉ số phân tích

**Ghép calendar với listings mà không làm tăng số dòng ngoài ý muốn.** Nhóm nhờ AI hỗ trợ phần ghép khu vực vào từng dòng lịch trong `compute()` của `src/kpi.py`. Khóa ghép gồm `listing_id` và `snapshot`, vì cùng một listing xuất hiện ở nhiều mốc dữ liệu. Đoạn ghép sử dụng kiểm tra quan hệ `many_to_one` để phát hiện trường hợp phía listings có khóa trùng, có thể làm nhân số ngày lịch và sai kết quả tổng hợp.

Sau khi ghép, phép tính chỉ nhận các ngày có trạng thái lịch, ngày và khu vực hợp lệ. Với K2/K3, mã tính `(1 - mean(available)) * 100` trên các dòng hợp lệ theo khu vực hoặc tháng. Nhóm nhờ AI hỗ trợ kết nối điều kiện này với dữ liệu sau QA. Khi diễn giải, đây là tỷ lệ ngày không khả dụng trong lịch, cần thận trọng nếu dùng để nhận định về công suất thực tế.

**Tránh đếm lặp review khi tổng hợp nhiều snapshot.** Một review có thể xuất hiện trong nhiều lần chụp dữ liệu. Nhóm nhờ AI hỗ trợ đoạn sắp xếp theo snapshot, giữ một bản ghi cho mỗi review ID rồi mới tổng hợp theo quý ở K5. Nếu cộng thẳng số review của từng snapshot thì cùng một review có thể được tính nhiều lần. Phần triển khai còn cần giữ rõ mẫu số là số listing duy nhất trong mẫu được phân công, để kết quả không bị hiểu thành thống kê cho toàn bộ thị trường.

**Kết nối KPI phụ thuộc LLM với thứ tự chạy pipeline.** Nhóm nhờ AI hỗ trợ tách việc tính các chỉ số từ dữ liệu bảng và việc bổ sung K7 từ kết quả LLM. Pipeline tính KPI sau QA để có các bảng cơ bản, rồi cập nhật lại sau bước LLM/evaluate trước khi vẽ hình. Phần AI hỗ trợ là luồng đọc kết quả, kiểm tra dữ liệu hợp lệ và xử lý khi chưa có dự đoán; khi thiếu dữ liệu, chương trình không tự điền một tỷ lệ để làm đầy bảng.

### 3. LLM + Baseline + Evaluate — Phân tích và đánh giá review

**Ràng buộc đầu ra Gemini để kết quả có thể dùng trực tiếp trong pipeline.** Nhóm nhờ AI hỗ trợ chỉnh prompt, xây dựng JSON schema và viết phần kiểm tra trong `validate_results()` của `src/llm.py`. Việc kiểm tra không dừng ở chỗ JSON đọc được mà còn xét đúng số review, đúng tập trường, đúng ID và thứ tự phản hồi, nhãn cảm xúc thuộc `positive/mixed/negative`, khía cạnh thuộc danh mục cấu hình và không bị lặp. Mục đích là tránh đưa một phản hồi có cấu trúc đọc được nhưng sai nội dung định dạng vào bảng kết quả.

**Xử lý giới hạn API và chạy tiếp từ kết quả đã lưu.** Nhóm nhờ AI hỗ trợ cơ chế giới hạn tốc độ, thử lại khi gặp lỗi có thể phục hồi và xử lý thời gian chờ `Retry-After`. Kết quả đã nhận được lưu vào cache để khi chạy lại không phải gọi lại toàn bộ review. AI còn hỗ trợ phần khóa cache dựa trên ID, văn bản, model, phiên bản prompt và nội dung prompt/schema. Nếu chỉ dùng ID, chương trình có thể lấy lại dự đoán cũ ngay cả khi nhóm đã thay đổi yêu cầu phân loại.

**Xử lý phủ định và cảm xúc hỗn hợp trong baseline.** Trong `predict()` của `src/baseline.py`, nhóm nhờ AI hỗ trợ triển khai cửa sổ từ phủ định đứng trước từ cảm xúc, thay vì chỉ cộng số từ tích cực và tiêu cực. AI cũng hỗ trợ điều kiện gán `mixed` khi review có cả hai nhóm cảm xúc, cùng cách tìm từ cảm xúc gần từ khóa khía cạnh trong một cửa sổ ngữ cảnh. Các quy tắc này là phương án đối chứng dựa trên từ điển và vẫn có hạn chế với câu dài, mỉa mai hoặc phủ định phức tạp.

**So sánh hai phương pháp trên cùng tập nhãn tay.** Nhóm nhờ AI hỗ trợ ghép dự đoán với gold theo `review_id`, kiểm tra khóa trùng và giữ nguyên tập review đánh giá trong `src/evaluate.py`. Dự đoán thiếu hoặc lỗi được đánh dấu `missing_or_error`, không âm thầm bỏ khỏi mẫu để làm tăng điểm. Với nhãn khía cạnh, AI hỗ trợ chuyển danh sách khía cạnh thành các cột nhị phân theo cùng danh mục rồi tính precision/recall/F1 cho bài toán nhiều nhãn.

**Ước lượng độ bất định của điểm đánh giá.** Ngoài Accuracy và macro-F1, nhóm nhờ AI hỗ trợ triển khai bootstrap: lấy mẫu review có hoàn lại nhiều lần, tính lại chỉ số rồi lấy các phân vị để tạo khoảng tin cậy. Danh sách ba lớp cảm xúc được giữ cố định vì một lần lấy mẫu có thể không có lớp hiếm. Phần so sánh chênh lệch Accuracy sử dụng kết quả đúng/sai của hai mô hình trên cùng review để giữ tính ghép cặp, thay vì lấy mẫu độc lập cho từng mô hình.

Về dữ liệu nhãn, Codex có hỗ trợ chuẩn hóa các khía cạnh do người dùng điền sang JSON và tạo nhãn gợi ý cho 50 review bổ sung. Các nhãn gợi ý được đánh dấu `AI_draft`; chỉ các dòng được xác nhận là nhãn người gán mới được dùng làm gold. Theo nhật ký triển khai, dự án đã có 1.000 dự đoán Gemini hợp lệ và bộ 100 review do người dùng gán nhãn để đánh giá. Phần chuẩn hóa định dạng và phần tạo nhãn gợi ý được khai báo riêng để không nhầm với việc gán nhãn tay.

### 4. Viz — Biểu đồ và báo cáo

**Giữ thống nhất tập dữ liệu giữa biểu đồ, KPI và phần nhận xét.** Nhóm nhờ AI hỗ trợ đoạn chọn dữ liệu hợp lệ trước khi vẽ trong `src/viz.py`, đặc biệt ở bản đồ giá và biểu đồ giá theo khu vực. Giá trung vị và cách chia nhóm giá phải dùng cùng điều kiện lọc với KPI. Nếu biểu đồ lấy cả giá đã bị QA gắn cờ còn bảng KPI loại các giá đó, hai phần có thể đưa ra thông tin khác nhau dù cùng nói về một mốc dữ liệu.

**Đưa kết quả đánh giá nhiều loại tác vụ lên biểu đồ.** Nhóm nhờ AI hỗ trợ phần đọc các dòng chỉ số của LLM/baseline và ghép cận dưới, cận trên của khoảng tin cậy để thể hiện sai số. Cần phân biệt macro-F1 của cảm xúc với micro-F1 của khía cạnh, vì chúng đánh giá các tác vụ khác nhau. Ma trận nhầm lẫn cũng cần giữ thứ tự lớp nhất quán với phần evaluate để tên lớp trên hình khớp với các ô số liệu.

**Tạo báo cáo từ số liệu đầu ra và kiểm tra tính nhất quán.** Nhóm nhờ AI hỗ trợ tập hợp các con số dùng chung, đưa số liệu và hình vào Markdown/PDF, đồng thời viết công cụ đối chiếu số trong báo cáo với bảng kết quả. AI cũng có tham gia dựng bố cục và viết bản nháp nhận xét. Khi xem bản render, phần nhãn bản đồ bị gần nhau đã được chỉnh lại vị trí và thêm nền để đọc được rõ hơn.

Đối với nội dung phân tích, đề xuất của AI cần được xem lại cùng số liệu nguồn. Một điểm cần chú ý là tập nhãn tay có ít review tiêu cực/hỗn hợp, nên điểm số và khoảng tin cậy không đủ để kết luận mô hình nào tốt hơn trong mọi tình huống. Nhóm chịu trách nhiệm về các nhận định được giữ trong báo cáo cuối.

### 5. Download + Run pipeline — Tải dữ liệu và chạy toàn bộ quy trình

**Ngăn tệp tải dở được dùng làm dữ liệu đầu vào.** Trong `download_file()` và `verify_file()` của `src/download.py`, nhóm nhờ AI hỗ trợ tải dạng stream vào tệp tạm `.part`, kiểm tra xong mới đổi sang tên tệp chính thức. Bước xác thực kiểm tra cột khóa, đọc hết tệp gzip để phát hiện lỗi CRC và tính SHA256 để ghi nhận tệp được sử dụng. SHA256 ở đây giúp nhận diện/đối chiếu tệp giữa các lần chạy; không tự chứng minh tệp giống nguồn nếu chưa có mã chuẩn từ nguồn để so sánh.

**Lọc dữ liệu lớn theo chunk và bảo toàn khóa ID.** Nhóm nhờ AI hỗ trợ `filtered_chunks()` để chỉ giữ các dòng thuộc danh sách được phân công trong từng khối đọc. Các cột ID được đọc dưới dạng chuỗi nhằm tránh sai lệch khi ID dài bị chuyển sang số thực. Khi ghép bảng phân công vào dữ liệu đã lọc, mã có kiểm tra quan hệ khóa để phát hiện trùng lặp thay vì để phép ghép tự nhân bản ghi.

**Phân biệt thiếu dữ liệu thật với lỗi tải hoặc lỗi lọc.** Nhóm nhờ AI hỗ trợ kiểm tra từng snapshot và xuất danh sách ID không tìm thấy. Ở mốc cuối, nhật ký ghi nhận thiếu 72 listing so với danh sách ban đầu; phần xử lý giữ nguyên mốc dữ liệu đã chọn và báo thiếu, không bổ sung dòng giả. Với `--skip-download`, tệp có sẵn vẫn được xác thực; nếu tệp thiếu/hỏng thì báo lỗi thay vì coi bước tải đã hoàn tất.

**Chạy lại các bước mà vẫn giữ đúng quan hệ phụ thuộc.** Trong `run_pipeline.py`, nhóm nhờ AI hỗ trợ kết nối thứ tự download → QA → KPI → LLM → baseline → evaluate → KPI → viz, cùng các tùy chọn chạy từng phần hoặc bỏ qua gọi API. AI cũng hỗ trợ kiểm thử tích hợp để kiểm tra các bước có đọc được đầu ra của nhau và tạo đủ các bảng cùng biểu đồ phân tích. Một lỗi từng gặp là pytest thu thập cả bản kiểm thử trong thư mục sao chép tạm, gây xung đột import; cấu hình phạm vi thu thập đã được điều chỉnh để tránh lặp lại.

### 6. Notebooks — Kiểm thử, công cụ kiểm tra và tham khảo bài giảng

**Phạm vi khai báo.** Thư mục `notebooks/` hiện chứa các tệp Python kiểm thử, công cụ hỗ trợ và cấu hình pytest; không có tệp Jupyter `.ipynb` trong bản mã hiện tại. Nhóm sử dụng Codex để hỗ trợ xây dựng, chỉnh sửa và rà soát các phần này cùng mã trong `src/`. Bảng dưới mô tả phạm vi hỗ trợ theo từng tệp, không có nghĩa toàn bộ nội dung của mỗi tệp đều do AI tạo ra.

#### 6.1. Cấu hình và dữ liệu kiểm thử

| Tệp | Nội dung có AI hỗ trợ |
| --- | --- |
| `notebooks/pytest.ini` | Thiết lập phạm vi thu thập test, loại trừ môi trường ảo và thư mục sao chép `.work`, tắt cache pytest và đặt thư mục tạm để tránh thu thập trùng test. |
| `notebooks/tests/conftest.py` | Tạo fixture cấu hình và dữ liệu tổng hợp trong thư mục tạm: bốn snapshot khác mốc thật, hai listing được chọn, ba review và calendar ba ngày. Bổ sung ID review dài để kiểm tra việc giữ nguyên khóa; nối các fixture qua bước filter và QA. |
| `notebooks/tests/fixtures/README.md` | Soạn mô tả nguồn dữ liệu giả lập, phạm vi sử dụng gold tổng hợp và phản hồi API mock; nêu rõ dữ liệu này chỉ phục vụ kiểm thử. |

#### 6.2. Các tệp kiểm thử

| Tệp | Nội dung có AI hỗ trợ |
| --- | --- |
| `notebooks/tests/test_config.py` | Kiểm tra bốn snapshot có thứ tự; kiểm tra từ chối cấu hình thiếu trường, trùng mốc, đường dẫn tuyệt đối và ngày không hợp lệ. |
| `notebooks/tests/test_download.py` | Giả lập lỗi kết nối rồi tải lại thành công, kiểm tra nội dung tải và tệp tạm `.part`; kiểm tra từ chối nguồn tải ngoài miền được cho phép. |
| `notebooks/tests/test_filter.py` | Đối chiếu lọc theo chunk với đọc toàn bảng; kiểm tra ID dài, số lượng sau lọc, kỳ vọng riêng từng snapshot, phân biệt lỗi và cảnh báo, phát hiện gzip bị cắt và tạo URL theo cấu hình. |
| `notebooks/tests/test_qa.py` | Kiểm tra chuẩn hóa giá và trạng thái lịch, cấu trúc báo cáo QA, giá ngoại lai, loại phòng không hợp lệ, review trống và trùng ID. Bổ sung kiểm tra theo Bài 10: tách điểm đánh giá thiếu với ngoài miền, tính IQR theo loại phòng và báo lỗi khi thiếu cột bắt buộc. |
| `notebooks/tests/test_kpi.py` | Xây dựng ví dụ nhỏ có kết quả tính tay để đối chiếu K1, K2, K4, K5; kiểm tra đơn vị, tiền tệ và cột cỡ mẫu của bảng KPI. |
| `notebooks/tests/test_llm.py` | Dùng mock để kiểm tra schema/ID/nhãn, retry HTTP 429 và dừng khi hết lượt thử, thông báo HTTP 400 có che khóa, khóa API bị lỗi khi sao chép, đọc khóa từ biến môi trường, cache và thay đổi phiên bản prompt. Kiểm tra thêm chế độ bỏ qua LLM, thiếu khóa và phản hồi không phải JSON. |
| `notebooks/tests/test_evaluate.py` | Đối chiếu Accuracy và macro-F1 với kết quả biết trước, kiểm tra khả năng lặp lại của bootstrap, xác thực nhãn gold và loại nhãn `AI_draft`; kiểm tra phủ định, cảm xúc hỗn hợp và trường hợp baseline không có từ điển ngôn ngữ. |
| `notebooks/tests/test_smoke.py` | Kết nối download/filter → QA → KPI → LLM mock → baseline → evaluate → KPI → viz trên dữ liệu tạm. Kiểm tra mẫu nhãn ban đầu còn trống, đầu ra đánh giá, đủ 11 hình và không sinh một số tệp CSV trùng dữ liệu. |

**Phân biệt dữ liệu kiểm thử với dữ liệu đánh giá thật.** Phản hồi Gemini giả lập, khóa giả và gold tổng hợp trong các test được tạo để kiểm tra hành vi chương trình; chúng không phải kết quả gọi API hoặc nhãn tay thực tế. Các fixture đặt gốc dữ liệu trong thư mục tạm pytest, không dùng các nhãn giả lập để bổ sung vào gold của dự án. Việc test dùng mock chạy thành công chỉ xác nhận những tình huống đã mô phỏng, không chứng minh API thật luôn hoạt động hay kết quả phân tích đúng trong mọi trường hợp.

#### 6.3. Các công cụ hỗ trợ kiểm tra và tái lập

| Tệp | Nội dung có AI hỗ trợ |
| --- | --- |
| `notebooks/tools/inspect_ids.py` | Đọc bảng phân công theo vị trí cột để xử lý tên cột trùng; lọc đúng lớp/nhóm, giữ ID dạng chuỗi, kiểm tra số lượng, tính duy nhất, quan hệ listing–review–khu vực và tập con nhãn tay/LLM; xuất danh sách ID và báo cáo khảo sát. Công cụ không tự gán nhãn tay. |
| `notebooks/tools/check_config_swap.py` | Rà soát chuỗi thành phố/ngày ghi cứng trong `src/`, rồi chạy các test cấu hình, KPI và smoke với mốc dữ liệu giả lập khác dữ liệu thật. Phép rà soát chỉ bao phủ mẫu chuỗi và các test được chọn. |
| `notebooks/tools/check_security.py` | Kiểm tra các loại tệp không nên được Git theo dõi, một số mẫu khóa trong mã/lịch sử Git và quy tắc ignore; kết quả JSON được in ra console, không tạo `security_check.json`. Phạm vi này không loại trừ mọi dạng bí mật. |
| `notebooks/tools/check_submission.py` | In checklist ra console từ kiểm tra lọc, dung lượng, nhãn tay, dự đoán LLM, chỉ số đánh giá, 11 hình, báo cáo Markdown và PDF tối đa 10 trang. Công cụ không tạo `submission_checklist.csv` và không tự commit, tag, push hoặc kiểm tra quyền riêng tư trên GitHub. |
| `notebooks/tools/clean_reproduce.py` | Chuẩn bị bản clone cục bộ cô lập, chép mã đang làm việc, tạo môi trường ảo riêng và dùng hardlink tới dữ liệu thô có sẵn; so sánh sáu bảng QA/KPI/tổng hợp giữa hai bản chạy. Phạm vi này không tương đương tải lại dữ liệu qua mạng hoặc tái lập từ commit cuối trên remote; bước LLM thật không được kiểm chứng bằng phép so sánh đó. |

Các bảng trên khai báo phần mã và cách kiểm tra có AI hỗ trợ, không xác nhận mọi công cụ đã được chạy thành công trong phiên cập nhật tài liệu này. Trạng thái chạy phải căn cứ vào log và các tệp bằng chứng tương ứng; việc có sẵn script không đồng nghĩa đã hoàn tất kiểm tra.

#### 6.4. Notebook bài giảng và tệp `lecture_10.py`

Bản khai báo trước của nhóm ghi nhận việc tham khảo tệp `lecture_10.py`, được xuất từ notebook `2627-1/notebooks/lecture-10.ipynb` của kho `uet-iai-course/programming-for-data-processing`, thuộc **Bài 10 · Làm sạch dữ liệu có cấu trúc** và dùng ví dụ Santiago. Tệp này không nằm trong danh sách tệp dự án tại lần cập nhật tài liệu này, nên thông tin nguồn ở đây được giữ theo khai báo trước, không phải kết quả kiểm tra lại tệp gốc. Nguồn bài giảng cần được phân biệt với phần mã dự án Toronto do nhóm triển khai có Codex hỗ trợ.

Nhóm nhờ AI hỗ trợ đối chiếu các nguyên tắc trong tài liệu với phần QA của dự án: giữ giá trị gốc khi chuyển kiểu, phân biệt giá trị thiếu và ngoài miền, xét ngoại lai theo nhóm loại phòng, kiểm tra cột bắt buộc và bổ sung test bằng dữ liệu lỗi đã biết. Các nội dung áp dụng được thể hiện trong `src/qa.py` và `notebooks/tests/test_qa.py`. Khai báo này ghi nhận hỗ trợ khi vận dụng bài giảng; không quy nguồn nội dung notebook gốc cho Codex.

### 7. Chi tiết nhiệm vụ AI hỗ trợ và phần nhóm phải kiểm tra

Phần này đi sâu vào đầu vào, thao tác, đầu ra và điều kiện chấp nhận của từng công đoạn. Các điều kiện kiểm tra mô tả cách thẩm định phần AI hỗ trợ; chúng không tự xác nhận rằng mọi phép kiểm tra đều đã được chạy trong lần sửa tài liệu này.

#### 7.1. Tổ chức chương trình và cấu hình

**Đầu vào công việc:** Yêu cầu phân tích một thành phố qua bốn snapshot, danh sách ID được giao, các bước xử lý cần có và bộ đầu ra phục vụ báo cáo.

**Phần AI hỗ trợ:**

1. Đề xuất tách mã theo trách nhiệm: tải/lọc dữ liệu, QA, KPI, LLM, baseline, đánh giá, trực quan hóa và báo cáo.
2. Hỗ trợ tổ chức `run_pipeline.py` thành điểm vào chung, gọi từng mô-đun theo thứ tự phụ thuộc thay vì phải chạy thủ công nhiều tệp không liên kết.
3. Đưa các tham số có thể thay đổi vào `configs/Toronto.yaml`: thành phố, snapshot, đường dẫn, cột khu vực, ngưỡng QA, bộ khía cạnh, model, batch, retry và bootstrap.
4. Hỗ trợ kiểm tra cấu hình ngay khi đọc để phát hiện thiếu trường hoặc giá trị không hợp lệ trước khi xử lý dữ liệu lớn.
5. Hỗ trợ các chế độ `--only`, `--skip-download`, `--skip-llm` và `--limit` để khoanh vùng lỗi và chạy thử một phần.

**Phần nhóm chịu trách nhiệm:** Xác nhận cấu hình đúng đề bài, phân biệt tham số do nhóm lựa chọn với đại lượng tính từ dữ liệu, và hiểu tác động khi thay đổi từng tham số. Ví dụ, `qa.price_max: 2000.0` là trần do cấu hình quy định, không phải giá lớn nhất quan sát được trong thị trường.

**Cách kiểm tra:** Đọc luồng `STEPS`, đối chiếu đầu vào/đầu ra giữa các mô-đun, thử cấu hình giả lập trong test và xem các thông báo lỗi cấu hình. Khả năng đổi cấu hình không đồng nghĩa có thể chuyển sang thành phố bất kỳ mà không kiểm tra lại schema và dữ liệu nguồn.

#### 7.2. Khảo sát bảng phân công, tải và lọc dữ liệu

**Đầu vào công việc:** Bảng phân công trong `data/samples/`, các ID listing/review, khung vùng A01–A08 và các tệp Inside Airbnb theo snapshot.

**Phần AI hỗ trợ:**

1. Đọc bảng phân công theo vị trí cột khi tên cột bị trùng, giữ đúng quan hệ giữa review, listing và vùng phân tích.
2. Chuẩn hóa ID thành chuỗi từ lúc đọc để tránh mất chữ số khi dữ liệu bị diễn giải thành số thực.
3. Tách danh sách listing, review, cờ mẫu LLM và cờ nhãn tay; kiểm tra tính duy nhất và quan hệ tập con.
4. Xây dựng URL từ cấu hình, tải dạng stream, ghi `.part`, kiểm tra nội dung rồi mới dùng tên chính thức.
5. Đọc tệp lớn theo chunk, lọc bằng tập ID và chỉ giữ các cột calendar cần thiết để giảm chi phí bộ nhớ.
6. Ghi nhận số dòng, tệp sử dụng, mã SHA256 và các chênh lệch so với số lượng kỳ vọng theo từng snapshot.
7. Phân biệt trường hợp sai mẫu phân công với trường hợp ID thật sự không xuất hiện ở một snapshot; xuất bằng chứng vào `reports/missing_ids.csv` và `reports/filter_checks.csv`.

**Phần nhóm chịu trách nhiệm:** Kiểm tra lớp, số nhóm, bộ ID được giao và quyết định phạm vi dữ liệu khi snapshot có thiếu. Việc giữ mốc cuối dù thiếu 72 listing là quyết định được ghi trong cấu hình, không phải kết quả do AI tự bổ sung hay thay đổi dữ liệu nguồn.

**Cách kiểm tra:** So sánh tập ID trước/sau lọc, đối chiếu số lượng theo snapshot, thử dữ liệu có ID dài và tệp gzip hỏng. Không dùng tổng số dòng qua bốn snapshot để diễn giải thành số listing hoặc số review duy nhất.

#### 7.3. QA: phân loại lỗi trước khi chọn dữ liệu phân tích

AI hỗ trợ triển khai theo hướng giữ bằng chứng về lỗi, sau đó chọn tập hợp lệ theo nhu cầu của từng phép tính. Một listing thiếu giá vẫn có thể có thông tin hợp lệ cho các chỉ số khác; loại toàn bộ listing chỉ vì thiếu một trường có thể làm thay đổi mẫu không cần thiết.

| Nhóm dữ liệu | Chi tiết AI hỗ trợ trong mã | Điều nhóm cần xác nhận |
| --- | --- | --- |
| Schema và khóa | Kiểm tra cột bắt buộc, ID thiếu, khóa trùng và quan hệ listing–review–calendar. | Khóa được dùng có đúng ý nghĩa ở từng bảng và từng snapshot hay không. |
| Giá | Bỏ ký hiệu tiền tệ/dấu phân cách; phân biệt thiếu, không chuyển kiểu được, không dương và ngoại lai. | Đơn vị CAD/đêm, trần cấu hình và điều kiện chọn giá trong QA/KPI/hình có thống nhất. |
| IQR theo loại phòng | Tính Q1, Q3 và IQR trên giá dương hợp lệ theo `room_type`; nhóm ít hơn bốn giá hợp lệ dùng ngưỡng toàn mốc. | Không trộn máy móc phân phối giá của các loại phòng khác nhau; ngưỡng có phù hợp mục tiêu bài. |
| Số đêm và trường số | Kiểm tra giá trị bất hợp lý, gắn cờ và tạo giá trị dùng cho các bước sau. | Không xem giá trị lỗi là 0 hoặc tự thay bằng trung bình khi chưa có quy tắc. |
| Điểm đánh giá | Phân biệt thiếu điểm với điểm nằm ngoài miền hợp lệ. | Listing chưa có review có thể thiếu điểm một cách hợp lý; thiếu không đồng nghĩa chất lượng kém. |
| Loại phòng và vùng | Chuẩn hóa cách viết, đối chiếu danh mục và phát hiện giá trị ngoài cấu hình. | Ánh xạ dùng trong phân tích phải đúng với bộ dữ liệu được phân công. |
| Review | Làm sạch nội dung, kiểm tra review trống, trùng ID, ngày và liên kết listing. | Làm sạch không được biến đổi ý nghĩa cảm xúc của câu gốc. |
| Calendar | Chuẩn hóa `t/f/true/false`, phân biệt thiếu và sai trạng thái, kiểm tra ngày và xung đột cùng listing/ngày. | Giá trị không hợp lệ không được chuyển thành ngày đã đặt. |
| So sánh snapshot | Hỗ trợ phát hiện review lặp, thay đổi nội dung hoặc quan hệ khóa giữa các mốc. | Bản ghi xuất hiện lại qua snapshot không mặc nhiên là lỗi trùng cần xóa khỏi toàn bộ dữ liệu. |

**Ví dụ về cách kiểm tra một quy tắc giá:** Với giá gốc `$1,250.00`, bước chuẩn hóa phải tạo được số `1250.0`; với chuỗi không phải giá, cần có cờ lỗi chuyển kiểu; với giá `0`, cần có cờ không hợp lệ. Chỉ giá dương hợp lệ mới được xét ngoại lai. Những giá trị ví dụ này minh họa quy tắc, không phải số liệu thống kê của Toronto.

**Ví dụ về trạng thái lịch:** Chuỗi `f` hợp lệ phải được hiểu là không khả dụng; chuỗi rỗng là thiếu; một giá trị ngoài danh mục là không hợp lệ. Nếu ép mọi chuỗi không rỗng sang boolean thì `f` có thể bị hiểu thành `True`; nếu ép giá trị lỗi thành `False` thì tỷ lệ không khả dụng có thể bị tăng sai. AI hỗ trợ sửa chính sự khác nhau giữa các trường hợp này.

**Đầu ra có thể đối chiếu:** Dữ liệu sạch theo snapshot trong `data/processed/`, bảng calendar sạch, `reports/qa_report.csv` và `reports/data_dictionary.csv`. Các cờ QA và phần giải thích quy tắc giúp truy lại lý do một giá trị được dùng hoặc loại khỏi phép tính.

#### 7.4. KPI: hỗ trợ hiện thực đầy đủ K1–K8

AI hỗ trợ chuyển công thức thành phép lọc, ghép và tổng hợp bằng pandas, đồng thời bổ sung đơn vị và cỡ mẫu vào bảng kết quả. Nhóm chịu trách nhiệm xác nhận câu hỏi phân tích mà mỗi chỉ số trả lời.

| KPI | Chi tiết công việc có AI hỗ trợ | Dữ liệu/điều kiện và giới hạn cần đọc cùng kết quả |
| --- | --- | --- |
| **K1 — Giá đêm trung vị** | Lấy snapshot cuối, nhóm theo `neighbourhood_cleansed`, chọn giá hợp lệ không ngoại lai rồi tính median và số giá tham gia. | Đơn vị CAD/đêm. Không đưa giá lỗi hoặc giá đã gắn cờ trở lại phép tính chỉ để tăng cỡ mẫu. |
| **K2 — Tỷ lệ ngày không khả dụng theo vùng/mốc** | Ghép vùng bằng `listing_id` và `snapshot`, chọn ngày lịch hợp lệ, tính `100 × (1 − mean(available))`. | Mẫu số là số dòng ngày lịch hợp lệ; không phải số listing. Không khả dụng có thể do chủ khóa lịch. |
| **K3 — Tỷ lệ ngày không khả dụng theo tháng lịch** | Tạo tháng từ `calendar.date`, tổng hợp trong từng snapshot và giữ mốc quan sát riêng. | Tháng của ngày lịch khác ngày chụp dữ liệu. Cùng tháng có thể được quan sát từ các snapshot khác nhau. |
| **K4 — Tỷ lệ yêu cầu thuê dài hạn** | Loại số đêm tối thiểu thiếu/bất hợp lý, tính tỷ lệ `minimum_nights >= 30` theo ngưỡng cấu hình. | Đo điều kiện tối thiểu do listing đặt ra; không đo số đêm khách thực tế đã ở. |
| **K5 — Tốc độ review trong mẫu** | Giữ một bản mới nhất mỗi review ID, chia theo quý của ngày review và chia cho số listing duy nhất trong mẫu. | Đơn vị `sample reviews/listing/quarter`; không ngoại suy trực tiếp thành tốc độ review toàn thành phố. |
| **K6 — Listing chưa có review** | Đếm `number_of_reviews == 0` trên tập listing sau QA theo mốc/vùng. | Không tự suy ra listing kém chất lượng hoặc không có khách; chỉ mô tả trạng thái review quan sát được. |
| **K7 — Cảm xúc và điểm khía cạnh** | Lọc dự đoán LLM hợp lệ, ghép review với listing/vùng; tính tỷ lệ `negative` và điểm `(praise − complaint)/(praise + complaint)`. | Điểm khía cạnh có miền [-1, 1]; khi không có lượt đề cập thì để thiếu. `n` của điểm này là số lượt khen/chê. |
| **K8 — Listing khả dụng cao, có nhiều review** | Tính khả dụng trung bình theo listing rồi kiểm tra đồng thời ngưỡng khả dụng 0,75 và ít nhất 10 review theo cấu hình. | Là chỉ số sàng lọc để xem xét thêm, không chứng minh chủ nhà hoạt động chuyên nghiệp hoặc vi phạm quy định. |

**Ví dụ kiểm chứng bằng tính tay:** Một nhóm có bốn ngày lịch hợp lệ với `available = [True, False, False, True]` thì K2 bằng `100 × (1 − 2/4) = 50%`. Nếu có thêm một ngày thiếu trạng thái, ngày đó không được tự thêm vào mẫu số như một ngày đã đặt. Đây là ví dụ tổng hợp dùng để giải thích phép tính, không phải dữ liệu kết quả của dự án.

**Điểm cần phân biệt về vùng:** Các KPI dùng `area_col` của cấu hình, hiện là `neighbourhood_cleansed`; K7 ghép theo `analysis_area` từ bảng phân công. AI hỗ trợ đường ghép của từng bảng, còn nhóm cần đọc đúng định nghĩa vùng trước khi đặt các kết quả cạnh nhau.

**Đầu ra có thể đối chiếu:** `data/processed/kpi_area.csv`, `kpi_time.csv`, `kpi_llm.csv` và `reports/kpi_definitions.csv`. Một KPI xuất hiện ở nhiều bảng là do có các góc nhìn theo thời gian/vùng, không phải nhiều bộ công thức khác nhau.

#### 7.5. Gemini: từ mẫu review đến đầu ra có kiểm tra

**Chuẩn bị mẫu:** AI hỗ trợ đọc review sạch từ bốn snapshot, giữ bản mới nhất theo ID, loại nội dung rỗng, ghép cờ mẫu và thông tin vùng. Khi có cờ mẫu của giảng viên, chương trình ưu tiên cờ đó. Nhánh dự phòng sử dụng seed và phân tầng theo vùng/ngôn ngữ; không được mô tả nhánh dự phòng như chiến lược đã dùng nếu lần chạy thực tế chọn mẫu theo cờ.

**Xây dựng yêu cầu phân loại:** AI hỗ trợ viết prompt quy định rõ ba lớp cảm xúc, bảy khía cạnh, phân biệt khen với chê và yêu cầu chỉ trích xuất điều được đề cập. Phần system instruction bổ sung yêu cầu xem review là dữ liệu, bỏ qua chỉ dẫn bên trong review, và trả mảng JSON đúng thứ tự ID.

**Viết API client:** AI hỗ trợ tạo payload, truyền khóa bằng header, đặt timeout, điều tiết tốc độ gọi, phân loại lỗi HTTP, xử lý thời gian chờ và thử lại trong số lượt cho phép. Mục tiêu là lưu được phần đã xử lý và báo rõ khi phần còn lại chưa hoàn thành.

**Kiểm tra phản hồi:** Chương trình kiểm tra mảng kết quả có đúng số review, từng đối tượng đúng tập trường, ID là chuỗi và khớp thứ tự, sentiment thuộc ba lớp, language có dạng hai chữ cái thường hoặc `und`, và danh sách khía cạnh đúng danh mục, không lặp. Kiểm tra này xác nhận hợp lệ cấu trúc; một kết quả đạt schema vẫn có thể phân loại sai nội dung.

**Lưu cache và kết quả:** AI hỗ trợ khóa cache có xét review, văn bản, model, phiên bản prompt và định danh prompt/schema. Mã hiện tại còn có nhánh tìm kết quả trong cache của model đã lưu trước đó khi các điều kiện khóa tương ứng khớp; vì vậy chỉ đọc `llm.model` hiện tại là chưa đủ để kết luận mọi dòng cache đã được gọi bằng model đó. Khi thẩm định nguồn dự đoán, cần đối chiếu metadata cache và lịch sử chạy.

**Phần nhóm chịu trách nhiệm:** Chấp nhận quy ước phân loại, kiểm tra review khó, quản lý API key, xem các dòng `parse_error`/`truncated`, và quyết định nhận xét nào có đủ bằng chứng. `temperature = 0` làm giảm tính ngẫu nhiên theo cấu hình, nhưng không bảo đảm nhãn đúng hoặc kết quả API bất biến giữa các lần gọi.

#### 7.6. Baseline: xây dựng phương pháp đối chứng có thể giải thích

AI hỗ trợ hiện thực một phương pháp từ điển để đánh giá giá trị bổ sung của Gemini. Baseline không dùng kết quả Gemini hoặc nhãn gold làm đầu vào dự đoán; nó đọc cùng mẫu review và áp dụng quy tắc đã cấu hình.

Các phần triển khai có hỗ trợ gồm nhận diện ngôn ngữ với seed, tách từ Unicode, đối chiếu từ tích cực/tiêu cực, đảo điểm khi có phủ định trong cửa sổ ba từ bên trái và xét từ nối tương phản. Khi có cả hai nhóm cảm xúc, quy tắc `mixed` còn xét sự xuất hiện của từ nối hoặc chênh lệch số từ cảm xúc theo ngưỡng.

Đối với khía cạnh, baseline tìm từ khóa của từng khía cạnh, xem các từ cảm xúc trong cửa sổ ngữ cảnh năm từ mỗi phía rồi thêm vào danh sách khen/chê. Đây là cách ghép bằng khoảng cách từ, nên có thể gán nhầm cảm xúc của một khía cạnh sang khía cạnh ở gần trong cùng câu.

Từ điển hiện có bốn ngôn ngữ `en`, `es`, `fr`, `pt`. Review quá ngắn hoặc không nhận diện được có thể mang mã `und`. Khi không có từ điển hoặc không có tín hiệu cảm xúc, baseline dùng nhãn dự phòng trong cấu hình, hiện là `positive`. Nhóm cần đọc độ phủ ngôn ngữ và cơ chế dự phòng khi giải thích điểm số cao trên một mẫu phần lớn tích cực.

**Cách kiểm tra:** Dùng ví dụ nhỏ có phủ định, câu chứa cả khen/chê, ngôn ngữ không có từ điển và review không chứa từ khóa. Ví dụ như `not clean` dùng để kiểm tra cơ chế phủ định; việc vượt qua ví dụ này không chứng minh baseline hiểu mọi cấu trúc phủ định trong ngôn ngữ tự nhiên.

#### 7.7. Đánh giá: giữ nguồn nhãn và mẫu so sánh nhất quán

AI hỗ trợ các công việc kỹ thuật sau:

1. Đọc nhãn tay từ tệp cấu hình hoặc template dự phòng, giữ `review_id` dạng chuỗi và kiểm tra số lượng tối thiểu.
2. Kiểm tra ID thiếu/trùng, nhãn cảm xúc ngoài danh mục và ID không nằm trong mẫu LLM.
3. Chuẩn hóa cột khía cạnh thành mảng JSON; phân biệt ô chưa có nhãn với mảng rỗng `[]` thể hiện không có khía cạnh.
4. Khi có cột `label_source`, chỉ giữ nguồn `user_manual` cho gold; các nhãn `AI_draft` chưa xác nhận bị loại.
5. Ghép từng phương pháp với cùng gold bằng quan hệ `one_to_one`, kiểm tra dự đoán trùng khóa và giữ các dự đoán thiếu trong mẫu đánh giá.
6. Tính Accuracy, macro-F1, precision/recall/F1 từng lớp, chỉ số nhiều nhãn cho khen/chê và độ chính xác ngôn ngữ khi có gold tương ứng.
7. Bootstrap với seed cố định, tạo khoảng tin cậy cho chỉ số cảm xúc và so sánh chênh lệch Accuracy theo cặp review.
8. Xuất ma trận nhầm lẫn, danh sách review lệch nhãn và gợi ý nhóm lỗi để nhóm đọc lại.

**Giới hạn kiểm tra nguồn nhãn:** Nếu tệp không có `label_source`, mã không thể xác minh bằng kỹ thuật ai thực sự đã gán nhãn. Ngay cả khi có `user_manual`, đây vẫn là thông tin khai báo trong bảng; trách nhiệm đọc review và xác nhận nhãn thuộc về nhóm. Đổi tên nguồn từ `AI_draft` thành `user_manual` mà không đọc và xác nhận nội dung không tạo ra gold đáng tin cậy.

**Giới hạn chỉ số khía cạnh:** Trong mã hiện tại, các chỉ số khía cạnh được tính theo từng tập nhãn khen/chê và từng khía cạnh; không tự có khoảng tin cậy bootstrap như các chỉ số cảm xúc. Vì vậy không nên mô tả mọi con số trên hình so sánh là đều có cùng loại khoảng tin cậy.

**Phần nhóm chịu trách nhiệm:** Đọc các ca bất đồng, xác nhận quy ước về lời khen tổng thể kèm lưu ý nhỏ, không sửa nhãn chỉ để khớp dự đoán, và không lựa chọn riêng những review thuận lợi cho một phương pháp. Phân tích nguyên nhân lỗi trong bản nháp AI chỉ trở thành nhận xét được chấp nhận sau khi đối chiếu văn bản review và nhãn thực tế.

#### 7.8. Trực quan hóa: hỗ trợ viết mã cho 11 hình

AI hỗ trợ chọn nguồn dữ liệu, chuẩn bị bảng vẽ, thiết lập trục/nhãn/chú giải, sắp thứ tự nhóm và xuất ảnh. Các hình là biểu đồ tạo bằng mã từ dữ liệu của dự án, không phải ảnh minh họa do mô hình sinh ảnh tạo ra.

| Tệp hình | Chi tiết công việc có AI hỗ trợ | Điểm cần nhóm kiểm tra khi đọc hình |
| --- | --- | --- |
| `fig_space_01_listings_map.pdf` | Vẽ vị trí listing và thể hiện thông tin giá theo dữ liệu hợp lệ, điều chỉnh nhãn vùng. | Tọa độ, đơn vị, tập listing và các nhãn có khớp bảng nguồn. |
| `fig_space_02_area_price.pdf` | Tổng hợp/biểu diễn giá theo vùng, thống nhất điều kiện giá với KPI. | Không trộn giá ngoại lai đã loại khỏi chỉ số vào nhận xét giá điển hình. |
| `fig_space_03_area_occupancy.pdf` | Biểu diễn tỷ lệ không khả dụng theo vùng. | Không diễn giải số ngày khóa lịch thành số đêm chắc chắn đã bán. |
| `fig_time_01_occupancy_by_snapshot.pdf` | So sánh tỷ lệ không khả dụng giữa các mốc. | Mỗi mốc là lần quan sát khác nhau; cỡ mẫu cuối kỳ có thể giảm. |
| `fig_time_02_kpi_trend.pdf` | Đặt các chỉ số theo thứ tự snapshot, giữ đúng thang đo. | Tỷ lệ, đơn vị tiền và đại lượng đếm phải được phân biệt. |
| `fig_time_03_reviews_per_quarter.pdf` | Vẽ review theo quý sau khử trùng ID. | Dữ liệu phản ánh mẫu review được giao, không phải toàn bộ review thành phố. |
| `fig_llm_01_sentiment_by_area.pdf` | Tổng hợp phân bố cảm xúc theo vùng từ dự đoán hợp lệ. | Tỷ lệ phải đọc cùng cỡ mẫu và nguồn nhãn dự đoán. |
| `fig_llm_02_aspects.pdf` | Đếm hoặc tổng hợp khía cạnh khen/chê từ danh sách nhiều nhãn. | Một review có thể nhắc nhiều khía cạnh; tổng lượt đề cập có thể lớn hơn số review. |
| `fig_llm_03_model_vs_baseline.pdf` | Đọc chỉ số đánh giá và thể hiện so sánh theo tác vụ. | Accuracy, macro-F1 và micro-F1 trả lời những câu hỏi khác nhau. |
| `fig_llm_04_confusion_llm.pdf` | Dựng ma trận nhầm lẫn Gemini với thứ tự lớp nhất quán. | Đúng chiều nhãn thật/dự đoán và chú ý số mẫu lớp hiếm. |
| `fig_llm_05_confusion_baseline.pdf` | Dựng ma trận nhầm lẫn baseline cùng quy ước. | So sánh trên cùng gold, không so hai tập review khác nhau. |

Nhóm cần kiểm tra ảnh sau khi render: chữ có bị cắt hoặc chồng, chú giải có rõ, giá trị có khớp bảng và hình có hỗ trợ đúng nhận xét hay không. Việc chương trình tạo đủ 11 tệp không tự xác nhận toàn bộ hình đã đạt chất lượng trình bày.

#### 7.9. Báo cáo, README và các tài liệu đi kèm

AI hỗ trợ tập hợp số liệu từ các bảng, tạo biến số dùng chung, chèn hình, dựng bố cục báo cáo và soạn bản nháp nhận xét. AI cũng hỗ trợ hướng dẫn cài môi trường, biến môi trường API, lệnh chạy pipeline, cách chạy từng bước và giải thích cấu trúc thư mục trong `README.md`.

Với `AI_USAGE.md`, AI hỗ trợ mở rộng mô tả theo mô-đun, làm rõ tỷ lệ 50%, phân biệt dữ liệu thật với dữ liệu kiểm thử, và trình bày giới hạn của các bằng chứng. Tài liệu này cũng thuộc phạm vi công việc có AI hỗ trợ soạn thảo.

Phần nhóm phải hoàn thiện là đọc lại câu chữ theo số liệu, bỏ nhận định chưa được kiểm chứng, xác nhận những việc thực tế đã làm và kiểm tra nguồn tham khảo. Nhận xét như “mô hình tốt hơn”, “khu vực cần ưu tiên” hoặc “thị trường thay đổi” phải gắn với đại lượng, mốc, cỡ mẫu và giới hạn suy luận cụ thể.

### 8. Công cụ, cấu hình và dữ liệu cung cấp cho AI

#### 8.1. Codex trong quá trình thực hiện bài

| Nội dung | Khai báo |
| --- | --- |
| Công cụ | Codex, dùng để hỗ trợ phát triển và rà soát dự án. |
| Tác vụ | Đọc mã/cấu hình, đề xuất phương án, viết/sửa mã, phân tích lỗi, hỗ trợ kiểm thử và viết tài liệu. |
| Ngữ cảnh công việc | Yêu cầu do nhóm cung cấp, các tệp dự án và đầu ra cần đối chiếu trong từng nhiệm vụ. |
| Phiên bản mô hình cho từng lần hỗ trợ | Chưa có nhật ký đầy đủ để xác định chính xác cho mọi lần tương tác; không tự gán một model/version cụ thể cho toàn bộ lịch sử. |
| Mức đóng góp | Nằm trong ước lượng chung 50%, có phần trực tiếp tạo mã và nội dung. |
| Giới hạn chứng cứ | Mã cuối phản ánh kết quả đã được chỉnh sửa; không tái dựng đầy đủ nội dung hội thoại hoặc nguồn gốc từng dòng. |

#### 8.2. Gemini trong pipeline

Các giá trị dưới đây được ghi theo `configs/Toronto.yaml` và mã `src/llm.py` tại thời điểm cập nhật tài liệu, không phải xác nhận về tình trạng dịch vụ hoặc bảng giá hiện hành của nhà cung cấp.

| Tham số | Giá trị trong dự án | Vai trò |
| --- | --- | --- |
| Provider | `gemini` | Dịch vụ phân loại review. |
| Model trong cấu hình | `gemini-3.5-flash-lite` | Tên model được dùng khi tạo yêu cầu gọi mới theo cấu hình hiện tại. |
| Phiên bản prompt | `v1` | Thành phần nhận diện yêu cầu và khóa cache. |
| Cỡ mẫu mục tiêu | `1000` review | Phạm vi phân tích LLM theo yêu cầu cấu hình. |
| Batch size | `50` | Số review mục tiêu trong một lô gọi. |
| Giới hạn tốc độ | `10` lượt/phút | Tham số điều tiết của client; không phải cam kết quota của tài khoản. |
| Retry | `6` lượt theo cấu hình | Giới hạn thử trong vòng xử lý lỗi của client. |
| Backoff | `2` | Cơ sở tăng thời gian chờ giữa các lần thử. |
| Timeout | `180` giây | Thời gian chờ yêu cầu theo cấu hình. |
| Giới hạn văn bản | `1500` ký tự/review | Nội dung dài hơn bị cắt khi tạo payload và được đánh dấu `truncated`. |
| Temperature | `0` trong mã | Cấu hình quá trình sinh kết quả. |
| Đầu ra | JSON với response schema | Phục vụ kiểm tra và xử lý tự động. |
| Biến môi trường khóa | `GEMINI_API_KEY` | Không yêu cầu ghi khóa trong mã hoặc YAML. |
| Cache | `data/processed/llm_cache.jsonl` | Lưu kết quả có metadata để giảm gọi lại. |
| Seed của dự án | `42` | Dùng cho các bước lấy mẫu/đánh giá có hỗ trợ seed, không phải cam kết kiểm soát hoàn toàn API Gemini. |
| Bootstrap | `1000` lần, mức tin cậy `0.95` | Tham số đánh giá trong `evaluation`. |

Tên model hiện tại có thể khác model của kết quả đã lưu trước đó. Không dùng riêng bảng cấu hình này để chứng nhận lịch sử gọi API; khi cần xác định nguồn từng dự đoán phải đọc cache và metadata liên quan.

#### 8.3. Dạng dữ liệu gửi vào và nhận về

Đối với bước Gemini, payload nghiệp vụ chứa ID review và phần văn bản đã làm sạch/cắt theo giới hạn, kèm prompt và schema. Mã gọi API không cần gửi toàn bộ bảng listing, calendar hoặc bảng gold để thực hiện phân loại.

Ví dụ dưới đây là **dữ liệu tự tạo để minh họa định dạng**, không phải review thật, phản hồi API thật hoặc nhãn gold:

```json
[
  {
    "review_id": "demo_review_001",
    "comments": "The apartment was clean, but the street was noisy at night."
  }
]
```

Một đầu ra có cấu trúc phù hợp có thể là:

```json
[
  {
    "review_id": "demo_review_001",
    "sentiment": "mixed",
    "aspects_praise": ["cleanliness"],
    "aspects_complaint": ["noise"],
    "language": "en"
  }
]
```

Khi ghi vào bảng kết quả, chương trình bổ sung các trường theo dõi như `parse_error`, `truncated`, `model` và `prompt_version`. Các trường này giúp phân biệt kết quả phân loại với trạng thái xử lý kỹ thuật.

#### 8.4. Chi phí và mức sử dụng

AI hỗ trợ viết phần ước lượng token và chi phí trong `estimate_cost()`. Khi có usage từ API, chương trình dùng thông tin đó; khi không có và đang dùng kết quả cache, chương trình có nhánh ước lượng dựa trên độ dài ký tự. Hai nguồn này cần được khai báo khác nhau.

Theo xác nhận của nhóm, dự án dùng **Gemini API free tier** nên chi phí API thực tế cho mẫu 1.000 review là **0 USD**. Tệp `reports/llm_cost_estimate.csv` lưu riêng `billing_tier`, `actual_spend_usd` và kịch bản paid-tier. Giá trị 88,09 USD trong cột `estimated_usd` chỉ là ước lượng giả định nếu mở rộng lên 729.202 review bằng Standard paid tier; đây không phải hóa đơn hay số tiền tài khoản đã thanh toán. Các giá tham chiếu và ngày tham chiếu được lưu trong cấu hình; cần kiểm tra lại trước một lần chạy có tính phí mới.

Tỷ lệ AI hỗ trợ 50% cũng không được suy ra từ tiền API hoặc số token: đây là các đại lượng đo những khía cạnh khác nhau của công việc.

## Prompt then chốt (5-10): bước nào, vào tệp nào

Nhóm lưu lại 10 prompt then chốt dưới dạng gần nguyên ý. Bảng này chỉ rõ bước xử lý và tệp chịu tác động; phần sau giải thích đầu ra mong đợi và cách nhóm thẩm định trước khi chấp nhận.

| Prompt | Bước sử dụng | Tệp chính chịu tác động |
| ---: | --- | --- |
| 1 | Tổ chức pipeline và cấu hình | `run_pipeline.py`, `configs/Toronto.yaml`, `src/download.py` |
| 2 | Khảo sát ID và lọc dữ liệu lớn | `src/download.py`, `notebooks/tools/inspect_ids.py`, `notebooks/tests/test_filter.py` |
| 3 | Chuẩn hóa giá và quy tắc QA | `src/qa.py`, `notebooks/tests/test_qa.py` |
| 4 | Chuẩn hóa trạng thái calendar | `src/qa.py`, `src/kpi.py`, `notebooks/tests/test_qa.py` |
| 5 | Ghép khóa và khử lặp giữa snapshot | `src/kpi.py`, `notebooks/tests/test_kpi.py` |
| 6 | Prompt và JSON schema Gemini | `configs/Toronto.yaml`, `src/llm.py`, `notebooks/tests/test_llm.py` |
| 7 | Retry, cache và bảo vệ khóa API | `src/llm.py`, `notebooks/tests/test_llm.py` |
| 8 | Baseline đối chứng đa ngôn ngữ | `src/baseline.py`, `configs/Toronto.yaml`, `notebooks/tests/test_evaluate.py` |
| 9 | Đánh giá và phân tích lỗi | `src/evaluate.py`, `reports/eval_metrics.csv`, `reports/error_analysis.csv` |
| 10 | Biểu đồ và hồ sơ bàn giao | `src/viz.py`, `README.md`, `AI_USAGE.md` |

### Prompt 1 — Hỗ trợ xây dựng luồng chạy

> Tổ chức dự án thành các bước tải/lọc, QA, KPI, LLM, baseline, đánh giá, vẽ hình và báo cáo. Cho phép chạy toàn bộ bằng một lệnh hoặc chọn từng bước. Đưa các tham số thành phố, snapshot và đường dẫn vào cấu hình.

**Kết quả mong đợi từ AI:** Khung mô-đun và mã điều phối có quan hệ đầu vào/đầu ra rõ ràng; báo lỗi khi thiếu dữ liệu cần thiết.

**Cách nhóm thẩm định:** Đọc thứ tự chạy thực tế, kiểm tra trường hợp KPI chưa có LLM và lý do phải tính KPI lần thứ hai; thử luồng tích hợp bằng dữ liệu tạm. Không chỉ kiểm tra chương trình kết thúc với mã thoát thành công.

### Prompt 2 — Hỗ trợ lọc dữ liệu lớn và giữ ID

> Viết phần lọc CSV nén theo danh sách ID được phân công, đọc theo chunk để giảm bộ nhớ. Giữ ID dạng chuỗi và kiểm tra kết quả tương đương với cách lọc toàn bảng trên một mẫu nhỏ.

**Kết quả mong đợi từ AI:** Hàm lọc, thống kê số dòng và kiểm thử chứa ID dài.

**Cách nhóm thẩm định:** Đối chiếu tập khóa và số dòng, không chỉ so kích thước tệp. Nếu ID bị làm tròn, việc đủ số dòng vẫn không bảo đảm đã lấy đúng review.

### Prompt 3 — Hỗ trợ chuẩn hóa giá và gắn cờ QA

> Tách giá thiếu, giá sai định dạng, giá không dương và giá ngoại lai. Tính IQR theo loại phòng, kết hợp trần cấu hình, giữ giá gốc và không xóa cả listing chỉ vì một trường giá lỗi.

**Kết quả mong đợi từ AI:** Hàm chuyển kiểu, các cờ độc lập và trường hợp kiểm tra ở ranh giới quy tắc.

**Cách nhóm thẩm định:** Dùng giá trị biết trước, kiểm tra quy tắc không biến thiếu thành 0, rồi đối chiếu tập giá tạo median trong QA, KPI và biểu đồ.

### Prompt 4 — Hỗ trợ sửa lỗi trạng thái calendar

> Sửa bước xử lý `available` để chấp nhận chuỗi `t/f/true/false` và boolean sau chuẩn hóa. Tách rõ thiếu, sai trạng thái và không khả dụng; không ép giá trị lỗi thành ngày đã đặt.

**Kết quả mong đợi từ AI:** Phần chuẩn hóa và kiểm thử bảo đảm chuỗi `f` không bị hiểu thành `True`.

**Cách nhóm thẩm định:** Đọc các cờ QA, kiểm tra mẫu số của K2/K3 và tính tay tỷ lệ trên một bảng nhỏ có cả ngày hợp lệ lẫn thiếu trạng thái.

### Prompt 5 — Hỗ trợ tránh đếm lặp giữa snapshot

> Rà soát các phép ghép listing–calendar và tổng hợp review qua nhiều mốc. Calendar phải ghép theo cả listing và snapshot; review theo quý phải khử lặp ID trước khi đếm.

**Kết quả mong đợi từ AI:** Khóa ghép đầy đủ, ràng buộc quan hệ ghép và quy tắc giữ một bản review phù hợp.

**Cách nhóm thẩm định:** Theo dõi số dòng trước/sau ghép, kiểm tra ID trùng ở phía bảng tra cứu và dùng trường hợp cùng review xuất hiện trong hai snapshot.

### Prompt 6 — Hỗ trợ prompt và JSON schema cho Gemini

> Thiết kế đầu ra review gồm sentiment, khía cạnh khen/chê và ngôn ngữ. Chỉ nhận ba nhãn cảm xúc và bảy khía cạnh trong cấu hình, trả JSON đúng ID, không suy diễn nội dung không được nhắc tới.

**Kết quả mong đợi từ AI:** Prompt, response schema và hàm kiểm tra độc lập với bước parse JSON.

**Cách nhóm thẩm định:** Thử phản hồi thiếu review, thừa trường, sai ID, đảo thứ tự, khía cạnh lạ và danh sách khía cạnh bị lặp. Sau khi cấu trúc hợp lệ, vẫn cần đánh giá chất lượng nhãn trên gold.

### Prompt 7 — Hỗ trợ lỗi API, retry và cache

> Bổ sung xử lý HTTP 429, timeout và lỗi phản hồi; chờ theo `Retry-After` khi phù hợp. Lưu kết quả từng lô để lần chạy sau tiếp tục; thay prompt/schema phải tránh dùng nhầm cache không tương thích. Không để khóa API xuất hiện trong URL hoặc thông báo lỗi.

**Kết quả mong đợi từ AI:** API client có giới hạn thử, thông báo chẩn đoán và cơ chế giữ kết quả đã nhận.

**Cách nhóm thẩm định:** Mock các phản hồi lỗi, kiểm tra số lượt gọi và thời gian chờ dự kiến, kiểm tra cache và thông báo lỗi. Test với mock xác nhận logic xử lý, không xác nhận quota thật của dịch vụ.

### Prompt 8 — Hỗ trợ xây dựng baseline

> Viết đối chứng từ điển đa ngôn ngữ có phủ định, cảm xúc hỗn hợp và khía cạnh theo cửa sổ ngữ cảnh. Chạy trên cùng mẫu với Gemini, ghi nhận ngôn ngữ chưa có từ điển và nhãn dự phòng.

**Kết quả mong đợi từ AI:** Thuật toán dự đoán có thể giải thích và đầu ra cùng khóa review để so sánh.

**Cách nhóm thẩm định:** Kiểm tra các câu đơn giản, câu có phủ định và nhánh không có từ điển; đọc giới hạn của cửa sổ từ thay vì mặc định coi baseline là hiểu ngữ nghĩa.

### Prompt 9 — Hỗ trợ đánh giá và phân tích lỗi

> So sánh Gemini và baseline trên cùng bộ nhãn tay. Giữ dự đoán thiếu/lỗi trong đánh giá, cố định ba lớp khi tính macro-F1, bootstrap có seed và so chênh lệch Accuracy theo cặp review. Xuất các review bất đồng để đọc lại.

**Kết quả mong đợi từ AI:** Mã tính chỉ số, khoảng tin cậy, ma trận nhầm lẫn và bảng lỗi.

**Cách nhóm thẩm định:** Đối chiếu với ví dụ có kết quả biết trước, kiểm tra số review đánh giá bằng số gold hợp lệ, rồi xem từng ca bất đồng. Bản nháp giải thích nguyên nhân không được dùng thay cho việc đọc review.

### Prompt 10 — Hỗ trợ trình bày và hoàn thiện hồ sơ bài làm

> Dùng số liệu từ các bảng kết quả để dựng 11 hình và báo cáo. Làm rõ đơn vị, snapshot, cỡ mẫu, giới hạn suy luận và hướng dẫn tái lập. Viết khai báo AI chi tiết theo phần việc thực tế.

**Kết quả mong đợi từ AI:** Mã vẽ, cơ chế lấy số liệu, bản nháp báo cáo, README và khai báo sử dụng AI.

**Cách nhóm thẩm định:** Đối chiếu số trong báo cáo với bảng nguồn, xem bản render, kiểm tra chú giải/nhãn trục và chỉnh nội dung theo những gì nhóm có thể giải thích bằng bằng chứng.

## AI sai ở đâu (ví dụ thật)

Các ví dụ dưới đây là lỗi thực tế trong bản mã hoặc nội dung do AI hỗ trợ trước khi nhóm kiểm tra và sửa. Nhóm không chấp nhận đầu ra AI chỉ vì mã chạy được; mỗi lỗi được đối chiếu lại bằng test, số dòng, bảng nguồn hoặc bản render.

| Tình huống AI/bản triển khai ban đầu làm chưa đúng | Hậu quả có thể xảy ra | Cách nhóm sửa | Bằng chứng kiểm chứng |
| --- | --- | --- | --- |
| Giá trung vị trong QA và K1 từng không khớp vì AI dùng hai điều kiện lọc khác nhau. | Báo cáo và KPI có thể công bố hai mức giá cho cùng một mẫu. | Thống nhất điều kiện giá hợp lệ, dương và không bị cờ ngoại lai trong `src/qa.py`, `src/download.py`, `src/kpi.py`. | Test QA/KPI và đối chiếu cùng snapshot, vùng, tập ID. |
| AI từng xử lý chuỗi `f` như một giá trị truthy hoặc ép trạng thái lỗi thành không khả dụng. | K2/K3 bị tăng hoặc sai mẫu số. | Chuẩn hóa riêng `t/f/true/false`, giữ cờ thiếu và sai trạng thái trước khi tính. | `notebooks/tests/test_qa.py` và ví dụ tính tay calendar. |
| Phép ghép ban đầu chỉ chú ý `listing_id`, chưa buộc cả `snapshot`. | Calendar có thể bị nhân dòng khi một listing xuất hiện ở bốn mốc. | Ghép bằng `listing_id + snapshot` và dùng `validate="many_to_one"`. | Theo dõi số dòng trước/sau ghép và test KPI. |
| Cách tổng hợp review ban đầu có nguy cơ cộng lại cùng review ở nhiều snapshot. | K5 phóng đại số review theo quý. | Sắp xếp theo snapshot và khử lặp `review_id` trước tổng hợp. | Kiểm tra số ID duy nhất và test tính tay K5. |
| Khóa cache ban đầu chưa bao gồm đầy đủ văn bản, prompt và schema. | Có thể tái dùng nhãn cũ sau khi thay yêu cầu phân loại. | Đưa ID, văn bản, model, phiên bản và định danh prompt/schema vào khóa SHA256. | Test thay prompt version và kiểm tra cache miss/hit. |
| AI từng mô tả công cụ kiểm tra như thể chúng sinh PDF, `security_check.json` và checklist CSV. | `AI_USAGE.md`/README hứa đầu ra không tồn tại. | Sửa tài liệu theo đúng hành vi: kiểm số trong Markdown, in JSON/checklist ra console. | Đối chiếu trực tiếp mã trong `notebooks/tools/` và danh sách `reports/`. |
| Pytest từng dùng thư mục tạm gây xung đột thu thập hoặc lỗi quyền. | Test có thể lỗi dù logic dự án đúng. | Giới hạn `testpaths`, loại thư mục sao chép và chuyển `basetemp` sang `.pytest_tmp`. | Chạy đủ 35 test từ lệnh trong README. |
| Nhãn bản đồ do AI bố trí từng chồng lên điểm và khó đọc. | Hình tồn tại nhưng không dùng được trong báo cáo. | Điều chỉnh vị trí nhãn và nền hiển thị. | Xem trực tiếp ảnh PNG ở kích thước đưa vào báo cáo. |

AI có vai trò đề xuất và hiện thực cách sửa; việc lựa chọn quy tắc nào phù hợp bài làm vẫn thuộc nhóm. Ví dụ, có thể sửa chương trình để không báo lỗi bằng cách bỏ kiểm tra số lượng, nhưng làm như vậy không giải thích được các ID thiếu. Phương án cần giữ bằng chứng về chênh lệch và ghi rõ quyết định sử dụng dữ liệu.

## Nhóm kiểm chứng thế nào

### Kết quả đánh giá dùng để thẩm định phần phân tích AI

#### Tách ba loại dữ liệu nhãn

| Loại | Nguồn và vai trò | Cách sử dụng trong đánh giá |
| --- | --- | --- |
| Dự đoán Gemini | Nhãn do mô hình trả về cho mẫu LLM, có thông tin lỗi và cấu hình liên quan. | Là đầu ra cần đánh giá, không dùng làm đáp án chuẩn cho chính Gemini. |
| Nhãn tay được nhóm xác nhận | Bộ nhãn đánh giá do người gán/xác nhận theo khai báo của nhóm. | Là gold khi đáp ứng kiểm tra và quy trình xác nhận. |
| Gợi ý AI và dữ liệu mock | Gợi ý `AI_draft`, fixture tổng hợp hoặc phản hồi API giả lập. | Dùng hỗ trợ gán nhãn/kiểm thử; không tự đưa vào gold thật. |

Bản khai báo trước ghi nhận Codex hỗ trợ chuẩn hóa khía cạnh sang JSON và tạo gợi ý cho 50 review bổ sung. Việc này được khai báo riêng với bộ 100 review dùng đánh giá. Không được hiểu mọi dòng bổ sung đều đã được người đọc và xác nhận, hoặc tự cộng chúng vào cỡ mẫu gold.

#### Các số liệu đang có trong bảng đánh giá

Bảng dưới được đối chiếu với `reports/eval_metrics.csv` tại lần sửa tài liệu này; giá trị được làm tròn bốn chữ số thập phân. Đây là số liệu đã lưu của dự án, không phải kết quả từ một lượt gọi API mới trong lần sửa `AI_USAGE.md`.

| Tác vụ/chỉ số | Gemini | Baseline | Số review đánh giá |
| --- | ---: | ---: | ---: |
| Cảm xúc — Accuracy | 0.9100 | 0.9900 | 100 |
| Cảm xúc — macro-F1 | 0.7112 | 0.9679 | 100 |
| Khía cạnh được khen — micro-F1 | 0.8503 | 0.6934 | 100 |
| Khía cạnh bị chê — micro-F1 | 0.3636 | 0.5333 | 100 |

Chênh lệch Accuracy theo cặp `Gemini − baseline` là **−0.0800**, với khoảng tin cậy bootstrap 95% đang lưu là **[−0.1400; −0.0300]**. Đây là chênh lệch **−8 điểm phần trăm** trên bộ gold này, không phải nhận định Gemini luôn kém baseline 8% ở mọi dữ liệu.

Phân bố nhãn được ghi nhận trong bộ đánh giá là **93 `positive`, 6 `mixed`, 1 `negative`**. Mẫu mất cân bằng như vậy khiến chỉ số tổng thể phụ thuộc mạnh vào lớp tích cực, còn kết quả ở lớp tiêu cực dựa trên rất ít quan sát. Khoảng tin cậy bootstrap cũng phụ thuộc bộ gold và cách lấy mẫu đã chọn, không bao quát mọi nguồn sai lệch như quy ước gán nhãn hoặc sự khác nhau giữa các thành phố.

#### Ý nghĩa đối với việc sử dụng AI

Các kết quả cho thấy việc dùng mô hình sinh không tự bảo đảm tốt hơn một đối chứng đơn giản trên mọi tác vụ. Trong bộ gold hiện tại, baseline có điểm cảm xúc và khía cạnh chê cao hơn; Gemini có micro-F1 khía cạnh khen cao hơn. Vì vậy, bản nháp báo cáo do AI hỗ trợ cần diễn giải theo từng tác vụ và cỡ mẫu cụ thể.

`reports/error_analysis.csv` cung cấp các review cần đọc lại; `reports/error_summary.md` ghi nhận nhóm bất đồng `mixed_confusion`. Khi review có lời khen tổng thể kèm một lưu ý nhỏ, kết quả có thể nhạy với quy ước về ranh giới `positive`/`mixed`. Nhóm phải xác nhận quy ước và đọc nội dung từng ca trước khi kết luận nguyên nhân lỗi.

Vai trò của Codex ở đây là hỗ trợ viết phép tính, sắp xếp bằng chứng và soạn nhận xét ban đầu. Quyết định chấp nhận nhãn, đánh giá giới hạn mẫu và kết luận cuối thuộc nhóm. Không dùng nhận xét AI tự sinh để chứng minh tính đúng đắn của một nhãn AI khác.

### Phần nhóm trực tiếp thực hiện và trách nhiệm học thuật

#### Các trách nhiệm gắn với phần việc của nhóm

Phần 50% do nhóm trực tiếp thực hiện được hiểu theo khung tự đánh giá ở đầu tài liệu. Những nhiệm vụ sau là phần việc và trách nhiệm mà nhóm phải đảm nhận khi sử dụng hỗ trợ AI:

1. **Xác định phạm vi bài:** Chọn đúng lớp/nhóm, xác nhận dữ liệu được phân công, mục tiêu phân tích và đối tượng sử dụng báo cáo.
2. **Xác nhận cấu hình:** Hiểu và chấp nhận các mốc dữ liệu, đồng tiền, ngưỡng QA, ngưỡng KPI, bộ nhãn và cách chọn mẫu.
3. **Quản lý dữ liệu:** Giữ dữ liệu nguồn, kiểm tra ID, đọc báo cáo thiếu, phân biệt dữ liệu sạch với dữ liệu bị gắn cờ và dữ liệu kiểm thử.
4. **Gán và xác nhận gold:** Đọc review, chọn nhãn theo quy ước, kiểm tra gợi ý trước khi xác nhận và không lấy dự đoán mô hình làm nhãn tay một cách tự động.
5. **Đọc hiểu mã:** Có khả năng giải thích công thức, khóa ghép, mẫu số, quy tắc loại dữ liệu và các nhánh lỗi trong phần AI hỗ trợ.
6. **Kiểm tra kết quả:** Đối chiếu bảng, biểu đồ, báo cáo và các ca lỗi; xem các lệnh kiểm tra đã chạy có đủ bằng chứng hay chưa.
7. **Biên tập phân tích:** Giữ nhận xét có cơ sở, trình bày giới hạn mẫu và không biến tương quan quan sát được thành quan hệ nhân quả.
8. **Hoàn thiện bản nộp:** Kiểm tra tài liệu, nguồn tham khảo, trạng thái tệp và các yêu cầu bàn giao thực tế của môn học.

Danh sách này mô tả phân công trách nhiệm; một kiểm tra cụ thể chỉ được xem là đã hoàn thành khi có kết quả hoặc bằng chứng tương ứng. Việc ghi tên nhiệm vụ vào tài liệu không thay thế quá trình thực hiện.

#### Ranh giới giữa hỗ trợ định dạng và gán nhãn

Đổi danh sách khía cạnh người gán đã chọn sang JSON là thao tác chuẩn hóa định dạng, miễn là nội dung nhãn được giữ nguyên. Đọc một review rồi đề xuất cảm xúc hoặc khía cạnh mới là thao tác tạo nhãn gợi ý. Hai việc này có mức can thiệp khác nhau và phải được khai báo rõ.

Khi có nhãn gợi ý, người gán cần đọc lại review thay vì chỉ chấp nhận vì câu trả lời có vẻ hợp lý. Việc xác nhận phải dựa vào quy ước nhãn của nhóm, nhất là với cảm xúc hỗn hợp, lời chê nhẹ và khía cạnh không được nêu trực tiếp. Nhóm không dùng số lượng dòng `user_manual` như bằng chứng duy nhất rằng mọi nhãn đều được gán độc lập với AI.

#### Nguồn dữ liệu, số liệu và tham khảo

Dữ liệu phân tích xuất phát từ Inside Airbnb và bộ phân công của bài. AI hỗ trợ xử lý và diễn giải, không được coi là nguồn dữ liệu gốc. Mọi con số về giá, tỷ lệ, review, điểm mô hình hoặc số ID thiếu phải có bảng đầu ra hay phép tính tương ứng để truy lại.

Tài liệu bài giảng, thư viện và nhà cung cấp API là các nguồn riêng với phần mã nhóm phát triển. AI có thể hỗ trợ áp dụng nguyên tắc từ tài liệu, nhưng không làm thay đổi nguồn gốc của nội dung tham khảo. Các phát biểu về giá API, phiên bản model hoặc khả năng dịch vụ cần có mốc tham chiếu phù hợp; cấu hình lưu trong repo không tự chứng minh thông tin đó còn hiệu lực ở mọi lần chạy sau.

### Kiểm tra, tái lập và các giới hạn của bằng chứng

#### Các lệnh kiểm tra đã được tài liệu hóa

Các lệnh dưới đây dùng để người đọc tái kiểm tra theo từng mục đích. Chúng không phải tuyên bố đã chạy lại toàn bộ trong lần cập nhật khai báo này. Trên Windows, có thể dùng trực tiếp Python trong `.venv` để chọn đúng môi trường:

```powershell
# Kiểm thử đơn vị và tích hợp bằng dữ liệu fixture/API mock
.\.venv\Scripts\python.exe -m pytest -c notebooks/pytest.ini -q --junitxml=reports/test_results.xml

# Kiểm tra khả năng thay cấu hình theo phạm vi công cụ hỗ trợ
.\.venv\Scripts\python.exe notebooks/tools/check_config_swap.py

# Kiểm tra các mẫu tệp/khóa nhạy cảm mà công cụ hỗ trợ
.\.venv\Scripts\python.exe notebooks/tools/check_security.py

# Tổng hợp bằng chứng phục vụ kiểm tra bản nộp
.\.venv\Scripts\python.exe notebooks/tools/check_submission.py
```

Để kiểm tra luồng chạy từ dữ liệu thô có sẵn và ưu tiên dùng cache, có thể chạy:

```powershell
.\.venv\Scripts\python.exe run_pipeline.py --config configs/Toronto.yaml --skip-download --skip-llm
```

`--skip-download` vẫn yêu cầu dữ liệu thô hợp lệ; `--skip-llm` không tạo dự đoán mới cho review thiếu cache. Lệnh pipeline có thể ghi lại các bảng và hình đầu ra, nên kết quả cần được đọc theo cấu hình, cache và dữ liệu có trong lần chạy đó.

#### Bằng chứng nào xác nhận được điều gì

| Bằng chứng | Điều có thể kiểm tra | Giới hạn |
| --- | --- | --- |
| Mã nguồn và cấu hình | Thuật toán, công thức, tham số và nhánh xử lý đang được cài đặt. | Không tái dựng đầy đủ ai đã viết từng dòng hoặc mọi lần chạy trước. |
| Manifest và báo cáo lọc | Tệp đầu vào, mã nhận diện và số lượng được ghi nhận theo mốc. | Cần đối chiếu đúng lần chạy và dữ liệu đang sử dụng. |
| Báo cáo QA và từ điển dữ liệu | Quy tắc, cờ lỗi và cấu trúc đầu ra. | Không tự chứng minh mọi ngoại lai đều là lỗi dữ liệu. |
| Cache và bảng LLM | Dự đoán đã lưu, trạng thái xử lý và một phần metadata nguồn. | Không chứng minh nhãn đúng; cần xem nguồn model khi có tái sử dụng cache. |
| Bộ gold và bảng đánh giá | Nhãn được dùng, cỡ mẫu và chỉ số tính từ nhãn đó. | Không tự chứng minh người gán độc lập với AI hoặc mẫu đại diện thị trường. |
| Kết quả pytest | Hành vi ở các trường hợp có test và môi trường đã chạy. | Không bao phủ mọi dữ liệu thật, lỗi mạng hoặc thay đổi API. |
| Báo cáo đối chiếu số | Tính nhất quán giữa các bảng số và tài liệu theo phạm vi script. | Không thay thế đọc nhận xét và kiểm tra hình thức trình bày. |
| Tài liệu AI_USAGE | Phạm vi hỗ trợ được nhóm khai báo và cách tự ước tính đóng góp. | Không phải bản ghi tự động đo chính xác 50% công việc. |

#### Những rủi ro cụ thể cần tiếp tục kiểm soát

- **Mã đúng cú pháp nhưng sai ý nghĩa:** Có thể dùng sai khóa ghép, mẫu số hoặc vùng phân tích; cần kiểm tra bằng dữ liệu nhỏ và định nghĩa KPI.
- **Chỉ số thiếu bối cảnh:** Accuracy cao trên mẫu 93% tích cực không đủ kết luận chất lượng tốt ở lớp tiêu cực.
- **Review bị cắt:** Nhãn có thể bỏ lỡ phàn nàn hoặc lời khen nằm cuối review vượt 1.500 ký tự; cần đọc cờ `truncated`.
- **Baseline có nhãn dự phòng:** `positive` ở trường hợp thiếu từ điển/tín hiệu có thể hưởng lợi trên mẫu lệch lớp; cần xem độ phủ và lỗi.
- **Nhận xét được viết trôi chảy:** Bản nháp AI có thể đưa ra lý do chưa được chứng minh; cần truy lại review, bảng hoặc hình hỗ trợ.
- **Dữ liệu thiếu ở snapshot:** Mẫu cuối kỳ giảm có thể ảnh hưởng so sánh; không tự quy mọi thay đổi thành biến động thực của thị trường.
- **Cache và cấu hình khác thời điểm:** Có thể dùng kết quả đã lưu mà không gọi API mới; cần khai báo đúng khi so sánh model hoặc prompt.
- **Dữ liệu gửi tới dịch vụ:** Review được gửi cho Gemini là dữ liệu thực của bài; cần tránh thêm thông tin nhạy cảm không phục vụ phân loại. Cơ chế hiện có không được mô tả như một hệ thống ẩn danh hóa đầy đủ.

Trong phạm vi mã hiện tại, khóa Gemini được đọc từ biến môi trường và truyền bằng header. Các test/công cụ hỗ trợ kiểm tra một số mẫu lộ khóa, nhưng không chứng minh toàn bộ lịch sử và mọi tệp ngoài phạm vi đã được kiểm tra đều không chứa thông tin nhạy cảm.

### Xác nhận phạm vi khai báo

Nhóm khai báo **AI hỗ trợ thực hiện khoảng 50% tổng khối lượng bài tập lớn**, gồm hỗ trợ thiết kế kỹ thuật, tạo và sửa mã, tích hợp Gemini, xây dựng baseline, kiểm thử, đối chiếu số liệu, trực quan hóa và soạn thảo tài liệu. Phần còn lại do nhóm trực tiếp thực hiện theo khung tự đánh giá; nhóm chịu trách nhiệm đầy đủ về dữ liệu, nhãn đánh giá, công thức, kết quả, nhận xét và bản nộp.

Tỷ lệ này là ước lượng tổng thể, không phải tỷ lệ cố định trong từng tệp, số giờ đo được hoặc tỷ lệ dữ liệu AI sinh. Tài liệu mô tả cả phần AI tham gia trực tiếp và các bước nhóm cần kiểm chứng, đồng thời phân biệt kết quả đã lưu, ví dụ minh họa, gợi ý chưa xác nhận và dữ liệu kiểm thử. Các công cụ kiểm tra chỉ được coi là đã hoàn thành khi có bằng chứng chạy tương ứng.
