"""Đối chiếu số liệu và tạo hình riêng cho bản báo cáo biên tập."""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd
from matplotlib.patches import Rectangle
from sklearn.metrics import accuracy_score, f1_score

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from src.download import load_config, read

cfg = load_config(ROOT / "configs/city.yaml")
ASSETS = ROOT / "reports/professional_assets"
ASSETS.mkdir(exist_ok=True)
BLUE, TEAL, ORANGE, GREY = "#234E70", "#1B7A78", "#C46A35", "#8A98A6"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9,
                     "axes.spines.top": False, "axes.spines.right": False,
                     "axes.labelcolor": "#243B53", "text.color": "#172B4D",
                     "axes.titleweight": "bold", "axes.titlesize": 11,
                     "axes.axisbelow": True, "grid.alpha": .15})

def save(fig, name):
    fig.tight_layout(pad=1.2)
    fig.savefig(ASSETS / name, dpi=230, facecolor="white")
    plt.close(fig)

listings = read(cfg, "listings_clean")
latest = listings[listings.snapshot.eq(cfg["snapshots"][-1])].copy()
valid = latest[latest.price.gt(0) & ~latest.flag_outlier_price].copy()
area = pd.read_csv(ROOT / "data/processed/kpi_area.csv")
times = pd.read_csv(ROOT / "data/processed/kpi_time.csv")
metrics = pd.read_csv(ROOT / "reports/eval_metrics.csv")
gold = pd.read_csv(ROOT / "data/samples/hand_labels.csv", dtype={"review_id": str})
sample = read(cfg, "llm_sample")
results = read(cfg, "llm_results")
base = read(cfg, "baseline_results")
llm = results[~results.parse_error & results.sentiment.notna()]

for name, predicted in (("llm", results), ("baseline", base)):
    joined = gold[["review_id", "sentiment"]].merge(
        predicted[["review_id", "sentiment"]], on="review_id", validate="one_to_one", suffixes=("_gold", "_pred"))
    assert len(joined) == 100
    for metric, value in (("accuracy", accuracy_score(joined.sentiment_gold, joined.sentiment_pred)),
                          ("macro_f1", f1_score(joined.sentiment_gold, joined.sentiment_pred,
                                               labels=cfg["evaluation"]["labels"], average="macro", zero_division=0))):
        expected = metrics.loc[metrics.method.eq(name) & metrics.task.eq("sentiment") & metrics.metric.eq(metric), "value"].iloc[0]
        assert abs(value - expected) < 1e-10, (name, metric)

k1 = area[area.snapshot.eq(cfg["snapshots"][-1]) & area.kpi_id.eq("K1")].dropna(subset=["value"])
recomputed = valid.groupby("neighbourhood_cleansed").price.agg(["median", "count"])
for row in k1.itertuples():
    assert abs(recomputed.loc[row.area, "median"] - row.value) < 1e-8
    assert recomputed.loc[row.area, "count"] == row.n
assert len(latest) == 928 and len(valid) == 783 and latest.price.isna().sum() == 114
assert abs(valid.price.median() - 201.07) < 1e-8

top = k1.sort_values(["n", "area"], ascending=[False, True]).head(12).sort_values("value")
fig, ax = plt.subplots(figsize=(7.25, 3.65))
bars = ax.barh(top.area, top.value, color=[ORANGE if x == top.value.max() else BLUE for x in top.value])
ax.bar_label(bars, labels=[f"{r.value:,.2f}  (n={int(r.n)})" for r in top.itertuples()], fontsize=8, padding=4)
ax.set(xlim=(0, top.value.max()*1.42), xlabel="Giá trung vị (CAD/đêm)")
ax.tick_params(axis="y", labelsize=8)
ax.grid(axis="x")
save(fig, "01_area_price.png")

fig, ax = plt.subplots(figsize=(7.25, 2.45))
room_order = ["Private room", "Entire home/apt"]
ax.boxplot([valid.loc[valid.room_type.eq(x), "price"].to_numpy() for x in room_order],
           orientation="horizontal",
           showfliers=False, patch_artist=True,
           boxprops={"facecolor": "#D9EAF1", "edgecolor": BLUE},
           medianprops={"color": ORANGE, "linewidth": 2}, whiskerprops={"color": BLUE}, capprops={"color": BLUE})
