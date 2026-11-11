"""KPI theo vùng/thời gian, luôn ghi mẫu số và phạm vi mẫu."""
import logging
import numpy as np
import pandas as pd
from .download import path, read, csv_report, cli


def compute(cfg: dict, listings: pd.DataFrame, calendar: pd.DataFrame, reviews: pd.DataFrame) -> tuple:
    """Tính K1-K6 và chỉ số khả dụng cao, không gọi đó là booking thực tế."""
    area, times = [], []
    area_col = cfg["kpi"]["area_col"]
    listing_map = listings[["id", "snapshot", area_col]].rename(columns={"id": "listing_id", area_col: "area"})
    cal = calendar.merge(listing_map, on=["listing_id", "snapshot"], how="left", validate="many_to_one")
    cal = cal.loc[cal.available.notna() & cal.date.notna() & cal.area.notna()].copy()
    cal["period"] = cal.date.dt.to_period("M").astype(str)
    for (snapshot, region), group in listings.groupby(["snapshot", area_col]):
        if snapshot == cfg["snapshots"][-1]:
            prices = group.loc[~group.flag_outlier_price & group.price.notna(), "price"]
            area.append({"snapshot": snapshot, "area": region, "kpi_id": "K1", "value": prices.median(), "unit": cfg["currency"], "currency": cfg["currency"], "n": len(prices)})
        minimum = group.loc[~group.flag_outlier_minimum_nights & group.minimum_nights.notna(), "minimum_nights"]
        for kid, value, n in (("K4", minimum.ge(cfg["kpi"]["long_stay_nights"]).mean() * 100, len(minimum)), ("K6", group.number_of_reviews.eq(0).mean() * 100, len(group))):
            area.append({"snapshot": snapshot, "area": region, "kpi_id": kid, "value": value, "unit": "%", "currency": "", "n": n})
        available = cal.loc[cal.snapshot.eq(snapshot)].groupby("listing_id").available.mean()
        valid = group.loc[group.id.isin(available.index)]
        professional = valid.id.map(available).ge(cfg["kpi"]["high_availability_ratio"]) & valid.number_of_reviews.ge(cfg["kpi"]["professional_min_reviews"])
        area.append({"snapshot": snapshot, "area": region, "kpi_id": "K8", "value": professional.mean() * 100, "unit": "%", "currency": "", "n": len(valid)})
    for (snapshot, region), group in cal.groupby(["snapshot", "area"]):
        area.append({"snapshot": snapshot, "area": region, "kpi_id": "K2", "value": (1 - group.available.astype(float).mean()) * 100, "unit": "%", "currency": "", "n": len(group)})
    for (snapshot, period), group in cal.groupby(["snapshot", "period"]):
        times.append({"snapshot": snapshot, "period": period, "kpi_id": "K3", "value": (1 - group.available.astype(float).mean()) * 100, "unit": "%", "currency": "", "n": len(group)})
    # 5.000 review được chọn sẵn: đo tốc độ trong mẫu, không ngoại suy toàn thành phố.
    unique = reviews.sort_values("snapshot").drop_duplicates("id", keep="last").copy()
    unique = unique.loc[unique.date.notna()]
    unique["period"] = unique.date.dt.to_period("Q").astype(str)
    denominator = listings.id.nunique()
    for period, group in unique.groupby("period"):
        times.append({"snapshot": "pooled_unique_review_sample", "period": period, "kpi_id": "K5", "value": len(group) / denominator, "unit": "sample reviews/listing/quarter", "currency": "", "n": denominator, "review_count": len(group)})
    for snapshot, group in listings.groupby("snapshot"):
        available = cal.loc[cal.snapshot.eq(snapshot), "available"]
        minimum = group.loc[~group.flag_outlier_minimum_nights & group.minimum_nights.notna(), "minimum_nights"]
        for kid, value, n in (("K2", (1 - available.astype(float).mean()) * 100, len(available)), ("K4", minimum.ge(cfg["kpi"]["long_stay_nights"]).mean() * 100, len(minimum)), ("K6", group.number_of_reviews.eq(0).mean() * 100, len(group))):
            times.append({"snapshot": snapshot, "period": snapshot, "kpi_id": kid, "value": value, "unit": "%", "currency": "", "n": n})
    return pd.DataFrame(area), pd.DataFrame(times)


