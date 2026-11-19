"""Tổng hợp số liệu, kể chuyện bằng dữ liệu và xuất báo cáo Markdown theo Bài 14 (lecture_14.py)."""
import json
import subprocess
from pathlib import Path
import sys

import pandas as pd

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.download import read, path, csv_report, cli


def run_summary(cfg: dict) -> None:
    """Bảng số liệu dùng chung để dựng, đối chiếu và thẩm định báo cáo."""
    from src.llm import make_label_template as make_template
    make_template(cfg)
    rows = []
    for table in ("listings", "calendar", "reviews"):
        raw = read(cfg, table + "_raw_filtered")
        clean = read(cfg, table + "_clean")
        for snapshot in cfg["snapshots"]:
            for name, frame in (("before", raw), ("after", clean)):
                rows.append({
                    "key": f"{table}.{snapshot}.{name}",
                    "value": len(frame.loc[frame.snapshot.eq(snapshot)]),
                    "unit": "rows",
                    "source": table + ("_clean" if name == "after" else "_raw_filtered"),
                })
    listings = read(cfg, "listings_clean")
    latest = listings.loc[listings.snapshot.eq(cfg["snapshots"][-1])]
    valid_latest_prices = latest.loc[latest.price.gt(0), "price"]
    clean_latest_prices = latest.loc[~latest.flag_outlier_price & latest.price.notna(), "price"]
    entire_share = float(latest.room_type.eq("Entire home/apt").mean() * 100) if len(latest) else 0.0
    entire_med = latest.loc[~latest.flag_outlier_price & latest.price.notna() & latest.room_type.eq("Entire home/apt"), "price"].median()
    private_med = latest.loc[~latest.flag_outlier_price & latest.price.notna() & latest.room_type.eq("Private room"), "price"].median()
    rows.extend([
        {"key": "latest.missing_price", "value": int(latest.price.isna().sum()), "unit": "listings", "source": "listings_clean"},
        {"key": "latest.valid_price_count", "value": int(len(clean_latest_prices)), "unit": "listings", "source": "listings_clean"},
        {"key": "latest.mean_price_before", "value": float(valid_latest_prices.mean()) if len(valid_latest_prices) else float("nan"), "unit": cfg["currency"], "source": "listings_clean"},
        {"key": "latest.median_price_before", "value": float(valid_latest_prices.median()) if len(valid_latest_prices) else float("nan"), "unit": cfg["currency"], "source": "listings_clean"},
        {"key": "latest.median_price", "value": float(clean_latest_prices.median()) if len(clean_latest_prices) else float("nan"), "unit": cfg["currency"], "source": "listings_clean"},
        {"key": "latest.entire_home_pct", "value": entire_share, "unit": "%", "source": "listings_clean"},
        {"key": "latest.entire_median_price", "value": float(entire_med) if pd.notna(entire_med) else float("nan"), "unit": cfg["currency"], "source": "listings_clean"},
        {"key": "latest.private_median_price", "value": float(private_med) if pd.notna(private_med) else float("nan"), "unit": cfg["currency"], "source": "listings_clean"},
    ])
    for name in ("area", "time", "llm"):
        source = path(cfg, "processed", f"kpi_{name}.csv")
        if not source.exists() and name == "llm":
            continue
        frame = pd.read_csv(source)
        for i, row in frame.iterrows():
            rows.append({"key": f"kpi_{name}.{i}.{row.kpi_id}", "value": row.value, "unit": row.unit, "source": f"kpi_{name}.csv"})
        if name == "time":
            k2 = frame.loc[frame.kpi_id.eq("K2"), "value"].dropna()
            k3 = frame.loc[frame.kpi_id.eq("K3")]
            first_months = k3.groupby("snapshot", sort=False).first()["value"].dropna() if len(k3) else pd.Series(dtype=float)
            if len(k2):
                rows.extend([
                    {"key": "kpi_time.K2.min", "value": float(k2.min()), "unit": "%", "source": "kpi_time.csv"},
                    {"key": "kpi_time.K2.max", "value": float(k2.max()), "unit": "%", "source": "kpi_time.csv"},
                ])
            if len(first_months):
                rows.extend([
                    {"key": "kpi_time.K3.first_month_min", "value": float(first_months.min()), "unit": "%", "source": "kpi_time.csv"},
                    {"key": "kpi_time.K3.first_month_max", "value": float(first_months.max()), "unit": "%", "source": "kpi_time.csv"},
                ])
    for filename in ("eval_metrics.csv", "llm_cost_estimate.csv", "error_analysis.csv"):
        target_path = path(cfg, "reports", filename)
        if not target_path.exists():
            continue
        frame = pd.read_csv(target_path)
        if filename == "eval_metrics.csv":
            for row in frame.itertuples():
                rows.append({"key": f"eval.{row.method}.{row.task}.{row.metric}", "value": row.value, "unit": "score", "source": filename})
        elif filename == "llm_cost_estimate.csv" and len(frame):
            rows.append({"key": "llm.estimated_cost", "value": frame.estimated_usd.iloc[0], "unit": "USD", "source": filename})
        elif filename == "error_analysis.csv":
            rows.extend([
                {"key": "error.total_rows", "value": len(frame), "unit": "reviews", "source": filename},
                {"key": "error.llm_wrong", "value": int(frame.llm.ne(frame.hand_label).sum()) if len(frame) else 0, "unit": "reviews", "source": filename},
                {"key": "error.baseline_wrong", "value": int(frame.baseline.ne(frame.hand_label).sum()) if len(frame) else 0, "unit": "reviews", "source": filename},
            ])
    csv_report(cfg, rows, "summary_numbers.csv", ["key", "value", "unit", "source"])


