"""Cấu hình, tiện ích chung, tải/xác thực và lọc dữ liệu Inside Airbnb."""
import argparse
import csv
import gzip
import hashlib
import logging
import time
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import requests
import yaml


def load_config(path: str | Path) -> dict:
    """Đường dẫn dữ liệu tính từ thư mục cha của configs, không phụ thuộc cwd."""
    path = Path(path).resolve()
    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    for key in ("city", "currency", "data_root", "snapshots", "paths", "inputs", "qa", "kpi", "llm", "seed", "io", "download", "evaluation"):
        if key not in cfg:
            raise ValueError(f"Thiếu khóa cấu hình: {key}")
    dates = cfg["snapshots"]
    if len(dates) != 4 or len(set(dates)) != 4:
        raise ValueError("snapshots phải gồm đúng bốn ngày khác nhau")
    for value in dates:
        if not isinstance(value, str) or date.fromisoformat(value).isoformat() != value:
            raise ValueError("snapshots phải có dạng YYYY-MM-DD")
    cfg["snapshots"] = sorted(dates)
    for section in (cfg["paths"], {k: v for k, v in cfg["inputs"].items() if k != "columns"}):
        for key, value in section.items():
            if Path(value).is_absolute() or ".." in Path(value).parts:
                raise ValueError(f"Đường dẫn {key} phải tương đối trong dự án")
    for key in ("sample_size", "batch_size", "rate_limit_per_min", "retries", "max_chars"):
        if cfg["llm"][key] <= 0:
            raise ValueError(f"llm.{key} phải dương")
    if cfg["io"]["chunksize"] <= 0:
        raise ValueError("io.chunksize phải dương")
    cfg["_root"] = path.parent.parent
    cfg["_config_path"] = path
    return cfg


def path(cfg: dict, name: str, filename: str = "") -> Path:
    """Lấy thư mục từ config."""
    return Path(cfg["_root"]) / cfg["paths"][name] / filename


def setup_logging(cfg: dict) -> None:
    """Ghi đồng thời console và run_log, không log biến môi trường."""
    for name in cfg["paths"]:
        path(cfg, name).mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", handlers=[logging.StreamHandler(), logging.FileHandler(path(cfg, "reports", "run_log.txt"), encoding="utf-8")], force=True)


def save(cfg: dict, df: pd.DataFrame, name: str) -> None:
    """Ghi Parquet nén, giữ ID dạng chuỗi."""
    path(cfg, "processed").mkdir(parents=True, exist_ok=True)
    df.to_parquet(path(cfg, "processed", name + ".parquet"), index=False, compression="zstd")


def read(cfg: dict, name: str) -> pd.DataFrame:
    """Báo bước đầu vào còn thiếu rõ ràng."""
    source = path(cfg, "processed", name + ".parquet")
    if source.exists():
        return pd.read_parquet(source)
    # QA lưu CSV theo mốc. Đọc trực tiếp các file đó để không tạo thêm
    # một bản Parquet trùng dữ liệu sạch trong data/processed/.
    csv_name = {"listings_clean": "listings_clean.csv",
                "reviews_clean": "reviews_clean.csv",
                "calendar_clean": "calendar_flagged.csv"}.get(name)
    if csv_name is None:
        raise ValueError(f"Thiếu {source.name}; hãy chạy bước trước")
    blocks = []
    for snapshot in cfg["snapshots"]:
        target = path(cfg, "processed", f"{snapshot}/{csv_name}")
        if not target.exists():
            raise ValueError(f"Thiếu {target}; hãy chạy QA trước")
        frame = pd.read_csv(target, dtype={"listing_id": str, "review_id": str, "id": str})
        frame = frame.rename(columns={"snapshot_date": "snapshot"})
        if name == "listings_clean":
            frame = frame.drop(columns=["price"], errors="ignore")
            frame = frame.rename(columns={"listing_id": "id", "price_cad": "price",
                                          "price_outlier": "flag_outlier_price"})
            frame["price"] = pd.to_numeric(frame["price"], errors="coerce")
            valid_price = frame["price_valid"].fillna(False).astype(bool) if "price_valid" in frame else frame["price"].gt(0)
            frame["flag_outlier_price"] = frame["flag_outlier_price"].fillna(False).astype(bool) | ~valid_price
            min_invalid = frame["invalid_minimum_nights"].fillna(False).astype(bool)
            min_gt_max = frame["min_greater_max"].fillna(False).astype(bool) if "min_greater_max" in frame else False
            frame["flag_outlier_minimum_nights"] = min_invalid | min_gt_max
            frame["minimum_nights"] = pd.to_numeric(frame["minimum_nights"], errors="coerce")
            frame["number_of_reviews"] = pd.to_numeric(frame["number_of_reviews"], errors="coerce")
        elif name == "reviews_clean":
            frame = frame.rename(columns={"review_id": "id"})
            frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
        else:
            frame["date"] = pd.to_datetime(frame["date_parsed"], errors="coerce")
            frame["available"] = frame["available_clean"].map({"t": 1.0, "f": 0.0, "true": 1.0, "false": 0.0})
            frame = frame.loc[~frame["duplicate_calendar"].fillna(False).astype(bool)
                              & ~frame["calendar_available_conflict"].fillna(False).astype(bool)]
        blocks.append(frame)
    return pd.concat(blocks, ignore_index=True)