def llm_kpi(cfg: dict, reviews: pd.DataFrame, listings: pd.DataFrame) -> pd.DataFrame:
    """Chỉ dùng dự đoán hợp lệ, có mapping vùng từ mẫu ID để tránh mất listing cuối kỳ."""
    columns = ["area", "kpi_id", "aspect", "value", "unit", "n"]
    source = path(cfg, "processed", "llm_results.parquet")
    if not source.exists():
        return pd.DataFrame(columns=columns)
    result = pd.read_parquet(source)
    result = result.loc[~result.parse_error & result.sentiment.notna()]
    mapping = pd.read_csv(cfg["_root"] / cfg["inputs"]["listing_ids"], dtype=str).rename(columns={"id": "listing_id", "analysis_area": "area"})
    result = result.merge(reviews.drop_duplicates("id")[["id", "listing_id"]], left_on="review_id", right_on="id").merge(mapping, on="listing_id")
    rows = []
    for region, group in result.groupby("area"):
        rows.append({"area": region, "kpi_id": "K7_negative", "aspect": "", "value": group.sentiment.eq("negative").mean() * 100, "unit": "%", "n": len(group)})
        for aspect in cfg["llm"]["aspects"]:
            praise = sum(aspect in x for x in group.aspects_praise)
            complaint = sum(aspect in x for x in group.aspects_complaint)
            rows.append({"area": region, "kpi_id": "K7_aspect", "aspect": aspect, "value": (praise - complaint) / (praise + complaint) if praise + complaint else np.nan, "unit": "[-1,1]", "n": praise + complaint})
    return pd.DataFrame(rows, columns=columns)


def run(cfg: dict) -> None:
    """Tính lại K7 sau LLM, dữ liệu không có thì xuất bảng trống có header."""
    listings, calendar, reviews = [read(cfg, name + "_clean") for name in ("listings", "calendar", "reviews")]
    area, times = compute(cfg, listings, calendar, reviews)
    llm = llm_kpi(cfg, reviews, listings)
    if llm.empty:
        logging.warning("Chưa có dự đoán LLM hợp lệ; K7 chưa có số liệu")
    for name, frame in (("area", area), ("time", times), ("llm", llm)):
        frame.to_csv(path(cfg, "processed", f"kpi_{name}.csv"), index=False)
    definitions = [
        ("K1", "Giá đêm trung vị", "So sánh giá vùng ở mốc cuối", "median(price hợp lệ)", cfg["currency"]),
        ("K2", "Tỷ lệ ngày không khả dụng theo vùng/mốc", "Theo dõi nguồn cung", "100*(1-mean(available))", "%"),
        ("K3", "Tỷ lệ ngày không khả dụng theo tháng lịch", "Theo dõi mùa vụ khả dụng", "100*(1-mean(available)) theo tháng ngày lịch", "%"),
        ("K4", "Tỷ lệ yêu cầu thuê dài hạn", "Theo dõi điều kiện tối thiểu", f"100*mean(minimum_nights>={cfg['kpi']['long_stay_nights']})", "%"),
        ("K5", "Tốc độ review trong mẫu", "Mô tả hoạt động mẫu, không suy rộng", "review duy nhất/quý / listing duy nhất trong mẫu", "sample reviews/listing/quarter"),
        ("K6", "Listing chưa có review", "Theo dõi cấu trúc mẫu", "100*mean(number_of_reviews==0)", "%"),
        ("K7", "Cảm xúc tiêu cực và điểm khía cạnh", "Phát hiện vấn đề trải nghiệm", "negative/valid; (praise-complaint)/(praise+complaint)", "% hoặc [-1,1]"),
        ("K8", "Listing khả dụng cao có nhiều review", "Sàng lọc để nghiên cứu thêm, không kết luận chuyên nghiệp", "mean(availability>=threshold and reviews>=threshold)*100", "%"),
    ]
    csv_report(cfg, [{"kpi_id": kid, "name": name, "stakeholder": cfg["kpi"]["stakeholder"], "goal": goal, "formula": formula, "unit": unit, "currency": cfg["currency"] if kid == "K1" else "", "filters_after_qa": "Giá hợp lệ ở mốc cuối; available không thiếu; minimum_nights hợp lệ. Không khả dụng không đồng nghĩa đã đặt."} for kid, name, goal, formula, unit in definitions], "kpi_definitions.csv")


if __name__ == "__main__":
    cli(run)
