"""Tạo check_<ma_du_lieu>.csv (Phần 1 của đề kiểm tra dữ liệu).

Chạy từ gốc repo:
    python tao_check_csv.py --raw data/raw --ids data-new.csv --ma DSE2049-C04-G07-toronto \
        --snapshots 2025-09-11 2025-12-12 2026-03-19 2026-06-15

--ids: file có cột listing_id (ID listing của nhóm) và review_id (ID review của nhóm),
       lấy từ sheet Phân công. Nếu có cột trùng tên, lấy cột đầu tiên.
Đầu ra: reports/check_<ma_du_lieu>.csv, đúng 4 dòng, đúng thứ tự cột trong đề.

Ô rỗng nghĩa là không tính được (ví dụ tệp thiếu). Script không đoán giá trị.
"""
import argparse
import os

import pandas as pd

COLS = ["ma_du_lieu", "moc", "ngay", "tai_ve_ok", "listings_bytes", "calendar_bytes", "reviews_bytes",
        "listings_dong", "calendar_dong", "reviews_dong", "entire_home", "private_room",
        "khong_co_review", "thieu_price", "so_cot_listings", "so_cot_nan_90"]
FILES = {"listings": "listings.csv.gz", "calendar": "calendar.csv.gz", "reviews": "reviews.csv.gz"}
ENTIRE, PRIVATE = "Entire home/apt", "Private room"


def read_group_ids(path):
    df = pd.read_csv(path, dtype=str)
    lst_col = df.columns[df.columns.str.startswith("listing_id")][0]
    rv_col = df.columns[df.columns.str.startswith("review_id")][0]
    lst = set(df[lst_col].dropna().str.strip())
    rv = set(df[rv_col].dropna().str.strip())
    return lst, rv


def check_one(raw_dir, snap, moc, ma, lst_ids, rv_ids):
    d = os.path.join(raw_dir, snap)
    paths = {k: os.path.join(d, v) for k, v in FILES.items()}
    row = dict.fromkeys(COLS)
    row.update(ma_du_lieu=ma, moc=moc, ngay=snap)

    missing = [k for k, p in paths.items() if not os.path.exists(p)]
    row["tai_ve_ok"] = "co" if not missing else f"thieu:{'+'.join(missing)}"
    for k in FILES:
        if os.path.exists(paths[k]):
            row[f"{k}_bytes"] = os.path.getsize(paths[k])
    if missing:
        return row

    # --- listings: đọc đủ cột để đếm NaN trên toàn tệp và trên nhóm ---
    full = pd.read_csv(paths["listings"], dtype=str, low_memory=False, compression="gzip")
    row["so_cot_listings"] = full.shape[1]
    ls = full[full["id"].astype(str).str.strip().isin(lst_ids)]
    row["listings_dong"] = len(ls)
    row["entire_home"] = int(ls["room_type"].eq(ENTIRE).sum())
    row["private_room"] = int(ls["room_type"].eq(PRIVATE).sum())
    nrev = pd.to_numeric(ls["number_of_reviews"], errors="coerce")
    row["khong_co_review"] = int(nrev.eq(0).sum())
    row["thieu_price"] = int(ls["price"].isna().sum())
    if len(ls):
        row["so_cot_nan_90"] = int((ls.isna().mean() >= 0.9).sum())

    # --- calendar: tệp lớn, đọc theo khối và chỉ đếm dòng của nhóm ---
    n_cal = 0
    for chunk in pd.read_csv(paths["calendar"], dtype={"listing_id": str}, usecols=["listing_id"],
                             chunksize=500_000, compression="gzip"):
        n_cal += int(chunk["listing_id"].astype(str).str.strip().isin(lst_ids).sum())
    row["calendar_dong"] = n_cal

    # --- reviews: lọc theo listing của nhóm ---
    rv = pd.read_csv(paths["reviews"], dtype={"listing_id": str, "id": str}, usecols=["listing_id", "id"],
                     compression="gzip")
    row["reviews_dong"] = int(rv["listing_id"].astype(str).str.strip().isin(lst_ids).sum())
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default=os.path.join("data", "raw"))
    ap.add_argument("--ids", required=True)
    ap.add_argument("--ma", required=True, help="Mã dữ liệu, ví dụ DSE2049-C04-G07-toronto")
    ap.add_argument("--snapshots", nargs="+", required=True, help="Các mốc theo thứ tự 1..4")
    ap.add_argument("--out", default=os.path.join("reports"))
    args = ap.parse_args()

    lst_ids, _ = read_group_ids(args.ids)
    rows = [check_one(args.raw, s, i + 1, args.ma, lst_ids, None) for i, s in enumerate(args.snapshots)]
    out = pd.DataFrame(rows, columns=COLS)
    os.makedirs(args.out, exist_ok=True)
    path = os.path.join(args.out, f"check_{args.ma}.csv")
    out.to_csv(path, index=False, encoding="utf-8")
    print(out.to_string(index=False))
    print("\nĐã ghi:", path)


if __name__ == "__main__":
    main()