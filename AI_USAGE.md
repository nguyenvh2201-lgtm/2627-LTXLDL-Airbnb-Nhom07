# Khai báo sử dụng AI

Trong bài tập lớn này, nhóm sử dụng Codex để hỗ trợ lập trình, phân tích lỗi và rà soát một số phần xử lý dữ liệu. Nhóm ước tính mức độ hỗ trợ của AI khoảng **40% tổng khối lượng công việc**. Đây là mức tự ước tính, chưa được đo bằng thời gian làm việc hay số dòng mã. Phạm vi hỗ trợ có cả gợi ý phương án, viết các đoạn xử lý và sửa mã sau khi chạy kiểm tra.

Dưới đây là những vấn đề kỹ thuật chính nhóm đã nhờ AI hỗ trợ, chia theo 6 phần của dự án, bao gồm phần kiểm thử và công cụ trong `notebooks/`. Các ví dụ tập trung vào những chỗ cần xử lý nhiều điều kiện hoặc liên kết nhiều bước. Gemini là mô hình phân tích review của bài; Codex là công cụ hỗ trợ quá trình thực hiện.

## 1. QA — Kiểm tra và làm sạch dữ liệu

**Đồng bộ quy tắc giá giữa dữ liệu QA và dữ liệu dùng tính KPI.** Nhóm nhờ AI rà soát phần xử lý giá trong `src/qa.py`, nhất là sự khác nhau giữa giá thiếu, giá không hợp lệ và giá ngoại lai. AI hỗ trợ chỉnh đoạn tạo cờ để giá dương hợp lệ mới được xét ngoại lai theo IQR, đồng thời kết hợp các giới hạn trong cấu hình. Phần này cần giữ riêng giá trị đã chuyển kiểu và các cờ kiểm tra để các bước sau biết bản ghi bị loại khỏi phép tính vì lý do gì, thay vì xóa toàn bộ dòng.

Một lỗi thực tế là số giá trung vị trong báo cáo QA chưa khớp với KPI vì hai bước chọn tập giá khác nhau. Nhóm nhờ AI đối chiếu `report_table()` trong `src/qa.py`, phần đọc dữ liệu trong `src/download.py` và phần tính K1 trong `src/kpi.py`. Điều kiện đã được thống nhất về giá hợp lệ và không có cờ ngoại lai. Cách kiểm tra là đối chiếu cùng một mốc, cùng tập listing và cùng điều kiện lọc giữa các đầu ra.

**Xử lý trạng thái lịch phòng trước khi đưa vào phép tính.** Cột `available` có thể được đọc dưới dạng chuỗi `t/f`, trong khi công thức KPI cần giá trị boolean hoặc số. Nhóm từng gặp lỗi chuyển chuỗi `f` sang số nên nhờ AI sửa bước chuyển kiểu và bổ sung kiểm thử cho chuỗi/boolean. Điểm cần chú ý là trạng thái thiếu hoặc không hợp lệ không được tự hiểu thành phòng đã được đặt; các dòng này cần được phân biệt trước khi tính tỷ lệ.

**Giảm dung lượng đầu ra calendar mà vẫn giữ dữ liệu phục vụ phân tích.** Bản triển khai trước tạo các tệp `calendar_flagged.csv` lớn và có thông tin trùng với dữ liệu đã lưu. Nhóm nhờ AI hỗ trợ chuyển sang bảng tóm tắt theo listing và dữ liệu sạch dạng Parquet nén, đồng thời điều chỉnh nơi đọc các đầu ra này. Đây là thay đổi liên quan đến cả QA và các bước phía sau nên cần kiểm tra lại luồng đọc dữ liệu, không chỉ kiểm tra việc ghi tệp thành công.

## 2. KPI — Tính các chỉ số phân tích

**Ghép calendar với listings mà không làm tăng số dòng ngoài ý muốn.** Nhóm nhờ AI hỗ trợ phần ghép khu vực vào từng dòng lịch trong `compute()` của `src/kpi.py`. Khóa ghép gồm `listing_id` và `snapshot`, vì cùng một listing xuất hiện ở nhiều mốc dữ liệu. Đoạn ghép sử dụng kiểm tra quan hệ `many_to_one` để phát hiện trường hợp phía listings có khóa trùng, có thể làm nhân số ngày lịch và sai kết quả tổng hợp.

