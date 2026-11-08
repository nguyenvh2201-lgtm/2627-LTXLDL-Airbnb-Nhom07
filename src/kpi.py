"""TV3 — Tính KPI theo mốc chụp từ bảng sạch của TV2 (nhóm 7, Toronto).

8 KPI (tiền tệ CAD cho mọi KPI giá):
  Nền (5)
    n_listings                  số listing                          kpi_snapshot.csv
    median_price_cad            giá niêm yết trung vị, CAD/đêm      kpi_snapshot.csv
    entire_home_share           tỷ lệ Entire home/apt               kpi_snapshot.csv
    availability_share_mean     tỷ lệ mở lịch quan sát được         kpi_snapshot.csv
    median_rating               điểm đánh giá trung vị              kpi_snapshot.csv
  Theo khu vực (1)
    area_price_premium          median khu vực / median TP − 1      kpi_area.csv
  Theo thời gian (1)
    delta_median_price_cad      median(t) − median(t−1), CAD/đêm    kpi_time.csv

  Dùng LLM (1)
    llm_negative_share          tỷ lệ đánh giá tiêu cực theo LLM    kpi_llm_snapshot.csv,
                                                                    kpi_llm_area.csv

Đầu vào (trong input_dir):
  listings_clean.csv, calendar_listing_summary.csv   (TV2)
  llm_pilot.jsonl                                    (TV4, tuỳ chọn — thiếu thì bỏ qua KPI LLM)

Đầu ra (mặc định data/processed/kpi_*.csv):
  kpi_snapshot.csv, kpi_area.csv, kpi_room_type.csv, kpi_room_type_missing.csv,
  kpi_time.csv, và (nếu có file LLM) kpi_llm_snapshot.csv, kpi_llm_area.csv,
  kpi_llm_aspect.csv
Kiểm tra: data/processed/kpi_checks.csv. Có FAIL thì không ghi KPI.

Chạy:
  python src/kpi.py                                # mặc định data/processed -> data/processed/kpi_*.csv
  python src/kpi.py --snapshots 2025-09-11         # chỉ một mốc
  python src/kpi.py --exclude-price-outliers       # bỏ listing có price_outlier_flag khỏi KPI giá
  python src/kpi.py --llm-file data/processed/llm_pilot.jsonl
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

import numpy as np
import pandas as pd

LISTINGS_FILE = "listings_clean.csv"
CALENDAR_FILE = "calendar_listing_summary.csv"
UNKNOWN = "Unknown"
ENTIRE = "Entire home/apt"
# Ngưỡng mẫu tối thiểu cho mọi tỷ lệ theo khu vực / khía cạnh LLM. Dưới ngưỡng thì để trống.
MIN_N_SHARE = 30
LLM_LABELS = ("positive", "mixed", "negative")
LLM_FILE_DEFAULT = os.path.join("data", "processed", "llm_pilot.jsonl")
OUT_DIR_DEFAULT = os.path.join("data", "processed")
ASPECT_COLS = ["snapshot_date", "aspect", "n_aspect_mentions", "n_llm_usable",
               "aspect_mention_share", "aspect_negative_share"]

REQ_LISTING_COLS = [
    "snapshot_date", "listing_id", "neighbourhood_cleansed", "room_type",
    "price_cad", "price_valid", "price_outlier_flag", "room_type_valid",
    "review_scores_rating", "rating_valid",
]
REQ_CALENDAR_COLS = [
    "snapshot_date", "listing_id", "n_calendar_days", "n_available_valid",
    "n_available", "availability_share", "coverage_share",
]

SNAPSHOT_COLS = [
    "snapshot_date", "n_listings", "n_price_valid", "median_price_cad",
    "price_q1_cad", "price_q3_cad", "n_room_type_valid", "entire_home_share",
    "n_calendar_listings", "availability_share_mean", "calendar_coverage_mean",
    "n_rating_valid", "median_rating",
]
ROUND = {
    "median_price_cad": 2, "price_q1_cad": 2, "price_q3_cad": 2,
    "entire_home_share": 4, "availability_share_mean": 4,
    "calendar_coverage_mean": 4, "median_rating": 2,
    "room_type_share": 4, "unknown_room_type_share": 4,
    "area_price_premium": 4, "city_median_price_cad": 2,
    "delta_median_price_cad": 2, "prev_median_price_cad": 2,
    "llm_parse_coverage": 4, "llm_positive_share": 4, "llm_negative_share": 4,
    "aspect_mention_share": 4, "aspect_negative_share": 4,
}


# ------------------------------------------------------------- đọc & kiểm tra

# Hàm này chuẩn hoá cả hai về số thực CAD/đêm. Ô không đọc được -> NaN và được
# đánh dấu price_unparseable để kiểm tra báo FAIL (xem run_checks).
# =============================================================================
# BẢNG ĐỊNH NGHĨA KPI — đọc phần này trước, rồi mới đến các hàm bên dưới.
# Mỗi KPI ghi: nhóm, file đầu ra, cột, công thức, đơn vị, mẫu số, điều kiện,
# hạn chế, và hàm tính trong code. Bảng này chỉ để tra cứu; code tính toán
# không đọc từ bảng này, nên sửa mô tả ở đây không làm thay đổi kết quả.
# =============================================================================
KPIS = {
    "n_listings": dict(
        nhom="quy mô nguồn cung", file="kpi_snapshot.csv", cot=["n_listings"],
        cong_thuc="Số listing_id duy nhất trong mốc",
        don_vi="listing", mau_so="—",
        dieu_kien="listing_id không trùng trong mốc (đã kiểm tra khi đọc)",
        han_che="Số listing hiển thị lúc thu thập, không phải số chủ nhà đang hoạt động",
        ham="_metrics"),
    "median_price_cad": dict(
        nhom="giá niêm yết", file="kpi_snapshot.csv", cot=["median_price_cad", "price_q1_cad", "price_q3_cad"],
        cong_thuc="Median (Q1, Q3 là phân vị 25%, 75%) của price_cad trên listing price_ok",
        don_vi="CAD/đêm", mau_so="n_price_valid",
        dieu_kien="price_valid = True và price_cad > 0; loại thêm price_outlier_flag nếu bật --exclude-price-outliers",
        han_che="Giá niêm yết, không phải giá đã đặt; chưa hiệu chỉnh theo số khách hay số đêm tối thiểu",
        ham="_metrics"),
    "entire_home_share": dict(
        nhom="cơ cấu loại phòng", file="kpi_snapshot.csv", cot=["entire_home_share"],
        cong_thuc="n(room_type = Entire home/apt) / n(room_type hợp lệ)",
        don_vi="tỷ lệ 0–1", mau_so="n_room_type_valid",
        dieu_kien="room_type khác Unknown; mẫu số = 0 thì để trống",
        han_che="Mô tả thành phần cung, không cho biết nhu cầu",
        ham="_metrics"),
    "availability_share_mean": dict(
        nhom="mở lịch", file="kpi_snapshot.csv", cot=["availability_share_mean", "n_calendar_listings", "calendar_coverage_mean"],
        cong_thuc="Trung bình availability_share_calc = n_available / n_available_valid trên listing có lịch",
        don_vi="tỷ lệ 0–1", mau_so="n_calendar_listings",
        dieu_kien="listing có n_available_valid > 0. Cột phụ calendar_coverage_mean tính trên tất cả listing, listing không có lịch được tính 0",
        han_che="available = f gồm cả ngày đã đặt và ngày bị chặn, KHÔNG phải occupancy, không dùng để ước doanh thu",
        ham="_metrics"),
    "median_rating": dict(
        nhom="chất lượng đánh giá", file="kpi_snapshot.csv", cot=["median_rating", "n_rating_valid"],
        cong_thuc="Median của review_scores_rating trên listing có rating_valid",
        don_vi="điểm (thang nguồn, Inside Airbnb 0–5)", mau_so="n_rating_valid",
        dieu_kien="rating_valid do QA xác nhận, điểm hợp lệ trong khoảng 1–5",
        han_che="Listing mới chưa có điểm bị loại khỏi mẫu",
        ham="_metrics"),
    "area_price_premium": dict(
        nhom="theo khu vực", file="kpi_area.csv", cot=["area_price_premium", "city_median_price_cad"],
        cong_thuc="median_price_cad(khu vực) / median_price_cad(thành phố, cùng mốc) − 1",
        don_vi="tỷ lệ (0,20 = đắt hơn trung vị thành phố 20%); tiền gốc CAD/đêm",
        mau_so="n_price_valid của khu vực",
        dieu_kien="khu vực không phải Unknown; n_price_valid >= MIN_N_SHARE (30); cả hai median có giá trị",
        han_che="So sánh thành phần listing, không phải giá của cùng một căn",
        ham="build_tables"),
    "delta_median_price_cad": dict(
        nhom="theo thời gian", file="kpi_time.csv", cot=["delta_median_price_cad", "median_price_cad", "prev_median_price_cad"],
        cong_thuc="median_price_cad(mốc t) − median_price_cad(mốc liền kề trước)",
        don_vi="CAD/đêm", mau_so="không có",
        dieu_kien="cả hai mốc có median; mốc đầu tiên để trống; không bắc cầu qua mốc thiếu giá",
        han_che="Thành phần listing có thể khác giữa hai mốc; không phải giá của cùng một căn",
        ham="build_time"),
    "llm_negative_share": dict(
        nhom="dùng LLM", file="kpi_llm_snapshot.csv, kpi_llm_area.csv",
        cot=["llm_negative_share", "n_llm_usable", "llm_positive_share", "llm_parse_coverage"],
        cong_thuc="n(sentiment = negative, dùng được) / n(dùng được)",
        don_vi="tỷ lệ 0–1", mau_so="n_llm_usable",
        dieu_kien="status = ok và sentiment thuộc positive/mixed/negative; n_llm_usable >= MIN_N_SHARE (30). llm_parse_coverage = n(status ok) / n(mẫu) là cột kiểm tra chất lượng",
        han_che="Chỉ trên mẫu review do LLM chạy (pilot), không phải toàn bộ review; phụ thuộc độ chính xác của LLM",
        ham="llm_metrics"),
}


def parse_price(value) -> float:
    """'$1,234.00' -> 1234.0 ; số -> số ; trống hoặc không đọc được -> NaN."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return np.nan
    if isinstance(value, (int, float, np.number)):
        return float(value)
    s = str(value).strip().replace("$", "").replace(",", "")
    try:
        return float(s)
    except ValueError:
        return np.nan


