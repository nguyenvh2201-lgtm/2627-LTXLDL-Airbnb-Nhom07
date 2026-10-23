"""Tách ba bảng đặt cạnh nhau, ghép review thật, giữ riêng test/dev."""
from __future__ import annotations

import argparse
import collections
import csv
import gzip
import hashlib
import json
import random
import shutil
import urllib.request
from pathlib import Path

from .common import ROOT, load_config, normalize_text, now, path, read_csv, write_csv, write_json

REVIEW_FIELDS = ["snapshot_date", "review_id", "listing_id", "date", "comments",
                 "analysis_area", "is_llm", "is_manual_test", "split", "text_valid", "listing_match"]
LABEL_FIELDS = ["snapshot_date", "review_id", "listing_id", "date", "comments",
                "manual_sentiment", "needs_review", "note", "split"]


def read_marking(filename):
    with path(filename).open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.reader(stream))
    expected = ["Lớp", "Nhóm", "Mã dữ liệu", "listing_id", "analysis_area", "review_id",
                "listing_id", "Mẫu LLM", "Nhãn tay", "Thành phố", "analysis_area",
                "lon_min", "lat_min", "lon_max", "lat_max"]
    if not rows or rows[0] != expected:
        raise ValueError("Header bảng đánh dấu khác bản đã kiểm tra; không tự đoán vị trí cột.")
    listings, reviews, areas, metadata = {}, {}, {}, set()
    placeholders = 0
    for line, row in enumerate(rows[1:], start=2):
        if len(row) != 15:
            raise ValueError(f"Dòng {line}: cần 15 cột.")
        row = [v.strip() for v in row]
        if row[2]:
            metadata.add(tuple(row[:3]))
        if row[3]:
            if not row[3].isdigit() or row[3] in listings:
                raise ValueError(f"Dòng {line}: listing_id không hợp lệ hoặc trùng.")
            listings[row[3]] = row[4]
        if row[5]:
            if not row[5].isdigit() or not row[6].isdigit() or row[5] in reviews:
                raise ValueError(f"Dòng {line}: review ID/listing ID không hợp lệ hoặc trùng.")
            if row[7].lower() not in ("", "x") or row[8].lower() not in ("", "x"):
                raise ValueError(f"Dòng {line}: cờ mẫu cần trống hoặc x.")
            reviews[row[5]] = {"review_id": row[5], "listing_id": row[6],
                                  "is_llm": row[7].lower() == "x",
                                  "is_manual_test": row[8].lower() == "x"}
        elif row[7] or row[8]:
            raise ValueError(f"Dòng {line}: đánh dấu mẫu nhưng thiếu review_id.")
        if row[10]:
            if row[10] in areas:
                raise ValueError("Trùng mã vùng trong bảng ranh giới.")
            area = dict(zip(expected[9:], row[9:]))
            for field in ["lon_min", "lat_min", "lon_max", "lat_max"]:
                area[field] = float(area[field].replace(",", "."))
            areas[row[10]] = area
        if row[1] and not any(v for i, v in enumerate(row) if i != 1):
            placeholders += 1
    if len(metadata) != 1:
        raise ValueError("Bảng đánh dấu phải thuộc đúng một lớp/nhóm/mã dữ liệu.")
    for row in reviews.values():
        if row["listing_id"] not in listings:
            raise ValueError("Review trỏ tới listing ngoài danh sách.")
        if row["is_manual_test"] and not row["is_llm"]:
            raise ValueError("Mẫu nhãn tay phải thuộc mẫu LLM.")
    if any(area not in areas for area in listings.values()):
        raise ValueError("Listing có vùng không nằm trong bảng ranh giới.")
    return listings, reviews, areas, next(iter(metadata)), placeholders


def download_reviews(config):
    snapshot = config["snapshot_date"]
    url = f'https://data.insideairbnb.com/{config["data_root"]}/{snapshot}/data/reviews.csv.gz'
    target = ROOT / "data" / "raw" / snapshot / "reviews.csv.gz"
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        temporary = target.with_suffix(".gz.part")
        with urllib.request.urlopen(url, timeout=60) as source, temporary.open("wb") as output:
            shutil.copyfileobj(source, output, 1024 * 1024)
        temporary.replace(target)
    return target, url


