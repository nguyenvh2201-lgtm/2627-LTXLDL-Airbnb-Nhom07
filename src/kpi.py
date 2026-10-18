"""TV3 — Tính KPI theo mốc chụp từ bảng sạch của TV2 (nhóm 7, Toronto).

Đầu vào (trong input_dir):
  listings_clean.csv
      snapshot_date, listing_id, neighbourhood_cleansed, room_type, price_cad,
      price_valid, price_outlier_flag, room_type_valid, review_scores_rating,
      rating_valid, ...
  calendar_listing_summary.csv
      snapshot_date, listing_id, n_calendar_days, n_available_valid,
      n_available, availability_share, coverage_share

Đầu ra (trong output_dir), một file cho tất cả mốc:
  kpi_snapshot.csv, kpi_area.csv, kpi_room_type.csv, kpi_room_type_missing.csv
Kiểm tra: checks_path (mặc định reports/kpi_checks.csv). Có FAIL thì không ghi KPI.

Chạy:
  python kpi.py                                    # mặc định data/processed -> reports/kpi_results
  python kpi.py --snapshots 2025-09-11             # chỉ một mốc
  python kpi.py --exclude-price-outliers           # bỏ listing có price_outlier_flag khỏi KPI giá
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
}


# ------------------------------------------------------------- đọc & kiểm tra

# Hàm này chuẩn hoá cả hai về số thực CAD/đêm. Ô không đọc được -> NaN và được
# đánh dấu price_unparseable để kiểm tra báo FAIL (xem run_checks).
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

#Điểm đánh giá (n_rating_valid, median_rating): chỉ listing có điểm
# không trống. Listing mới chưa có review bị loại khỏi mẫu, không điền 0.
    df["rating"] = pd.to_numeric(df["review_scores_rating"], errors="coerce")
    df["rating_ok"] = df["rating"].notna()
    if (_to_bool(df["rating_valid"]) != df["rating_ok"]).any():
        raise ValueError("rating_valid không khớp với review_scores_rating không trống")
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
#Hàm này tính TẤT CẢ KPI cho một nhóm (cả mốc, hoặc mốc × khu vực,
# hoặc mốc × loại phòng). Mỗi dòng trong g là một listing đã gộp lịch.
# Quy tắc chung: median và quantile tính TRỰC TIẾP từ listing hợp lệ của nhóm,
# không lấy trung bình của các median; tỷ lệ là (số hợp lệ đạt điều kiện) /
# (số hợp lệ làm mẫu số), không phải trên toàn bộ listing.
def _metrics(g: pd.DataFrame) -> dict:
    n = len(g)
    pv = g.loc[g["price_ok"], "price_cad"]
    n_rtv = int(g["room_ok"].sum())
    n_ent = int((g["room_ok"] & g["room_type"].eq(ENTIRE)).sum())
    cal = g.loc[g["has_cal"], "availability_share_calc"]
    rt = g.loc[g["rating_ok"], "rating"]
    return {
        "n_listings": n,
        # KPI 1–2 — n_listings = số listing; n_price_valid = mẫu số của giá.
        # Median/Q1/Q3 tính trên pv (listing có giá hợp lệ). Nhóm không có giá
        # thì để NaN và n_price_valid = 0, không điền 0 làm giá.
        "n_price_valid": int(len(pv)),
        "median_price_cad": pv.median() if len(pv) else np.nan,
        "price_q1_cad": pv.quantile(0.25) if len(pv) else np.nan,
        "price_q3_cad": pv.quantile(0.75) if len(pv) else np.nan,
        # KPI 3 — entire_home_share = (số "Entire home/apt") / (số room_type hợp lệ).
        # Mẫu số loại trừ Unknown. Nếu mẫu số = 0 thì để NaN.
        "n_room_type_valid": n_rtv,
        "entire_home_share": n_ent / n_rtv if n_rtv else np.nan,
        # KPI 4 — availability_share_mean: trung bình availability_share_calc
        # CHỈ trên listing có lịch (has_cal). n_calendar_listings là mẫu số đó.
        # Đây là trung bình của các tỷ lệ theo listing, không phải tỷ lệ gộp.
        "n_calendar_listings": int(g["has_cal"].sum()),
        "availability_share_mean": cal.mean() if len(cal) else np.nan,
        # calendar_coverage_mean: trung bình coverage trên TẤT CẢ listing của nhóm;
        # listing không có lịch được tính 0 (đúng định nghĩa đã nộp). Vì vậy
        # KPI này phản ánh cả việc thiếu lịch, khác với availability_share_mean.
        # listing không có lịch tính coverage = 0, đúng định nghĩa đã nộp
        "calendar_coverage_mean": g["coverage_calc"].mean() if n else np.nan,
        # KPI 5 — median_rating: median review_scores_rating trên listing có điểm.
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


# ----------------------------------------------------------------- chạy
def run(cfg: dict) -> dict:
    in_dir = cfg["input_dir"]
    out_dir = cfg["output_dir"]
    checks_file = cfg.get("checks_path", "reports/kpi_checks.csv")
    for folder in (out_dir, os.path.dirname(checks_file) or "."):
        if os.path.isfile(folder):
            raise ValueError(
                f"'{folder}' đang là một FILE, không phải thư mục. "
                "Xoá hoặc đổi tên file đó rồi chạy lại.")
    checks_path = cfg.get("checks_path", "reports/kpi_checks.csv")
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
    }
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
    ap.add_argument("--output-dir", default="reports/kpi_results")
    ap.add_argument("--checks-path", default="reports/kpi_checks.csv")
    ap.add_argument("--snapshots", default="all",
                    help="'all' hoặc danh sách cách nhau bởi dấu phẩy, ví dụ 2025-09-11,2025-11-11")
    ap.add_argument("--exclude-price-outliers", action="store_true")
    args = ap.parse_args()

    snapshots = None if args.snapshots == "all" else [s.strip() for s in args.snapshots.split(",")]
    cfg = {
        "input_dir": args.input_dir,
        "output_dir": args.output_dir,
        "checks_path": args.checks_path,
        "snapshots": snapshots,
        "exclude_price_outliers": args.exclude_price_outliers,
    }
    try:
        result = run(cfg)
    except (FileNotFoundError, ValueError, AssertionError) as e:
        print(f"Lỗi: {e}", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()