"""Một lệnh chạy toàn bộ hoặc từng bước độc lập."""
import argparse
import importlib
import logging
from pathlib import Path
import sys
from src.download import load_config, setup_logging, path

STEPS = ["download", "qa", "kpi", "llm", "baseline", "evaluate", "kpi", "viz", "report"]
# Các bước phụ vẫn gọi được riêng.
EXTRA_STEPS = {
    "filter": ("download", "run_filter"),
    "labels": ("llm", "make_label_template"),
    "figures": ("viz", "run_figures"),
    "summary": ("report", "run_summary"),
}


def main() -> int:
    """Không che lỗi dữ liệu; thiếu LLM/gold được báo trong từng bước."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        default=str(Path(__file__).resolve().parent / "configs/Toronto.yaml"),
        help="Tệp cấu hình (mặc định: configs/Toronto.yaml)",
    )
    parser.add_argument("--skip-download", action="store_true")
    parser.add_argument("--skip-llm", action="store_true")
    parser.add_argument("--only", help="Tên bước, phân tách dấu phẩy")
    parser.add_argument("--limit", type=int, help="Giới hạn mẫu LLM/baseline cho chạy thử")
    args = parser.parse_args()
    try:
        cfg = load_config(args.config)
        cfg["_options"] = vars(args)
        setup_logging(cfg)
        steps = args.only.split(",") if args.only else STEPS
        if any(step not in STEPS and step not in EXTRA_STEPS for step in steps):
            raise ValueError("Bước không hợp lệ: " + str(steps))
        for step in steps:
            logging.info("=== %s ===", step)
            module, function = EXTRA_STEPS.get(step, (step, "run"))
            getattr(importlib.import_module("src." + module), function)(cfg)
        size = sum(p.stat().st_size for p in path(cfg, "processed").rglob("*") if p.is_file()) / 1e6
        logging.info("data/processed: %.2f MB (ngưỡng %.2f MB)", size, cfg["io"]["processed_max_mb"])
        if size >= cfg["io"]["processed_max_mb"]:
            logging.warning("Không commit data/processed: vượt giới hạn dung lượng")
        for folder in ("processed", "reports", "figures"):
            logging.info("Đầu ra %s: %s", folder, ", ".join(p.name for p in sorted(path(cfg, folder).glob("*")) if p.is_file()))
        return 0
    except (ValueError, OSError, KeyError) as exc:
        logging.error("Pipeline dừng: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
