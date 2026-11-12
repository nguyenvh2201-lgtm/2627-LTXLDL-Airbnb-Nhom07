"""Sinh hình, tổng hợp số liệu và xuất báo cáo PDF/Markdown."""
import html
import json
import logging
import subprocess
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Rectangle
from pypdf import PdfReader
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak

from .download import read, path, csv_report, cli


def run_figures(cfg: dict) -> None:
    """Sinh hình với tiêu đề, đơn vị và nguồn."""
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10})
    listings = read(cfg, "listings_clean")
    latest = listings.loc[listings.snapshot.eq(cfg["snapshots"][-1])]
    area = pd.read_csv(path(cfg, "processed", "kpi_area.csv"))
    times = pd.read_csv(path(cfg, "processed", "kpi_time.csv"))
    statuses = []

    def figure():
        return plt.subplots(figsize=(cfg["viz"]["width"], cfg["viz"]["height"]))

    def finish(fig, ax, filename, title, xlabel, ylabel, snapshots=None):
        ax.set(title=title, xlabel=xlabel, ylabel=ylabel)
        source = "Nguồn: Inside Airbnb (CC BY 4.0); snapshot " + (snapshots or ", ".join(cfg["snapshots"]))
        fig.text(0.02, 0.015, source, fontsize=7)
        fig.tight_layout(rect=[0, 0.055, 1, 1])
        fig.savefig(path(cfg, "figures", filename), dpi=cfg["viz"]["dpi"])
        plt.close(fig)
        statuses.append({"figure": filename, "status": "created", "reason": ""})

    fig, ax = figure()
    prices = latest.price.clip(upper=latest.price.quantile(cfg["viz"]["price_percentile"]))
    ax.scatter(latest.longitude, latest.latitude, color="lightgrey", s=10, label="Thiếu giá")
    points = ax.scatter(latest.longitude, latest.latitude, c=prices, cmap="viridis", s=12)
    fig.colorbar(points, ax=ax, label=cfg["currency"] + "/đêm (cắt màu P95)")
    regions = pd.read_csv(cfg["_root"] / cfg["inputs"]["areas"])
    for row in regions.itertuples():
        ax.add_patch(Rectangle((row.lon_min, row.lat_min), row.lon_max - row.lon_min, row.lat_max - row.lat_min, fill=False, linewidth=0.8))
        ax.text((row.lon_min + row.lon_max) / 2, (row.lat_min + row.lat_max) / 2, row.area, fontsize=8, ha="center", va="center", bbox={"facecolor": "white", "alpha": 0.8, "edgecolor": "none", "pad": 1})
    finish(fig, ax, "fig_space_01_listings_map.png", "Listing và 8 vùng mẫu (không phải ranh giới hành chính)", "Kinh độ", "Vĩ độ", cfg["snapshots"][-1])
    for kid, filename, title, unit in (("K1", "fig_space_02_area_price.png", "Giá trung vị theo vùng, n = số listing có giá hợp lệ", cfg["currency"] + "/đêm"), ("K2", "fig_space_03_area_occupancy.png", "Ngày không khả dụng theo vùng (không phải booking thực)", "% ngày")):
        data = area.loc[area.kpi_id.eq(kid) & area.snapshot.eq(cfg["snapshots"][-1])].dropna(subset=["value"])
        data = data.nlargest(12, "n").sort_values("value")
        fig, ax = figure()
        bars = ax.bar(data.area, data.value, color=plt.cm.viridis(np.linspace(0.2, 0.8, len(data))))
        ax.bar_label(bars, labels=[f"n={n:,}" for n in data.n], fontsize=8)
        ax.margins(y=0.18)
        ax.tick_params(axis="x", rotation=75, labelsize=7)
        finish(fig, ax, filename, title + " (12 neighbourhood có mẫu lớn nhất)", "neighbourhood_cleansed", unit, cfg["snapshots"][-1])
    fig, ax = figure()
    for snapshot, group in times.loc[times.kpi_id.eq("K3")].groupby("snapshot"):
        ax.plot(pd.to_datetime(group.period), group.value, marker=".", label=snapshot)
    ax.legend(title="Snapshot")
    finish(fig, ax, "fig_time_01_occupancy_by_snapshot.png", "Không khả dụng theo tháng lịch; tháng biên có thể chưa đủ ngày", "Tháng của ngày lịch", "% ngày không khả dụng")
    fig, ax = figure()
    for kid, group in times.loc[times.kpi_id.isin(["K2", "K4", "K6"])].groupby("kpi_id"):
        ax.plot(group.snapshot, group.value, marker="o", label=kid)
    ax.legend(title="K2 không khả dụng; K4 thuê dài hạn; K6 chưa review", fontsize=8)
    finish(fig, ax, "fig_time_02_kpi_trend.png", "Xu hướng mẫu quan sát (cỡ mẫu thay đổi ở mốc cuối)", "Snapshot", "%")
    fig, ax = figure()
    data = times.loc[times.kpi_id.eq("K5")]
    ax.plot(data.period, data.value, marker=".")
    ax.tick_params(axis="x", rotation=90, labelsize=7)
    finish(fig, ax, "fig_time_03_reviews_per_quarter.png", "Review theo quý trong mẫu được giao", "Quý", "Review mẫu / listing / quý")
    results = read(cfg, "llm_results")
    valid = results.loc[~results.parse_error & results.sentiment.notna()]
    if len(valid):
        sample = read(cfg, "llm_sample")
        merged = valid.merge(sample[["id", "analysis_area"]], left_on="review_id", right_on="id")
        grouped = pd.crosstab(merged.analysis_area, merged.sentiment, normalize="index").reindex(columns=cfg["evaluation"]["labels"], fill_value=0) * 100
        fig, ax = figure()
        grouped.plot.bar(stacked=True, ax=ax, colormap="viridis")
        finish(fig, ax, "fig_llm_01_sentiment_by_area.png", "Cảm xúc LLM trên review có kết quả hợp lệ", "Vùng", "% review")
        counts = pd.DataFrame({key: [sum(a in items for items in valid[key]) for a in cfg["llm"]["aspects"]] for key in ("aspects_praise", "aspects_complaint")}, index=cfg["llm"]["aspects"])
        fig, ax = figure()
        counts.plot.bar(ax=ax, colormap="viridis")
        finish(fig, ax, "fig_llm_02_aspects.png", "Khía cạnh được khen/chê theo LLM", "Khía cạnh", "Số review")
    else:
        for filename in ("fig_llm_01_sentiment_by_area.png", "fig_llm_02_aspects.png"):
            statuses.append({"figure": filename, "status": "missing", "reason": "Chưa có kết quả LLM thật"})
    metrics = pd.read_csv(path(cfg, "reports", "eval_metrics.csv"))
    if len(metrics):
        fig, ax = figure()
        selected = metrics.loc[metrics.task.eq("sentiment") & metrics.metric.isin(["accuracy", "macro_f1"])]
        labels = selected.method + " / " + selected.metric
        errors = np.vstack([(selected.value - selected.ci_low).clip(lower=0), (selected.ci_high - selected.value).clip(lower=0)])
        ax.bar(labels, selected.value, yerr=errors, capsize=4, color=plt.cm.viridis(np.linspace(0.2, 0.8, len(selected))))
        ax.set_ylim(0, 1.1)
        finish(fig, ax, "fig_llm_03_model_vs_baseline.png", "Đánh giá trên nhãn tay, khoảng tin cậy bootstrap 95%", "Phương pháp / metric", "Điểm [0,1]")
        for method, number in (("llm", "04"), ("baseline", "05")):
            matrix = pd.read_csv(path(cfg, "reports", f"confusion_{method}.csv"), index_col=0)
            fig, ax = figure()
            image = ax.imshow(matrix.to_numpy(), cmap="cividis")
            ax.set_xticks(range(len(matrix.columns)), matrix.columns, rotation=20)
            ax.set_yticks(range(len(matrix.index)), matrix.index)
            for i in range(len(matrix)):
                for j in range(len(matrix.columns)):
                    ax.text(j, i, str(matrix.iloc[i, j]), ha="center", color="white" if matrix.iloc[i, j] < matrix.to_numpy().max() / 2 else "black")
            fig.colorbar(image, ax=ax, label="Số review")
            finish(fig, ax, f"fig_llm_{number}_confusion_{method}.png", "Ma trận nhầm lẫn " + method, "Dự đoán", "Nhãn tay")
    else:
        for filename in ("fig_llm_03_model_vs_baseline.png", "fig_llm_04_confusion_llm.png", "fig_llm_05_confusion_baseline.png"):
            statuses.append({"figure": filename, "status": "missing", "reason": "Chưa có nhãn tay để đánh giá"})
    csv_report(cfg, statuses, "figure_status.csv")
    for row in statuses:
        if row["status"] != "created":
            # Xóa riêng hình sinh tự động đã cũ, tránh đưa nhầm vào báo cáo lần sau.
            target = path(cfg, "figures", row["figure"])
            if target.exists():
                target.unlink()
            logging.warning("Bỏ hình %s: %s", row["figure"], row["reason"])


