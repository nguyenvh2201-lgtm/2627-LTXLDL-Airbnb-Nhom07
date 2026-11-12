"""Tính đúng một bộ tám KPI (K1–K8) từ dữ liệu đã qua QA.

K1, K2, K4, K6 và K8 nằm trong kpi_area.csv.
K2, K3, K4, K5 và K6 nằm trong kpi_time.csv.
K7 nằm trong kpi_llm.csv; bảng này trống khi chưa có kết quả Gemini hợp lệ.
Một KPI có thể xuất hiện ở hai bảng nếu cần xem theo cả khu vực và thời gian.
"""

import logging
import numpy as np
import pandas as pd

from .download import cli, csv_report, path, read


LLM_COLUMNS = ["area", "kpi_id", "aspect", "value", "unit", "n"]


def compute(
    cfg: dict,
    listings: pd.DataFrame,
    calendar: pd.DataFrame,
    reviews: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Tính K1–K6 và K8. Đầu vào là các bảng sạch sau QA."""
    area_rows = []
    time_rows = []
    area_col = cfg["kpi"]["area_col"]

    # Chỉ dùng ngày lịch có trạng thái hợp lệ, ngày hợp lệ và khu vực xác định.
    listing_areas = listings[["id", "snapshot", area_col]].rename(
        columns={"id": "listing_id", area_col: "area"}
    )
    days = calendar.merge(
        listing_areas, on=["listing_id", "snapshot"],
        how="left", validate="many_to_one",
    )
    days = days.loc[
        days.available.notna() & days.date.notna() & days.area.notna()
    ].copy()
    days["period"] = days.date.dt.to_period("M").astype(str)
    availability_by_listing = days.groupby(
        ["snapshot", "listing_id"]
    ).available.mean()

    # K1: giá trung vị tại mốc cuối, theo neighbourhood.
    # K4: tỷ lệ yêu cầu tối thiểu nhiều đêm. K6: chưa có review.
    # K8: listing mở lịch nhiều và đã có đủ review theo ngưỡng cấu hình.
    for (snapshot, region), group in listings.groupby(["snapshot", area_col]):
        if snapshot == cfg["snapshots"][-1]:
            prices = group.loc[
                ~group.flag_outlier_price & group.price.notna(), "price"
            ]
            area_rows.append({
                "snapshot": snapshot, "area": region, "kpi_id": "K1",
                "value": prices.median(), "unit": cfg["currency"] + "/đêm",
                "currency": cfg["currency"], "n": len(prices),
            })

        minimum = group.loc[
            ~group.flag_outlier_minimum_nights & group.minimum_nights.notna(),
            "minimum_nights",
        ]
        for kid, value, n in (
            ("K4", minimum.ge(cfg["kpi"]["long_stay_nights"]).mean() * 100,
             len(minimum)),
            ("K6", group.number_of_reviews.eq(0).mean() * 100, len(group)),
        ):
            area_rows.append({
                "snapshot": snapshot, "area": region, "kpi_id": kid,
                "value": value, "unit": "%", "currency": "", "n": n,
            })

        available = availability_by_listing.get(
            snapshot, pd.Series(dtype=float)
        )
        valid = group.loc[group.id.isin(available.index)]
        professional = (
            valid.id.map(available).ge(cfg["kpi"]["high_availability_ratio"])
            & valid.number_of_reviews.ge(
                cfg["kpi"]["professional_min_reviews"]
            )
        )
        area_rows.append({
            "snapshot": snapshot, "area": region, "kpi_id": "K8",
            "value": professional.mean() * 100, "unit": "%",
            "currency": "", "n": len(valid),
        })

    # K2: phần trăm ngày không khả dụng theo khu vực và mốc.
    for (snapshot, region), group in days.groupby(["snapshot", "area"]):
        area_rows.append({
            "snapshot": snapshot, "area": region, "kpi_id": "K2",
            "value": (1 - group.available.astype(float).mean()) * 100,
            "unit": "%", "currency": "", "n": len(group),
        })

    # K3: cùng công thức không khả dụng, nhóm theo tháng của ngày lịch.
    for (snapshot, period), group in days.groupby(["snapshot", "period"]):
        time_rows.append({
            "snapshot": snapshot, "period": period, "kpi_id": "K3",
            "value": (1 - group.available.astype(float).mean()) * 100,
            "unit": "%", "currency": "", "n": len(group),
        })

    # K5: review duy nhất theo quý trong mẫu được giao; không ngoại suy.
    unique_reviews = reviews.sort_values("snapshot").drop_duplicates(
        "id", keep="last"
    ).copy()
    unique_reviews = unique_reviews.loc[unique_reviews.date.notna()]
    unique_reviews["period"] = unique_reviews.date.dt.to_period("Q").astype(str)
    denominator = listings.id.nunique()
    for period, group in unique_reviews.groupby("period"):
        time_rows.append({
            "snapshot": "pooled_unique_review_sample",
            "period": period, "kpi_id": "K5",
            "value": len(group) / denominator,
            "unit": "sample reviews/listing/quarter",
            "currency": "", "n": denominator, "review_count": len(group),
        })

    # K2, K4, K6 ở mức toàn thành phố theo từng snapshot.
    for snapshot, group in listings.groupby("snapshot"):
        available = days.loc[days.snapshot.eq(snapshot), "available"]
        minimum = group.loc[
            ~group.flag_outlier_minimum_nights & group.minimum_nights.notna(),
            "minimum_nights",
        ]
        for kid, value, n in (
            ("K2", (1 - available.astype(float).mean()) * 100, len(available)),
            ("K4", minimum.ge(cfg["kpi"]["long_stay_nights"]).mean() * 100,
             len(minimum)),
            ("K6", group.number_of_reviews.eq(0).mean() * 100, len(group)),
        ):
            time_rows.append({
                "snapshot": snapshot, "period": snapshot, "kpi_id": kid,
                "value": value, "unit": "%", "currency": "", "n": n,
            })

    return pd.DataFrame(area_rows), pd.DataFrame(time_rows)


def llm_kpi(cfg: dict, reviews: pd.DataFrame) -> pd.DataFrame:
    """K7: tỷ lệ tiêu cực và điểm khen/chê trên dự đoán LLM hợp lệ."""
    source = path(cfg, "processed", "llm_results.parquet")
    if not source.exists():
        return pd.DataFrame(columns=LLM_COLUMNS)

    predictions = pd.read_parquet(source)
    predictions = predictions.loc[
        ~predictions.parse_error & predictions.sentiment.notna()
    ]

    # ID review có thể xuất hiện qua nhiều mốc. Giữ một mapping để không đếm
    # cùng review nhiều lần; vùng mẫu lấy từ danh sách listing được giao.
    review_listings = reviews.drop_duplicates("id")[["id", "listing_id"]]
    assigned_areas = pd.read_csv(
        cfg["_root"] / cfg["inputs"]["listing_ids"], dtype=str
    ).rename(columns={"id": "listing_id", "analysis_area": "area"})
    predictions = (
        predictions.merge(
            review_listings, left_on="review_id", right_on="id"
        ).merge(assigned_areas, on="listing_id")
    )

    rows = []
    for region, group in predictions.groupby("area"):
        rows.append({
            "area": region, "kpi_id": "K7_negative", "aspect": "",
            "value": group.sentiment.eq("negative").mean() * 100,
            "unit": "%", "n": len(group),
        })
        for aspect in cfg["llm"]["aspects"]:
            praise = sum(aspect in items for items in group.aspects_praise)
            complaint = sum(
                aspect in items for items in group.aspects_complaint
            )
            mentions = praise + complaint
            rows.append({
                "area": region, "kpi_id": "K7_aspect", "aspect": aspect,
                "value": (praise - complaint) / mentions if mentions else np.nan,
                "unit": "[-1,1]", "n": mentions,
            })
    return pd.DataFrame(rows, columns=LLM_COLUMNS)


def definition_rows(cfg: dict) -> list[dict]:
    """Tên, mục tiêu, công thức, đơn vị và điều kiện của đúng tám KPI."""
    specs = [
        ("K1", "Giá đêm trung vị", "So sánh giá neighbourhood ở mốc cuối",
         "median(price hợp lệ)", cfg["currency"] + "/đêm",
         "neighbourhood_cleansed; mốc cuối; price hợp lệ và không bị cờ ngoại lai"),
        ("K2", "Tỷ lệ ngày không khả dụng theo vùng/mốc",
         "Theo dõi nguồn cung", "100*(1-mean(available))", "%",
         "neighbourhood_cleansed hoặc toàn mốc; ngày lịch có available hợp lệ; không khả dụng không đồng nghĩa đã đặt"),
        ("K3", "Tỷ lệ ngày không khả dụng theo tháng lịch",
         "Theo dõi mùa vụ khả dụng",
         "100*(1-mean(available)) theo tháng ngày lịch", "%",
         "ngày lịch có available hợp lệ, nhóm theo tháng của ngày lịch và snapshot"),
        ("K4", "Tỷ lệ yêu cầu thuê dài hạn",
         "Theo dõi điều kiện tối thiểu",
         f"100*mean(minimum_nights>={cfg['kpi']['long_stay_nights']})", "%",
         "minimum_nights có giá trị và không bị cờ bất hợp lý"),
        ("K5", "Tốc độ review trong mẫu",
         "Mô tả hoạt động mẫu, không suy rộng",
         "review duy nhất/quý / listing duy nhất trong mẫu",
         "sample reviews/listing/quarter",
         "review ID duy nhất có ngày hợp lệ trong mẫu được giao; không ngoại suy toàn thành phố"),
        ("K6", "Listing chưa có review", "Theo dõi cấu trúc mẫu",
         "100*mean(number_of_reviews==0)", "%",
         "listing sau QA; number_of_reviews bằng 0"),
        ("K7", "Cảm xúc tiêu cực và điểm khía cạnh",
         "Phát hiện vấn đề trải nghiệm",
         "negative/valid; (praise-complaint)/(praise+complaint)",
         "% hoặc [-1,1]",
         "review trong mẫu có kết quả LLM hợp lệ; không dùng nhãn dự đoán thiếu/lỗi"),
        ("K8", "Listing khả dụng cao có nhiều review",
         "Sàng lọc để nghiên cứu thêm, không kết luận chuyên nghiệp",
         "mean(availability>=threshold and reviews>=threshold)*100", "%",
         "listing có lịch hợp lệ và number_of_reviews; dùng ngưỡng trong config"),
    ]
    return [
        {
            "kpi_id": kid, "name": name,
            "stakeholder": cfg["kpi"]["stakeholder"],
            "goal": goal, "formula": formula, "unit": unit,
            "currency": cfg["currency"] if kid == "K1" else "",
            "filters_after_qa": conditions,
        }
        for kid, name, goal, formula, unit, conditions in specs
    ]


def run(cfg: dict) -> None:
    """Tính KPI từ dữ liệu sạch và xuất đúng ba bảng kết quả."""
    listings, calendar, reviews = [
        read(cfg, name + "_clean")
        for name in ("listings", "calendar", "reviews")
    ]
    area, times = compute(cfg, listings, calendar, reviews)
    llm = llm_kpi(cfg, reviews)
    if llm.empty:
        logging.warning("Chưa có dự đoán LLM hợp lệ; K7 chưa có số liệu")

    for name, frame in (("area", area), ("time", times), ("llm", llm)):
        frame.to_csv(path(cfg, "processed", f"kpi_{name}.csv"), index=False)
    csv_report(cfg, definition_rows(cfg), "kpi_definitions.csv")


if __name__ == "__main__":
    cli(run)