def _to_bool(s: pd.Series) -> pd.Series:
    return s.astype(str).str.strip().str.lower().isin(["true", "t", "1"])


def _require(df: pd.DataFrame, cols: list[str], name: str) -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ValueError(f"{name} thiếu cột: {missing}")


SNAPSHOT_DIR_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


# Đọc dữ liệu: tất cả cột đọc dạng chuỗi (dtype=str) để không bị pandas
# tự đổi kiểu (ví dụ listing_id dài bị làm tròn thành số thực, mất chữ số cuối).
# Kiểu số được chuyển ở bước load_listings / load_calendar.
def read_inputs(input_dir: str, snapshots):
    """Đọc listing và calendar, hỗ trợ hai cách TV2 xuất dữ liệu:

    1) Một file phẳng: input_dir/listings_clean.csv (đã có cột snapshot_date)
    2) Theo thư mục mốc: input_dir/<YYYY-MM-DD>/listings_clean.csv
       (cột snapshot_date lấy từ tên thư mục nếu file không có)
    """
    flat_l = os.path.join(input_dir, LISTINGS_FILE)
    flat_c = os.path.join(input_dir, CALENDAR_FILE)
    if os.path.exists(flat_l):
        if not os.path.exists(flat_c):
            raise FileNotFoundError(f"Không tìm thấy {flat_c}")
        return (pd.read_csv(flat_l, dtype=str, low_memory=False),
                pd.read_csv(flat_c, dtype=str, low_memory=False))

    dirs = sorted(d for d in os.listdir(input_dir)
                  if SNAPSHOT_DIR_RE.match(d) and os.path.isdir(os.path.join(input_dir, d)))
    if snapshots is not None:
        missing = sorted(set(snapshots) - set(dirs))
        if missing:
            raise ValueError(f"Không có thư mục cho mốc: {missing}")
        dirs = [d for d in dirs if d in snapshots]
    if not dirs:
        raise FileNotFoundError(
            f"Không tìm thấy {LISTINGS_FILE} trong {input_dir} và không có thư mục mốc YYYY-MM-DD nào")

    ls, cs = [], []
    for d in dirs:
        lp = os.path.join(input_dir, d, LISTINGS_FILE)
        cp = os.path.join(input_dir, d, CALENDAR_FILE)
        for p in (lp, cp):
            if not os.path.exists(p):
                raise FileNotFoundError(f"Thiếu {p} (có các file: {os.listdir(os.path.join(input_dir, d))})")
        for path, bucket in ((lp, ls), (cp, cs)):
            part = pd.read_csv(path, dtype=str, low_memory=False)
            if "snapshot_date" not in part.columns:
                part["snapshot_date"] = d
            elif not (part["snapshot_date"].str.strip() == d).all():
                raise ValueError(f"{path}: snapshot_date không khớp tên thư mục {d}")
            bucket.append(part)
    return pd.concat(ls, ignore_index=True), pd.concat(cs, ignore_index=True)


