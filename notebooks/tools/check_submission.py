"""Six submission checks; reuse the report/security checkers, never rerun pytest."""
import sys
from pathlib import Path
import subprocess
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import pandas as pd
from pypdf import PdfReader
from pypdf.errors import PdfReadError
from src.download import load_config, path
from notebooks.tools.check_report_numbers import check as check_report
from notebooks.tools.check_security import audit as security_audit

FIGURES = [
    "fig_space_01_listings_map", "fig_space_02_area_price", "fig_space_03_area_occupancy",
    "fig_time_01_occupancy_by_snapshot", "fig_time_02_kpi_trend", "fig_time_03_reviews_per_quarter",
    "fig_llm_01_sentiment_by_area", "fig_llm_02_aspects", "fig_llm_03_model_vs_baseline",
    "fig_llm_04_confusion_llm", "fig_llm_05_confusion_baseline",
]


def run(cfg: dict) -> int:
    rows = []
    def add(item, passed, evidence):
        rows.append({"item": item, "status": "Đạt" if passed else "Chưa đạt", "evidence": evidence})

    size = sum(p.stat().st_size for p in path(cfg, "processed").rglob("*") if p.is_file()) / 1e6
    add("Processed dưới giới hạn", size < cfg["io"]["processed_max_mb"], f"{size:.2f}/{cfg['io']['processed_max_mb']} MB")
    missing = [name for name in FIGURES if not path(cfg, "figures", name + ".pdf").is_file()]
    add("Đủ hình ở ba góc độ", not missing, ", ".join(missing) if missing else f"{len(FIGURES)}/{len(FIGURES)} PDF")
    try:
        count = len(PdfReader(path(cfg, "reports", "report.pdf")).pages)
        maximum = cfg.get("report", {}).get("max_pages", 10)
        add("Giới hạn trang PDF", 0 < count <= maximum, f"{count}/{maximum} trang")
    except (OSError, ValueError, PdfReadError) as exc:
        add("Giới hạn trang PDF", False, type(exc).__name__)
    try:
        count = check_report(cfg)
        add("Số liệu dữ liệu/Markdown/PDF", True, f"{count} giá trị khai báo; không kiểm mọi câu/ý nghĩa")
    except (OSError, ValueError, KeyError, TypeError, PdfReadError) as exc:
        add("Số liệu dữ liệu/Markdown/PDF", False, str(exc))
    sec = security_audit()
    add("Security pattern audit", not any(sec[k] for k in ("forbidden_tracked_files", "secret_pattern_paths", "secret_pattern_in_history")), "Dùng check_security.audit(); không in nội dung secret")
    status = subprocess.check_output(["git", "status", "--porcelain"], cwd=cfg["_root"], text=True)
    add("Git status sạch", not status.strip(), "Có thay đổi chưa commit/file chưa track" if status.strip() else "Sạch")
    print(pd.DataFrame(rows).to_string(index=False))
    print("Xác nhận thủ công trước nộp: quyền repo/giảng viên, liên kết nộp bài, commit báo cáo và tag final.")
    return int(any(row["status"] == "Chưa đạt" for row in rows))


if __name__ == "__main__":
    raise SystemExit(run(load_config("configs/Toronto.yaml")))