Sau khi ghép, phép tính chỉ nhận các ngày có trạng thái lịch, ngày và khu vực hợp lệ. Với K2/K3, mã tính `(1 - mean(available)) * 100` trên các dòng hợp lệ theo khu vực hoặc tháng. Nhóm nhờ AI hỗ trợ kết nối điều kiện này với dữ liệu sau QA. Khi diễn giải, đây là tỷ lệ ngày không khả dụng trong lịch, cần thận trọng nếu dùng để nhận định về công suất thực tế.

**Tránh đếm lặp review khi tổng hợp nhiều snapshot.** Một review có thể xuất hiện trong nhiều lần chụp dữ liệu. Nhóm nhờ AI hỗ trợ đoạn sắp xếp theo snapshot, giữ một bản ghi cho mỗi review ID rồi mới tổng hợp theo quý ở K5. Nếu cộng thẳng số review của từng snapshot thì cùng một review có thể được tính nhiều lần. Phần triển khai còn cần giữ rõ mẫu số là số listing duy nhất trong mẫu được phân công, để kết quả không bị hiểu thành thống kê cho toàn bộ thị trường.

**Kết nối KPI phụ thuộc LLM với thứ tự chạy pipeline.** Nhóm nhờ AI hỗ trợ tách việc tính các chỉ số từ dữ liệu bảng và việc bổ sung K7 từ kết quả LLM. Pipeline tính KPI sau QA để có các bảng cơ bản, rồi cập nhật lại sau bước LLM/evaluate trước khi vẽ hình. Phần AI hỗ trợ là luồng đọc kết quả, kiểm tra dữ liệu hợp lệ và xử lý khi chưa có dự đoán; khi thiếu dữ liệu, chương trình không tự điền một tỷ lệ để làm đầy bảng.

## 3. LLM + Baseline + Evaluate — Phân tích và đánh giá review

**Ràng buộc đầu ra Gemini để kết quả có thể dùng trực tiếp trong pipeline.** Nhóm nhờ AI hỗ trợ chỉnh prompt, xây dựng JSON schema và viết phần kiểm tra trong `validate_results()` của `src/llm.py`. Việc kiểm tra không dừng ở chỗ JSON đọc được mà còn xét đúng số review, đúng tập trường, đúng ID và thứ tự phản hồi, nhãn cảm xúc thuộc `positive/mixed/negative`, khía cạnh thuộc danh mục cấu hình và không bị lặp. Mục đích là tránh đưa một phản hồi có cấu trúc đọc được nhưng sai nội dung định dạng vào bảng kết quả.

**Xử lý giới hạn API và chạy tiếp từ kết quả đã lưu.** Nhóm nhờ AI hỗ trợ cơ chế giới hạn tốc độ, thử lại khi gặp lỗi có thể phục hồi và xử lý thời gian chờ `Retry-After`. Kết quả đã nhận được lưu vào cache để khi chạy lại không phải gọi lại toàn bộ review. AI còn hỗ trợ phần khóa cache dựa trên ID, văn bản, model, phiên bản prompt và nội dung prompt/schema. Nếu chỉ dùng ID, chương trình có thể lấy lại dự đoán cũ ngay cả khi nhóm đã thay đổi yêu cầu phân loại.

**Xử lý phủ định và cảm xúc hỗn hợp trong baseline.** Trong `predict()` của `src/baseline.py`, nhóm nhờ AI hỗ trợ triển khai cửa sổ từ phủ định đứng trước từ cảm xúc, thay vì chỉ cộng số từ tích cực và tiêu cực. AI cũng hỗ trợ điều kiện gán `mixed` khi review có cả hai nhóm cảm xúc, cùng cách tìm từ cảm xúc gần từ khóa khía cạnh trong một cửa sổ ngữ cảnh. Các quy tắc này là phương án đối chứng dựa trên từ điển và vẫn có hạn chế với câu dài, mỉa mai hoặc phủ định phức tạp.

**So sánh hai phương pháp trên cùng tập nhãn tay.** Nhóm nhờ AI hỗ trợ ghép dự đoán với gold theo `review_id`, kiểm tra khóa trùng và giữ nguyên tập review đánh giá trong `src/evaluate.py`. Dự đoán thiếu hoặc lỗi được đánh dấu `missing_or_error`, không âm thầm bỏ khỏi mẫu để làm tăng điểm. Với nhãn khía cạnh, AI hỗ trợ chuyển danh sách khía cạnh thành các cột nhị phân theo cùng danh mục rồi tính precision/recall/F1 cho bài toán nhiều nhãn.