def csv_report(cfg: dict, records, filename: str, columns=None) -> None:
    """Lưu bảng báo cáo UTF-8."""
    path(cfg, "reports").mkdir(parents=True, exist_ok=True)
    pd.DataFrame(records, columns=columns).to_csv(path(cfg, "reports", filename), index=False)


def money(series: pd.Series) -> pd.Series:
    """Giá Inside Airbnb dùng dấu phẩy phân nghìn và dấu chấm thập phân."""
    return pd.to_numeric(series.astype("string").str.replace(r"[^0-9.\-]", "", regex=True), errors="coerce")


def cli(run) -> None:
    """Cho phép python -m src.<bước> --config ... hoặc python src/<bước>.py"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(Path(__file__).resolve().parents[1] / "configs/city.yaml"))
    parser.add_argument("--skip-llm", action="store_true")
    parser.add_argument("--skip-download", action="store_true")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    cfg = load_config(args.config)
    cfg["_options"] = vars(args)
    setup_logging(cfg)
    run(cfg)


TABLE_KEYS = {"listings": {"id"}, "calendar": {"listing_id", "date"}, "reviews": {"id", "listing_id", "date", "comments"}}


def build_url(cfg: dict, snapshot: str, table: str) -> str:
    """Chỉ dựng URL dữ liệu Inside Airbnb."""
    if table not in TABLE_KEYS:
        raise ValueError(f"Bảng không hợp lệ: {table}")
    return f"{cfg['download']['base_url']}/{cfg['data_root']}/{snapshot}/data/{table}.csv.gz"


def verify_file(source: Path, table: str) -> str:
    """Đọc hết gzip theo block để kiểm CRC, đồng thời tính SHA256 file nén."""
    if not source.exists() or source.stat().st_size == 0:
        raise ValueError(f"Tệp thiếu/rỗng: {source}")
    with gzip.open(source, "rt", encoding="utf-8") as handle:
        columns = next(csv.reader(handle))
        if not TABLE_KEYS[table].issubset(columns):
            raise ValueError(f"Thiếu cột khóa ở {source.name}")
    with gzip.open(source, "rb") as handle:
        while handle.read(1024 * 1024):
            pass
    with source.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def download_file(url: str, dest: Path, settings: dict) -> None:
    """Ghi tệp tạm, không để file tải dở được dùng làm đầu vào."""
    if urlparse(url).hostname != "data.insideairbnb.com" or urlparse(url).scheme != "https":
        raise ValueError("Chỉ tải HTTPS từ data.insideairbnb.com")
    dest.parent.mkdir(parents=True, exist_ok=True)
    temp = dest.with_suffix(dest.suffix + ".part")
    for attempt in range(settings["retries"]):
        try:
            with requests.get(url, stream=True, timeout=settings["timeout"], allow_redirects=False) as response:
                response.raise_for_status()
                if response.is_redirect:
                    raise ValueError("Không chấp nhận chuyển hướng ngoài nguồn đã xác nhận")
                with temp.open("wb") as handle:
                    for block in response.iter_content(settings["block_bytes"]):
                        handle.write(block)
            verify_file(temp, dest.name.split(".")[0])
            temp.replace(dest)
            return
        except (requests.RequestException, OSError, ValueError, EOFError) as exc:
            logging.warning("Tải lỗi %s lần %d: %s", url, attempt + 1, type(exc).__name__)
            if attempt + 1 == settings["retries"]:
                raise ValueError(f"Không tải được {url}; kiểm tra mạng hoặc cung cấp file trong data/raw") from None
            time.sleep(settings["backoff"] ** attempt)


def run_download(cfg: dict) -> None:
    """Kiểm các file có sẵn; skip-download vẫn xác thực và lập manifest."""
    records = []
    for snapshot in cfg["snapshots"]:
        for table in TABLE_KEYS:
            source = path(cfg, "raw", f"{snapshot}/{table}.csv.gz")
            url = build_url(cfg, snapshot, table)
            downloaded = False
            try:
                digest = verify_file(source, table)
            except (OSError, ValueError, EOFError):
                if cfg.get("_options", {}).get("skip_download"):
                    raise ValueError(f"File thiếu/hỏng khi --skip-download: {source}") from None
                download_file(url, source, cfg["download"])
                downloaded = True
                digest = verify_file(source, table)
            now = datetime.now(timezone.utc).isoformat()
            records.append({"snapshot": snapshot, "table": table, "url": url, "bytes": source.stat().st_size, "sha256": digest, "downloaded_at_utc": now if downloaded else "", "verified_at_utc": now, "origin": "downloaded" if downloaded else "preexisting_download_time_unknown"})
            logging.info("Đã xác thực %s %s", snapshot, table)
    csv_report(cfg, records, "download_manifest.csv")


def load_ids(cfg: dict) -> tuple:
    """Đọc ID dạng chuỗi tránh sai số nguyên lớn."""
    result = []
    for name in ("listing_ids", "review_ids", "areas"):
        frame = pd.read_csv(cfg["_root"] / cfg["inputs"][name], dtype=str).rename(columns={v: k for k, v in cfg["inputs"]["columns"][name].items()})
        key = "area" if name == "areas" else "id"
        if frame[key].isna().any() or frame[key].duplicated().any():
            raise ValueError(f"ID thiếu/trùng: {name}")
        result.append(frame)
    for key in ("in_llm_sample", "in_hand_label"):
        values = result[1][key].str.lower()
        if not values.isin(["true", "false"]).all():
            raise ValueError(f"Cờ {key} phải là True/False")
        result[1][key] = values.eq("true")
    return tuple(result)


def filtered_chunks(source, ids: set, key: str, chunksize: int, usecols=None) -> tuple:
    """Lọc ngay trong mỗi khối; không giữ toàn bộ dữ liệu thành phố."""
    blocks, total = [], 0
    for chunk in pd.read_csv(source, dtype={"id": "string", "listing_id": "string", "reviewer_id": "string", "host_id": "string"}, usecols=usecols, chunksize=chunksize, low_memory=False):
        total += len(chunk)
        blocks.append(chunk.loc[chunk[key].isin(ids)].copy())
    return pd.concat(blocks, ignore_index=True), total


def validate_snapshot(cfg: dict, snapshot: str, listings: pd.DataFrame, calendar: pd.DataFrame, reviews: pd.DataFrame, ids: tuple) -> list:
    """Kỳ vọng mốc chưa biết chỉ cảnh báo; lỗi cấu trúc luôn dừng."""
    expected = cfg.get("expected", {})
    by_snapshot = expected.get("by_snapshot", {})
    known = snapshot in by_snapshot
    snapshot_expected = by_snapshot.get(snapshot, {})
    records = []

    def wanted(name, fallback):
        return snapshot_expected.get(name, expected.get(name, fallback))

    def check(name, actual, wanted, structural=False):
        passed = actual == wanted
        severity = "error" if structural or known else "warning"
        records.append({"check": name, "snapshot": snapshot, "expected": wanted, "actual": actual, "passed": passed, "severity": severity})
        if not passed:
            logging.warning("%s: %s có %s, kỳ vọng %s (%s)", snapshot, name, actual, wanted, severity)

    check("listing_count", len(listings), wanted("listing_count", len(ids[0])))
    check("listing_unique", listings.id.nunique(), len(listings), True)
    check("review_count", len(reviews), wanted("review_count", len(ids[1])))
    check("review_unique", reviews.id.nunique(), len(reviews), True)
    check("calendar_listing_ids", set(calendar.listing_id) == set(listings.id), True)
    check("calendar_unique_dates", int(calendar.duplicated(["listing_id", "date"]).sum()), 0, True)
    days = calendar.groupby("listing_id").date.nunique()
    check("calendar_days_per_listing", bool(days.eq(cfg["io"]["calendar_days"]).all()), True)
    parsed_dates = pd.to_datetime(calendar.date, errors="coerce")
    check("calendar_valid_dates", bool(parsed_dates.notna().all()), True, True)
    ranges = calendar.assign(parsed_date=parsed_dates).groupby("listing_id").parsed_date.agg(["min", "max", "nunique"])
    check("calendar_contiguous_days", bool(((ranges["max"] - ranges["min"]).dt.days + 1).eq(ranges["nunique"]).all()), True, True)
    check("calendar_rows", len(calendar), len(listings) * cfg["io"]["calendar_days"])
    for room, count in wanted("room_types", {}).items():
        check("room_type:" + room, int(listings.room_type.eq(room).sum()), count)
    for field, key in (("in_llm_sample", "llm_count"), ("in_hand_label", "hand_count")):
        check(field, int(reviews[field].sum()), wanted(key, int(ids[1][field].sum())))
    check("hand_subset_llm", bool((~reviews.in_hand_label | reviews.in_llm_sample).all()), True, True)
    areas = listings.analysis_area.value_counts()
    check("area_count", len(areas), wanted("area_count", len(ids[2])))
    check("area_size_range", bool(areas.between(wanted("area_min", 0), wanted("area_max", len(listings))).all()), True)
    for name in ("zero_reviews", "missing_price"):
        if name not in snapshot_expected:
            continue
        count = snapshot_expected[name]
        actual = int(listings.number_of_reviews.eq(0).sum()) if name == "zero_reviews" else int(listings.price.isna().sum())
        check(name, actual, count)
    if not known:
        logging.warning("%s chưa có bộ kỳ vọng riêng; tiếp tục với số quan sát thực, không bù ID thiếu", snapshot)
    return records


def run_filter(cfg: dict) -> None:
    """Xuất ba bảng đã lọc và audit ID thiếu, tổng review thành phố."""
    ids = load_ids(cfg)
    tables = {name: [] for name in ("listings", "calendar", "reviews")}
    checks, missing, totals = [], [], []
    for snapshot in cfg["snapshots"]:
        logging.info("Lọc snapshot %s", snapshot)
        folder = path(cfg, "raw", snapshot)
        listings, _ = filtered_chunks(folder / "listings.csv.gz", set(ids[0].id), "id", cfg["io"]["chunksize"])
        listings = listings.drop(columns=["analysis_area"], errors="ignore").merge(ids[0], on="id", validate="one_to_one")
        listings["price"] = money(listings.price)
        header = pd.read_csv(folder / "calendar.csv.gz", nrows=0).columns
        usecols = [c for c in cfg["io"]["calendar_columns"] if c in header]
        calendar, _ = filtered_chunks(folder / "calendar.csv.gz", set(ids[0].id), "listing_id", cfg["io"]["chunksize"], usecols)
        reviews, total = filtered_chunks(folder / "reviews.csv.gz", set(ids[1].id), "id", cfg["io"]["chunksize"])
        reviews = reviews.merge(ids[1], on="id", validate="one_to_one")
        for table, frame, id_key, target in (("listings", listings, "id", ids[0]), ("reviews", reviews, "id", ids[1])):
            for value in sorted(set(target.id) - set(frame[id_key])):
                missing.append({"snapshot": snapshot, "table": table, "id": value})
        checks.extend(validate_snapshot(cfg, snapshot, listings, calendar, reviews, ids))
        totals.append({"snapshot": snapshot, "city_total_reviews": total})
        for name, frame in (("listings", listings), ("calendar", calendar), ("reviews", reviews)):
            frame["snapshot"] = snapshot
            tables[name].append(frame.sort_values("listing_id" if name == "calendar" else "id"))
    csv_report(cfg, checks, "filter_checks.csv")
    csv_report(cfg, missing, "missing_ids.csv", ["snapshot", "table", "id"])
    csv_report(cfg, totals, "city_review_counts.csv")
    errors = [r for r in checks if not r["passed"] and r["severity"] == "error"]
    if errors:
        raise ValueError(f"Lọc sai hoặc đọc sai ID: {len(errors)} kiểm tra bắt buộc không đạt; xem filter_checks.csv")
    for name, blocks in tables.items():
        save(cfg, pd.concat(blocks, ignore_index=True), name + "_raw_filtered")

def run(cfg: dict) -> None:
    """Tải/xác thực dữ liệu rồi lọc đúng phần của nhóm."""
    run_download(cfg)
    run_filter(cfg)


if __name__ == "__main__":
    cli(run)
