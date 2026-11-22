# Báo cáo Phân tích Thị trường Airbnb Toronto (Nhóm 07)

> **Ý chính:** Trong phạm vi mẫu được phân công tại mốc 2026-09-16, **Waterfront Communities-The Island có 161 chỗ ở có giá hợp lệ, gấp 5.0 lần Niagara** (n = 32), cho thấy đây là khu vực tập trung nguồn cung nổi bật nhất cần được theo dõi trong mẫu; kết quả không đại diện cho toàn bộ Toronto.

**Người đọc & mục tiêu quyết định:** Báo cáo hướng tới **Cơ quan quản lý du lịch thành phố Toronto (đã xác nhận bởi nhóm)** nhằm xác định khu vực tập trung nguồn cung cho thuê ngắn hạn, chênh lệch mặt bằng giá, nhịp độ lịch phòng và các điểm mạnh/hạn chế nổi bật trong trải nghiệm lưu trú của khách.

**Giới hạn cần lưu ý ngay từ đầu:** Dữ liệu lấy từ Inside Airbnb (CC BY 4.0, không thu thập trực tiếp từ airbnb.com) trên mẫu được giảng viên phân công qua 4 mốc chụp (2025-09-11, 2026-03-19, 2026-06-15, 2026-09-16), không đại diện toàn bộ thị trường thành phố. Ở mốc cuối không còn quan sát thấy **72** chỗ ở và **235** đánh giá có mặt ở các mốc trước (chi tiết tại `missing_ids.csv`); dữ liệu không đủ để kết luận nguyên nhân các ID vắng mặt.

## 1. Quy mô mẫu dữ liệu qua 4 mốc chụp

| Mốc chụp (Snapshot) | Listing sau QA | Calendar sau QA | Review sau QA |
| --- | ---: | ---: | ---: |
| 2025-09-11 | 1,000 | 365,000 | 5,000 |
| 2026-03-19 | 1,000 | 365,000 | 5,000 |
| 2026-06-15 | 1,000 | 365,000 | 5,000 |
| 2026-09-16 | 928 | 338,720 | 4,765 |

Ba mốc đầu giữ nguyên đủ **1,000** chỗ ở và **5,000** đánh giá; mốc cuối (2026-09-16) còn **928** chỗ ở. Toàn bộ đường dẫn tải và mã băm SHA256 của 12 tệp nguồn được lưu tại `download_manifest.csv`.

## 2. Giá trung vị giữa 12 khu vực lớn nhất chênh 2.6 lần

- **Chênh lệch giá theo khu vực (K1):** Trong 12 khu vực có cỡ mẫu giá hợp lệ lớn nhất tại mốc 2026-09-16, **Niagara** có giá trung vị cao nhất (**336.12 CAD/đêm**, n = 32), gấp **2.6 lần** Dovercourt-Wallace Emerson-Junction (128.61 CAD/đêm, n = 24). Ba khu vực có số lượng chỗ ở có giá hợp lệ lớn nhất là **Waterfront Communities-The Island** (n = 161), **Niagara** (n = 32) và **Annex** (n = 30, trung vị 321.66 CAD/đêm); đây là số lượng trong mẫu, không phải mật độ theo diện tích.
- **Chênh lệch theo cơ cấu loại phòng:** Tại mốc cuối, giá trung vị của chỗ ở nguyên căn đạt **232.88 CAD/đêm**, cao gấp **2.6 lần** phòng riêng (**90.5 CAD/đêm**). Do cơ cấu loại phòng khác nhau giữa các khu vực, chênh lệch giá trung vị chịu tác động đồng thời của vị trí và tỷ trọng nguyên căn, không nên diễn giải thành hiệu ứng nhân quả của riêng vị trí.
- **Giới hạn về cỡ mẫu và đơn vị không gian:** Các KPI K1, K2, K4, K6 và K8 nhóm theo `neighbourhood_cleansed`; có **118** khu vực có giá hợp lệ sau khi loại giá ngoại lai ở mốc cuối, trong đó **76** khu vực có n < 5, nên biểu đồ chỉ xếp hạng 12 khu vực có cỡ mẫu lớn nhất. Bản đồ và K7 dùng 8 vùng `analysis_area` A01–A08.

**Hình:** [Giá đêm trung vị (K1) tại 12 khu vực có cỡ mẫu lớn nhất, mốc 2026-09-16 — mở bản PDF vector](../figures/fig_space_02_area_price.pdf)

**Hình:** [Phân bố không gian theo trung vị giá (201.07 CAD/đêm) và 8 vùng phân tích A01–A08 — mở bản PDF vector](../figures/fig_space_01_listings_map.pdf)