def join_reviews(filename, reviews, listings, snapshot):
    opener = gzip.open if str(filename).endswith(".gz") else open
    found, duplicate_count, total = {}, 0, 0
    with opener(filename, "rt", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        id_col = "review_id" if "review_id" in (reader.fieldnames or []) else "id"
        if not {id_col, "listing_id", "comments", "date"} <= set(reader.fieldnames or []):
            raise ValueError("Nguồn review cần id/review_id, listing_id, date, comments.")
        if "snapshot_date" in reader.fieldnames:
            check_snapshot = True
        else:
            check_snapshot = False
        for raw in reader:
            if check_snapshot and raw["snapshot_date"] != snapshot:
                continue
            total += 1
            rid = raw[id_col].strip()
            if rid not in reviews:
                continue
            if None in raw or any(v is None for v in raw.values()):
                raise ValueError("Nguồn review có dòng sai số cột.")
            record = {"snapshot_date": snapshot, "review_id": rid,
                      "listing_id": raw["listing_id"].strip(), "date": raw["date"],
                      "comments": raw["comments"]}
            if rid in found:
                if found[rid] != record:
                    raise ValueError(f"Nguồn có review_id trùng nhưng nội dung khác: {rid}")
                duplicate_count += 1
            found[rid] = record
    output, issues = [], []
    for rid, mark in reviews.items():
        source = found.get(rid)
        record = source or {"snapshot_date": snapshot, "review_id": rid,
                            "listing_id": mark["listing_id"], "date": "", "comments": ""}
        record = dict(record)
        record.update({"analysis_area": listings[mark["listing_id"]],
                       "is_llm": str(mark["is_llm"]).lower(),
                       "is_manual_test": str(mark["is_manual_test"]).lower(),
                       "split": "test" if mark["is_manual_test"] else "analysis",
                       "text_valid": str(bool(normalize_text(record["comments"])) and
                                         bool(source) and record["date"] <= snapshot).lower(),
                       "listing_match": str(bool(source) and source["listing_id"] == mark["listing_id"]).lower()})
        if source is None:
            issues.append({"review_id": rid, "reason": "missing_in_snapshot"})
        elif record["listing_match"] != "true":
            issues.append({"review_id": rid, "reason": "listing_id_mismatch"})
        elif record["text_valid"] != "true":
            issues.append({"review_id": rid, "reason": "empty_text_or_date_after_snapshot"})
        output.append(record)
    return output, issues, total, duplicate_count


def choose_pilot(rows, size, seed):
    eligible = [r for r in rows if r["is_llm"] == "true" and r["is_manual_test"] == "false"
                and r["text_valid"] == "true" and r["listing_match"] == "true"]
    eligible.sort(key=lambda r: (len(normalize_text(r["comments"])), r["review_id"]))
    if len(eligible) < size:
        raise ValueError(f"Chỉ có {len(eligible)} review dev hợp lệ; cần {size}.")
    # Chia theo thứ hạng độ dài rồi chọn luân phiên, tránh chỉ lấy câu ngắn.
    buckets = [[] for _ in range(4)]
    for i, row in enumerate(eligible):
        buckets[min(3, i * 4 // len(eligible))].append(row)
    rng = random.Random(seed)
    for bucket in buckets:
        rng.shuffle(bucket)
    selected = []
    while len(selected) < size:
        for bucket in buckets:
            if bucket and len(selected) < size:
                selected.append(bucket.pop())
    return selected, len(eligible)


def preserve_labels(filename, rows, split):
    labels = [{**row, "manual_sentiment": "", "needs_review": "", "note": "", "split": split}
              for row in rows]
    target = path(filename)
    if target.exists():
        previous = read_csv(target)
        keys = lambda records: {(r["snapshot_date"], r["review_id"], r["comments"]) for r in records}
        if keys(previous) != keys(labels):
            raise ValueError(f"Không ghi đè {filename}: dữ liệu/mẫu đã đổi; giữ bản nhãn tay cũ.")
        return
    write_csv(target, labels, LABEL_FIELDS)


def prepare(config, source=None, download=False):
    listings, marks, areas, metadata, placeholders = read_marking(config["marking_csv"])
    if metadata != (config["class"], config["group"], config["data_code"]):
        raise ValueError("Thông tin nhóm trong CSV không khớp cấu hình.")
    write_csv("data/samples/listing_ids.csv", [{"listing_id": k, "analysis_area": v}
              for k, v in listings.items()], ["listing_id", "analysis_area"])
    write_csv("data/samples/review_ids.csv", marks.values(),
              ["review_id", "listing_id", "is_llm", "is_manual_test"])
    write_csv("data/samples/analysis_areas.csv", areas.values(),
              ["Thành phố", "analysis_area", "lon_min", "lat_min", "lon_max", "lat_max"])
    source_url = None
    if download:
        source, source_url = download_reviews(config)
    if source is None:
        source = ROOT / "data" / "raw" / config["snapshot_date"] / "reviews.csv.gz"
    source = path(source)
    if not source.exists():
        raise FileNotFoundError("Đã tách ID, còn thiếu review text. Chạy prepare --download hoặc --reviews FILE.")
    joined, issues, total, duplicates = join_reviews(source, marks, listings, config["snapshot_date"])
    pilot, eligible_count = choose_pilot(joined, config["pilot_size"], config["seed"])
    pilot_ids = {r["review_id"] for r in pilot}
    for row in joined:
        if row["review_id"] in pilot_ids:
            row["split"] = "dev"
    pilot = [r for r in joined if r["review_id"] in pilot_ids]
    test = [r for r in joined if r["is_manual_test"] == "true"]
    llm = [r for r in joined if r["is_llm"] == "true"]
    # Xác minh nhãn tay trước khi ghi lại bất cứ mẫu có nội dung nào.
    preserve_labels("data/samples/reviews_pilot_labels.csv", pilot, "dev")
    preserve_labels("data/samples/reviews_test_labels.csv", test, "test")
    for name, records in [("reviews_selected", joined), ("reviews_llm", llm),
                          ("reviews_pilot", pilot), ("reviews_test", test)]:
        write_csv(f"data/samples/{name}.csv", records, REVIEW_FIELDS)
    write_csv("reports/review_join_issues.csv", issues, ["review_id", "reason"])
    with source.open("rb") as stream:
        sha256 = hashlib.file_digest(stream, "sha256").hexdigest()
    report = {"created_at": now(), "city": config["city"], "group": config["group"],
              "snapshot_date": config["snapshot_date"], "source_url": source_url,
              "source_file": str(source.relative_to(ROOT)) if source.is_relative_to(ROOT) else source.name,
              "source_sha256": sha256, "source_reviews_scanned": total,
              "listings": len(listings), "selected_reviews": len(joined),
              "llm_reviews": len(llm), "manual_test_reviews": len(test),
              "pilot_reviews": len(pilot), "dev_eligible": eligible_count,
              "matched_reviews": len(joined) - sum(r["reason"] == "missing_in_snapshot" for r in issues),
              "join_issues": len(issues), "identical_source_duplicates": duplicates,
              "ignored_group_only_rows": placeholders, "seed": config["seed"],
              "pilot_method": "20 from non-test LLM pool; 4 text-length rank strata; seeded random selection",
              "test_dev_overlap": len(pilot_ids & {r["review_id"] for r in test}),
              "manual_labels_filled_by_ai": 0}
    write_json("reports/data_checks.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/toronto.json")
    parser.add_argument("--reviews", help="CSV/CSV.GZ thật, có comments; nếu có nhiều snapshot phải có cột snapshot_date")
    parser.add_argument("--download", action="store_true")
    args = parser.parse_args(argv)
    prepare(load_config(args.config), args.reviews, args.download)


if __name__ == "__main__":
    main()