**Ước lượng độ bất định của điểm đánh giá.** Ngoài Accuracy và macro-F1, nhóm nhờ AI hỗ trợ triển khai bootstrap: lấy mẫu review có hoàn lại nhiều lần, tính lại chỉ số rồi lấy các phân vị để tạo khoảng tin cậy. Danh sách ba lớp cảm xúc được giữ cố định vì một lần lấy mẫu có thể không có lớp hiếm. Phần so sánh chênh lệch Accuracy sử dụng kết quả đúng/sai của hai mô hình trên cùng review để giữ tính ghép cặp, thay vì lấy mẫu độc lập cho từng mô hình.

Về dữ liệu nhãn, Codex có hỗ trợ chuẩn hóa các khía cạnh do người dùng điền sang JSON và tạo nhãn gợi ý cho 50 review bổ sung. Các nhãn gợi ý được đánh dấu `AI_draft`; chỉ các dòng được xác nhận là nhãn người gán mới được dùng làm gold. Theo nhật ký triển khai, dự án đã có 1.000 dự đoán Gemini hợp lệ và bộ 100 review do người dùng gán nhãn để đánh giá. Phần chuẩn hóa định dạng và phần tạo nhãn gợi ý được khai báo riêng để không nhầm với việc gán nhãn tay.

## 4. Viz — Biểu đồ và báo cáo

**Giữ thống nhất tập dữ liệu giữa biểu đồ, KPI và phần nhận xét.** Nhóm nhờ AI hỗ trợ đoạn chọn dữ liệu hợp lệ trước khi vẽ trong `src/viz.py`, đặc biệt ở bản đồ giá và biểu đồ giá theo khu vực. Giá trung vị và cách chia nhóm giá phải dùng cùng điều kiện lọc với KPI. Nếu biểu đồ lấy cả giá đã bị QA gắn cờ còn bảng KPI loại các giá đó, hai phần có thể đưa ra thông tin khác nhau dù cùng nói về một mốc dữ liệu.

**Đưa kết quả đánh giá nhiều loại tác vụ lên biểu đồ.** Nhóm nhờ AI hỗ trợ phần đọc các dòng chỉ số của LLM/baseline và ghép cận dưới, cận trên của khoảng tin cậy để thể hiện sai số. Cần phân biệt macro-F1 của cảm xúc với micro-F1 của khía cạnh, vì chúng đánh giá các tác vụ khác nhau. Ma trận nhầm lẫn cũng cần giữ thứ tự lớp nhất quán với phần evaluate để tên lớp trên hình khớp với các ô số liệu.

**Tạo báo cáo từ số liệu đầu ra và kiểm tra tính nhất quán.** Nhóm nhờ AI hỗ trợ tập hợp các con số dùng chung, đưa số liệu và hình vào Markdown/PDF, đồng thời viết công cụ đối chiếu số trong báo cáo với bảng kết quả. AI cũng có tham gia dựng bố cục và viết bản nháp nhận xét. Khi xem bản render, phần nhãn bản đồ bị gần nhau đã được chỉnh lại vị trí và thêm nền để đọc được rõ hơn.

Đối với nội dung phân tích, đề xuất của AI cần được xem lại cùng số liệu nguồn. Một điểm cần chú ý là tập nhãn tay có ít review tiêu cực/hỗn hợp, nên điểm số và khoảng tin cậy không đủ để kết luận mô hình nào tốt hơn trong mọi tình huống. Nhóm chịu trách nhiệm về các nhận định được giữ trong báo cáo cuối.

## 5. Download + Run pipeline — Tải dữ liệu và chạy toàn bộ quy trình

**Ngăn tệp tải dở được dùng làm dữ liệu đầu vào.** Trong `download_file()` và `verify_file()` của `src/download.py`, nhóm nhờ AI hỗ trợ tải dạng stream vào tệp tạm `.part`, kiểm tra xong mới đổi sang tên tệp chính thức. Bước xác thực kiểm tra cột khóa, đọc hết tệp gzip để phát hiện lỗi CRC và tính SHA256 để ghi nhận tệp được sử dụng. SHA256 ở đây giúp nhận diện/đối chiếu tệp giữa các lần chạy; không tự chứng minh tệp giống nguồn nếu chưa có mã chuẩn từ nguồn để so sánh.