## 3. Tỷ lệ không khả dụng ổn định nhưng cao nhất sát mốc chụp

- **Xu hướng khả dụng (K2, K3):** Tỷ lệ ngày không khả dụng toàn mẫu nằm trong khoảng **41.18%–43.62%** qua 4 mốc chụp. Trong cửa sổ lịch 365 ngày, tỷ lệ này cao nhất ở tháng sát ngày thu thập (**57.64%–71.34%**), giảm ở phần giữa rồi tăng trở lại về cuối cửa sổ. Mẫu hình chưa đủ để kết luận về mùa cao điểm. K4 nằm trong khoảng **9.6%–10.4%**; K6 giảm từ **5.0%** xuống **2.3%**.
- **Giới hạn diễn giải bắt buộc:** (1) Ngày `available = f` gộp chung cả ngày đã được khách đặt lẫn ngày chủ nhà chủ động khóa lịch, do đó **không được đồng nhất với công suất thuê phòng thực tế hay doanh thu**; (2) Số đánh giá không phải tổng lượt khách thuê, chỉ tính trên mẫu được giao, và mốc cuối không còn quan sát thấy một số ID có mặt ở các mốc trước.

**Hình:** [Tỷ lệ ngày không khả dụng theo tháng lịch (K3) qua 4 mốc chụp — mở bản PDF vector](../figures/fig_time_01_occupancy_by_snapshot.pdf)

**Hình:** [Xu hướng các chỉ số K2, K4 và K6 qua 4 mốc chụp (tách khung chung trục thời gian) — mở bản PDF vector](../figures/fig_time_02_kpi_trend.pdf)

## 4. Mô hình từ điển đạt Accuracy cảm xúc cao hơn LLM

Mẫu LLM gồm **1,000/1,000** đánh giá hợp lệ: 955 đánh giá ở mốc 2026-09-16 và 45 đánh giá bổ sung từ mốc 2026-06-15. Mô hình gán nhãn `positive` cho 89,7%–95,3% đánh giá ở 8 vùng phân tích; **chủ nhà**, **vị trí** và **tiện nghi** là ba khía cạnh được khen nhiều nhất.

| Phương pháp | Thước đo | Giá trị | Khoảng tin cậy 95% | Cỡ mẫu (n) |
| --- | --- | ---: | ---: | ---: |
| LLM | accuracy | 0.9100 | [0.8500, 0.9600] | 100 |
| LLM | macro_f1 | 0.7112 | [0.3139, 0.8070] | 100 |
| BASELINE | accuracy | 0.9900 | [0.9700, 1.0000] | 100 |
| BASELINE | macro_f1 | 0.9679 | [0.5799, 1.0000] | 100 |

**Hình:** [Ba khía cạnh được khen nhiều nhất là chủ nhà, vị trí và tiện nghi — mở bản PDF vector](../figures/fig_llm_02_aspects.pdf)

- **So sánh định lượng trên 100 nhãn tay (`hand_labels.csv`):** Ở phân loại cảm xúc (`sentiment`), Baseline đạt Accuracy cao hơn LLM một cách có ý nghĩa thống kê (chênh lệch ghép cặp `llm_minus_baseline` = **-0.0800**, 95% CI `[-0.1400, -0.0300]`; LLM lệch **9** ca, Baseline lệch **1** ca). Toàn bộ **9** ca lệch của LLM đều rơi vào ranh giới `mixed_confusion` giữa `positive` và `mixed` khi khách khen tổng thể nhưng kèm một lưu ý nhẹ.
- **Thế mạnh và giới hạn ở bài toán khía cạnh:** Ở trích xuất khía cạnh khen (`aspects_praise`), LLM đạt Micro-F1 = **0.8503**, cao hơn **0.6934** của mô hình từ điển trên tập nhãn tay; chưa thực hiện kiểm định ghép cặp cho chênh lệch này. Ở khía cạnh bị chê, Micro-F1 của LLM đạt **0.3636**, thấp hơn mức **0.5333** của mô hình từ điển.
- **Giới hạn cỡ mẫu nhãn tay:** Tập đối chứng 100 review lệch lớp mạnh (93 `positive`, 6 `mixed`, 1 `negative`), khiến khoảng tin cậy 95% của Macro-F1 rất rộng (`[0.3139, 0.8070]` với LLM); cần bổ sung thêm mẫu `negative`/`mixed` trước khi đưa ra kết luận khái quát hơn.

