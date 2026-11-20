"""Khảo sát CSV ghép ngang và xuất danh sách ID, không tạo nhãn tay."""
from __future__ import annotations

import argparse
import csv
import json
import logging
from collections import Counter
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def require(condition: bool, message: str) -> None:
    """Dừng với thông báo rõ ràng khi dữ liệu không đúng hợp đồng."""
    if not condition:
        raise ValueError(message)


def inspect_and_export(config_path: Path) -> dict:
    """Đọc ánh xạ theo vị trí để không mất cột có tên trùng."""
    cfg = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    spec = cfg["id_inspection"]
    source = ROOT / spec["source"]
    with source.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        rows = list(reader)
    require(all(len(row) == len(header) for row in rows), "CSV có dòng sai số cột")
    columns = spec["columns"]
    for name, col in columns.items():
        require(header[col["index"]] == col["header"], f"Cột {name} thay đổi; cần xác nhận ánh xạ")

    def cell(row: list[str], name: str) -> str:
        return row[columns[name]["index"]].strip()

    def flag(value: str) -> bool:
        require(value in spec["true_markers"] + [""], f"Dấu đánh dấu chưa rõ: {value!r}")
        return value in spec["true_markers"]

    selected = [r for r in rows if cell(r, "class") == spec["class"] and cell(r, "group") == str(spec["group"])]
    require(bool(selected), "Không có dòng khớp cặp Lớp + Nhóm")
    listings, reviews, areas = [], [], []
    review_listing_ids = []
    for row in selected:
        if cell(row, "listing_id"):
            listings.append({"id": cell(row, "listing_id"), "analysis_area": cell(row, "listing_area")})
        if cell(row, "review_id"):
            reviews.append({"id": cell(row, "review_id"), "in_llm_sample": flag(cell(row, "llm")), "in_hand_label": flag(cell(row, "hand"))})
            review_listing_ids.append(cell(row, "review_listing_id"))
        if cell(row, "area"):
            require(cell(row, "city").casefold() == cfg["city"].casefold(), "Thành phố vùng khác config")
            area = {"area": cell(row, "area")}
            for key in ("lat_min", "lat_max", "lon_min", "lon_max"):
                area[key] = float(cell(row, key).replace(spec["decimal_separator"], "."))
            require(-90 <= area["lat_min"] < area["lat_max"] <= 90, "Vĩ độ vùng không hợp lệ")
            require(-180 <= area["lon_min"] < area["lon_max"] <= 180, "Kinh độ vùng không hợp lệ")
            areas.append(area)
    checks = []

    def check(name: str, actual: object, expected: object) -> None:
        checks.append({"check": name, "actual": actual, "expected": expected, "passed": actual == expected})

    expected = spec["expected"]
    for name, records, key in (("listings", listings, "id"), ("reviews", reviews, "id"), ("areas", areas, "area")):
        check(name, len(records), expected[name])
        check(name + "_unique", len({r[key] for r in records}), len(records))
    check("llm_sample", sum(r["in_llm_sample"] for r in reviews), expected["llm_sample"])
    check("hand_sample", sum(r["in_hand_label"] for r in reviews), expected["hand_sample"])
    check("hand_subset_llm", all(not r["in_hand_label"] or r["in_llm_sample"] for r in reviews), True)
    check("review_listing_membership", set(review_listing_ids) <= {r["id"] for r in listings}, True)
    check("listing_area_membership", {r["analysis_area"] for r in listings} == {r["area"] for r in areas}, True)
    check("numeric_ids", all(r["id"].isdigit() for r in listings + reviews), True)
    snapshots = cfg["snapshots"]
    require(len(snapshots) == 4 and len(set(snapshots)) == 4, "Cần bốn snapshot khác nhau")
    for snapshot in snapshots:
        require(date.fromisoformat(snapshot).isoformat() == snapshot, "Ngày phải có dạng YYYY-MM-DD")
    report = {
        "source": spec["source"], "rows": len(rows), "selected_rows": len(selected),
        "excluded_rows": len(rows) - len(selected),
        "columns": [{"index": i, "name": name, "dtype": "string (giữ nguyên ID)", "missing": sum(not r[i].strip() for r in rows), "unique_nonempty": len({r[i] for r in rows if r[i].strip()})} for i, name in enumerate(header)],
        "first_five_rows": rows[:5], "checks": checks,
        "area_counts": dict(Counter(r["analysis_area"] for r in listings)),
        "metadata_source": "city/currency/data_root/snapshots lấy từ config có sẵn, chưa xác minh từ bảng phân công gốc",
        "snapshots_in_config_order": snapshots, "snapshots_chronological": sorted(snapshots),
        "assignment_codes": sorted({cell(r, "assignment_code") for r in selected}),
    }
    reports = ROOT / cfg["reports_dir"]
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "id_inspection.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    logging.info("Khảo sát: %s", json.dumps(report, ensure_ascii=False))
    require(all(c["passed"] for c in checks), "Kiểm tra ID không đạt; xem reports/id_inspection.json. Không xuất CSV mới.")
    outputs = {
        "listing_ids": listings, "review_ids": reviews, "areas": areas,
        "assignment": [{"city": cfg["city"], "currency": cfg["currency"], "snapshots": json.dumps(sorted(snapshots)), "data_root": cfg["data_root"]}],
    }
    for name, records in outputs.items():
        dest = ROOT / cfg["inputs"][name]
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(records[0]))
            writer.writeheader()
            writer.writerows(records)
        logging.info("Đã xuất %s: %d dòng", dest, len(records))
    if snapshots != sorted(snapshots):
        logging.warning("Thứ tự snapshot trong config chưa tăng dần; cần xác nhận trước khi áp dụng kỳ vọng theo mốc.")
    return report


def main() -> None:
    """Chạy khảo sát bằng cấu hình dự án."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "configs/Toronto.yaml")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    inspect_and_export(args.config)


if __name__ == "__main__":
    main()
