import pandas as pd
import numpy as np
import yaml
from pathlib import Path

# Tính từ vị trí qa.py, không phụ thuộc thư mục đang mở terminal.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"

def prepare_listings(raw_listings, phan_cong,snapshot_date):
    mask = raw_listings['id'].isin(phan_cong["listing_id"])
    raw_listings = raw_listings[mask]
    bang_area = phan_cong[["listing_id","analysis_area"]]
    bang_moi = raw_listings.merge(
    bang_area,
    left_on = "id",
    right_on = "listing_id",
    how = "left",
    )
    bang_moi["snapshot_date"] = snapshot_date
    return bang_moi
# 1. Kiểm tra missing
def check_missing(df):
    """
    Trả về bảng:
    column | missing_count | missing_pct
    """
    missing = df.isna().sum()
    missing_pct = df.isna().mean() * 100
    return pd.DataFrame({
        "missing_count" : missing,
        "missing percent": missing_pct
    })


# 2. Kiểm tra duplicate
def check_duplicates(df):
    """
    Kiểm tra:
    - trùng toàn bộ dòng
    - trùng listing_id trong cùng snapshot
    """

    duplicate_full = df.duplicated(keep = False)
    duplicate_id = df.duplicated(
        subset = ["listing_id"],
        keep = False
        )

    return pd.DataFrame({
        "duplicate_full_row": duplicate_full,
        "duplicate_listing_id": duplicate_id
    })


# 3. Làm sạch price
def clean_price(price):
    """
    - bỏ $
    - bỏ ,
    - chuyển sang numeric
    - không làm mất NaN gốc
    """
    cleaned = price.astype("string").str.replace("$","").str.replace(",","")
    return pd.to_numeric(cleaned, errors = "coerce")



# 4. QA price
def check_price(raw_price):
    """
    Kiểm tra:
    - missing
    - price <= 0
    - outlier
    """
    price = clean_price(raw_price)
    price_valid = price.notna() & (price > 0)

    valid_prices = price[price_valid]
    q1 = valid_prices.quantile(0.25)
    q3 = valid_prices.quantile(0.75)
    iqr = q3 - q1

    outlier = price_valid & (
        (price < q1 - 1.5 * iqr)
        | (price > q3 + 1.5 * iqr)
    )

    return pd.DataFrame({
        "price_cad": price,
        "price_missing": raw_price.isna(),
        "price_parse_error": raw_price.notna() & price.isna(),
        "price_nonpositive": price <= 0,
        "price_valid": price_valid,
        "price_outlier_flag": outlier,
    })
    pass


# 5. Kiểm tra các cột numeric khác
def check_numeric_rules(df):
    """
    Ví dụ:
    - minimum_nights <= 0
    - maximum_nights <= 0
    - minimum_nights > maximum_nights
    - availability_365 ngoài [0, 365]
    """
    rule_1 = df["minimum_nights"] <= 0
    rule_2 = df["maximum_nights"] <= 0
    rule_3 = df["minimum_nights"] > df["maximum_nights"]
    rule_4 = (df["availability_365"] < 0) | (df["availability_365"] > 365)
    return pd.DataFrame({
        "Dem toi thieu <= 0": rule_1,
        "Dem toi da <= 0": rule_2,
        "Dem toi thieu > dem toi da": rule_3,
        "Out of range": rule_4,
    })
    pass
def check_rating(df):
    rating_valid = df["review_scores_rating"].notna() & (df["review_scores_rating"] >= 1) & (df["review_scores_rating"] <= 5)
    return pd.DataFrame({
        "rating_valid" : rating_valid
    })
# 6. Kiểm tra category
def check_categories(df):
    """
    Ví dụ:
    - room_type
    - analysis_area
    """
    valid_area = ["A01","A02","A03","A04","A05","A06","A07","A08"]
    room_type_valid = df["room_type"].notna() & df["room_type"].isin(["Entire home/apt","Private room"])
    analysis_area_valid = df["analysis_area"].isin(valid_area)
    return pd.DataFrame({
        "room_type_valid": room_type_valid,
        "Khu phan tich hop le" : analysis_area_valid
    })