# Chuẩn hoá listing. Mọi cờ hợp lệ (price_valid,
# room_type_valid, rating_valid) để KPI khớp với QA đã chốt; code chỉ tính thêm
# các điều kiện cần cho KPI. Không tự suy hợp lệ từ việc có/không có giá trị.
def load_listings(raw: pd.DataFrame, snapshots, exclude_outliers: bool) -> pd.DataFrame:
    df = raw.copy()
    _require(df, REQ_LISTING_COLS, LISTINGS_FILE)
    df["snapshot_date"] = df["snapshot_date"].str.strip()
    df["listing_id"] = df["listing_id"].str.strip()
    if snapshots is not None:
        df = df[df["snapshot_date"].isin(snapshots)].copy()
    if df.duplicated(["snapshot_date", "listing_id"]).any():
        raise ValueError("listings_clean: trùng (snapshot_date, listing_id) — sửa ở QA của TV2")

    # Giá hợp lệ cho KPI giá (n_price_valid, median, Q1, Q3):
    #   price_ok = price_valid AND price_cad > 0
    #   nếu --exclude-price-outliers: bỏ thêm listing có price_outlier_flag.
    raw_price = df["price_cad"]
    df["price_cad"] = raw_price.map(parse_price)
    has_text = raw_price.notna() & raw_price.astype(str).str.strip().ne("")
    df["price_unparseable"] = has_text & df["price_cad"].isna()
    price_ok = _to_bool(df["price_valid"]) & df["price_cad"].gt(0)
    if exclude_outliers:
        price_ok &= ~_to_bool(df["price_outlier_flag"])
    df["price_ok"] = price_ok

# Nhãn Unknown: room_type / neighbourhood_cleansed trống được gán
# "Unknown" và giữ thành nhóm riêng. Nhóm này KHÔNG có trong mẫu số room_type
# (room_ok = False), nhưng vẫn được đếm trong n_listings của khu vực để tổng khớp.
    df["room_type"] = df["room_type"].fillna(UNKNOWN).astype(str).str.strip()
    df["room_type"] = df["room_type"].mask(df["room_type"].eq(""), UNKNOWN)
    df["neighbourhood_cleansed"] = (df["neighbourhood_cleansed"].fillna(UNKNOWN)
                                    .astype(str).str.strip()
                                    .mask(lambda s: s.eq(""), UNKNOWN))
    df["room_ok"] = _to_bool(df["room_type_valid"]) & df["room_type"].ne(UNKNOWN)

    # Dùng cờ QA để loại điểm thiếu hoặc không hợp lệ khỏi KPI đánh giá.
    df["rating"] = pd.to_numeric(df["review_scores_rating"], errors="coerce")
    df["rating_ok"] = _to_bool(df["rating_valid"])
    if (df["rating_ok"] & ~df["rating"].between(1, 5)).any():
        raise ValueError("rating_valid=True nhưng review_scores_rating nằm ngoài khoảng 1–5 hoặc bị thiếu")
    return df


# kiểm tra trùng khoá (snapshot_date, listing_id) và chuyển số.
def load_calendar(raw: pd.DataFrame, snapshots) -> pd.DataFrame:
    cal = raw.copy()
    _require(cal, REQ_CALENDAR_COLS, CALENDAR_FILE)
    cal["snapshot_date"] = cal["snapshot_date"].str.strip()
    cal["listing_id"] = cal["listing_id"].str.strip()
    if snapshots is not None:
        cal = cal[cal["snapshot_date"].isin(snapshots)].copy()
    if cal.duplicated(["snapshot_date", "listing_id"]).any():
        raise ValueError("calendar_listing_summary: trùng (snapshot_date, listing_id)")
    for c in ["n_calendar_days", "n_available_valid", "n_available",
              "availability_share", "coverage_share"]:
        cal[c] = pd.to_numeric(cal[c], errors="coerce")
    return cal


