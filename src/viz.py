"""Sinh bộ 11 biểu đồ trực quan theo 5 điểm kiểm tra của Bài 12 và Bài 13."""
import logging
from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Rectangle

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.download import read, path, cli


XANH, CAM, XAM = "#1E93AB", "#E8890C", "#9a9a9a"


def run_figures(cfg: dict) -> None:
    """Sinh hình tự giải thích được theo 5 điểm kiểm tra của Bài 12 & Bài 13:
    1. Thông điệp: tiêu đề nêu phát hiện chính (căn trái, in đậm).
    2. Trục: có nhãn và đơn vị; biểu đồ cột bắt đầu từ 0; hình so sánh dùng chung thang.
    3. Cỡ mẫu: ghi rõ n trên từng nhóm/nhãn trục.
    4. Dạng và màu: thanh ngang cho tên quận dài, bảng màu XANH/CAM nhấn điểm cực đại, điểm nhỏ + alpha cho bản đồ.
    5. Nguồn và diễn giải: ghi nguồn, mốc chụp; không suy diễn quá dữ liệu.
    """
    # Root logger của pipeline dùng INFO; hai logger thư viện này rất dài khi
    # nhúng font PDF hoặc nhận chuỗi giống ngày/số nhưng không phải lỗi dữ liệu.
    logging.getLogger("fontTools").setLevel(logging.WARNING)
    logging.getLogger("matplotlib.category").setLevel(logging.WARNING)
    plt.rcParams.update({
        "font.family": "DejaVu Sans",
        "font.size": 10,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.alpha": 0.25,
        # Nhúng font TrueType để chữ trong biểu đồ PDF vẫn là vector/searchable.
        "pdf.fonttype": 42,
    })
    listings = read(cfg, "listings_clean")
    last_snap = cfg["snapshots"][-1]
    latest = listings.loc[listings.snapshot.eq(last_snap)]
    area = pd.read_csv(path(cfg, "processed", "kpi_area.csv"))
    times = pd.read_csv(path(cfg, "processed", "kpi_time.csv"))
    statuses = []

    def figure(width=None, height=None):
        return plt.subplots(figsize=(width or cfg["viz"]["width"], height or cfg["viz"]["height"]))

    def save_pdf(fig, filename):
        """Chỉ xuất biểu đồ ở định dạng PDF vector."""
        pdf_target = path(cfg, "figures", filename).with_suffix(".pdf")
        fig.savefig(pdf_target, format="pdf", bbox_inches="tight")

    def finish(fig, ax, filename, title, xlabel, ylabel, snapshots=None, grid=True, top_pad=1.0):
        ax.set_title(title, loc="left", fontweight="bold", fontsize=10.5, pad=10)
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        ax.grid(grid)
        source = "Nguồn: Inside Airbnb (CC BY 4.0), mốc chụp " + (snapshots or ", ".join(cfg["snapshots"]))
        fig.text(0.98, 0.015, source, ha="right", fontsize=8, color="#555555")
        fig.tight_layout(rect=[0, 0.055, 1, top_pad])
        save_pdf(fig, filename)
        plt.close(fig)
        statuses.append({"figure": filename, "status": "created", "reason": ""})

    # 1. Bản đồ phân tán (Bài 12 §3: điểm nhỏ + alpha tránh overplotting, màu XANH/CAM theo trung vị giá, set_aspect equal)
    fig, ax = figure()
    valid_price = latest.loc[~latest.flag_outlier_price & latest.price.notna()].copy()
    missing_or_out = latest.loc[latest.flag_outlier_price | latest.price.isna()]
    median_p = float(valid_price.price.median()) if len(valid_price) else 0.0
    if len(missing_or_out):
        ax.scatter(
            missing_or_out.longitude, missing_or_out.latitude,
            color=XAM, s=10, alpha=0.45, linewidths=0,
            label=f"Thiếu giá / ngoại lai (n = {len(missing_or_out):,})",
        )
    low_p = valid_price.loc[valid_price.price <= median_p]
    high_p = valid_price.loc[valid_price.price > median_p]
    ax.scatter(
        low_p.longitude, low_p.latitude,
        color=XANH, s=14, alpha=0.65, linewidths=0,
        label=f"≤ trung vị {median_p:,.0f} {cfg['currency']} (n = {len(low_p):,})",
    )
    ax.scatter(
        high_p.longitude, high_p.latitude,
        color=CAM, s=14, alpha=0.65, linewidths=0,
        label=f"> trung vị {median_p:,.0f} {cfg['currency']} (n = {len(high_p):,})",
    )
    regions = pd.read_csv(cfg["_root"] / cfg["inputs"]["areas"])
    for row in regions.itertuples():
        ax.add_patch(Rectangle(
            (row.lon_min, row.lat_min), row.lon_max - row.lon_min, row.lat_max - row.lat_min,
            fill=False, edgecolor="#333333", linewidth=0.9, linestyle="--",
        ))
        ax.text(
            (row.lon_min + row.lon_max) / 2, (row.lat_min + row.lat_max) / 2, row.area,
            fontsize=8, ha="center", va="center",
            bbox={"facecolor": "white", "alpha": 0.85, "edgecolor": "none", "pad": 1},
        )
    ax.set_aspect("equal", adjustable="datalim")
    ax.legend(loc="lower right", fontsize=8, frameon=True)
    area_hi = (
        valid_price.assign(hi=valid_price.price > median_p)
        .groupby("analysis_area")["hi"]
        .mean()
        .mul(100)
        .sort_values(ascending=False)
    )
    top_areas_str = ", ".join(f"{a} ({v:.0f}%)" for a, v in area_hi.head(2).items()) if len(area_hi) else "trung tâm"
    finish(
        fig, ax, "fig_space_01_listings_map.pdf",
        f"Chỗ ở trên trung vị ({median_p:,.2f} {cfg['currency']}/đêm, cam) tập trung cao nhất tại {top_areas_str} (n = {len(latest):,})",
        "Kinh độ", "Vĩ độ", last_snap,
    )

    # 2 & 3. Thanh ngang xếp hạng K1 và K2 theo khu vực (Bài 12 §3 & Bài 13 §3: barh cho tên quận dài, tô CAM thanh cao nhất, ghi giá trị + cỡ mẫu n)
    for kid, filename, unit in (
        ("K1", "fig_space_02_area_price.pdf", f"Giá trung vị ({cfg['currency']}/đêm)"),
        ("K2", "fig_space_03_area_occupancy.pdf", "Tỷ lệ ngày không khả dụng (%)"),
    ):
        data = area.loc[area.kpi_id.eq(kid) & area.snapshot.eq(last_snap)].dropna(subset=["value"])
        data = data.nlargest(12, "n").sort_values("value")
        top_row = data.iloc[-1]
        colors_bar = [CAM if r == top_row.area else XANH for r in data.area]
        fig, ax = figure()
        bars = ax.barh(data.area, data.value, color=colors_bar, height=0.65)
        if kid == "K1":
            bar_labels = [f" {r.value:,.2f} {cfg['currency']} (n={int(r.n):,})" for r in data.itertuples()]
            msg_title = f"{top_row.area} dẫn đầu giá trung vị ({top_row.value:,.2f} {cfg['currency']}/đêm) trong 12 khu vực đông nhất"
        else:
            bar_labels = [f" {r.value:.1f}% (n={int(r.n) // cfg['io']['calendar_days']:,} listing)" for r in data.itertuples()]
            msg_title = f"{top_row.area} có tỷ lệ không khả dụng cao nhất ({top_row.value:.1f}%, không đồng nghĩa đã đặt)"
        ax.bar_label(bars, labels=bar_labels, fontsize=8)
        ax.set_xlim(0, float(data.value.max()) * 1.32 if len(data) else 1)
        finish(
            fig, ax, filename, msg_title,
            f"{unit} — 12 khu vực có cỡ mẫu n lớn nhất tại mốc {last_snap}",
            "", last_snap,
        )

    # 4. K3 theo tháng lịch (Bài 12 §2: biểu đồ đường theo thời gian, trục y từ 0, chú thích đỉnh bằng annotate)
    fig, ax = figure()
    k3_data = times.loc[times.kpi_id.eq("K3")].copy()
    palette_snap = ["#1E93AB", "#2B5B84", "#7A9A95", "#E8890C"]
    for idx, (snapshot, group) in enumerate(k3_data.groupby("snapshot")):
        dates = pd.to_datetime(group.period)
        color_line = palette_snap[idx % len(palette_snap)]
        lw = 2.2 if snapshot == last_snap else 1.5
        ax.plot(dates, group.value, marker="o", markersize=4, lw=lw, color=color_line, label=f"Mốc {snapshot}")
    first_m = k3_data.groupby("snapshot", sort=False).first()["value"].dropna() if len(k3_data) else pd.Series(dtype=float)
    k3_min_s = f"{first_m.min():.1f}%" if len(first_m) else "0%"
    k3_max_s = f"{first_m.max():.1f}%" if len(first_m) else "0%"
    if len(k3_data):
        peak_row = k3_data.loc[k3_data.value.idxmax()]
        peak_x = pd.to_datetime(peak_row.period)
        ax.annotate(
            f"Đỉnh {peak_row.period}: {peak_row.value:.1f}%",
            xy=(peak_x, peak_row.value),
            xytext=(12, -14), textcoords="offset points",
            fontsize=8, color=CAM, fontweight="bold",
            arrowprops={"arrowstyle": "->", "color": CAM, "lw": 1},
        )
    ax.set_ylim(0, min(105, float(k3_data.value.max()) * 1.2 if len(k3_data) else 100))
    ax.legend(title="Mốc chụp (Snapshot)", fontsize=8)
    finish(
        fig, ax, "fig_time_01_occupancy_by_snapshot.pdf",
        f"Tỷ lệ ngày không khả dụng cao nhất ở tháng ngay sát mốc chụp ({k3_min_s}–{k3_max_s}) rồi giảm dần",
        "Tháng của ngày lịch (tháng biên có thể chưa trọn ngày)",
        "% ngày không khả dụng",
    )

    # 5. Xu hướng K2, K4, K6 qua 4 snapshot (Bài 13 §3 sửa lỗi hình A & C: tránh nhồi các chỉ số khác quy mô vào 1 trục bị bẹt, tách 3 khung nhỏ sharex=True, trục y từ 0)
    k246 = times.loc[times.kpi_id.isin(["K2", "K4", "K6"])]
    fig, axes = plt.subplots(3, 1, sharex=True, figsize=(cfg["viz"]["width"], cfg["viz"]["height"] * 1.15))
    panel_specs = [
        ("K2", "K2: Không khả dụng (%)", XANH),
        ("K4", f"K4: Thuê ≥ {cfg['kpi']['long_stay_nights']} đêm (%)", CAM),
        ("K6", "K6: Chưa có review (%)", "#2B5B84"),
    ]
    for ax_sub, (kid, ylabel_sub, col_line) in zip(axes, panel_specs):
        sub = k246.loc[k246.kpi_id.eq(kid)].sort_values("snapshot")
        ax_sub.plot(sub.snapshot, sub.value, marker="o", color=col_line, lw=2)
        for r in sub.itertuples():
            ax_sub.annotate(
                f"{r.value:.1f}%", (r.snapshot, r.value),
                xytext=(0, 6), textcoords="offset points", ha="center", fontsize=8, color=col_line,
            )
        ax_sub.set_ylabel(ylabel_sub, fontsize=8.5)
        ax_sub.set_ylim(0, max(float(sub.value.max()) * 1.35, 5.0) if len(sub) else 10)
        ax_sub.grid(True, alpha=0.25)
    k2_vals = k246.loc[k246.kpi_id.eq("K2"), "value"]
    k4_vals = k246.loc[k246.kpi_id.eq("K4"), "value"]
    k6_vals = k246.loc[k246.kpi_id.eq("K6")].sort_values("snapshot")["value"]
    k2_rng = f"{k2_vals.min():.1f}%–{k2_vals.max():.1f}%" if len(k2_vals) else ""
    k4_rng = f"{k4_vals.min():.1f}%–{k4_vals.max():.1f}%" if len(k4_vals) else ""
    k6_chg = f"{k6_vals.iloc[0]:.1f}% xuống {k6_vals.iloc[-1]:.1f}%" if len(k6_vals) else ""
    axes[0].set_title(
        f"K2 ({k2_rng}) và K4 ({k4_rng}) ổn định; K6 giảm từ {k6_chg}",
        loc="left", fontweight="bold", fontsize=10.5,
    )
    n_first = int(listings.loc[listings.snapshot.eq(cfg["snapshots"][0]), "id"].nunique())
    n_last = int(latest["id"].nunique())
    axes[-1].set_xlabel(f"Mốc chụp (Snapshot — cỡ mẫu n={n_first:,} ở mốc đầu, n={n_last:,} ở mốc cuối)")
    source = "Nguồn: Inside Airbnb (CC BY 4.0), mốc chụp " + ", ".join(cfg["snapshots"])
    fig.text(0.98, 0.015, source, ha="right", fontsize=8, color="#555555")
    fig.tight_layout(rect=[0, 0.055, 1, 1])
    save_pdf(fig, "fig_time_02_kpi_trend.pdf")
    plt.close(fig)
    statuses.append({"figure": "fig_time_02_kpi_trend.pdf", "status": "created", "reason": ""})

    # 6. K5 review theo quý (Bài 12 §2: biểu đồ đường + annotate đỉnh + trục y từ 0)
    fig, ax = figure()
    data = times.loc[times.kpi_id.eq("K5")].copy()
    ax.plot(data.period, data.value, marker=".", color=XANH, lw=1.8)
    ax.set_ylim(0, float(data.value.max()) * 1.22 if len(data) else 1)
    if len(data):
        peak_k5 = data.loc[data.value.idxmax()]
        peak_idx = list(data.period).index(peak_k5.period)
        ax.plot(peak_idx, peak_k5.value, "o", color=CAM, markersize=6)
        ax.annotate(
            f"Đỉnh {peak_k5.period}: {peak_k5.value:.2f} (n={int(peak_k5.review_count)} review)",
            xy=(peak_idx, peak_k5.value),
            xytext=(-130, -10), textcoords="offset points",
            fontsize=8.5, color=CAM, fontweight="bold",
            arrowprops={"arrowstyle": "->", "color": CAM, "lw": 1},
        )
    step = max(1, len(data) // 16)
    tick_positions = list(range(0, len(data), step))
    ax.set_xticks(tick_positions, [data.period.iloc[i] for i in tick_positions], rotation=60, fontsize=8)
    n_unique_rev = int(data.review_count.sum()) if "review_count" in data else 0
    n_listings_k5 = int(data.n.iloc[0]) if len(data) else 0
    first_q = data.period.iloc[0] if len(data) else ""
    peak_q = data.loc[data.value.idxmax(), "period"] if len(data) else ""
    peak_v = float(data.value.max()) if len(data) else 0.0
    finish(
        fig, ax, "fig_time_03_reviews_per_quarter.pdf",
        f"Tốc độ đánh giá mẫu đạt đỉnh vào {peak_q} ({peak_v:.2f} review/listing/quý, n = {n_unique_rev:,} review)",
        f"Quý ({first_q}–{peak_q}; tổng n = {n_unique_rev:,} review duy nhất trên {n_listings_k5:,} listing; quý cuối tính đến 10/09/2025)",
        "Review mẫu / listing / quý",
    )

    # 7 & 8. Biểu đồ LLM (Bài 12 & 13: thanh ngang xếp hạng, bảng màu phân biệt khen=XANH / chê=CAM, ghi rõ n)
    results = read(cfg, "llm_results")
    valid = results.loc[~results.parse_error & results.sentiment.notna()]
    if len(valid):
        sample = read(cfg, "llm_sample")
        merged = valid.merge(sample[["id", "analysis_area"]], left_on="review_id", right_on="id")
        area_counts = merged.analysis_area.value_counts()
        grouped = (
            pd.crosstab(merged.analysis_area, merged.sentiment, normalize="index")
            .reindex(columns=cfg["evaluation"]["labels"], fill_value=0) * 100
        )
        grouped = grouped.sort_values("positive", ascending=True)
        area_labels = [f"{a} (n={int(area_counts.get(a, 0))})" for a in grouped.index]
        fig, ax = figure()
        left_acc = np.zeros(len(grouped))
        sent_colors = {"positive": XANH, "mixed": CAM, "negative": "#C0392B"}
        sent_names = {"positive": "Tích cực (positive)", "mixed": "Hỗn hợp (mixed)", "negative": "Tiêu cực (negative)"}
        for col in cfg["evaluation"]["labels"]:
            vals = grouped[col].to_numpy()
            bars = ax.barh(area_labels, vals, left=left_acc, color=sent_colors.get(col, XAM), height=0.65, label=sent_names.get(col, col))
            for bar, v in zip(bars, vals):
                if v >= 6.0:
                    ax.text(
                        bar.get_x() + bar.get_width() / 2, bar.get_y() + bar.get_height() / 2,
                        f"{v:.1f}%", ha="center", va="center", fontsize=8,
                        color="white" if col != "mixed" else "black", fontweight="bold",
                    )
            left_acc += vals
        ax.set_xlim(0, 100)
        ax.legend(loc="center left", fontsize=8.5, frameon=True)
        pos_min, pos_max = float(grouped["positive"].min()), float(grouped["positive"].max())
        finish(
            fig, ax, "fig_llm_01_sentiment_by_area.pdf",
            f"Cảm xúc tích cực chiếm áp đảo ({pos_min:.1f}%–{pos_max:.1f}%) ở cả {len(grouped)} vùng phân tích (n = {len(valid):,} review)",
            "Tỷ lệ % đánh giá trong từng vùng", "Vùng phân tích (cỡ mẫu n)",
        )

        aspect_labels = cfg["llm"].get("aspect_labels", {})
        counts = pd.DataFrame({
            "Khen (praise)": [sum(a in items for items in valid["aspects_praise"]) for a in cfg["llm"]["aspects"]],
            "Chê (complaint)": [sum(a in items for items in valid["aspects_complaint"]) for a in cfg["llm"]["aspects"]],
        }, index=[f"{aspect_labels.get(a, a)} ({a})" for a in cfg["llm"]["aspects"]])
        counts = counts.sort_values("Khen (praise)", ascending=True)
        fig, ax = figure()
        y_pos = np.arange(len(counts))
        h = 0.38
        b_praise = ax.barh(y_pos + h / 2, counts["Khen (praise)"], height=h, color=XANH, label="Được khen (aspects_praise)")
        b_comp = ax.barh(y_pos - h / 2, counts["Chê (complaint)"], height=h, color=CAM, label="Bị chê (aspects_complaint)")
        ax.set_yticks(y_pos, counts.index)
        ax.bar_label(b_praise, labels=[f" {int(v):,}" for v in counts["Khen (praise)"]], fontsize=8, color=XANH)
        ax.bar_label(b_comp, labels=[f" {int(v):,}" for v in counts["Chê (complaint)"]], fontsize=8, color=CAM)
        ax.set_xlim(0, float(counts.to_numpy().max()) * 1.18 if len(counts) else 10)
        ax.legend(loc="lower right", fontsize=8.5)
        top3_praise = ", ".join(f"{idx.split(' (')[0]} ({int(val):,})" for idx, val in counts["Khen (praise)"].iloc[::-1].head(3).items())
        finish(
            fig, ax, "fig_llm_02_aspects.pdf",
            f"Ba khía cạnh được khen nhiều nhất: {top3_praise} (n = {len(valid):,} review)",
            f"Số lượng đánh giá đề cập khía cạnh (trên n = {len(valid):,} review hợp lệ)", "",
        )
    else:
        for filename in ("fig_llm_01_sentiment_by_area.pdf", "fig_llm_02_aspects.pdf"):
            statuses.append({"figure": filename, "status": "missing", "reason": "Chưa có kết quả LLM thật"})

    # 9, 10, 11. So sánh LLM vs Baseline và Ma trận nhầm lẫn (Bài 12 & 13: màu XANH cho LLM, CAM cho Baseline, heatmap Blues tuần tự cho số đếm)
    metrics = pd.read_csv(path(cfg, "reports", "eval_metrics.csv"))
    if len(metrics):
        fig, ax = figure()
        selected = metrics.loc[metrics.task.eq("sentiment") & metrics.metric.isin(["accuracy", "macro_f1"])].copy()
        n_gold = int(selected.n.iloc[0]) if len(selected) else 0
        labels = [f"{r.method.upper()} — {r.metric}" for r in selected.itertuples()]
        colors_eval = [CAM if r.method == "baseline" else XANH for r in selected.itertuples()]
        errors = np.vstack([(selected.value - selected.ci_low).clip(lower=0), (selected.ci_high - selected.value).clip(lower=0)])
        bars = ax.bar(labels, selected.value, yerr=errors, capsize=5, color=colors_eval, width=0.52)
        for bar, r in zip(bars, selected.itertuples()):
            ax.text(
                bar.get_x() + bar.get_width() / 2, min(1.06, r.ci_high + 0.03),
                f"{r.value:.2f}\n[{r.ci_low:.2f}, {r.ci_high:.2f}]",
                ha="center", va="bottom", fontsize=8, fontweight="bold",
            )
        ax.set_ylim(0, 1.18)
        llm_acc_v = float(selected.loc[selected.method.eq("llm") & selected.metric.eq("accuracy"), "value"].iloc[0])
        base_acc_v = float(selected.loc[selected.method.eq("baseline") & selected.metric.eq("accuracy"), "value"].iloc[0])
        cmp_word = "cao hơn" if base_acc_v >= llm_acc_v else "thấp hơn"
        finish(
            fig, ax, "fig_llm_03_model_vs_baseline.pdf",
            f"Baseline đạt Accuracy cảm xúc ({base_acc_v:.2f}) {cmp_word} LLM ({llm_acc_v:.2f}) trên mẫu nhãn tay (n = {n_gold})",
            f"Phương pháp / Thước đo (khoảng tin cậy bootstrap 95% trên n = {n_gold} review nhãn tay)",
            "Điểm số [0, 1]",
        )
        conf_all = pd.read_csv(path(cfg, "reports", "confusion_matrices.csv"))
        for method, number_str in (("llm", "04"), ("baseline", "05")):
            matrix = conf_all.loc[conf_all.method.eq(method)].drop(columns=["method"]).set_index("true_label")
            total_m = int(matrix.to_numpy().sum())
            correct_m = int(np.trace(matrix.to_numpy()))
            fig, ax = figure(width=8.6, height=4.8)
            image = ax.imshow(matrix.to_numpy(), cmap="Blues")
            ax.set_xticks(range(len(matrix.columns)), matrix.columns, rotation=15)
            ax.set_yticks(range(len(matrix.index)), matrix.index)
            max_val = max(1, int(matrix.to_numpy().max()))
            for i in range(len(matrix)):
                for j in range(len(matrix.columns)):
                    val = int(matrix.iloc[i, j])
                    ax.text(
                        j, i, str(val), ha="center", va="center",
                        color="white" if val > max_val / 2 else "#111111",
                        fontweight="bold" if val > 0 else "normal", fontsize=10,
                    )
            fig.colorbar(image, ax=ax, label="Số lượng đánh giá")
            finish(
                fig, ax, f"fig_llm_{number_str}_confusion_{method}.pdf",
                f"Ma trận nhầm lẫn {method.upper()}: khớp {correct_m}/{total_m} nhãn tay (n = {total_m})",
                "Nhãn dự đoán", "Nhãn tay chuẩn (Gold)", grid=False,
            )
    else:
        for filename in ("fig_llm_03_model_vs_baseline.pdf", "fig_llm_04_confusion_llm.pdf", "fig_llm_05_confusion_baseline.pdf"):
            statuses.append({"figure": filename, "status": "missing", "reason": "Chưa có nhãn tay để đánh giá"})
    for row in statuses:
        if row["status"] != "created":
            # Xóa riêng hình sinh tự động đã cũ, tránh đưa nhầm vào báo cáo lần sau.
            target = path(cfg, "figures", row["figure"])
            if target.exists():
                target.unlink()
            logging.warning("Bỏ hình %s: %s", row["figure"], row["reason"])


def run(cfg: dict) -> None:
    """Chỉ thực hiện vẽ và xuất bộ biểu đồ trực quan vào figures/."""
    run_figures(cfg)


if __name__ == "__main__":
    cli(run)