#REVIEWS
def prepare_reviews(raw_reviews, phan_cong, snapshot_date):
    mask = raw_reviews["id"].isin(phan_cong["review_id"].dropna())
    bang_moi = raw_reviews[mask].copy()
    bang_moi = bang_moi.rename(
        columns={"id": "review_id"}
    )
    bang_moi["snapshot_date"] = snapshot_date
    return bang_moi
def check_duplicate_review(reviews_df):
    duplicate_all = reviews_df.duplicated(keep = False)
    duplicate_id = reviews_df.duplicated(
        subset = "review_id",
        keep = False
    )
    return pd.DataFrame({
        "duplicate_all" : duplicate_all,
        "duplicate_id" : duplicate_id
    })
def check_comments(reviews_df):
    valid_cmt = (reviews_df["comments"].notna()) & (reviews_df["comments"].astype("string").str.strip() != "")
    return pd.DataFrame({
        "text_valid" : valid_cmt
    })
def check_date(df):
    date_parsed = pd.to_datetime(df["date"], errors="coerce")
    date_missing = df["date"].isna()
    date_parse_error = df["date"].notna() & date_parsed.isna()
    date_valid = date_parsed.notna()
    return pd.DataFrame({
        "date_parsed": date_parsed,
        "date_missing" : date_missing,
        "date_parse_error" : date_parse_error,
        "date_valid" : date_valid
    })
def check_listing_match(reviews_df, listings_df):
    listing_match = reviews_df["listing_id"].isin(listings_df['listing_id'])
    return pd.DataFrame({
        "listing_match" : listing_match
    })
#Calendar
def prepare_calendar(raw_calendar,phan_cong,snapshot):
    mask = raw_calendar["listing_id"].isin(phan_cong["listing_id"])
    raw_calendar = raw_calendar[mask]
    bang_moi = raw_calendar.copy()
    bang_moi["snapshot_date"] = snapshot
    return bang_moi
def check_duplicate_calendar(calendar_df):
    duplicate_all = calendar_df.duplicated(keep = False)
    duplicate_date = calendar_df.duplicated(
        subset = ["listing_id","date"],
        keep = False
    )
    return pd.DataFrame({
            "duplicate_full_row": duplicate_all,
            "duplicate_listing_date": duplicate_date
        })
def check_available(calendar_df):
    available_clean = calendar_df["available"].astype("string").str.strip().str.lower()
    available_valid = available_clean.isin(["t", "f", "true", "false"])
    available_true = available_clean.isin(["t", "true"])
    return pd.DataFrame({
            "available_clean": available_clean,
            "available_valid": available_valid,
            "available_true": available_true
        })
# 7. Chạy toàn bộ QA cho một snapshot
def run_qa_calendar(calendar_df, listings_df):
    missing_summary = check_missing(calendar_df)

    duplicate_flags = check_duplicate_calendar(calendar_df)
    date_flags = check_date(calendar_df)
    available_flags = check_available(calendar_df)
    listing_match_flags = check_listing_match(calendar_df, listings_df)

    row_flags = pd.concat(
        [
            duplicate_flags,
            date_flags,
            available_flags,
            listing_match_flags
        ],
        axis=1
    )
    report = {
            "missing_summary":  missing_summary ,
            "row_flags": row_flags
        }

    return report