# Tính tỷ lệ lịch từ số đếm (không tin cột có sẵn một cách mù quáng):
#   availability_share_calc = n_available / n_available_valid
#       tỷ lệ ngày "khả dụng" trên các ngày quan sát được. Chỉ tính khi có
#       ngày quan sát (obs > 0), còn lại để trống, KHÔNG thành 0.
#   coverage_calc = n_available_valid / n_calendar_days
#       độ phủ: có bao nhiêu phần của cửa sổ lịch được quan sát.
# "available = f" gồm cả ngày đã đặt lẫn ngày bị chặn, nên đây KHÔNG phải
# occupancy và không dùng để ước doanh thu.
def add_calendar_kpis(cal: pd.DataFrame) -> pd.DataFrame:
    """Tính lại tỷ lệ từ số đếm, rồi đối chiếu với cột có sẵn của TV2.

    days_observed     = n_available_valid      (số ngày quan sát được)
    availability_share = n_available / n_available_valid
    coverage          = n_available_valid / n_calendar_days
    """
    cal = cal.copy()
    obs = cal["n_available_valid"]
    cal["availability_share_calc"] = (cal["n_available"] / obs).where(obs > 0)
    cal["coverage_calc"] = obs / cal["n_calendar_days"]
    return cal


# ------------------------------------------------------------------ KPI
# ------------------------------------------------------------------ KPI
# Quy tắc chung cho mọi KPI:
#   - Tính trên bảng sau QA của TV2; cờ hợp lệ (price_valid, room_type_valid, rating_valid)
#     lấy từ TV2, không tự suy lại.
#   - Median và quantile tính TRỰC TIẾP từ listing hợp lệ của nhóm, không lấy trung bình các median.
#   - Tỷ lệ = số đạt điều kiện / số hợp lệ làm mẫu số, không phải trên toàn bộ listing.
#   - Nhóm thiếu dữ liệu: để NaN và ghi số mẫu = 0, không điền 0.
#   - Tiền tệ: CAD/đêm. Tỷ lệ lưu dạng 0–1.
# Hàm này tính KPI cho một nhóm: cả mốc, hoặc mốc × khu vực, hoặc mốc × loại phòng.
# Mỗi dòng trong g là một listing đã ghép lịch.
def _metrics(g: pd.DataFrame) -> dict:
    n = len(g)
    pv = g.loc[g["price_ok"], "price_cad"]
    n_rtv = int(g["room_ok"].sum())
    n_ent = int((g["room_ok"] & g["room_type"].eq(ENTIRE)).sum())
    cal = g.loc[g["has_cal"], "availability_share_calc"]
    rt = g.loc[g["rating_ok"], "rating"]
    return {
        # ---- KPI 1. n_listings — Số listing
        #   Mục tiêu : quy mô nguồn cung tại mốc.
        #   Công thức: số listing_id duy nhất trong nhóm.
        #   Đơn vị   : listing.
        #   Hạn chế  : là số listing hiển thị khi thu thập, không phải số chủ nhà đang hoạt động.
        "n_listings": n,

        # ---- KPI 2. median_price_cad (kèm price_q1_cad, price_q3_cad) — Giá niêm yết trung vị
        #   Mục tiêu : mức giá điển hình một đêm và độ phân tán.
        #   Công thức: median(price_cad) trên listing price_ok; price_ok = price_valid và price_cad > 0,
        #              và loại thêm price_outlier_flag nếu chạy với --exclude-price-outliers.
        #              Q1, Q3 là phân vị 25% và 75% trên cùng tập.
        #   Đơn vị   : CAD/đêm.
        #   Mẫu số   : n_price_valid. Nhóm không có giá hợp lệ thì để NaN.
        #   Hạn chế  : giá niêm yết, không phải giá đã đặt; chưa hiệu chỉnh theo số khách.
        #              Các listing có price_outlier_flag vẫn được tính mặc định.
        "n_price_valid": int(len(pv)),
        "median_price_cad": pv.median() if len(pv) else np.nan,
        "price_q1_cad": pv.quantile(0.25) if len(pv) else np.nan,
        "price_q3_cad": pv.quantile(0.75) if len(pv) else np.nan,

        # ---- KPI 3. entire_home_share — Tỷ lệ Entire home/apt
        #   Mục tiêu : thị trường thiên về nguyên căn hay phòng chia sẻ.
        #   Công thức: n(room_type = "Entire home/apt") / n(room_type hợp lệ).
        #   Đơn vị   : tỷ lệ 0–1.
        #   Mẫu số   : n_room_type_valid, loại trừ Unknown. Mẫu số = 0 thì NaN.
        #   Hạn chế  : mô tả thành phần cung, không cho biết nhu cầu.
        "n_room_type_valid": n_rtv,
        "entire_home_share": n_ent / n_rtv if n_rtv else np.nan,

        # ---- KPI 4. availability_share_mean — Tỷ lệ mở lịch quan sát được
        #   Mục tiêu : trong các ngày quan sát được, listing mở bao nhiêu phần lịch.
        #   Công thức: với mỗi listing, availability_share_calc = n_available / n_available_valid;
        #              lấy trung bình trên listing có lịch (has_cal). Đây là trung bình của các
        #              tỷ lệ theo listing, không phải tỷ lệ gộp.
        #   Đơn vị   : tỷ lệ 0–1.
        #   Mẫu số   : n_calendar_listings (số listing có ít nhất một ngày quan sát được).
        #   Hạn chế  : "available = f" gồm cả ngày đã đặt lẫn ngày bị chặn, KHÔNG phải occupancy,
        #              không dùng để ước doanh thu.
        "n_calendar_listings": int(g["has_cal"].sum()),
        "availability_share_mean": cal.mean() if len(cal) else np.nan,
        # Cột phụ (không phải KPI riêng): calendar_coverage_mean = trung bình coverage_calc trên
        # TẤT CẢ listing của nhóm; listing không có lịch được tính 0 (đúng định nghĩa đã nộp).
        # Phản ánh cả việc thiếu lịch, khác với availability_share_mean.
        "calendar_coverage_mean": g["coverage_calc"].mean() if n else np.nan,

        # ---- KPI 5. median_rating — Điểm đánh giá trung vị
        #   Mục tiêu : chất lượng cảm nhận điển hình của listing đã có đánh giá.
        #   Công thức: median(review_scores_rating) trên listing có rating_valid theo QA.
        #   Đơn vị   : điểm theo thang của nguồn (Inside Airbnb dùng thang 0–5).
        #   Mẫu số   : n_rating_valid. Listing mới chưa có điểm bị loại khỏi mẫu, không điền 0.
        "n_rating_valid": int(len(rt)),
        "median_rating": rt.median() if len(rt) else np.nan,
    }


