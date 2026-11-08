"""Sinh hình theo khu vực, thời gian và khía cạnh LLM từ các bảng KPI."""

from pathlib import Path

import matplotlib
import pandas as pd

matplotlib.use("Agg")
from matplotlib import pyplot as plt


def render_figures(outputs, snapshot, figures_dir, currency):
    """Ghi ba hình PNG và trả danh sách đường dẫn."""
    directory = Path(figures_dir)
    directory.mkdir(parents=True, exist_ok=True)
    paths = []

    def save(figure, filename):
        path = directory / filename
        figure.savefig(path, dpi=150, bbox_inches="tight")
        plt.close(figure)
        paths.append(str(path))

    by_area = pd.read_csv(outputs["kpi_area.csv"])
    area = by_area.loc[by_area["snapshot_date"].eq(snapshot)].dropna(subset=["median_price_cad"])
    area = area.nlargest(12, "median_price_cad").sort_values("median_price_cad")
    figure, axis = plt.subplots(figsize=(8, 5), layout="constrained")
    axis.barh(area["neighbourhood_cleansed"], area["median_price_cad"], color="#247477")
    axis.set(title=f"Giá niêm yết trung vị theo khu vực · {snapshot}",
             xlabel=f"{currency}/đêm · tối đa 12 khu vực có trung vị cao nhất")
    save(figure, "price_by_area.png")

    timeline = pd.read_csv(outputs["kpi_snapshot.csv"]).sort_values("snapshot_date")
    dates = pd.to_datetime(timeline["snapshot_date"])
    figure, axis = plt.subplots(figsize=(8, 4), layout="constrained")
    axis.plot(dates, timeline["median_price_cad"], marker="o", color="#247477")
    axis.set_xticks(dates, timeline["snapshot_date"])
    axis.set(title="Giá niêm yết trung vị theo mốc", xlabel="Mốc chụp",
             ylabel=f"{currency}/đêm")
    axis.grid(axis="y", alpha=0.25)
    save(figure, "price_over_time.png")

    aspects = pd.read_csv(outputs["kpi_llm_aspect.csv"])
    aspects = aspects.loc[aspects["snapshot_date"].eq(snapshot)].sort_values("aspect_mention_share")
    summary = pd.read_csv(outputs["kpi_llm_snapshot.csv"])
    usable = int(summary.loc[summary["snapshot_date"].eq(snapshot), "n_llm_usable"].iloc[0])
    figure, axis = plt.subplots(figsize=(8, 4), layout="constrained")
    if aspects.empty:
        axis.text(0.5, 0.5, "Chưa có khía cạnh được trích xuất", ha="center", va="center")
        axis.set_axis_off()
    else:
        axis.barh(aspects["aspect"], 100 * aspects["aspect_mention_share"], color="#A95C34")
        axis.set(xlim=(0, 100), xlabel="Tỷ lệ review dùng được nhắc đến khía cạnh (%)")
    axis.set_title(f"Khía cạnh được LLM trích xuất · {snapshot} · n={usable}")
    save(figure, "llm_aspects.png")
    return paths