def calendar_listing_summary(calendar_qa_df):
    daily = calendar_qa_df.groupby(
    ["listing_id", "date_parsed"],
    as_index=False
        ).agg(
            n_valid_rows=("available_valid", "sum"),
            n_true_rows=("available_true", "sum")
        )
    daily["available_valid_day"] = (
            (daily["n_valid_rows"] > 0)
            & (
                (daily["n_true_rows"] == 0)
                | (daily["n_true_rows"] == daily["n_valid_rows"])
            )
        )
    daily["available_true_day"] = (
            daily["available_valid_day"]
            & (daily["n_true_rows"] == daily["n_valid_rows"])
        )
    summary = daily.groupby("listing_id").agg(
        calendar_start = ("date_parsed","min"),
        calendar_end=("date_parsed", "max"),
        n_calendar_days=("date_parsed", "size"),
        n_available_valid=("available_valid_day", "sum"),
        n_available=("available_true_day", "sum")
    ).reset_index()
    summary["availability_share"] = (
    summary["n_available"] / summary["n_available_valid"]
    ).where(summary["n_available_valid"] != 0)
    # KPI dùng số ngày có trong lịch của từng listing làm mẫu số.
    summary["coverage_share"] = summary["n_available_valid"] / summary["n_calendar_days"]
    return summary
def run_qa_reviews(reviews_df,raw_listings):
    missing_summary = check_missing(reviews_df)
    duplicate_reviews_flags = check_duplicate_review(reviews_df)
    comments_reviews_flags = check_comments(reviews_df)
    listing_match_flags = check_listing_match(reviews_df, raw_listings)
    date_reviews_flags = check_date(reviews_df)
    row_flags = pd.concat(
        [
        duplicate_reviews_flags,
        comments_reviews_flags,
        date_reviews_flags,
        listing_match_flags
        ],
        axis = 1
    )
    report = {
        "missing_summary":  missing_summary ,
        "row_flags": row_flags
    }

    return report
def run_qa_listings(df):
    # 1. Gọi các hàm kiểm tra
    missing_summary = check_missing(df)
    duplicate_flags = check_duplicates(df)
    price_flags = check_price(df["price"])  # Truyền cột giá, không phải cả df
    numeric_flags = check_numeric_rules(df)
    category_flags = check_categories(df)
    rating_flags = check_rating(df)
    # 2. Ghép các bảng cờ theo chiều ngang
    row_flags = pd.concat(
        [duplicate_flags , price_flags, numeric_flags, category_flags,rating_flags],
        axis=1
    )
    # 3. Gom kết quả thành report
    report = {
        "missing_summary":  missing_summary ,
        "row_flags": row_flags
    }

    return report