- **Chi phí thực tế và kịch bản mở rộng:** Theo xác nhận của nhóm, 1,000 review được xử lý bằng `Gemini API free tier`, chi phí thực tế **0 USD**. **88.09 USD** là ước tính trả phí cho **729,202** review của Toronto tại mốc 2026-09-16: trung bình **72.88** token vào và **39.58** token ra/review (chars/4 từ cache, chưa tính thinking tokens), đơn giá tham khảo **0.30 USD/1M** token vào và **2.50 USD/1M** token ra, tra ngày **2026-11-11** tại https://ai.google.dev/gemini-api/docs/pricing.

## 5. Không nhận định AI nào được giữ nguyên sau thẩm định

Bản nháp gồm năm nhận định được Codex tạo trong phiên ngày 21/11/2026 từ một prompt yêu cầu viết ngắn, ấn tượng dựa trên bảng số liệu tóm tắt. Nguyên văn năm nhận định được giữ trong cột “Nhận định ban đầu” bên dưới. Nhóm áp dụng quy trình 4 bước — **(1) Tính lại số liệu $\rightarrow$ (2) Kiểm tra phương pháp $\rightarrow$ (3) Kiểm tra diễn giải $\rightarrow$ (4) Kết luận: Giữ / Sửa / Chưa đủ căn cứ** — và không dùng trực tiếp bản nháp AI làm kết luận cuối.

| Nhận định ban đầu cần thẩm định | Số liệu | Phương pháp | Diễn giải | Kết luận & Bản sửa đúng mức |
| --- | --- | --- | --- | --- |
| 1. 86.75% chỗ ở là nguyên căn, chứng tỏ tiềm năng dòng tiền đầu tư lớn. | Đúng | Đúng | Sai: suy diễn doanh thu/dòng tiền từ số lượng listing. | **Sửa:** Mốc 2026-09-16 có 928 chỗ ở trong mẫu, trong đó 86.75% là nguyên căn (không có dữ liệu doanh thu). |
| 2. Giá trung bình (289.01 CAD) cao hơn trung vị (201.07 CAD) chứng minh thị trường siêu sang. | Đúng | Lệch: trung bình bị kéo bởi vài ngoại lai cực đoan. | Quá mức: dùng từ 'chứng minh'. | **Sửa:** Phân phối giá lệch phải; báo cáo dùng trung vị sau lọc IQR (**201.07 CAD/đêm**, n = 783) để phản ánh mức giá điển hình. |
| 3. Tỷ lệ không khả dụng 41.18%–43.62% cho thấy công suất lấp đầy khách luôn vượt 41%. | Đúng | Sai: gộp ngày chủ nhà khóa lịch với ngày đã đặt. | Sai: đồng nhất `available=f` với lượt đặt phòng. | **Chưa đủ căn cứ** kết luận công suất thuê; chỉ ghi nhận tỷ lệ ngày không khả dụng trên lịch. |
| 4. Dovercourt-Wallace Emerson-Junction rẻ hơn Niagara là do kém hấp dẫn về vị trí. | Đúng | Thiếu: chưa kiểm soát cơ cấu loại phòng; 76/118 khu có n < 5. | Sai: suy diễn nhân quả đơn biến. | **Sửa:** Trong 12 khu có cỡ mẫu lớn nhất, trung vị giá dao động từ 128.61 đến 336.12 CAD/đêm và chịu ảnh hưởng của tỷ trọng nguyên căn. |
| 5. LLM vượt trội hoàn toàn mô hình từ điển ở mọi tác vụ phân tích đánh giá. | Sai ở `sentiment` | Đúng với bootstrap ghép cặp cho Accuracy | Sai: bỏ qua độ lệch lớp và kết quả thấp hơn trên cảm xúc. | **Sửa:** Mô hình từ điển đạt Accuracy cao hơn có ý nghĩa thống kê (0.99 so với 0.91); LLM đạt Micro-F1 khía cạnh khen cao hơn trên tập nhãn tay nhưng chưa kiểm định ý nghĩa chênh lệch này. |

## 6. Phụ lục phương pháp: Kiểm soát chất lượng (QA), định nghĩa KPI và tái lập

- **Tác động QA lên giá tại mốc cuối (2026-09-16):** Ghi nhận **114** chỗ ở thiếu giá (giữ nguyên NA, không tự điền). Giá trung vị trước lọc ngoại lai là **211.09 CAD/đêm** (trung bình **289.01 CAD/đêm**); sau khi gắn cờ ngoại lai theo quy tắc IQR tính riêng từng `room_type` kết hợp trần `qa.price_max = 2,000 CAD`, giá trung vị hợp lệ đạt **201.07 CAD/đêm** (n = 783).
- **Nguyên tắc QA theo Bài 10:** Tách giá trị thiếu (`missing_price`, `missing_rating`, `missing_minimum_nights`, `missing_maximum_nights`) khỏi lỗi ngoài miền (`invalid_price`, `invalid_rating` ngoài `[1, 5]`, `invalid_minimum_nights`, `invalid_maximum_nights`); giữ dữ liệu gốc và chỉ gắn cờ thay vì tự điền hoặc xóa vật lý.

