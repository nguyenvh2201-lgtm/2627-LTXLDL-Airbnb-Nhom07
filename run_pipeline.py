"""Chạy quy trình Inside Airbnb theo cấu hình thành phố."""

import argparse
import json
from pathlib import Path
import sys

import yaml

from src import download, kpi, llm, qa, viz


def run_pipeline(args):
    config = yaml.safe_load(args.config.read_text(encoding="utf-8-sig"))
    if not isinstance(config, dict) or not isinstance(config.get("snapshots"), list):
        raise ValueError("Cấu hình cần danh sách snapshots.")
    snapshots = [str(snapshot) for snapshot in config["snapshots"]]
    llm_config = llm.load_config(args.profile, args.config)
    snapshot = llm_config["snapshot_date"]
    if snapshot not in snapshots or len(snapshots) != len(set(snapshots)):
        raise ValueError("snapshot_date phải thuộc snapshots và các mốc không được trùng.")
    sample_snapshot = llm_config.get("sample_snapshot_date")
    if sample_snapshot is not None and snapshot != str(sample_snapshot):
        llm_config["sample_ids"] = None

    if not args.skip_download:
        print("Tải và kiểm tra dữ liệu", flush=True)
        downloads = download.run_download(config, overwrite=False)
        failed = []
        for date, files in downloads.items():
            for filename, valid in files.items():
                if not valid:
                    failed.append(f"{date}/{filename}")
        if failed:
            raise ValueError("Dữ liệu tải thiếu hoặc không hợp lệ: " + ", ".join(failed))

    print("Kiểm tra và làm sạch dữ liệu", flush=True)
    city_review_counts = qa.run_qa(config)
    rows = llm.reviews(llm_config)
    has_test = any(row.get("split") == "test" for row in rows)
    labels_path = Path(config.get("samples_dir", "data/samples")) / "reviews_test_labels.csv"
    if has_test and not labels_path.is_file():
        raise FileNotFoundError(f"Thiếu bộ nhãn tay: {labels_path}")

    signature = llm.build_run_signature(llm_config, rows)
    run_name = f"{snapshot}_{args.profile}_{signature[:12]}"
    output = Path(llm_config["output_dir"]) / f"{run_name}.jsonl"
    print(f"Phân tích LLM tại {snapshot} với profile {args.profile}", flush=True)
    if llm.run(rows, llm_config, output, signature, args):
        raise ValueError(f"LLM chưa hoàn tất. Chạy lại cùng cấu hình để tiếp tục từ {output}.")
    predictions = llm.read_results(output, rows, signature)

    reports_dir = Path(config.get("reports_dir", "reports"))
    evaluation_dir = reports_dir / "llm" / run_name
    evaluation_dir.mkdir(parents=True, exist_ok=True)
    if has_test:
        print("Đánh giá LLM và baseline trên nhãn tay", flush=True)
        llm.evaluate(rows, predictions, str(labels_path), evaluation_dir)
    cost_report = llm.cost(predictions, llm_config, city_review_counts[snapshot])
    (evaluation_dir / "cost.json").write_text(
        json.dumps(cost_report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print("Tính KPI", flush=True)
    processed_dir = config.get("processed_dir", "data/processed")
    result = kpi.run({
        "input_dir": processed_dir,
        "output_dir": processed_dir,
        "checks_path": str(reports_dir / "kpi_checks.csv"),
        "snapshots": snapshots,
        "llm_file": str(output),
        "exclude_price_outliers": config.get("kpi", {}).get("exclude_price_outliers", False),
    })
    print("Sinh biểu đồ", flush=True)
    figures = viz.render_figures(
        result["outputs"], snapshot, config.get("figures_dir", "figures"), config["currency"]
    )
    print(json.dumps({
        "llm_output": str(output),
        "llm_report_dir": str(evaluation_dir),
        "evaluated_on_test": has_test,
        "kpi_checks": result["checks"],
        "kpi_warnings": result["warnings"],
        "figures": figures,
    }, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=llm.DEFAULT_CITY_CONFIG)
    parser.add_argument("--profile", choices=tuple(llm.MODEL_PROFILES), default="luna")
    parser.add_argument("--skip-download", action="store_true", help="Dùng dữ liệu thô đã tải")
    parser.add_argument("--skip-llm", action="store_true", help="Dùng checkpoint đúng cấu hình")
    parser.add_argument("--max-new-requests", type=int, help="Giới hạn lượt gọi API mới")
    args = parser.parse_args()
    if args.max_new_requests is not None and args.max_new_requests < 0:
        parser.error("--max-new-requests phải >= 0")
    try:
        run_pipeline(args)
    except (OSError, ValueError, AssertionError, KeyError, yaml.YAMLError) as error:
        print(f"Lỗi pipeline: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
