"""Vẽ biểu đồ từ dữ liệu đã QA, bảng KPI và kết quả đánh giá."""

import logging
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import Rectangle
from matplotlib.ticker import PercentFormatter

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.download import cli, csv_report, path, read

BLUE, ORANGE, GREEN = "#2F6B8D", "#B75924", "#347A66"
MODEL_COLORS = {"llm": BLUE, "baseline": ORANGE}
MODEL_NAMES = {"llm": "LLM", "baseline": "Đối chứng"}


def new_chart(cfg):
    """Tạo một Figure và một khung vẽ."""
    settings = cfg["viz"]
    return plt.subplots(figsize=(settings["width"], settings["height"]))


def save_chart(cfg, fig, ax, filename, title, xlabel, ylabel, detail):
    """Ghi đơn vị, phạm vi và nguồn dưới mỗi hình."""
    ax.set(title=title, xlabel=xlabel, ylabel=ylabel)
    fig.text(0.02, 0.015, detail, fontsize=8, linespacing=1.4)
    bottom = 0.12 if "\n" in detail else 0.08
    fig.tight_layout(rect=(0, bottom, 1, 1))
    target = path(cfg, "figures", filename)
    target.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(target, dpi=cfg["viz"]["dpi"])
    plt.close(fig)
    return {"figure": filename, "status": "created", "reason": ""}


def missing_chart(cfg, filename, reason):
    """Ghi rõ hình nào chưa có dữ liệu và bỏ ảnh cũ của chính hình đó."""
    path(cfg, "figures", filename).unlink(missing_ok=True)
    logging.warning("Bỏ hình %s: %s", filename, reason)
    return {"figure": filename, "status": "missing", "reason": reason}


def snapshot_source(snapshot):
    return f"Nguồn: Inside Airbnb (CC BY 4.0) · Mẫu nhóm · Mốc chụp: {snapshot}"


def plot_map(cfg, snapshot):
    """Vẽ vị trí listing và các vùng phân tích do nhóm sử dụng."""
    filename = "fig_space_01_listings_map.png"
    listings = read(cfg, "listings_clean")
    points = listings.loc[listings.snapshot.eq(snapshot)].dropna(subset=["longitude", "latitude"])
    if points.empty:
        return missing_chart(cfg, filename, f"Không có tọa độ tại mốc {snapshot}")

    fig, ax = new_chart(cfg)
    valid = points.loc[points.price.notna() & ~points.flag_outlier_price]
    other = points.drop(index=valid.index)
    ax.scatter(other.longitude, other.latitude, s=9, color="#B9C1C7", label="Không có giá hợp lệ")
    if not valid.empty:
        percentile = cfg["viz"]["price_percentile"]
        limit = valid.price.quantile(percentile)
        colored = ax.scatter(valid.longitude, valid.latitude, c=valid.price, vmax=limit,
                             s=12, alpha=0.8, cmap="viridis")
        fig.colorbar(colored, ax=ax, extend="max",
                     label=f"{cfg['currency']}/đêm (màu bão hòa tại P{percentile * 100:.0f})")
    regions = pd.read_csv(cfg["_root"] / cfg["inputs"]["areas"])
    for row in regions.itertuples():
        width, height = row.lon_max - row.lon_min, row.lat_max - row.lat_min
        ax.add_patch(Rectangle((row.lon_min, row.lat_min), width, height,
                               fill=False, edgecolor="#566169", linewidth=0.7))
        ax.text(row.lon_min + width / 2, row.lat_min + height / 2, row.area,
                ha="center", va="center", fontsize=8,
                bbox={"facecolor": "white", "alpha": 0.8, "edgecolor": "none", "pad": 1})
    if not other.empty:
        ax.legend(loc="upper left", fontsize=8)
    note = f"{snapshot_source(snapshot)}\nCó tọa độ: {len(points):,}; trong đó có giá hợp lệ: {len(valid):,}."
    return save_chart(cfg, fig, ax, filename, "Vị trí listing trong vùng mẫu (không phải địa giới)",
                      "Kinh độ", "Vĩ độ", note)