ax.set_yticks([1, 2], ["Phòng riêng (n=112)", "Nguyên căn (n=671)"])
ax.set(xlabel="Giá hợp lệ sau QA (CAD/đêm)", xlim=(0, None))
ax.grid(axis="x")
save(fig, "02_room_distribution.png")

fig, ax = plt.subplots(figsize=(7.25, 2.8))
other = latest[latest.price.isna() | latest.flag_outlier_price]
ax.scatter(other.longitude, other.latitude, color="#C5CED6", s=8, alpha=.65, label="Thiếu giá / bị cờ giá")
lo, hi = valid[valid.price.le(valid.price.median())], valid[valid.price.gt(valid.price.median())]
ax.scatter(lo.longitude, lo.latitude, color=BLUE, s=9, alpha=.65, label="Giá ≤ 201,07 CAD/đêm")
ax.scatter(hi.longitude, hi.latitude, color=ORANGE, s=9, alpha=.65, label="Giá > 201,07 CAD/đêm")
for row in pd.read_csv(ROOT / cfg["inputs"]["areas"]).itertuples():
    ax.add_patch(Rectangle((row.lon_min, row.lat_min), row.lon_max-row.lon_min, row.lat_max-row.lat_min,
                           fill=False, linewidth=.6, edgecolor=GREY, linestyle="--"))
    ax.text((row.lon_min+row.lon_max)/2, (row.lat_min+row.lat_max)/2, row.area, fontsize=6.5,
            ha="center", bbox={"facecolor":"white", "edgecolor":"none", "alpha":.8, "pad":.5})
ax.set(xlabel="Kinh độ", ylabel="Vĩ độ")
ax.set_aspect(1 / np.cos(np.deg2rad(latest.latitude.mean())))
ax.legend(loc="upper center", bbox_to_anchor=(.5, 1.25), ncol=3, fontsize=7, frameon=False)
save(fig, "03_spatial_sample.png")

fig, axes = plt.subplots(3, 1, sharex=True, figsize=(7.25, 3.25))
for ax, key, name, color in zip(axes, ["K2", "K4", "K6"], ["K2 · Không khả dụng (%)", "K4 · Tối thiểu ≥ 30 đêm (%)", "K6 · Chưa có review (%)"], [BLUE, TEAL, ORANGE]):
    subset = times[times.kpi_id.eq(key)].sort_values("snapshot")
    dates = pd.to_datetime(subset.snapshot)
    ax.plot(dates, subset.value, color=color, marker="o", markersize=4)
    for day, value in zip(dates, subset.value):
        ax.annotate(f"{value:.2f}", (day,value), xytext=(0,5), textcoords="offset points", ha="center", fontsize=8)
    ax.set_ylim(0, max(subset.value.max()*1.35, 5))
    ax.text(.01,.89,name,transform=ax.transAxes,fontsize=8,va="top")
    ax.grid(axis="y")
axes[-1].set_xticks(pd.to_datetime(cfg["snapshots"]))
axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%d/%m/%Y"))
save(fig, "04_snapshot_trends.png")

fig, ax = plt.subplots(figsize=(7.25, 2.7))
for snapshot, subset in times[times.kpi_id.eq("K3")].groupby("snapshot"):
    ax.plot(pd.to_datetime(subset.period), subset.value, marker=".", label=snapshot)
ax.set(xlabel="Tháng của ngày lịch", ylabel="Ngày không khả dụng (%)", ylim=(0,100))
loc = mdates.AutoDateLocator(minticks=4,maxticks=7)
ax.xaxis.set_major_locator(loc)
ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(loc))
ax.legend(title="Mốc chụp", loc="upper right", fontsize=7, title_fontsize=7, frameon=False)
ax.grid(axis="y")
save(fig, "05_calendar_months.png")