def run_qa(config):
    """Chạy QA theo cấu hình và trả số review thô của từng mốc."""
    raw_dir = PROJECT_ROOT / config.get("raw_dir", RAW_DIR)
    processed_dir = PROJECT_ROOT / config.get("processed_dir", DATA_DIR / "processed")
    reports_dir = PROJECT_ROOT / config.get("reports_dir", "reports")
    report_rows = []
    raw_review_counts = {}
    seen_listing_scrapes = set()
    seen_reviews = set()

    def record(snapshot, table, check, affected, before, after, unit="rows"):
        report_rows.append({
            "snapshot_date": snapshot, "table": table, "check": check,
            "affected_rows": int(affected), "before_qa": before,
            "after_qa": after, "unit": unit,
        })

    def record_flags(snapshot, table, report, valid_flags):
        flags = report["row_flags"]
        for column, missing in report["missing_summary"]["missing_count"].items():
            if missing:
                record(snapshot, table, f"missing:{column}", missing, len(flags), len(flags))
        for column in flags.select_dtypes(include="bool"):
            mask = flags[column].fillna(False)
            affected = (~mask).sum() if column in valid_flags else mask.sum()
            record(snapshot, table, column, affected, len(flags), len(flags))

    snapshots = []
    for snapshot in config["snapshots"]:
        snapshots.append(str(snapshot))
    snapshots.sort()

    # Đặt đoạn đọc dữ liệu và chạy QA ở đây.
    phan_cong = pd.read_csv(
        DATA_DIR / "data-new.csv",
        encoding="utf-8",
        dtype={"listing_id": "string", "review_id": "string"},
    )
    for date in snapshots:
        df = pd.read_csv(
            raw_dir / date / "listings.csv.gz",
            dtype={"id": "string"},
        )
        prepare = prepare_listings(df,phan_cong,date)
        report = run_qa_listings(prepare)
        row_flags = report["row_flags"]
        record(date, "listings", "assigned_scope", len(df) - len(prepare), len(df), len(prepare))
        record_flags(date, "listings", report, {
            "price_valid", "rating_valid", "room_type_valid", "Khu phan tich hop le",
        })
        scrape_keys = list(prepare[["listing_id", "last_scraped"]].dropna().itertuples(index=False, name=None))
        repeated_scrapes = sum(key in seen_listing_scrapes for key in scrape_keys)
        record(date, "listings", "listing_scrape_repeated_across_snapshots",
               repeated_scrapes, len(prepare), len(prepare))
        seen_listing_scrapes.update(scrape_keys)
        price = row_flags["price_cad"]
        record(date, "listings", "median_price", (~row_flags["price_valid"]).sum(),
               price.median(), price[row_flags["price_valid"]].median(), config.get("currency", "CAD"))
        rating = prepare["review_scores_rating"]
        record(date, "listings", "median_rating", (~row_flags["rating_valid"]).sum(),
               rating.median(), rating[row_flags["rating_valid"]].median(), "score")
        all_data = pd.concat(
        [
            prepare.reset_index(drop=True),
            row_flags.reset_index(drop=True)
        ],
        axis=1
    )
        listings_clean = all_data[
            [
                "snapshot_date",
                "listing_id",
                "neighbourhood_cleansed",
                "room_type",
                "price_cad",
                "price_valid",
                "price_outlier_flag",
                "room_type_valid",
                "review_scores_rating",
                "rating_valid",
                "latitude",
                "longitude",
                "last_scraped",
                "availability_365",
                "number_of_reviews",
            ]
        ].copy()
        output_dir = processed_dir / date

        output_dir.mkdir(
                    parents=True,
                    exist_ok=True
                )

                # 7. Lưu file
        listings_clean.to_csv(
                    output_dir / "listings_clean.csv",
                    index = False)
        print(date)
        print("Shape:", listings_clean.shape)
        print("Unique listing:", listings_clean["listing_id"].nunique())
        print()
    for date in snapshots:

        # 1. Đọc reviews raw
        raw_reviews = pd.read_csv(
            raw_dir / date / "reviews.csv.gz",
            dtype={"id": "string", "listing_id": "string"},
        )
        raw_review_counts[date] = len(raw_reviews)

        # 2. Đọc listings_clean cùng snapshot
        listings_df = pd.read_csv(
            processed_dir / date / "listings_clean.csv",
            dtype={"listing_id": "string"},
        )

        # 3. Lọc reviews thuộc 1000 listings của nhóm
        prepared_reviews = prepare_reviews(
            raw_reviews,
            phan_cong,
            date
        )

        # 4. Chạy QA reviews
        review_report = run_qa_reviews(
            prepared_reviews,
            listings_df
        )
        review_flags = review_report["row_flags"]
        record(date, "reviews", "assigned_scope", len(raw_reviews) - len(prepared_reviews),
               len(raw_reviews), len(prepared_reviews))
        record_flags(date, "reviews", review_report, {"text_valid", "listing_match", "date_valid"})
        review_ids = prepared_reviews["review_id"]
        record(date, "reviews", "review_seen_in_earlier_snapshot", review_ids.isin(seen_reviews).sum(),
               len(prepared_reviews), len(prepared_reviews))
        seen_reviews.update(review_ids.dropna())

        # 5. Ghép reviews + QA flags
        all_reviews = pd.concat(
            [
                prepared_reviews.reset_index(drop=True),
                review_flags.reset_index(drop=True)
            ],
            axis=1
        )

        # 6. Tạo reviews_clean
        reviews_clean = all_reviews[
            [
                "snapshot_date",
                "review_id",
                "listing_id",
                "date_parsed",
                "comments",
                "text_valid",
                "listing_match"
            ]
        ].copy()

        # đổi date_parsed về tên date cho output cuối
        reviews_clean = reviews_clean.rename(
            columns={"date_parsed": "date"}
        )
        print("Tổng số review:", len(reviews_clean))
        print("Số listing có review:", reviews_clean["listing_id"].nunique())
        print("Review ID bị trùng:", reviews_clean["review_id"].duplicated().sum())

        print(
            reviews_clean.groupby("listing_id")
            .size()
            .sort_values(ascending=False)
            .head(10)
        )
        # 7. Folder output
        output_dir = processed_dir / date
        output_dir.mkdir(
            parents=True,
            exist_ok=True
        )
        # 8. Lưu reviews_clean
        reviews_clean.to_csv(
            output_dir / "reviews_clean.csv",
            index=False
        )
        print("REVIEWS:", date)
        print("Shape:", reviews_clean.shape)
        print("Unique review_id:", reviews_clean["review_id"].nunique())
        unmatched = reviews_clean.loc[
            ~reviews_clean["listing_match"], "listing_id"
        ]
        print("Số listing không match:", unmatched.nunique())
        print(unmatched.value_counts().head(10))
        print()
    for date in snapshots:

        # 1. Đọc calendar raw
        calendar_parts = []
        raw_calendar_count = 0
        for chunk in pd.read_csv(
            raw_dir / date / "calendar.csv.gz",
            dtype={"listing_id": "string"},
            chunksize=200_000,
        ):
            raw_calendar_count += len(chunk)
            calendar_parts.append(prepare_calendar(chunk, phan_cong, date))

        # 2. Đọc listings_clean cùng snapshot
        listings_df = pd.read_csv(
            processed_dir / date / "listings_clean.csv",
            dtype={"listing_id": "string"},
        )

        # 3. Chuẩn bị calendar của 1000 listings nhóm
        prepared_calendar = pd.concat(calendar_parts, ignore_index=True)
        record(date, "calendar", "assigned_scope", raw_calendar_count - len(prepared_calendar),
               raw_calendar_count, len(prepared_calendar))

        # 4. Chạy QA calendar
        calendar_report = run_qa_calendar(
            prepared_calendar,
            listings_df
        )

        row_flags = calendar_report["row_flags"]
        record_flags(date, "calendar", calendar_report, {"date_valid", "available_valid", "listing_match"})

        # 5. Ghép calendar với các QA flags
        calendar_qa_df = pd.concat(
            [
                prepared_calendar.reset_index(drop=True),
                row_flags.reset_index(drop=True)
            ],
            axis=1
        )

        # 6. Tạo summary theo listing
        calendar_summary = calendar_listing_summary(
            calendar_qa_df
        )

        # 7. Thêm snapshot_date
        calendar_summary.insert(
            0,
            "snapshot_date",
            date
        )

        # 8. Tạo folder output
        output_dir = processed_dir / date

        output_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        # 9. Lưu calendar summary
        calendar_summary.to_csv(
            output_dir / "calendar_listing_summary.csv",
            index=False
        )

        # 10. Check nhanh
        print("CALENDAR:", date)
        print("Shape:", calendar_summary.shape)
        print(
            "Unique listing:",
            calendar_summary["listing_id"].nunique()
        )

        print(
            "Sai n_available:",
            (
                calendar_summary["n_available"]
                > calendar_summary["n_available_valid"]
            ).sum()
        )

        print(
            "Sai n_available_valid:",
            (
                calendar_summary["n_available_valid"]
                > calendar_summary["n_calendar_days"]
            ).sum()
        )

        print()

    reports_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(report_rows).to_csv(reports_dir / "qa_report.csv", index=False)
    return raw_review_counts


if __name__ == "__main__":
    with (PROJECT_ROOT / "configs" / "city.yaml").open(encoding="utf-8-sig") as config_file:
        config = yaml.safe_load(config_file)
    run_qa(config)