def plot_area(cfg, area, snapshot, kpi, filename, title, unit, sample_unit):
    """Xếp hạng trong tối đa 12 neighbourhood có mẫu lớn nhất."""
    rows = area.loc[area.kpi_id.eq(kpi) & area.snapshot.eq(snapshot)]
    rows = rows.dropna(subset=["area", "value", "n"]).loc[lambda data: data.n.gt(0)]
    rows = rows.sort_values(["n", "area"], ascending=[False, True]).head(12).sort_values("value")
    if rows.empty:
        return missing_chart(cfg, filename, f"Không có KPI {kpi} hợp lệ tại {snapshot}")

    fig, ax = new_chart(cfg)
    labels = [f"{row.area} (n={row.n:,})" for row in rows.itertuples()]
    ax.barh(labels, rows.value, color=BLUE)
    ax.set_xlim(left=0, right=100 if unit == "%" else None)
    if unit == "%":
        ax.xaxis.set_major_formatter(PercentFormatter(100))
    note = f"{snapshot_source(snapshot)}\nChọn theo cỡ mẫu (tối đa 12 vùng); n là số {sample_unit}."
    return save_chart(cfg, fig, ax, filename, title, unit, "Khu vực", note)


def time_axis(ax, dates=None):
    """Hiển thị ngày thật thay cho trục phân loại cách đều."""
    locator = mdates.AutoDateLocator(minticks=3, maxticks=7)
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))
    if dates is not None:
        ax.set_xticks(dates)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))


def plot_time(cfg, times):
    """Vẽ KPI theo tháng lịch, mốc chụp hoặc quý."""
    source = snapshot_source(", ".join(cfg["snapshots"]))
    snapshots = pd.to_datetime(cfg["snapshots"])
    titles = {
        "K2": "Ngày không khả dụng",
        "K4": f"Yêu cầu tối thiểu {cfg['kpi']['long_stay_nights']} đêm trở lên",
        "K6": "Chưa có review",
    }
    specs = [
        ("01_occupancy_by_snapshot", ["K3"], "Ngày không khả dụng theo tháng lịch",
         "Tháng lịch", "% ngày không khả dụng",
         "Mẫu số: ngày lịch hợp lệ; tháng đầu/cuối có thể chưa đủ. Không phải tỷ lệ đặt phòng."),
        ("02_kpi_trend", list(titles), "Ba tỷ lệ quan sát qua các mốc chụp", "Ngày mốc", "%",
         "K2 tính theo ngày lịch; K4 và K6 theo listing. Thành phần mẫu có thể đổi giữa các mốc."),
        ("03_reviews_per_quarter", ["K5"], "Review trong mẫu qua các quý", "Quý",
         "Review mẫu / listing / quý", "Chỉ tính review duy nhất; quý cuối có thể chưa đủ."),
    ]
    charts = []
    for name, kpis, title, xlabel, unit, detail in specs:
        filename = f"fig_time_{name}.png"
        rows = times.loc[times.kpi_id.isin(kpis)].dropna(subset=["value"])
        if rows.empty:
            charts.append(missing_chart(cfg, filename, f"Chưa có KPI {', '.join(kpis)}"))
            continue
        fig, ax = new_chart(cfg)
        if kpis == ["K3"] or kpis == ["K5"]:
            freq = "M" if kpis == ["K3"] else "Q"
            for snapshot, group in rows.groupby("snapshot"):
                values = group.set_index(pd.PeriodIndex(group.period, freq=freq)).value
                periods = pd.period_range(values.index.min(), values.index.max(), freq=freq)
                ax.plot(periods.to_timestamp(), values.reindex(periods), marker=".", label=snapshot)
            time_axis(ax)
        else:
            for kpi, group in rows.groupby("kpi_id"):
                values = group.set_index(pd.to_datetime(group.snapshot)).value
                ax.plot(snapshots, values.reindex(snapshots), marker="o", label=titles[kpi])
            time_axis(ax, snapshots)
        if kpis != ["K5"]:
            ax.set_ylim(0, 100)
            ax.yaxis.set_major_formatter(PercentFormatter(100))
            ax.legend(fontsize=8)
        charts.append(save_chart(cfg, fig, ax, filename, title, xlabel, unit, source + "\n" + detail))
    return charts