**Lọc dữ liệu lớn theo chunk và bảo toàn khóa ID.** Nhóm nhờ AI hỗ trợ `filtered_chunks()` để chỉ giữ các dòng thuộc danh sách được phân công trong từng khối đọc. Các cột ID được đọc dưới dạng chuỗi nhằm tránh sai lệch khi ID dài bị chuyển sang số thực. Khi ghép bảng phân công vào dữ liệu đã lọc, mã có kiểm tra quan hệ khóa để phát hiện trùng lặp thay vì để phép ghép tự nhân bản ghi.

**Phân biệt thiếu dữ liệu thật với lỗi tải hoặc lỗi lọc.** Nhóm nhờ AI hỗ trợ kiểm tra từng snapshot và xuất danh sách ID không tìm thấy. Ở mốc cuối, nhật ký ghi nhận thiếu 72 listing so với danh sách ban đầu; phần xử lý giữ nguyên mốc dữ liệu đã chọn và báo thiếu, không bổ sung dòng giả. Với `--skip-download`, tệp có sẵn vẫn được xác thực; nếu tệp thiếu/hỏng thì báo lỗi thay vì coi bước tải đã hoàn tất.

**Chạy lại các bước mà vẫn giữ đúng quan hệ phụ thuộc.** Trong `run_pipeline.py`, nhóm nhờ AI hỗ trợ kết nối thứ tự download → QA → KPI → LLM → baseline → evaluate → KPI → viz, cùng các tùy chọn chạy từng phần hoặc bỏ qua gọi API. AI cũng hỗ trợ kiểm thử tích hợp để kiểm tra các bước có đọc được đầu ra của nhau và đi đến bước tạo báo cáo. Một lỗi từng gặp là pytest thu thập cả bản kiểm thử trong thư mục sao chép tạm, gây xung đột import; cấu hình phạm vi thu thập đã được điều chỉnh để tránh lặp lại.

## 6. Notebooks — Kiểm thử, công cụ kiểm tra và tham khảo bài giảng

**Phạm vi khai báo.** Thư mục `notebooks/` hiện chứa các tệp Python kiểm thử, công cụ hỗ trợ và cấu hình pytest; không có tệp Jupyter `.ipynb` trong bản mã hiện tại. Nhóm sử dụng Codex để hỗ trợ xây dựng, chỉnh sửa và rà soát các phần này cùng mã trong `src/`. Bảng dưới mô tả phạm vi hỗ trợ theo từng tệp, không có nghĩa toàn bộ nội dung của mỗi tệp đều do AI tạo ra.

### 6.1. Cấu hình và dữ liệu kiểm thử

| Tệp | Nội dung có AI hỗ trợ |
| --- | --- |
| `notebooks/pytest.ini` | Thiết lập phạm vi thu thập test, loại trừ môi trường ảo và thư mục sao chép `.work`, tắt cache pytest và đặt thư mục tạm để tránh thu thập trùng test. |
| `notebooks/tests/conftest.py` | Tạo fixture cấu hình và dữ liệu tổng hợp trong thư mục tạm: bốn snapshot khác mốc thật, hai listing được chọn, ba review và calendar ba ngày. Bổ sung ID review dài để kiểm tra việc giữ nguyên khóa; nối các fixture qua bước filter và QA. |
| `notebooks/tests/fixtures/README.md` | Soạn mô tả nguồn dữ liệu giả lập, phạm vi sử dụng gold tổng hợp và phản hồi API mock; nêu rõ dữ liệu này chỉ phục vụ kiểm thử. |

### 6.2. Các tệp kiểm thử