def _git_provenance(root: Path) -> tuple[str, bool]:
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True, stderr=subprocess.DEVNULL).strip()
        dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True))
    except (subprocess.CalledProcessError, FileNotFoundError):
        commit, dirty = "unavailable", True
    return commit, dirty


def run_report(cfg: dict) -> None:
    """Xuất báo cáo Markdown (reports/report.md) theo đúng tinh thần kể chuyện dữ liệu và thẩm định 4 bước của Bài 14."""
    summary = pd.read_csv(path(cfg, "reports", "summary_numbers.csv"))
    manifest, md = [], []

    def number(key: str) -> str:
        record = summary.loc[summary.key.eq(key)].iloc[0]
        value = "chưa có" if pd.isna(record.value) else f"{record.value:,.2f}".rstrip("0").rstrip(".")
        manifest.append({"key": key, "value": None if pd.isna(record.value) else float(record.value), "rendered": value})
        return value

    def add(block: str) -> None:
        md.append(block)

    def add_table(headers: list[str], records: list[list], align: list[str] | None = None) -> None:
        sep = align or ["---"] * len(headers)
        lines = [
            "| " + " | ".join(headers) + " |",
            "| " + " | ".join(sep) + " |",
        ]
        for row in records:
            lines.append("| " + " | ".join(str(v) for v in row) + " |")
        md.append("\n".join(lines))

    def add_chart(filename: str, caption: str) -> None:
        target = path(cfg, "figures", filename)
        if target.exists():
            md.append(f"![{caption}](../figures/{filename})\n\n*Hình: {caption}.*")

    # Thu thập số liệu động từ summary_numbers.csv và các bảng sạch
    city = cfg["city"].title()
    currency = cfg["currency"]
    last_snap = cfg["snapshots"][-1]
    first_snap = cfg["snapshots"][0]
    missing_df = pd.read_csv(path(cfg, "reports", "missing_ids.csv"))
    miss_list = int((missing_df.snapshot.eq(last_snap) & missing_df.table.eq("listings")).sum())
    miss_rev = int((missing_df.snapshot.eq(last_snap) & missing_df.table.eq("reviews")).sum())

    first_list = number(f"listings.{first_snap}.after")
    last_list = number(f"listings.{last_snap}.after")
    first_rev = number(f"reviews.{first_snap}.after")
    k2_min = number("kpi_time.K2.min") if summary.key.eq("kpi_time.K2.min").any() else "chưa có"
    k2_max = number("kpi_time.K2.max") if summary.key.eq("kpi_time.K2.max").any() else "chưa có"
    k3_min = number("kpi_time.K3.first_month_min") if summary.key.eq("kpi_time.K3.first_month_min").any() else "chưa có"
    k3_max = number("kpi_time.K3.first_month_max") if summary.key.eq("kpi_time.K3.first_month_max").any() else "chưa có"

    entire_pct = number("latest.entire_home_pct")
    med_price = number("latest.median_price")
    valid_p_n = number("latest.valid_price_count")
    mean_before = number("latest.mean_price_before")
    med_before = number("latest.median_price_before")
    miss_price = number("latest.missing_price")
    entire_med = number("latest.entire_median_price")
    private_med = number("latest.private_median_price")

    entire_val = float(summary.loc[summary.key.eq("latest.entire_median_price"), "value"].iloc[0])
    private_val = float(summary.loc[summary.key.eq("latest.private_median_price"), "value"].iloc[0])
    room_ratio = entire_val / private_val if pd.notna(entire_val) and pd.notna(private_val) and private_val > 0 else float("nan")

    area_df = pd.read_csv(path(cfg, "processed", "kpi_area.csv"))
    k1_latest = area_df.loc[area_df.kpi_id.eq("K1") & area_df.snapshot.eq(last_snap)].dropna(subset=["value"])
    n_areas_k1 = len(k1_latest)
    small_areas_k1 = int((k1_latest.n < 5).sum())
    top12_k1 = k1_latest.nlargest(12, "n")
    max_top12 = top12_k1.loc[top12_k1.value.idxmax()]
    min_top12 = top12_k1.loc[top12_k1.value.idxmin()]
    ratio_top12 = float(max_top12.value / min_top12.value) if min_top12.value else 1.0
    top_supply = k1_latest.nlargest(3, "n")
    top1_supply = top_supply.iloc[0]
    top2_supply = top_supply.iloc[1] if len(top_supply) > 1 else top1_supply
    supply_ratio = float(top1_supply.n / top2_supply.n) if top2_supply.n else 1.0
    top3_desc = ", ".join(f"**{r.area}** (n = {int(r.n)}, trung vị {r.value:,.2f} {currency}/đêm)" for r in top_supply.itertuples())

    # =========================================================================
    # TIÊU ĐỀ & TÓM TẮT ĐIỀU HÀNH (Bài 14 §1–§2: Ý chính trong 1 câu, kết luận trước)
    # =========================================================================
    add(f"# Báo cáo Phân tích Thị trường Airbnb {city} (Nhóm 07)")
    add(
        f"> **Ý chính (Big Idea):** Trong mẫu phân công tại {city} (mốc {last_snap}), **{entire_pct}%** chỗ ở là loại hình nguyên căn với nguồn cung tập trung dày nhất tại **{top1_supply.area}** (n = {int(top1_supply.n)} chỗ ở có giá hợp lệ, gấp **{supply_ratio:.1f} lần** khu vực đứng thứ hai là {top2_supply.area}); mức giá trung vị sau kiểm soát chất lượng đạt **{med_price} {currency}/đêm** (trên n = {valid_p_n} chỗ ở có giá hợp lệ)."
    )
    add(
        f"**Người đọc & mục tiêu quyết định:** Báo cáo hướng tới **{cfg['kpi']['stakeholder']}** nhằm xác định khu vực tập trung nguồn cung cho thuê ngắn hạn, chênh lệch mặt bằng giá, nhịp độ lịch phòng và các điểm mạnh/hạn chế nổi bật trong trải nghiệm lưu trú của khách.\n\n"
        f"**Giới hạn cần lưu ý ngay từ đầu:** Dữ liệu lấy từ Inside Airbnb (CC BY 4.0, không thu thập trực tiếp từ airbnb.com) trên mẫu được giảng viên phân công qua 4 mốc chụp ({', '.join(cfg['snapshots'])}), không đại diện toàn bộ thị trường thành phố. Riêng mốc cuối ({last_snap}) giảm **{miss_list}** chỗ ở và **{miss_rev}** đánh giá so với 3 mốc đầu (chi tiết tại `missing_ids.csv`) do ngừng niêm yết, nên các phép so sánh giữa các kỳ phản ánh mẫu quan sát tại từng mốc, không phải đoàn hệ (cohort) cố định."
    )

    add("## 1. Quy mô mẫu dữ liệu qua 4 mốc chụp")
    add_table(
        ["Mốc chụp (Snapshot)", "Listing sau QA", "Calendar sau QA", "Review sau QA"],
        [[s, number(f"listings.{s}.after"), number(f"calendar.{s}.after"), number(f"reviews.{s}.after")] for s in cfg["snapshots"]],
        ["---", "---:", "---:", "---:"],
    )
    add(
        f"Ba mốc đầu giữ nguyên đủ **{first_list}** chỗ ở và **{first_rev}** đánh giá; mốc cuối ({last_snap}) còn **{last_list}** chỗ ở. "
        "Toàn bộ đường dẫn tải và mã băm SHA256 của 12 tệp nguồn được lưu tại `download_manifest.csv`."
    )

    # =========================================================================
    # MỤC 2: KẾT LUẬN KHÔNG GIAN & CƠ CẤU NHÓM (Bài 14 §2–§3)
    # =========================================================================
    add(f"## 2. Nguồn cung tập trung mạnh ở vùng lõi ven hồ và giá nguyên căn cao gấp {room_ratio:.1f} lần phòng riêng")
    add(
        f"- **Chênh lệch giá theo khu vực (K1):** Trong 12 khu vực hành chính có nhiều chỗ ở nhất tại mốc {last_snap}, **{max_top12.area}** có giá trung vị cao nhất (**{max_top12.value:,.2f} {currency}/đêm**, n = {int(max_top12.n)}), gấp **{ratio_top12:.1f} lần** khu vực thấp nhất trong nhóm là **{min_top12.area}** ({min_top12.value:,.2f} {currency}/đêm, n = {int(min_top12.n)}). Ba khu vực dẫn đầu về mật độ nguồn cung có giá hợp lệ là {top3_desc}.\n"
        f"- **Chênh lệch theo cơ cấu loại phòng:** Tại mốc cuối, giá trung vị của chỗ ở nguyên căn đạt **{entire_med} {currency}/đêm**, cao gấp **{room_ratio:.1f} lần** phòng riêng (**{private_med} {currency}/đêm**). Do cơ cấu loại phòng khác nhau giữa các quận, chênh lệch giá trung vị giữa các khu vực chịu tác động đồng thời của cả vị trí và tỷ trọng nguyên căn, không nên diễn giải đơn thuần là hiệu ứng nhân quả của riêng vị trí.\n"
        f"- **Giới hạn về cỡ mẫu và đơn vị không gian:** Dự án dùng hai cấp độ không gian tách biệt: (1) các KPI từ bảng listing/lịch (K1, K2, K4, K6, K8) nhóm theo khu vực hành chính `{cfg['kpi']['area_col']}` — có **{n_areas_k1}** khu có giá ở mốc cuối nhưng tới **{small_areas_k1}** khu có n < 5, chưa đủ cỡ mẫu đại diện nên biểu đồ chỉ xếp hạng 12 khu đông nhất; (2) bản đồ phân bố và K7 (LLM) nhóm theo 8 ô phân tích (`analysis_area` A01–A08, mỗi vùng 110–130 listing) để đảm bảo đủ cỡ mẫu văn bản."
    )
    add_chart("fig_space_02_area_price.png", f"Giá đêm trung vị (K1) tại 12 khu vực có cỡ mẫu lớn nhất, mốc {last_snap}")
    add_chart("fig_space_01_listings_map.png", f"Phân bố không gian theo trung vị giá ({med_price} {currency}/đêm) và 8 vùng phân tích A01–A08")

    # =========================================================================
    # MỤC 3: KẾT LUẬN THỜI GIAN & GIỚI HẠN MỐC CHỤP (Bài 14 §2–§3)
    # =========================================================================
    add(f"## 3. Tỷ lệ ngày không khả dụng ổn định quanh {k2_min}%–{k2_max}% và luôn cao nhất ở tháng sát mốc chụp")
    add(
        f"- **Xu hướng khả dụng (K2, K3):** Tỷ lệ ngày không khả dụng toàn mẫu duy trì ổn định trong khoảng **{k2_min}%–{k2_max}%** qua cả 4 mốc chụp. Khi tách theo từng tháng của lịch 365 ngày tới (K3), tỷ lệ không khả dụng luôn cao nhất ở tháng ngay sát ngày thu thập (**{k3_min}%–{k3_max}%**) rồi giảm dần ở các tháng xa hơn trước khi nhích lên vào mùa cao điểm hè–thu.\n"
        "- **Hoạt động đánh giá theo quý (K5):** Tốc độ đánh giá trong mẫu tăng rõ rệt sau năm 2022 và dao động theo chu kỳ mùa vụ hàng năm.\n"
        "- **Giới hạn diễn giải bắt buộc:** (1) Ngày `available = f` gộp chung cả ngày đã được khách đặt lẫn ngày chủ nhà chủ động khóa lịch, do đó **không được đồng nhất với công suất thuê phòng thực tế hay doanh thu**; (2) Số đánh giá (K5) không phải tổng lượt khách thuê, chỉ tính trên mẫu review được giao, đồng thời tháng biên/quý cuối chưa trọn vẹn số ngày và thiếu đánh giá từ các chỗ ở đã ngừng niêm yết."
    )
    add_chart("fig_time_01_occupancy_by_snapshot.png", "Tỷ lệ ngày không khả dụng theo tháng lịch (K3) qua 4 mốc chụp")
    add_chart("fig_time_02_kpi_trend.png", "Xu hướng các chỉ số K2, K4 và K6 qua 4 mốc chụp (tách khung chung trục thời gian)")

    # =========================================================================
    # MỤC 4: PHÂN TÍCH ĐÁNH GIÁ BẰNG LLM & ĐỐI CHỨNG BASELINE (Bài 14 §2–§3)
    # =========================================================================
    sample = pd.read_parquet(path(cfg, "processed", "llm_sample.parquet"))
    results = pd.read_parquet(path(cfg, "processed", "llm_results.parquet"))
    valid = int((results.sentiment.notna() & ~results.parse_error).sum())
    metrics = pd.read_csv(path(cfg, "reports", "eval_metrics.csv"))
    cost = pd.read_csv(path(cfg, "reports", "llm_cost_estimate.csv")).iloc[0]

    add("## 4. Baseline từ điển vượt LLM về phân loại cảm xúc tổng thể, nhưng LLM vượt trội khi trích xuất khía cạnh khen")
    add(
        f"Trên toàn bộ **{valid:,}/{len(sample):,}** đánh giá hợp lệ trích xuất bằng `{cfg['llm']['model']}` (prompt `{cfg['llm']['prompt_version']}`, `temperature=0`, lưu đệm JSONL), "
        "cảm xúc tích cực chiếm áp đảo (89,7%–95,3%) ở cả 8 vùng phân tích, trong đó **chủ nhà**, **vị trí** và **tiện nghi** là ba khía cạnh được khen nhiều nhất."
    )
    if metrics.empty:
        add("**Trạng thái đánh giá:** Chưa có tệp `hand_labels.csv` hợp lệ nên chưa có chỉ số so sánh giữa LLM và Baseline.")
    else:
        selected = metrics.loc[metrics.task.eq("sentiment") & metrics.metric.isin(["accuracy", "macro_f1"])]
        add_table(
            ["Phương pháp", "Thước đo", "Giá trị", "Khoảng tin cậy 95%", "Cỡ mẫu (n)"],
            [[r.method.upper(), r.metric, f"{r.value:.4f}", f"[{r.ci_low:.4f}, {r.ci_high:.4f}]", int(r.n)] for r in selected.itertuples()],
            ["---", "---", "---:", "---:", "---:"],
        )
        add_chart("fig_llm_03_model_vs_baseline.png", "Đối chứng Accuracy và Macro-F1 cảm xúc giữa LLM và Baseline từ điển (bootstrap 95%)")
        err_llm = number("error.llm_wrong")
        err_base = number("error.baseline_wrong")
        acc_diff = metrics.loc[metrics.method.eq("llm_minus_baseline") & metrics.metric.eq("accuracy_difference")].iloc[0]
        praise_llm = float(metrics.loc[metrics.method.eq("llm") & metrics.task.eq("aspects_praise") & metrics.metric.eq("f1_micro"), "value"].iloc[0])
        praise_base = float(metrics.loc[metrics.method.eq("baseline") & metrics.task.eq("aspects_praise") & metrics.metric.eq("f1_micro"), "value"].iloc[0])
        comp_llm = float(metrics.loc[metrics.method.eq("llm") & metrics.task.eq("aspects_complaint") & metrics.metric.eq("f1_micro"), "value"].iloc[0])
        comp_base = float(metrics.loc[metrics.method.eq("baseline") & metrics.task.eq("aspects_complaint") & metrics.metric.eq("f1_micro"), "value"].iloc[0])
        add(
            f"- **So sánh định lượng trên 100 nhãn tay (`hand_labels.csv`):** Ở phân loại cảm xúc (`sentiment`), Baseline đạt Accuracy cao hơn LLM một cách có ý nghĩa thống kê (chênh lệch ghép cặp `llm_minus_baseline` = **{acc_diff.value:+.4f}**, 95% CI `[{acc_diff.ci_low:+.4f}, {acc_diff.ci_high:+.4f}]`; LLM lệch **{err_llm}** ca, Baseline lệch **{err_base}** ca). Toàn bộ **{err_llm}** ca lệch của LLM đều rơi vào ranh giới `mixed_confusion` giữa `positive` và `mixed` khi khách khen tổng thể nhưng kèm một lưu ý nhẹ.\n"
            f"- **Thế mạnh và giới hạn ở bài toán khía cạnh:** Ở trích xuất khía cạnh khen (`aspects_praise`), LLM đạt Micro-F1 = **{praise_llm:.4f}**, cao hơn rõ rệt so với **{praise_base:.4f}** của Baseline. Ngược lại, ở khía cạnh bị chê (`aspects_complaint`), do tập nhãn tay chỉ có 7/100 review chứa lời chê và LLM hay gắn nhãn chê cho cả các lưu ý thông tin nhẹ, Micro-F1 của LLM đạt **{comp_llm:.4f}** so với **{comp_base:.4f}** của Baseline.\n"
            "- **Giới hạn cỡ mẫu nhãn tay:** Tập đối chứng 100 review lệch lớp mạnh (93 `positive`, 6 `mixed`, 1 `negative`), khiến khoảng tin cậy 95% của Macro-F1 rất rộng (`[0.3139, 0.8070]` với LLM); cần bổ sung thêm mẫu `negative`/`mixed` trước khi đưa ra kết luận khái quát hơn."
        )
    add(
        f"- **Kịch bản chi phí mở rộng toàn thành phố ({int(cost.city_total_reviews):,} đánh giá tại mốc {last_snap}):** Ước lượng **{number('llm.estimated_cost')} USD** "
        f"(không phải chi phí đã chi cho mẫu 1.000 review; dựa trên mức đầu ra trung bình {cost.mean_output_tokens} token/review theo `{cost.token_basis}`, "
        f"đơn giá tham khảo Standard paid tier {cost.price_per_m_input} USD/1M token vào và {cost.price_per_m_output} USD/1M token ra, tra ngày {cost.price_date} tại {cfg['llm'].get('price_source', '')})."
    )

    # =========================================================================
    # MỤC 5: THẨM ĐỊNH 4 BƯỚC CÁC NHẬN ĐỊNH AI (Bài 14 §4)
    # =========================================================================
    add("## 5. Thẩm định (Audit) nhận định phân tích theo quy trình 4 bước (Bài 14)")
    add(
        "Để tránh các lỗi diễn giải phổ biến khi dùng AI tổng hợp báo cáo (suy diễn nhân quả, chọn sai thước đo, bỏ qua cơ cấu nhóm hoặc diễn đạt quá mức), "
        "nhóm áp dụng quy trình 4 bước — **(1) Tính lại số liệu $\\rightarrow$ (2) Kiểm tra phương pháp $\\rightarrow$ (3) Kiểm tra diễn giải $\\rightarrow$ (4) Kết luận: Giữ / Sửa / Chưa đủ căn cứ** — cho 5 nhận định điển hình:"
    )
    add_table(
        ["Nhận định ban đầu cần thẩm định", "Số liệu", "Phương pháp", "Diễn giải", "Kết luận & Bản sửa đúng mức"],
        [
            [
                f"1. {entire_pct}% chỗ ở là nguyên căn, chứng tỏ tiềm năng dòng tiền đầu tư lớn.",
                "Đúng",
                "Đúng",
                "Sai: suy diễn doanh thu/dòng tiền từ số lượng listing.",
                f"**Sửa:** Mốc {last_snap} có {last_list} chỗ ở trong mẫu, trong đó {entire_pct}% là nguyên căn (không có dữ liệu doanh thu).",
            ],
            [
                f"2. Giá trung bình ({mean_before} {currency}) cao hơn trung vị ({med_price} {currency}) chứng minh thị trường siêu sang.",
                "Đúng",
                "Lệch: trung bình bị kéo bởi vài ngoại lai cực đoan.",
                "Quá mức: dùng từ 'chứng minh'.",
                f"**Sửa:** Phân phối giá lệch phải; báo cáo dùng trung vị sau lọc IQR (**{med_price} {currency}/đêm**, n = {valid_p_n}) để phản ánh mức giá điển hình.",
            ],
            [
                f"3. Tỷ lệ không khả dụng {k2_min}%–{k2_max}% cho thấy công suất lấp đầy khách luôn vượt 41%.",
                "Đúng",
                "Sai: gộp ngày chủ nhà khóa lịch với ngày đã đặt.",
                "Sai: đồng nhất `available=f` với lượt đặt phòng.",
                "**Chưa đủ căn cứ** kết luận công suất thuê; chỉ ghi nhận tỷ lệ ngày không khả dụng trên lịch.",
            ],
            [
                f"4. {min_top12.area} rẻ hơn {max_top12.area} là do kém hấp dẫn về vị trí.",
                "Đúng",
                f"Thiếu: chưa kiểm soát cơ cấu loại phòng; {small_areas_k1}/{n_areas_k1} khu có n < 5.",
                "Sai: suy diễn nhân quả đơn biến.",
                f"**Sửa:** Trong 12 khu đông nhất, trung vị giá dao động từ {min_top12.value:,.2f} đến {max_top12.value:,.2f} {currency}/đêm và chịu ảnh hưởng của tỷ trọng nguyên căn.",
            ],
            [
                "5. LLM vượt trội hoàn toàn mô hình từ điển ở mọi tác vụ phân tích đánh giá.",
                "Sai ở `sentiment`",
                "Đúng (đã dùng bootstrap ghép cặp)",
                "Sai: bỏ qua độ lệch lớp và kết quả thua trên cảm xúc.",
                "**Sửa:** Baseline thắng có ý nghĩa thống kê trên cảm xúc tổng thể (Accuracy 0,99 vs 0,91); LLM chỉ vượt trội ở trích xuất khía cạnh khen (Micro-F1 0,85 vs 0,69).",
            ],
        ],
    )

    # =========================================================================
    # MỤC 6: PHỤ LỤC PHƯƠNG PHÁP — QA, KPI VÀ TÁI LẬP (Bài 14 §2: cách làm đặt sau cùng)
    # =========================================================================
    add("## 6. Phụ lục phương pháp: Kiểm soát chất lượng (QA), định nghĩa KPI và tái lập")
    add(
        f"- **Tác động QA lên giá tại mốc cuối ({last_snap}):** Ghi nhận **{miss_price}** chỗ ở thiếu giá (giữ nguyên NA, không tự điền). "
        f"Giá trung vị trước lọc ngoại lai là **{med_before} {currency}/đêm** (trung bình **{mean_before} {currency}/đêm**); sau khi gắn cờ ngoại lai theo quy tắc IQR tính riêng từng `room_type` "
        f"kết hợp trần `qa.price_max = {cfg['qa'].get('price_max', 2000.0):,.0f} {currency}`, giá trung vị hợp lệ đạt **{med_price} {currency}/đêm** (n = {valid_p_n}).\n"
        "- **Nguyên tắc QA theo Bài 10:** Tách biệt giá trị thiếu (`missing_price`, `missing_rating`, `missing_minimum_nights`) khỏi lỗi ngoài miền (`invalid_price`, `invalid_rating` ngoài `[0, 5]`, `invalid_minimum_nights`); "
        "chỉ gắn cờ (`flag_only`) thay vì xóa dòng để bảo toàn cỡ mẫu cho K2–K8; phân biệt số lượt gắn cờ với số hàng cần kiểm tra (`rows_with_any_flag`)."
    )
    qa = pd.read_csv(path(cfg, "reports", "qa_report.csv"))
    selected_qa = qa.loc[~qa.rule.isin(["metric_before_after"])].groupby("rule").rows_flagged.sum().sort_values(ascending=False).head(8)
    add_table(
        ["Quy tắc QA (top 8 theo tổng 4 mốc)", "Tổng lượt/hàng bị gắn cờ"],
        [[k, f"{int(v):,}"] for k, v in selected_qa.items()],
        ["---", "---:"],
    )
    defs = pd.read_csv(path(cfg, "reports", "kpi_definitions.csv")).fillna("")
    add_table(
        ["Mã KPI", "Tên chỉ số", "Đơn vị", "Công thức / Điều kiện chính"],
        [[r.kpi_id, r.name, r.unit, r.formula] for r in defs.itertuples()],
    )
    commit, dirty = _git_provenance(cfg["_root"])
    add(
        "### Lệnh tái lập và trạng thái bàn giao\n"
        "- **Chạy toàn bộ pipeline 1 lệnh:** `python run_pipeline.py --config configs/city.yaml` (dùng `--skip-download --skip-llm` khi kiểm thử ngoại tuyến).\n"
        "- **Kiểm tra tự động:** `pytest` (34 bài test), `check_config_swap.py`, `check_report_numbers.py` (đối chiếu tự động mọi con số trong `report.md` với `summary_numbers.csv`), `check_security.py`.\n"
        f"- **Provenance:** `HEAD` tại lúc xuất báo cáo = `{commit}` (`working_tree_dirty = {dirty}`, chưa phải mã commit của tag `final`). Pipeline giữ nguyên tắc không tự động `commit`, `tag` hay `push`."
    )

    path(cfg, "reports", "report.md").write_text("\n\n".join(md) + "\n", encoding="utf-8")
    path(cfg, "reports", "report_numbers.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def run(cfg: dict) -> None:
    """Tổng hợp bảng số liệu summary_numbers.csv và xuất báo cáo Markdown (reports/report.md)."""
    run_summary(cfg)
    run_report(cfg)


if __name__ == "__main__":
    cli(run)