def plot_reviews(cfg):
    """Tách mô tả mẫu LLM khỏi đánh giá chất lượng trên nhãn tay."""
    sentiment_file = "fig_llm_01_sentiment_by_area.png"
    aspect_file = "fig_llm_02_aspects.png"
    results_file = path(cfg, "processed", "llm_results.parquet")
    if not results_file.exists():
        return [missing_chart(cfg, name, "Chưa có kết quả LLM") for name in (sentiment_file, aspect_file)]

    results = read(cfg, "llm_results")
    labels = cfg["evaluation"]["labels"]
    valid = results.loc[~results.parse_error & results.sentiment.isin(labels)]
    if valid.empty:
        return [missing_chart(cfg, name, "Chưa có dự đoán hợp lệ") for name in (sentiment_file, aspect_file)]

    sample = read(cfg, "llm_sample")
    merged = valid.merge(sample[["id", "analysis_area"]], left_on="review_id", right_on="id",
                         validate="one_to_one").dropna(subset=["analysis_area"])
    status = []
    if merged.empty:
        status.append(missing_chart(cfg, sentiment_file, "Không ghép được review hợp lệ với vùng phân tích"))
    else:
        counts = pd.crosstab(merged.analysis_area, merged.sentiment).reindex(columns=labels, fill_value=0)
        sizes = counts.sum(axis=1)
        shares = counts.div(sizes, axis=0)
        shares.index = [f"{area} (n={n:,})" for area, n in sizes.items()]
        fig, ax = new_chart(cfg)
        shares.plot.barh(stacked=True, ax=ax, color=[GREEN, "#C69843", "#A14347"][:len(labels)])
        ax.set_xlim(0, 1)
        ax.xaxis.set_major_formatter(PercentFormatter(1))
        ax.legend(title="Nhãn LLM", loc="upper left", bbox_to_anchor=(1.01, 1), fontsize=8)
        note = f"Nguồn: dự đoán LLM trên mẫu Inside Airbnb · {len(merged):,}/{len(sample):,} review ghép được và hợp lệ."
        status.append(save_chart(cfg, fig, ax, sentiment_file, "Cảm xúc theo vùng trong mẫu LLM",
                                 "% review hợp lệ", "Vùng phân tích", note))

    aspects = cfg["llm"]["aspects"]
    counts = pd.DataFrame({
        "Khen": [valid.aspects_praise.map(lambda items: aspect in items).sum() for aspect in aspects],
        "Chê": [valid.aspects_complaint.map(lambda items: aspect in items).sum() for aspect in aspects],
    }, index=[cfg["llm"].get("aspect_labels", {}).get(aspect, aspect) for aspect in aspects])
    fig, ax = new_chart(cfg)
    counts.plot.barh(ax=ax, color=[BLUE, ORANGE])
    note = f"Nguồn: dự đoán LLM trên mẫu Inside Airbnb · n = {len(valid):,} review hợp lệ; mỗi review có thể nhắc nhiều khía cạnh."
    status.append(save_chart(cfg, fig, ax, aspect_file, "Khía cạnh được khen và chê trong mẫu LLM",
                             "Số review", "Khía cạnh", note))
    return status