| Tệp | Nội dung có AI hỗ trợ |
| --- | --- |
| `notebooks/tests/test_config.py` | Kiểm tra bốn snapshot có thứ tự; kiểm tra từ chối cấu hình thiếu trường, trùng mốc, đường dẫn tuyệt đối và ngày không hợp lệ. |
| `notebooks/tests/test_download.py` | Giả lập lỗi kết nối rồi tải lại thành công, kiểm tra nội dung tải và tệp tạm `.part`; kiểm tra từ chối nguồn tải ngoài miền được cho phép. |
| `notebooks/tests/test_filter.py` | Đối chiếu lọc theo chunk với đọc toàn bảng; kiểm tra ID dài, số lượng sau lọc, kỳ vọng riêng từng snapshot, phân biệt lỗi và cảnh báo, phát hiện gzip bị cắt và tạo URL theo cấu hình. |
| `notebooks/tests/test_qa.py` | Kiểm tra chuẩn hóa giá và trạng thái lịch, cấu trúc báo cáo QA, giá ngoại lai, loại phòng không hợp lệ, review trống và trùng ID. Bổ sung kiểm tra theo Bài 10: tách điểm đánh giá thiếu với ngoài miền, tính IQR theo loại phòng và báo lỗi khi thiếu cột bắt buộc. |
| `notebooks/tests/test_kpi.py` | Xây dựng ví dụ nhỏ có kết quả tính tay để đối chiếu K1, K2, K4, K5; kiểm tra đơn vị, tiền tệ và cột cỡ mẫu của bảng KPI. |
| `notebooks/tests/test_llm.py` | Dùng mock để kiểm tra schema/ID/nhãn, retry HTTP 429 và dừng khi hết lượt thử, thông báo HTTP 400 có che khóa, khóa API bị lỗi khi sao chép, đọc khóa từ biến môi trường, cache và thay đổi phiên bản prompt. Kiểm tra thêm chế độ bỏ qua LLM, thiếu khóa và phản hồi không phải JSON. |
| `notebooks/tests/test_evaluate.py` | Đối chiếu Accuracy và macro-F1 với kết quả biết trước, kiểm tra khả năng lặp lại của bootstrap, xác thực nhãn gold và loại nhãn `AI_draft`; kiểm tra phủ định, cảm xúc hỗn hợp và trường hợp baseline không có từ điển ngôn ngữ. |
| `notebooks/tests/test_smoke.py` | Kết nối download/filter → QA → KPI → LLM mock → baseline → evaluate → KPI → viz → report trên dữ liệu tạm. Kiểm tra mẫu nhãn ban đầu còn trống, đầu ra đánh giá, đủ 11 hình, đối chiếu số trong PDF và không sinh một số tệp CSV trùng dữ liệu. |

**Phân biệt dữ liệu kiểm thử với dữ liệu đánh giá thật.** Phản hồi Gemini giả lập, khóa giả và gold tổng hợp trong các test được tạo để kiểm tra hành vi chương trình; chúng không phải kết quả gọi API hoặc nhãn tay thực tế. Các fixture đặt gốc dữ liệu trong thư mục tạm pytest, không dùng các nhãn giả lập để bổ sung vào gold của dự án. Việc test dùng mock chạy thành công chỉ xác nhận những tình huống đã mô phỏng, không chứng minh API thật luôn hoạt động hay kết quả phân tích đúng trong mọi trường hợp.

### 6.3. Các công cụ hỗ trợ kiểm tra và tái lập

| Tệp | Nội dung có AI hỗ trợ |
| --- | --- |
| `notebooks/tools/inspect_ids.py` | Đọc bảng phân công theo vị trí cột để xử lý tên cột trùng; lọc đúng lớp/nhóm, giữ ID dạng chuỗi, kiểm tra số lượng, tính duy nhất, quan hệ listing–review–khu vực và tập con nhãn tay/LLM; xuất danh sách ID và báo cáo khảo sát. Công cụ không tự gán nhãn tay. |
| `notebooks/tools/check_config_swap.py` | Rà soát chuỗi thành phố/ngày ghi cứng trong `src/`, rồi chạy các test cấu hình, KPI và smoke với mốc dữ liệu giả lập khác dữ liệu thật. Phép rà soát chỉ bao phủ mẫu chuỗi và các test được chọn. |
| `notebooks/tools/check_report_numbers.py` | Đối chiếu giá trị trong `report_numbers.json` với `summary_numbers.csv`, kiểm tra chuỗi số đã định dạng có xuất hiện trong PDF và giới hạn số trang theo cấu hình. Công cụ không thay thế việc đọc nhận xét hoặc kiểm tra bố cục báo cáo. |
| `notebooks/tools/check_security.py` | Kiểm tra các loại tệp không nên được Git theo dõi, một số mẫu khóa trong mã và lịch sử Git, cùng quy tắc ignore; xuất `security_check.json`. Kết quả chỉ phản ánh các mẫu được hỗ trợ, không phải bằng chứng loại trừ mọi dạng bí mật. |
| `notebooks/tools/check_submission.py` | Tổng hợp bằng chứng từ kết quả pytest, kiểm tra lọc, dung lượng, nhãn tay, dự đoán LLM, chỉ số đánh giá, hình, PDF và các báo cáo kiểm tra để xuất checklist. Những phần chưa xác nhận như tag/push, quyền riêng tư repo hoặc mời giảng viên được ghi chưa đạt; công cụ không tự thực hiện các việc này. |
| `notebooks/tools/clean_reproduce.py` | Chuẩn bị bản clone cục bộ cô lập, chép mã đang làm việc, tạo môi trường ảo riêng và dùng hardlink tới dữ liệu thô có sẵn; so sánh sáu bảng QA/KPI/tổng hợp giữa hai bản chạy. Phạm vi này không tương đương tải lại dữ liệu qua mạng hoặc tái lập từ commit cuối trên remote; bước LLM thật không được kiểm chứng bằng phép so sánh đó. |