def _table(df: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    rows = []
    for key, g in df.groupby(keys, sort=True):
        key = key if isinstance(key, tuple) else (key,)
        rows.append({**dict(zip(keys, key)), **_metrics(g)})
    return pd.DataFrame(rows)


def build_tables(df: pd.DataFrame):
    snap = _table(df, ["snapshot_date"])[SNAPSHOT_COLS]

    area = _table(df, ["snapshot_date", "neighbourhood_cleansed"])
    area = area[["snapshot_date", "neighbourhood_cleansed"] + SNAPSHOT_COLS[1:]]

    # ---- KPI 6. area_price_premium — Chênh lệch giá khu vực so với thành phố (theo khu vực)
    #   Mục tiêu : khu vực nào đắt hơn hoặc rẻ hơn mặt bằng chung của Toronto trong cùng mốc.
    #   Công thức: median_price_cad(khu vực) / median_price_cad(thành phố, cùng mốc) − 1.
    #              Ví dụ 0,20 nghĩa là khu vực đắt hơn trung vị thành phố 20%.
    #   Đơn vị   : tỷ lệ. Tiền gốc là CAD/đêm.
    #   Mẫu số   : n_price_valid của khu vực. Điều kiện để tính:
    #              khu vực không phải Unknown; n_price_valid >= MIN_N_SHARE (30);
    #              cả hai median đều có giá trị. Không đạt thì để NaN.
    #   Đối chiếu: cột city_median_price_cad được ghi kèm trong kpi_area.csv.
    #   Hạn chế  : so sánh thành phần listing, không phải giá của cùng một căn.
    city_med = snap.set_index("snapshot_date")["median_price_cad"]
    area["city_median_price_cad"] = area["snapshot_date"].map(city_med)
    ok = (area["neighbourhood_cleansed"].ne(UNKNOWN)
          & (area["n_price_valid"] >= MIN_N_SHARE)
          & area["median_price_cad"].notna() & area["city_median_price_cad"].notna())
    area["area_price_premium"] = (area["median_price_cad"] / area["city_median_price_cad"] - 1).where(ok)

    rt = _table(df, ["snapshot_date", "room_type"]).drop(columns="entire_home_share")
# room_type_share = n_listings(loại) / n_room_type_valid(cả mốc).
# Mẫu số lấy từ bảng snapshot, không phải tổng của riêng nhóm loại phòng, nên
# tổng share các loại hợp lệ bằng 1 (được kiểm tra trong run_checks).
# Nhóm Unknown không có share (để trống) nhưng vẫn có dòng để hiển thị.
    snap_valid = snap.set_index("snapshot_date")["n_room_type_valid"]
    rt["n_room_type_valid"] = rt["snapshot_date"].map(snap_valid)
    is_valid = rt["room_type"].ne(UNKNOWN)
    rt["room_type_share"] = (rt["n_listings"] / rt["n_room_type_valid"]).where(
        is_valid & rt["n_room_type_valid"].gt(0))
    rt = rt[["snapshot_date", "room_type", "n_listings", "n_price_valid",
             "median_price_cad", "price_q1_cad", "price_q3_cad",
             "n_room_type_valid", "room_type_share", "n_calendar_listings",
             "availability_share_mean", "calendar_coverage_mean",
             "n_rating_valid", "median_rating"]]

# Bảng thiếu dữ liệu: đếm số listing Unknown room_type theo mốc, để
# thấy mức thiếu mà không đưa nhóm này vào mẫu số của room_type.
    missing = (df.assign(is_unknown=df["room_type"].eq(UNKNOWN))
               .groupby("snapshot_date", as_index=False)
               .agg(n_listings=("listing_id", "size"),
                    n_unknown_room_type=("is_unknown", "sum")))
    missing["unknown_room_type_share"] = (
        missing["n_unknown_room_type"] / missing["n_listings"])
    return snap, area, rt, missing


# ----------------------------------------------------------- kiểm tra
#  Kiểm tra tự động. fail => dừng, không ghi KPI. WARN => ghi và cảnh báo.
#   sum_area_* / sum_room_type_*  : tổng theo khu vực / loại phòng phải bằng tổng mốc
#   sum_room_type_share_valid     : share các loại hợp lệ phải bằng 1
#   missing_table_total           : bảng thiếu phải có đủ số listing
#   price_all_values_readable     : không được có giá không đọc được (FAIL)
#   snapshot_has_valid_prices     : mốc không có giá hợp lệ nào (WARN)
#   calendar_share_matches_tv2    : tỷ lệ tự tính phải khớp cột TV2 (FAIL nếu lệch)
#   calendar_orphans_not_in_listings : có lịch không thuộc listing nào (WARN)
def run_checks(df, snap, area, rt, missing, cal_orphans, cal_mismatch) -> pd.DataFrame:
    rows = []

    def add(name, snapshot, value, expected, ok, severity="FAIL"):
        rows.append({"check": name, "snapshot_date": snapshot, "value": value,
                     "expected": expected,
                     "status": "PASS" if ok else severity})

    for s in snap["snapshot_date"]:
        s_row = snap.loc[snap["snapshot_date"] == s].iloc[0]
        a = area[area["snapshot_date"] == s]
        r = rt[rt["snapshot_date"] == s]
        for col in ["n_listings", "n_price_valid", "n_rating_valid"]:
            ga, gr = a[col].sum(), r[col].sum()
            add(f"sum_area_{col}", s, ga, s_row[col], ga == s_row[col])
            add(f"sum_room_type_{col}", s, gr, s_row[col], gr == s_row[col])
        if s_row["n_room_type_valid"] > 0:
            share = r["room_type_share"].sum()
            add("sum_room_type_share_valid", s, round(share, 10), 1.0,
                abs(share - 1.0) < 1e-9)
        m = missing.loc[missing["snapshot_date"] == s].iloc[0]
        add("missing_table_total", s, m["n_listings"], s_row["n_listings"],
            m["n_listings"] == s_row["n_listings"])

    n_bad = int(df["price_unparseable"].sum())
    add("price_all_values_readable", "ALL", n_bad, 0, n_bad == 0)
    for s in snap["snapshot_date"]:
        npv = int(snap.loc[snap["snapshot_date"] == s, "n_price_valid"].iloc[0])
        add("snapshot_has_valid_prices", s, npv, ">0", npv > 0, severity="WARN")

    add("calendar_share_matches_tv2", "ALL", cal_mismatch, 0.0,
        cal_mismatch < 1e-9)
    add("calendar_orphans_not_in_listings", "ALL", cal_orphans, 0,
        cal_orphans == 0, severity="WARN")
    return pd.DataFrame(rows)


# ---------------------------------------------------------- KPI 7 (theo thời gian)
# ---- KPI 7. delta_median_price_cad — Thay đổi giá trung vị so với mốc trước
#   Mục tiêu : hướng và độ lớn thay đổi giá niêm yết giữa hai mốc liền kề.
#   Công thức: median_price_cad(t) − median_price_cad(t−1), đơn vị CAD/đêm.
#   Mẫu số   : không có. Điều kiện: cả hai mốc phải có median; nếu thiếu thì để trống.
#   Mốc đầu tiên không có mốc trước nên để trống.
#   Không bắc cầu qua mốc thiếu giá (ví dụ 2025-12-12 thiếu giá thì không so 2026-03-19 với 2025-09-11).
#   Hạn chế  : thành phần listing có thể khác giữa hai mốc; đây không phải giá của cùng một căn.
def build_time(snap: pd.DataFrame) -> pd.DataFrame:
    s = snap.sort_values("snapshot_date").reset_index(drop=True)
    prev = s.shift(1)
    out = pd.DataFrame({
        "snapshot_date": s["snapshot_date"],
        "prev_snapshot_date": prev["snapshot_date"],
        "median_price_cad": s["median_price_cad"],
        "prev_median_price_cad": prev["median_price_cad"],
    })
    out["delta_median_price_cad"] = out["median_price_cad"] - out["prev_median_price_cad"]
    return out


# ------------------------------------------------------------- KPI dùng LLM
# Đầu vào: JSONL do llm.py (TV4) ghi, mỗi dòng là một review với các khoá:
#   snapshot_date, review_id, listing_id, status (ok | needs_review | error),
#   sentiment (positive | mixed | negative | null), aspects ([{aspect, polarity}]),
#   language, error, split (tuỳ chọn).
# Một review chỉ được tính là "dùng được" khi status = "ok" VÀ sentiment thuộc LLM_LABELS.

def read_llm(path: str, snapshots) -> pd.DataFrame:
    # Đọc JSONL từng dòng. Dòng lỗi JSON báo rõ số dòng để TV4 sửa.
    records = []
    with open(path, encoding="utf-8") as f:
        for n, line in enumerate(f, start=1):
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise ValueError(f"{path} dòng {n}: không phải JSON hợp lệ") from e
    df = pd.DataFrame(records)
    if df.empty:
        raise ValueError(f"{path} không có dòng nào")
    _require(df, ["snapshot_date", "review_id", "listing_id", "status", "sentiment", "aspects"],
             os.path.basename(path))
    for c in ["snapshot_date", "review_id", "listing_id"]:
        df[c] = df[c].astype(str).str.strip()
    if snapshots is not None:
        df = df[df["snapshot_date"].isin(snapshots)].copy()
        if df.empty:
            raise ValueError(f"{path} không có review cho các mốc KPI được chọn")
    if df.duplicated(["snapshot_date", "review_id"]).any():
        raise ValueError("llm: trùng (snapshot_date, review_id) — TV4 cần sửa")
    # valid: LLM trả đúng định dạng (status ok). usable: valid và nhãn thuộc LLM_LABELS.
    # usable là mẫu số của mọi tỷ lệ cảm xúc.
    df["valid"] = df["status"].eq("ok")
    df["label"] = df["sentiment"].where(df["valid"])
    df["usable"] = df["valid"] & df["label"].isin(LLM_LABELS)
    df["aspects"] = df["aspects"].apply(lambda v: v if isinstance(v, list) else [])
    return df


def attach_area(llm: pd.DataFrame, listings: pd.DataFrame) -> pd.DataFrame:
    # Gắn neighbourhood_cleansed của listing vào từng review (cùng mốc).
    # Review không khớp listing nào được gán Unknown, không bỏ đi.
    area = listings[["snapshot_date", "listing_id", "neighbourhood_cleansed"]]
    out = llm.merge(area, on=["snapshot_date", "listing_id"], how="left",
                    validate="many_to_one")
    out["neighbourhood_cleansed"] = out["neighbourhood_cleansed"].fillna(UNKNOWN)
    return out


def llm_metrics(g: pd.DataFrame, min_n: int) -> dict:
    # ---- KPI 8. llm_negative_share — Tỷ lệ đánh giá tiêu cực theo LLM (theo mốc và khu vực)
    #   Mục tiêu : phản ánh mức độ không hài lòng của khách, theo mốc và theo khu vực.
    #   Công thức: n(sentiment = negative, dùng được) / n(dùng được).
    #              "Dùng được" = status = "ok" VÀ sentiment thuộc LLM_LABELS (positive, mixed, negative).
    #   Đơn vị   : tỷ lệ 0–1.
    #   Mẫu số   : n_llm_usable. Nếu nhỏ hơn MIN_N_SHARE (30) thì để NaN (mẫu quá nhỏ).
    #   Hạn chế  : chỉ trên mẫu review do TV4 chạy LLM, không phải toàn bộ review;
    #              độ chính xác phụ thuộc LLM, cần đối chiếu với nhãn tay.
    #   Cột phụ  : llm_positive_share (tương tự, chiều tích cực) và llm_parse_coverage
    #              (= n(status ok) / n(mẫu), đo chất lượng đầu ra LLM, không phải KPI thị trường).
    n = len(g)
    n_use = int(g["usable"].sum())
    enough = n_use >= min_n and n_use > 0
    pos = int((g["usable"] & g["label"].eq("positive")).sum())
    neg = int((g["usable"] & g["label"].eq("negative")).sum())
    return {
        "n_llm_sample": n,
        "n_llm_usable": n_use,
        "llm_parse_coverage": g["valid"].sum() / n if n else np.nan,
        "llm_positive_share": pos / n_use if enough else np.nan,
        "llm_negative_share": neg / n_use if enough else np.nan,
    }


def llm_tables(llm_area: pd.DataFrame, min_n: int):
    snap_rows, area_rows = [], []
    for s, g in llm_area.groupby("snapshot_date", sort=True):
        snap_rows.append({"snapshot_date": s, **llm_metrics(g, min_n)})
        for a, ga in g.groupby("neighbourhood_cleansed", sort=True):
            area_rows.append({"snapshot_date": s, "neighbourhood_cleansed": a,
                              **llm_metrics(ga, min_n)})
    return pd.DataFrame(snap_rows), pd.DataFrame(area_rows)


def aspect_table(llm_area: pd.DataFrame, min_n: int) -> pd.DataFrame:
    # KPI theo khía cạnh do LLM trích xuất, chỉ trên review dùng được.
    #   aspect_mention_share  = n(review nhắc khía cạnh) / n(dùng được)
    #   aspect_negative_share = n(nhắc với polarity negative) / n(nhắc), cần n(nhắc) >= min_n
    # Một review nhắc cùng khía cạnh nhiều lần chỉ được đếm một lần.
    rows = []
    for s, g in llm_area.groupby("snapshot_date", sort=True):
        usable = g[g["usable"]]
        n_use = len(usable)
        mentions = []
        for aspects in usable["aspects"]:
            seen = set()
            for a in aspects:
                name = a.get("aspect") if isinstance(a, dict) else None
                if name and name not in seen:
                    seen.add(name)
                    mentions.append((name, a.get("polarity")))
        if not mentions:
            continue
        m = pd.DataFrame(mentions, columns=["aspect", "polarity"])
        for asp, ga in m.groupby("aspect", sort=True):
            n_m = len(ga)
            n_neg = int(ga["polarity"].eq("negative").sum())
            rows.append({"snapshot_date": s, "aspect": asp, "n_aspect_mentions": n_m,
                         "n_llm_usable": n_use,
                         "aspect_mention_share": n_m / n_use if n_use else np.nan,
                         "aspect_negative_share": n_neg / n_m if n_m >= min_n else np.nan})
    return pd.DataFrame(rows, columns=ASPECT_COLS)


def llm_checks(llm: pd.DataFrame, listings: pd.DataFrame) -> pd.DataFrame:
    # Kiểm tra đầu vào LLM. Đây là WARN (không dừng): dòng lỗi đã loại khỏi mẫu số
    # và được đếm ở đây để nhóm biết.
    rows = []

    def add(name, value, expected, ok):
        rows.append({"check": name, "snapshot_date": "ALL", "value": value,
                     "expected": expected, "status": "PASS" if ok else "WARN"})

    keys_l = set(zip(listings["snapshot_date"], listings["listing_id"]))
    orphan = sum(1 for k in zip(llm["snapshot_date"], llm["listing_id"]) if k not in keys_l)
    add("llm_listing_in_listings", orphan, 0, orphan == 0)
    bad_label = int((llm["valid"] & ~llm["usable"]).sum())
    add("llm_ok_sentiment_in_labels", bad_label, 0, bad_label == 0)
    bad_status = int((~llm["status"].isin({"ok", "needs_review", "error"})).sum())
    add("llm_status_known", bad_status, 0, bad_status == 0)
    bad_pol = 0
    for aspects in llm.loc[llm["usable"], "aspects"]:
        for a in aspects:
            if isinstance(a, dict) and a.get("polarity") not in LLM_LABELS:
                bad_pol += 1
    add("llm_aspect_polarity_in_labels", bad_pol, 0, bad_pol == 0)
    return pd.DataFrame(rows)


def build_llm_outputs(path, snapshots, listings, min_n):
    llm = read_llm(path, snapshots)
    checks = llm_checks(llm, listings)
    llm_area = attach_area(llm, listings)
    snap_t, area_t = llm_tables(llm_area, min_n)
    asp_t = aspect_table(llm_area, min_n)
    tables = {"kpi_llm_snapshot.csv": snap_t,
              "kpi_llm_area.csv": area_t,
              "kpi_llm_aspect.csv": asp_t}
    return checks, tables


# ----------------------------------------------------------------- chạy
def run(cfg: dict) -> dict:
    in_dir = cfg["input_dir"]
    out_dir = cfg["output_dir"]
    checks_file = cfg.get("checks_path", "data/processed/kpi_checks.csv")
    for folder in (out_dir, os.path.dirname(checks_file) or "."):
        if os.path.isfile(folder):
            raise ValueError(
                f"'{folder}' đang là một FILE, không phải thư mục. "
                "Xoá hoặc đổi tên file đó rồi chạy lại.")
    checks_path = cfg.get("checks_path", "data/processed/kpi_checks.csv")
    snapshots = cfg.get("snapshots")
    if snapshots is not None:
        snapshots = [str(s) for s in snapshots]
    exclude_outliers = bool(cfg.get("exclude_price_outliers", False))

    raw_l, raw_c = read_inputs(in_dir, snapshots)
    listings = load_listings(raw_l, snapshots, exclude_outliers)
    cal = add_calendar_kpis(load_calendar(raw_c, snapshots))

    if snapshots is None:
        snapshots = sorted(listings["snapshot_date"].unique())
    for s in snapshots:
        if not (listings["snapshot_date"] == s).any():
            raise ValueError(f"Không có listing nào cho mốc {s}")

    # Ghép lịch vào listing theo (snapshot_date, listing_id), phải 1–1
    df = listings.merge(
        cal[["snapshot_date", "listing_id", "n_available_valid",
             "availability_share_calc", "coverage_calc"]],
        on=["snapshot_date", "listing_id"], how="left", validate="one_to_one")
#Ghép lịch vào listing theo (snapshot_date, listing_id), validate
# "one_to_one" để báo lỗi ngay nếu một listing có nhiều dòng lịch trong cùng
# mốc. Listing không có lịch: has_cal = False và coverage = 0.
    df["has_cal"] = df["n_available_valid"].fillna(0).gt(0)
    df["coverage_calc"] = df["coverage_calc"].fillna(0.0)

    # Kiểm tra: tỷ lệ tự tính có khớp cột của TV2 không
    both = cal.dropna(subset=["availability_share", "availability_share_calc"])
# NOTE — Đối chiếu: lấy độ lệch lớn nhất giữa tỷ lệ tự tính và cột của TV2.
# Nếu lệch, định nghĩa của hai bên khác nhau và phải thống nhất trước khi dùng KPI.
    cal_mismatch = float(np.max(np.abs(both["availability_share"] - both["availability_share_calc"]))) if len(both) else 0.0
    cov_both = cal.dropna(subset=["coverage_share", "coverage_calc"])
    if len(cov_both):
        cal_mismatch = max(cal_mismatch, float(np.max(np.abs(cov_both["coverage_share"] - cov_both["coverage_calc"]))))

    keys_l = set(zip(listings["snapshot_date"], listings["listing_id"]))
    keys_c = set(zip(cal["snapshot_date"], cal["listing_id"]))
    cal_orphans = len(keys_c - keys_l)

    snap, area, rt, missing = build_tables(df)
    checks = run_checks(df, snap, area, rt, missing, cal_orphans, cal_mismatch)
    # KPI 7 (theo thời gian) tính từ bảng snapshot đã có median giá; xem build_time.
    time_tbl = build_time(snap)

    # KPI 8 (dùng LLM) là tuỳ chọn: chỉ tính khi có file JSONL của TV4 (llm_file).
    # Thiếu file thì KPI 1–7 vẫn chạy và có cảnh báo llm_file_present.
    llm_path = cfg.get("llm_file")
    llm_out = {}
    if llm_path and os.path.exists(llm_path):
        llm_checks_df, llm_out = build_llm_outputs(llm_path, snapshots, listings, MIN_N_SHARE)
        checks = pd.concat([checks, llm_checks_df], ignore_index=True)
    elif llm_path:
        checks = pd.concat([checks, pd.DataFrame([{
            "check": "llm_file_present", "snapshot_date": "ALL", "value": 0,
            "expected": 1, "status": "WARN"}])], ignore_index=True)

    os.makedirs(os.path.dirname(checks_path) or ".", exist_ok=True)
    checks.to_csv(checks_path, index=False)
    if (checks["status"] == "FAIL").any():
        raise AssertionError("KPI không qua kiểm tra:\n"
                             + checks[checks["status"] == "FAIL"].to_string(index=False))

    os.makedirs(out_dir, exist_ok=True)
    outputs = {
        "kpi_snapshot.csv": snap,
        "kpi_area.csv": area,
        "kpi_room_type.csv": rt,
        "kpi_room_type_missing.csv": missing,
        "kpi_time.csv": time_tbl,
    }
    outputs.update(llm_out)
    for name, table in outputs.items():
        t = table.copy()
        for col, nd in ROUND.items():
            if col in t.columns:
                t[col] = t[col].round(nd)
        t.to_csv(os.path.join(out_dir, name), index=False)

    return {
        "snapshots": snapshots,
        "outputs": {k: os.path.join(out_dir, k) for k in outputs},
        "checks": checks_path,
        "warnings": int((checks["status"] == "WARN").sum()),
        "exclude_price_outliers": exclude_outliers,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="TV3: tính KPI theo mốc")
    ap.add_argument("--input-dir", default="data/processed")
    ap.add_argument("--output-dir", default=OUT_DIR_DEFAULT)
    ap.add_argument("--checks-path", default="data/processed/kpi_checks.csv")
    ap.add_argument("--snapshots", default="all",
                    help="'all' hoặc danh sách cách nhau bởi dấu phẩy, ví dụ 2025-09-11,2025-11-11")
    ap.add_argument("--exclude-price-outliers", action="store_true")
    ap.add_argument("--llm-file", default=LLM_FILE_DEFAULT,
                    help="JSONL kết quả LLM của TV4; thiếu file thì bỏ qua KPI LLM")
    args = ap.parse_args()

    snapshots = None if args.snapshots == "all" else [s.strip() for s in args.snapshots.split(",")]
    cfg = {
        "input_dir": args.input_dir,
        "output_dir": args.output_dir,
        "checks_path": args.checks_path,
        "snapshots": snapshots,
        "exclude_price_outliers": args.exclude_price_outliers,
        "llm_file": args.llm_file,
    }
    try:
        result = run(cfg)
    except (FileNotFoundError, ValueError, AssertionError) as e:
        print(f"Lỗi: {e}", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