def plot_evaluation(cfg):
    """Đặt hai phương pháp trên cùng thang và ghi rõ cỡ mẫu nhãn tay."""
    score_file = "fig_llm_03_model_vs_baseline.png"
    matrix_files = {method: f"fig_llm_{number}_confusion_{method}.png"
                    for method, number in (("llm", "04"), ("baseline", "05"))}
    metrics_file = path(cfg, "reports", "eval_metrics.csv")
    metrics = pd.read_csv(metrics_file) if metrics_file.exists() else pd.DataFrame()
    if metrics.empty:
        return [missing_chart(cfg, name, "Chưa có kết quả đánh giá")
                for name in (score_file, *matrix_files.values())]

    rows = metrics.loc[metrics.task.eq("sentiment") & metrics.metric.isin(["accuracy", "macro_f1"])
                       & metrics.method.isin(MODEL_NAMES)].dropna(subset=["value"]).reset_index(drop=True)
    if rows.empty:
        return [missing_chart(cfg, name, "Chưa có kết quả đánh giá cảm xúc")
                for name in (score_file, *matrix_files.values())]
    fig, ax = new_chart(cfg)
    ax.bar(range(len(rows)), rows.value, color=rows.method.map(MODEL_COLORS))
    for i, row in rows.iterrows():
        if pd.notna(row.ci_low) and pd.notna(row.ci_high):
            ax.plot([i, i], [row.ci_low, row.ci_high], color="#222222", marker="_")
    names = {"accuracy": "Accuracy", "macro_f1": "Macro F1"}
    ax.set_xticks(range(len(rows)), [f"{MODEL_NAMES[r.method]}\n{names[r.metric]} (n={r.n:,})"
                                    for r in rows.itertuples()], fontsize=9)
    ax.set_ylim(0, 1)
    confidence = cfg["evaluation"]["confidence"]
    note = f"Nguồn: eval_metrics.csv · Mẫu nhãn tay · Khoảng tin cậy bootstrap {confidence:.0%} nếu có."
    status = [save_chart(cfg, fig, ax, score_file, "Accuracy và Macro F1 trên tập nhãn tay",
                         "", "Điểm (0–1)", note)]
    for method, filename in matrix_files.items():
        source = path(cfg, "reports", f"confusion_{method}.csv")
        matrix = pd.read_csv(source, index_col=0) if source.exists() else pd.DataFrame()
        if matrix.empty:
            status.append(missing_chart(cfg, filename, "Chưa có ma trận nhầm lẫn"))
            continue
        fig, ax = new_chart(cfg)
        values = matrix.to_numpy()
        scale_max = max(rows.n.max(), values.max(), 1)
        image = ax.imshow(values, cmap="Blues", vmin=0, vmax=scale_max)
        ax.set_xticks(range(len(matrix.columns)), matrix.columns, rotation=15, fontsize=8)
        ax.set_yticks(range(len(matrix.index)), matrix.index, fontsize=8)
        for i, row in enumerate(values):
            for j, count in enumerate(row):
                ax.text(j, i, str(count), ha="center", va="center",
                        color="white" if count > scale_max / 2 else "#172733")
        fig.colorbar(image, ax=ax, label="Số review")
        note = f"Nguồn: {source.name} · Mẫu nhãn tay · n = {values.sum():,} review."
        status.append(save_chart(cfg, fig, ax, filename, f"Ma trận nhầm lẫn — {MODEL_NAMES[method]}",
                                 "Dự đoán", "Nhãn tay", note))
    return status


def run_figures(cfg):
    """Sinh hình theo ba góc nhìn: không gian, thời gian và LLM."""
    snapshot = max(cfg["snapshots"])
    area = pd.read_csv(path(cfg, "processed", "kpi_area.csv"))
    times = pd.read_csv(path(cfg, "processed", "kpi_time.csv"))
    figures = [
        plot_map(cfg, snapshot),
        plot_area(cfg, area, snapshot, "K1", "fig_space_02_area_price.png",
                  "Giá niêm yết trung vị theo khu vực", f"{cfg['currency']}/đêm", "listing có giá hợp lệ"),
        plot_area(cfg, area, snapshot, "K2", "fig_space_03_area_occupancy.png",
                  "Ngày không khả dụng theo khu vực", "%", "ngày lịch hợp lệ"),
        *plot_time(cfg, times),
        *plot_reviews(cfg),
        *plot_evaluation(cfg),
    ]
    csv_report(cfg, figures, "figure_status.csv")


def run_summary(cfg):
    from src.report import run_summary as summarize

    summarize(cfg)


def run_report(cfg):
    from src.report import run_report as build_report

    build_report(cfg)


def run(cfg):
    """Giữ giao diện pipeline: hình → số liệu tóm tắt → báo cáo."""
    run_figures(cfg)
    run_summary(cfg)
    run_report(cfg)


if __name__ == "__main__":
    cli(run)