Các bảng trên khai báo phần mã và cách kiểm tra có AI hỗ trợ, không xác nhận mọi công cụ đã được chạy thành công trong phiên cập nhật tài liệu này. Trạng thái chạy phải căn cứ vào log và các tệp bằng chứng tương ứng; việc có sẵn script không đồng nghĩa đã hoàn tất kiểm tra.

### 6.4. Notebook bài giảng và tệp `lecture_10.py`

Tệp `lecture_10.py` có phần đầu ghi rõ được xuất tự động từ Colab, nguồn là notebook `2627-1/notebooks/lecture-10.ipynb` thuộc kho `uet-iai-course/programming-for-data-processing` (đường dẫn nguồn được giữ trong tệp). Đây là tài liệu bài giảng **Bài 10 · Làm sạch dữ liệu có cấu trúc**, dùng ví dụ Santiago; nguồn bài giảng cần được phân biệt với phần mã dự án Toronto do nhóm triển khai có Codex hỗ trợ.

Nhóm nhờ AI hỗ trợ đối chiếu các nguyên tắc trong tài liệu với phần QA của dự án: giữ giá trị gốc khi chuyển kiểu, phân biệt giá trị thiếu và ngoài miền, xét ngoại lai theo nhóm loại phòng, kiểm tra cột bắt buộc và bổ sung test bằng dữ liệu lỗi đã biết. Các nội dung áp dụng được thể hiện trong `src/qa.py` và `notebooks/tests/test_qa.py`. Khai báo này ghi nhận hỗ trợ khi vận dụng bài giảng; không quy nguồn nội dung notebook gốc cho Codex.

Nhóm chịu trách nhiệm kiểm tra mã, cấu hình, nhãn đánh giá và kết quả nộp cuối cùng. Mức khoảng 40% là ước lượng chung về sự hỗ trợ của AI trong toàn bài, bao gồm các phần thuộc `notebooks/`; các nội dung trên mô tả cụ thể phạm vi hỗ trợ, không quy đổi thành tỷ lệ đóng góp riêng cho từng tệp.


## Biên tập báo cáo chuyên nghiệp - 20/11/2026

- Công cụ: Codex. Yêu cầu: viết báo cáo chuyên nghiệp dựa trên reports/report.md và các nguyên tắc Bài 12-14.
- Sản phẩm: reports/report_professional.md; output/pdf/toronto_airbnb_report.pdf; bảy hình riêng trong reports/professional_assets/. Hai script trong notebooks/tools/prepare_professional_report.py và render_professional_report.py giúp dựng lại các hình và PDF. Bản report.md đầu vào được giữ nguyên.
- AI đối chiếu K1 từ dữ liệu listing, tính lại accuracy/macro-F1 từ dự đoán và gold, kiểm tra độ phủ giá 114+31+783=928; chạy bộ test hiện có đạt 34 passed. Không tải lại raw, không gọi API trong lần biên tập này.
- Những diễn giải đã chỉnh: tách tổng listing Waterfront (193) khỏi số có giá hợp lệ (161); không khẳng định nguyên nhân thiếu ID là ngừng niêm yết; không suy lịch không khả dụng thành booking. Bổ sung giới hạn gold thuộc 87 listing, độc lập holdout chưa được xác nhận và ngoại lệ mốc chụp trong cấu hình.
- Lỗi AI thực gặp: mã boxplot ban đầu dùng tham số labels không được phiên bản Matplotlib tại môi trường này chấp nhận. Đã bỏ tham số đó, đặt nhãn bằng set_yticks và dùng orientation; sau đó dựng hình thành công.
- Kiểm tra tài liệu bằng công cụ: render PDF thành PNG, rà bố cục và nhãn; xác nhận số trang trong giới hạn 10. Việc duyệt nội dung cuối cùng, xác nhận ngoại lệ với giảng viên, thông tin thành viên và commit/tag nộp vẫn thuộc nhóm.