fig, ax = plt.subplots(figsize=(7.25, 2.9))
for method, offset, color, label in (("llm",-.17,BLUE,"Gemini (LLM)"),("baseline",.17,ORANGE,"Keyword Baseline")):
    data = metrics[metrics.method.eq(method)&metrics.task.eq("sentiment")].set_index("metric").loc[["accuracy","macro_f1"]]
    positions=np.arange(2)+offset
    bars=ax.bar(positions,data.value,width=.30,color=color,label=label)
    for i, (_, row) in enumerate(data.iterrows()):
        ax.plot([positions[i],positions[i]],[row.ci_low,row.ci_high],color="#172B4D",lw=1)
        ax.scatter([positions[i],positions[i]],[row.ci_low,row.ci_high],marker="_",color="#172B4D",s=40)
        ax.text(positions[i],max(row.value,row.ci_high)+.025,f"{row.value:.3f}",ha="center",fontsize=8)
ax.set(xticks=[0,1],xticklabels=["Accuracy","Macro-F1"],ylim=(0,1.15),ylabel="Điểm (0-1)")
ax.legend(loc="upper center",bbox_to_anchor=(.5,1.17),ncol=2,fontsize=8,frameon=False)
ax.grid(axis="y")
save(fig,"06_model_vs_baseline.png")

aspects = cfg["llm"]["aspects"]
counts={key:[int(llm[key].map(lambda values: aspect in values).sum()) for aspect in aspects]
        for key in ("aspects_praise","aspects_complaint")}
fig, ax = plt.subplots(figsize=(7.25, 2.85))
y=np.arange(len(aspects))
for key,offset,color,label in (("aspects_praise",-.17,BLUE,"Khen"),("aspects_complaint",.17,ORANGE,"Chê")):
    bars=ax.barh(y+offset,counts[key],height=.30,color=color,label=label)
    ax.bar_label(bars,fontsize=8,padding=3)
ax.set(yticks=y,yticklabels=[cfg["llm"]["aspect_labels"][a] for a in aspects],xlabel="Số review nhắc đến khía cạnh",xlim=(0,max(counts["aspects_praise"])*1.12))
ax.invert_yaxis()
ax.legend(loc="lower right",fontsize=8,frameon=False)
ax.grid(axis="x")
save(fig,"07_aspects.png")

summary = pd.read_csv(ROOT/"reports/summary_numbers.csv")
assert abs(summary.set_index("key").loc["latest.median_price","value"]-valid.price.median())<1e-8
facts={
    "latest_count":len(latest),"latest_valid_price":len(valid),"median_price":float(valid.price.median()),
    "full_supply":latest.neighbourhood_cleansed.value_counts().head(5).to_dict(),
    "valid_supply":valid.neighbourhood_cleansed.value_counts().head(5).to_dict(),
    "room_counts":latest.room_type.value_counts().to_dict(),
    "room_prices":valid.groupby("room_type").price.agg(["count","median"]).to_dict(),
    "price_missing":int(latest.price.isna().sum()),"price_flagged_nonmissing":int((latest.flag_outlier_price&latest.price.notna()).sum()),
    "room_mean_before":float(latest.loc[latest.price.gt(0),"price"].mean()),
    "room_median_before":float(latest.loc[latest.price.gt(0),"price"].median()),
    "gold_classes":gold.sentiment.value_counts().to_dict(),
    "gold_complaint_reviews":sum(bool(json.loads(x)) for x in gold.aspects_complaint),
    "aspect_counts":counts,
    "cache_models":results.model.value_counts().to_dict(),
    "valid_results":len(llm),"sample_count":len(sample),
    "source_commit":"b166756",
    "checks":["K1 recomputed from listing-level prices", "Accuracy and macro-F1 recomputed from predictions and gold", "Price coverage reconciled: 114 + 31 + 783 = 928"]
}
(ROOT/"tmp/report_build").mkdir(parents=True, exist_ok=True)
(ROOT/"tmp/report_build/facts.json").write_text(json.dumps(facts,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(facts,ensure_ascii=False,indent=2))
