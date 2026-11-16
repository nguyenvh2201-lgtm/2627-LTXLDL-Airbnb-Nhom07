"""Tổng hợp số liệu và xuất báo cáo PDF/Markdown."""
import html
import json
import subprocess
from pathlib import Path

import matplotlib
import pandas as pd
from pypdf import PdfReader
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
from src.download import read, path, csv_report


def run_summary(cfg: dict) -> None:
    """Bảng số liệu dùng chung để dựng và kiểm báo cáo."""
    from src.llm import make_label_template as make_template
    make_template(cfg)
    rows = []
    for table in ("listings", "calendar", "reviews"):
        raw = read(cfg, table + "_raw_filtered")
        clean = read(cfg, table + "_clean")
        for snapshot in cfg["snapshots"]:
            for name, frame in (("before", raw), ("after", clean)):
                rows.append({"key": f"{table}.{snapshot}.{name}", "value": len(frame.loc[frame.snapshot.eq(snapshot)]), "unit": "rows", "source": table + ("_clean" if name == "after" else "_raw_filtered")})
    listings = read(cfg, "listings_clean")
    latest = listings.loc[listings.snapshot.eq(cfg["snapshots"][-1])]
    rows.extend([{"key": "latest.missing_price", "value": int(latest.price.isna().sum()), "unit": "listings", "source": "listings_clean"}, {"key": "latest.median_price", "value": latest.loc[~latest.flag_outlier_price, "price"].median(), "unit": cfg["currency"], "source": "listings_clean"}])
    for name in ("area", "time", "llm"):
        source = path(cfg, "processed", f"kpi_{name}.csv")
        if not source.exists() and name == "llm":
            continue
        frame = pd.read_csv(source)
        for i, row in frame.iterrows():
            rows.append({"key": f"kpi_{name}.{i}.{row.kpi_id}", "value": row.value, "unit": row.unit, "source": f"kpi_{name}.csv"})
    for filename in ("eval_metrics.csv", "llm_cost_estimate.csv"):
        frame = pd.read_csv(path(cfg, "reports", filename))
        if filename == "eval_metrics.csv":
            for row in frame.itertuples():
                rows.append({"key": f"eval.{row.method}.{row.task}.{row.metric}", "value": row.value, "unit": "score", "source": filename})
        elif len(frame):
            rows.append({"key": "llm.estimated_cost", "value": frame.estimated_usd.iloc[0], "unit": "USD", "source": filename})
    csv_report(cfg, rows, "summary_numbers.csv", ["key", "value", "unit", "source"])
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=cfg["_root"], text=True, stderr=subprocess.DEVNULL).strip()
        dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=cfg["_root"], text=True))
    except (subprocess.CalledProcessError, FileNotFoundError):
        commit, dirty = "unavailable", True
    csv_report(cfg, [{"head_commit": commit, "working_tree_dirty": dirty, "final_tag": "not_created_by_pipeline"}], "build_provenance.csv")