def run_summary(cfg: dict) -> None:
    """Bảng số liệu dùng chung để dựng và kiểm báo cáo."""
    from .llm import make_label_template as make_template
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
    text("BẢN NHÁP - số liệu tự động, nhóm cần viết nhận định", "Heading2")
    text("1. Mục tiêu và phạm vi", "Heading1")
    text("Bên đặt hàng đề xuất: " + cfg["kpi"]["stakeholder"] + ". Mục tiêu: mô tả giá, khả dụng và trải nghiệm trong mẫu giảng viên giao.")
    text("Nguồn: https://insideairbnb.com/get-the-data/; dữ liệu CC BY 4.0. URL và SHA256 từng file nằm trong download_manifest.csv. Không thu thập airbnb.com.")
    text("Snapshot: " + ", ".join(cfg["snapshots"]) + ". Tiền tệ: " + cfg["currency"] + ".")
    table(["Snapshot", "Listing", "Calendar", "Review"], [[s, number(f"listings.{s}.after"), number(f"calendar.{s}.after"), number(f"reviews.{s}.after")] for s in cfg["snapshots"]], [4.1 * cm] * 4)
    text("Mốc cuối giữ theo yêu cầu người dùng dù thiếu ID so với danh sách gốc. Danh sách chi tiết: missing_ids.csv. So sánh kỳ dùng mẫu thay đổi, không phải cohort cố định.")
    text("Tóm tắt và nhận định: TODO - nhóm tự viết dựa trên các bảng kiểm chứng.")
    story.append(PageBreak())
    text("2. Tái lập và kiểm soát chất lượng", "Heading1")
    text("Lệnh: python run_pipeline.py --config configs/city.yaml --skip-download --skip-llm. Bỏ --skip-llm để dùng GEMINI_API_KEY từ môi trường. Calendar được lọc theo khối; seed trong config.")
    text("QA gắn cờ thiếu dữ liệu, ngoại lai, sai kiểu, danh mục, trùng và nhất quán chéo. KPI trước/sau trong qa_report.csv là tác động giả định loại dòng của từng rule, không phải số dòng thực bị xóa.")
    text("Thiếu giá ở mốc cuối: " + number("latest.missing_price") + " listing. Giá trung vị sau lọc giá bất hợp lý: " + number("latest.median_price") + " " + cfg["currency"] + "/đêm.")
    qa = pd.read_csv(path(cfg, "reports", "qa_report.csv"))
    selected = qa.groupby("rule").rows_flagged.sum().sort_values(ascending=False).head(9)
    table(["Quy tắc", "Lượt dòng bị cờ (cộng các mốc)"], [[k, f"{v:,}"] for k, v in selected.items()], [11 * cm, 5.4 * cm])
    text("Một dòng có thể mang nhiều cờ. Giá listing các mốc trước không dùng trong phân tích. Số review mẫu không được so bằng số review toàn bộ của listing.")
    text("TODO - nhóm giải thích và bảo vệ ngưỡng QA; đây là ngưỡng cấu hình đề xuất.")
    story.append(PageBreak())
    text("3. KPI và góc nhìn không gian", "Heading1")
    defs = pd.read_csv(path(cfg, "reports", "kpi_definitions.csv")).fillna("")
    table(["KPI", "Tên", "Đơn vị"], [[r.kpi_id, r.name, r.unit] for r in defs.itertuples()], [1.2 * cm, 11 * cm, 4.2 * cm])
    chart("fig_space_02_area_price.png")
    text("KPI luôn ghi n. Tám vùng là hình chữ nhật phân tích, không phải địa giới hành chính. TODO - nhóm viết nhận định theo vùng.")
    story.append(PageBreak())
    text("4. Không gian và thời gian", "Heading1")
    chart("fig_space_01_listings_map.png")
    chart("fig_time_01_occupancy_by_snapshot.png")
    text("Không khả dụng có thể do đã đặt hoặc chủ nhà khóa lịch; không diễn giải thành công suất thực. Các cửa sổ lịch tương lai khác nhau và tháng biên có số ngày khác nhau.")
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
    text("Tài liệu API: https://ai.google.dev/gemini-api/docs/structured-output. Nhóm tự phân tích lỗi theo error_analysis.csv; không tự gán nguyên nhân mỉa mai bằng máy.")
    story.append(PageBreak())
    text("6. Hạn chế, phần còn thiếu và bàn giao", "Heading1")
    text("Mẫu được giảng viên chọn, không bảo đảm đại diện toàn thành phố. K5 là review trong mẫu, không phải toàn bộ review mới của thị trường. Không suy luận quốc tịch từ ngôn ngữ review.")
    text("Mốc mới có listing/review bị thiếu. Giá thiếu không được điền. Các hình LLM chưa có dữ liệu sẽ được bỏ qua và ghi figure_status.csv.")
    text("Việc nhóm cần làm: xác nhận bên đặt hàng và ngưỡng; gán nhãn tay; cung cấp khóa qua môi trường; tra giá model; chạy lại; viết nhận định và phân tích lỗi; kiểm tra định dạng chính thức.")
    provenance = pd.read_csv(path(cfg, "reports", "build_provenance.csv")).iloc[0]
    text("HEAD tại lúc dựng: " + str(provenance.head_commit) + ". Working tree có thay đổi: " + str(provenance.working_tree_dirty) + ". Đây không phải mã commit của tag final.")
    text("Tag final: TODO - người dùng xác nhận việc nộp, commit và tag rồi cập nhật báo cáo. Pipeline không tự push/tag.")
    text("TODO - nhóm tự viết kết luận, hướng phát triển và chuẩn bị vấn đáp; mọi số liệu phải đối chiếu summary_numbers.csv.")
    dest = path(cfg, "reports", "report.pdf")
    doc = SimpleDocTemplate(str(dest), pagesize=(21 * cm, 29.7 * cm), rightMargin=2 * cm, leftMargin=2 * cm, topMargin=1.6 * cm, bottomMargin=1.5 * cm)

    def footer(canvas, document):
        canvas.setFont("ReportFont", 8)
        canvas.drawString(2 * cm, cm, "BTL Inside Airbnb | Bản nháp cần nhóm kiểm chứng")
        canvas.drawRightString(19 * cm, cm, str(document.page))

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    pages = len(PdfReader(dest).pages)
    if pages > cfg["report"]["max_pages"]:
        raise ValueError(f"Báo cáo có {pages} trang, vượt giới hạn")
    path(cfg, "reports", "report.md").write_text("\n\n".join(markdown), encoding="utf-8")
    path(cfg, "reports", "report_numbers.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

def run(cfg: dict) -> None:
    """Sinh hình, tổng hợp số liệu và xuất báo cáo trong reports/."""
    run_figures(cfg)
    run_summary(cfg)
    run_report(cfg)


if __name__ == "__main__":
    cli(run)