`review_id_repeated = 29,295` là tổng lượt ID xuất hiện lại trong sáu phép so sánh cặp giữa các mốc và có hành động `record_only`, không phải 29,295 hàng lỗi. `room_change = 9` cũng là chỉ báo `record_only`.

| Cờ/chỉ báo QA theo từng bảng và mốc | Tổng lượt/hàng |
| --- | ---: |
| rows_with_any_flag | 4,128 |
| comment_markup | 3,650 |
| missing_price | 213 |
| price_outlier | 169 |
| missing_rating | 121 |
| room_change | 9 |
| missing_minimum_nights | 1 |
| missing_maximum_nights | 1 |

| Mã KPI | Tên chỉ số | Đơn vị | Công thức / Điều kiện chính |
| --- | --- | --- | --- |
| K1 | Giá đêm trung vị | CAD/đêm | median(price hợp lệ) |
| K2 | Tỷ lệ ngày không khả dụng theo vùng/mốc | % | 100*(1-mean(available)) |
| K3 | Tỷ lệ ngày không khả dụng theo tháng lịch | % | 100*(1-mean(available)) theo tháng ngày lịch |
| K4 | Tỷ lệ yêu cầu thuê dài hạn | % | 100*mean(minimum_nights>=30) |
| K5 | Mật độ đánh giá trong mẫu | đánh giá mẫu/chỗ ở/quý | đánh giá duy nhất trong quý / chỗ ở duy nhất trong mẫu |
| K6 | Listing chưa có review | % | 100*mean(number_of_reviews==0) |
| K7 | Cảm xúc tiêu cực và điểm khía cạnh | % hoặc [-1,1] | 100*negative/valid; (praise-complaint)/(praise+complaint) |
| K8 | Listing khả dụng cao có nhiều review | % | 100*mean(r >= 0.75 và number_of_reviews >= 10); r là tỷ lệ available trên ngày lịch hợp lệ của từng listing |

### Lệnh tái lập và trạng thái bàn giao
- **Chạy toàn bộ pipeline bằng một lệnh:** `python run_pipeline.py --skip-llm` để đọc cache không gọi API; khi raw đã có đủ dùng thêm `--skip-download`; cấu hình mặc định là `configs/Toronto.yaml`.
- **Kiểm tra tự động:** `python -m pytest -c notebooks/pytest.ini -q` (27 test), `check_report_numbers.py` và `check_security.py`. `check_report_numbers.py` tính lại 36 số khai báo trong `report_numbers.json` từ dữ liệu sạch và dự đoán hiện tại, rồi kiểm chuỗi hiển thị trong cả `report.md` và `report.pdf`; không kiểm mọi số hay ý nghĩa của câu nhận xét.
- **Điều kiện tính toán:** K2 toàn mẫu và K3 giữ ngày lịch hợp lệ kể cả khi thiếu neighbourhood; tổng hợp theo vùng yêu cầu vùng xác định. Dự đoán `parse_error` không nhận điểm cho cảm xúc, khía cạnh hoặc ngôn ngữ. Ngày trên hình và thống kê lỗi lấy từ dữ liệu lần chạy.
- **Tái lập ngày 22/11/2026:** Chạy đầy đủ pipeline bằng cache trong thư mục tạm, tải mới 12 CSV gzip và 4 GeoJSON; SHA256 của 12 CSV khớp manifest. Pipeline kết thúc không cảnh báo/lỗi; 34 bảng đối chiếu khớp trong sai số 1e-10 (không so timestamp manifest), đủ 1,000 dự đoán LLM hợp lệ, không gọi API mới.
- **Làm tròn:** Annex hiển thị 321.66 CAD/đêm theo cùng định dạng hai chữ số của pipeline, từ giá trị KPI 321.66499999999996.
- **Ngoại lệ snapshot:** Nhóm chọn 2026-09-16 thay cho 2025-11-11; cần giảng viên chấp thuận nếu áp dụng ngoại lệ đề bài.
- **Provenance:** Trước khi nộp, chạy `git rev-parse HEAD` và `git status --short` để ghi đúng commit và bảo đảm cây làm việc sạch. Pipeline không tự động `commit`, `tag` hoặc `push`.

LaTeX nguồn: `reports/latex/main.tex`, `content.tex`, `cover.tex`; biên dịch từ `reports/latex` bằng `pdflatex -no-shell-escape -interaction=nonstopmode -halt-on-error -jobname=report main.tex` hai lần. Pipeline sinh số liệu và hình, không tự biên dịch báo cáo.