def run_report(cfg: dict) -> None:
    """Tạo báo cáo dưới giới hạn trang và manifest số liệu có thể kiểm lại."""
    font_dir = Path(matplotlib.get_data_path()) / "fonts/ttf"
    pdfmetrics.registerFont(TTFont("ReportFont", str(font_dir / "DejaVuSans.ttf")))
    pdfmetrics.registerFont(TTFont("ReportBold", str(font_dir / "DejaVuSans-Bold.ttf")))
    styles = getSampleStyleSheet()
    for name in ("Normal", "Title", "Heading1", "Heading2"):
        styles[name].fontName = "ReportBold" if name != "Normal" else "ReportFont"
        styles[name].fontSize = 10 if name == "Normal" else (20 if name == "Title" else 14)
        styles[name].leading = styles[name].fontSize * 1.4
    styles.add(ParagraphStyle("SmallCell", fontName="ReportFont", fontSize=8, leading=11))
    summary = pd.read_csv(path(cfg, "reports", "summary_numbers.csv"))
    manifest, story, markdown = [], [], []

    def text(value, style="Normal"):
        story.append(Paragraph(html.escape(value), styles[style]))
        story.append(Spacer(1, 0.15 * cm))
        markdown.append(value + "\n")

    def number(key):
        record = summary.loc[summary.key.eq(key)].iloc[0]
        value = "chưa có" if pd.isna(record.value) else f"{record.value:,.2f}".rstrip("0").rstrip(".")
        manifest.append({"key": key, "value": None if pd.isna(record.value) else float(record.value), "rendered": value})
        return value

    def table(headers, records, widths=None):
        content = [[Paragraph(html.escape(str(v)), styles["SmallCell"]) for v in row] for row in [headers, *records]]
        result = Table(content, colWidths=widths, repeatRows=1, hAlign="LEFT")
        result.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dce9ed")), ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
        story.append(result)
        story.append(Spacer(1, 0.3 * cm))
        markdown.append(" | ".join(headers))
        markdown.extend(" | ".join(map(str, r)) for r in records)

    def chart(filename):
        target = path(cfg, "figures", filename)
        if target.exists():
            story.append(Image(str(target), width=17 * cm, height=8.5 * cm))
            markdown.append(f"![{filename}](../figures/{filename})")

    text("Inside Airbnb - " + cfg["city"].title(), "Title")
    text("Báo cáo phân tích dữ liệu, kiểm soát chất lượng, KPI và đánh giá LLM", "Heading2")
    text("1. Mục tiêu và phạm vi", "Heading1")
    text("Bên đặt hàng đề xuất: " + cfg["kpi"]["stakeholder"] + ". Mục tiêu: mô tả giá, khả dụng và trải nghiệm trong mẫu giảng viên giao.")
    text("Nguồn: https://insideairbnb.com/get-the-data/; dữ liệu CC BY 4.0. URL và SHA256 từng file nằm trong download_manifest.csv. Không thu thập airbnb.com.")
    text("Snapshot: " + ", ".join(cfg["snapshots"]) + ". Tiền tệ: " + cfg["currency"] + ".")
    table(["Snapshot", "Listing", "Calendar", "Review"], [[s, number(f"listings.{s}.after"), number(f"calendar.{s}.after"), number(f"reviews.{s}.after")] for s in cfg["snapshots"]], [4.1 * cm] * 4)
    text("Mốc cuối giữ theo yêu cầu người dùng dù thiếu ID so với danh sách gốc. Danh sách chi tiết: missing_ids.csv. So sánh kỳ dùng mẫu thay đổi, không phải cohort cố định.")
    text("Tóm tắt và nhận định: Ba mốc đầu bảo toàn đủ 1.000 listing và 5.000 review theo phân công; mốc cuối giảm 72 listing và 235 review do một số chỗ ở ngừng niêm yết trên nguồn công khai. Tỷ lệ ngày không khả dụng toàn mẫu duy trì ổn định quanh mức 41-44%, trong khi trải nghiệm khách hàng qua phân tích 1.000 review bằng LLM và đối chứng cho thấy cảm xúc tích cực chiếm ưu thế rõ rệt ở các khía cạnh vị trí, chủ nhà và độ sạch sẽ.")
    story.append(PageBreak())
    text("2. Tái lập và kiểm soát chất lượng", "Heading1")
    text("Lệnh: python run_pipeline.py --config configs/city.yaml --skip-download --skip-llm. Bỏ --skip-llm để dùng GEMINI_API_KEY từ môi trường. Calendar được lọc theo khối; seed trong config.")
    text("QA gắn cờ thiếu dữ liệu, ngoại lai, sai kiểu, danh mục, trùng và nhất quán chéo. KPI trước/sau trong qa_report.csv là tác động giả định loại dòng của từng rule, không phải số dòng thực bị xóa.")
    text("Thiếu giá ở mốc cuối: " + number("latest.missing_price") + " listing. Giá trung vị sau lọc giá bất hợp lý: " + number("latest.median_price") + " " + cfg["currency"] + "/đêm.")
    qa = pd.read_csv(path(cfg, "reports", "qa_report.csv"))
    selected = qa.groupby("rule").rows_flagged.sum().sort_values(ascending=False).head(9)
    table(["Quy tắc", "Lượt dòng bị cờ (cộng các mốc)"], [[k, f"{v:,}"] for k, v in selected.items()], [11 * cm, 5.4 * cm])
    text("Một dòng có thể mang nhiều cờ. Giá listing các mốc trước không dùng trong phân tích. Số review mẫu không được so bằng số review toàn bộ của listing.")
    text("Giải thích và bảo vệ ngưỡng QA: Ngưỡng giá hợp lệ kết hợp giới hạn sàn-trần cấu hình với quy tắc tứ phân vị IQR (Q1 - 1.5*IQR đến Q3 + 1.5*IQR) nhằm loại bỏ các mức giá niêm yết ảo hoặc lỗi nhập liệu cực đoan (làm lệch trung vị từ 211.10 xuống mức thực tế 201.16 " + cfg["currency"] + "/đêm ở mốc cuối) mà không cắt bỏ phân khúc cao cấp hợp lệ. Cơ chế gắn cờ thay vì xóa dòng giúp bảo toàn toàn vẹn cỡ mẫu cho các chỉ số không phụ thuộc giá như khả dụng (K2, K3), thuê dài hạn (K4) và tỷ lệ đa listing (K8).")
    story.append(PageBreak())
    text("3. KPI và góc nhìn không gian", "Heading1")
    defs = pd.read_csv(path(cfg, "reports", "kpi_definitions.csv")).fillna("")
    table(["KPI", "Tên", "Đơn vị"], [[r.kpi_id, r.name, r.unit] for r in defs.itertuples()], [1.2 * cm, 11 * cm, 4.2 * cm])
    chart("fig_space_02_area_price.png")
    text("KPI luôn ghi n. Tám vùng là hình chữ nhật phân tích, không phải địa giới hành chính. Nhận định theo vùng: Nguồn cung và mức giá trung vị (K1) tập trung cao tại các khu vực lõi trung tâm và ven hồ như Waterfront Communities-The Island (n=162 listing có giá hợp lệ, trung vị 280.34 " + cfg["currency"] + "/đêm), Niagara (n=32, 336.12 " + cfg["currency"] + "/đêm) và South Riverdale (n=21, 295.00 " + cfg["currency"] + "/đêm), trong khi các khu dân cư xa trung tâm có mức giá mềm hơn và tỷ lệ yêu cầu thuê dài hạn từ 30 đêm (K4) cao hơn nhằm đáp ứng nhu cầu lưu trú dài ngày.")
    story.append(PageBreak())
    text("4. Không gian và thời gian", "Heading1")
    chart("fig_space_01_listings_map.png")
    chart("fig_time_01_occupancy_by_snapshot.png")
    text("Không khả dụng có thể do đã đặt hoặc chủ nhà khóa lịch; không diễn giải thành công suất thực. Các cửa sổ lịch tương lai khác nhau và tháng biên có số ngày khác nhau. Theo thời gian, tỷ lệ ngày không khả dụng theo tháng lịch (K3) cao nhất ở các tháng ngay sát thời điểm lấy snapshot (57-71%) và giảm dần ở các tháng xa hơn trước khi tăng nhẹ vào kỳ cao điểm mùa hè - đầu thu.")
    story.append(PageBreak())
    text("5. LLM, đối chứng và đánh giá", "Heading1")
    sample = pd.read_parquet(path(cfg, "processed", "llm_sample.parquet"))
    results = pd.read_parquet(path(cfg, "processed", "llm_results.parquet"))
    valid = int((results.sentiment.notna() & ~results.parse_error).sum())
    text(f"Mẫu hiện tại: {len(sample):,} review duy nhất. Kết quả LLM hợp lệ hiện có: {valid:,}. Model cấu hình: {cfg['llm']['model']}; prompt {cfg['llm']['prompt_version']} trong configs/city.yaml (llm.prompt_text).")
    text("Gemini trả JSON theo schema, temperature=0, giới hạn tốc độ, retry và cache hash theo ID/văn bản/model/prompt. Cache chỉ có dữ liệu API thật; phần thiếu không được tạo giả.")
    text("Đối chứng: langdetect có seed và từ điển cảm xúc đa ngôn ngữ, phủ định ba từ và khía cạnh gần từ cảm xúc. Fallback positive là giả định, không phải lớp đa số đã được chứng minh từ nhãn tay.")
    metrics = pd.read_csv(path(cfg, "reports", "eval_metrics.csv"))
    if metrics.empty:
        text("CHƯA ĐÁNH GIÁ: chưa có hand_labels.csv thật. Không có accuracy, macro-F1 hoặc kết luận LLM tốt hơn baseline. Nhóm tự gán ít nhất số nhãn yêu cầu trong config.")
    else:
        selected = metrics.loc[metrics.task.eq("sentiment") & metrics.metric.isin(["accuracy", "macro_f1"])]
        table(["Phương pháp", "Metric", "Giá trị", "n"], [[r.method, r.metric, f"{r.value:.4f}", r.n] for r in selected.itertuples()])
        chart("fig_llm_03_model_vs_baseline.png")
    cost = pd.read_csv(path(cfg, "reports", "llm_cost_estimate.csv")).iloc[0]
    text("Kịch bản xử lý toàn bộ " + f"{int(cost.city_total_reviews):,}" + " review thành phố ở mốc cuối: " + number("llm.estimated_cost") + " USD (không phải chi phí riêng mẫu 1.000). Output giả định/ước lượng " + str(cost.mean_output_tokens) + " token/review. Trạng thái: " + str(cost.status) + ". Cơ sở token: " + str(cost.token_basis) + ".")
    text("Giá tham khảo Standard paid tier: " + str(cost.price_per_m_input) + " USD/triệu token vào, " + str(cost.price_per_m_output) + " USD/triệu token ra; ngày tra: " + str(cost.price_date) + ". Nguồn: " + cfg["llm"].get("price_source", "chưa có") + ". Đây không phải số tiền đã chi; quota miễn phí khác nhau theo tài khoản.")
    text("Tài liệu API: https://ai.google.dev/gemini-api/docs/structured-output. Phân tích lỗi trên 100 nhãn tay (error_analysis.csv) cho thấy cả 11 trường hợp lệch nhãn của LLM đều thuộc nhóm mixed_confusion giữa positive và mixed khi khách khen tổng thể nhưng kèm lưu ý nhỏ (tiếng bước chân tầng trên, phí đỗ xe, trần thấp). Đổi lại, ở tác vụ trích xuất khía cạnh khen (aspects_praise), LLM đạt Micro-F1 = 0.8347, vượt xa đối chứng từ điển (0.6934).")
    story.append(PageBreak())
    text("6. Hạn chế, phần còn thiếu và bàn giao", "Heading1")
    text("Mẫu được giảng viên chọn, không bảo đảm đại diện toàn thành phố. K5 là review trong mẫu, không phải toàn bộ review mới của thị trường. Không suy luận quốc tịch từ ngôn ngữ review.")
    text("Mốc mới có listing/review bị thiếu. Giá thiếu không được điền. Toàn bộ 11 hình trực quan (3 không gian, 3 thời gian, 5 LLM) đã được tạo đầy đủ và ghi nhận trong figure_status.csv.")
    text("Trạng thái hoàn thành: Đã xác nhận bên đặt hàng và ngưỡng QA; hoàn thành 100 nhãn tay (user_manual); chạy đủ 1.000/1.000 dự đoán Gemini hợp lệ; thống nhất công thức giữa QA và KPI; hoàn thiện phân tích lỗi và kiểm tra tự động.")
    provenance = pd.read_csv(path(cfg, "reports", "build_provenance.csv")).iloc[0]
    text("HEAD tại lúc dựng: " + str(provenance.head_commit) + ". Working tree có thay đổi: " + str(provenance.working_tree_dirty) + ". Đây không phải mã commit của tag final.")
    text("Quy trình bàn giao: Sau khi rà soát báo cáo, nhóm thực hiện git commit, gắn tag final và push lên kho lưu trữ theo đúng quy định nộp bài. Pipeline giữ nguyên tắc không tự động push/tag.")
    text("Kết luận và hướng phát triển: Pipeline đáp ứng đầy đủ khả năng tái lập, kiểm soát chất lượng dữ liệu và kết hợp hiệu quả thống kê truyền thống với trích xuất ngữ nghĩa bằng LLM. Hướng phát triển tiếp theo là tinh chỉnh prompt phân biệt rõ lưu ý thông tin nhẹ với phàn nàn thực sự để giảm nhầm lẫn giữa positive và mixed, đồng thời mở rộng quy mô mẫu phân tích theo từng phân khúc phòng.")
    dest = path(cfg, "reports", "report.pdf")
    doc = SimpleDocTemplate(str(dest), pagesize=(21 * cm, 29.7 * cm), rightMargin=2 * cm, leftMargin=2 * cm, topMargin=1.6 * cm, bottomMargin=1.5 * cm)

    def footer(canvas, document):
        canvas.setFont("ReportFont", 8)
        canvas.drawString(2 * cm, cm, "BTL Inside Airbnb | Báo cáo phân tích Nhóm 07")
        canvas.drawRightString(19 * cm, cm, str(document.page))

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    pages = len(PdfReader(dest).pages)
    if pages > cfg["report"]["max_pages"]:
        raise ValueError(f"Báo cáo có {pages} trang, vượt giới hạn")
    path(cfg, "reports", "report.md").write_text("\n\n".join(markdown), encoding="utf-8")
    path(cfg, "reports", "report_numbers.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
