"""Checklist trung thực, phân biệt mã đã làm và dữ liệu còn thiếu."""
import subprocess
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import pandas as pd
from src.download import load_config
from src.download import path


def run(cfg: dict) -> None:
    """In bảng kiểm chứng nhanh ra console, không tự tạo tag/push hay file rác."""
    rows = []
    def add(item, passed, evidence):
        rows.append({"item": item, "status": "Đạt" if passed else "Chưa đạt", "evidence": evidence})
    checks = pd.read_csv(path(cfg, "reports", "filter_checks.csv"))
    add("Kiểm dữ liệu bắt buộc", not ((~checks.passed) & checks.severity.eq("error")).any(), f"{len(checks)} checks; {int((~checks.passed).sum())} warnings; reports/filter_checks.csv")
    add("Khớp toàn bộ kỳ vọng bộ mốc gốc", bool(checks.passed.all()), "Mốc mới được người dùng giữ dù thiếu 72 listing, 235 review; missing_ids.csv")
    size = sum(p.stat().st_size for p in path(cfg, "processed").rglob("*") if p.is_file()) / 1e6
    add("processed < giới hạn", size < cfg["io"]["processed_max_mb"], f"{size:.2f} MB / {cfg['io']['processed_max_mb']} MB")
    valid_gold = False
    gold_evidence = "Chưa có file nhãn tay hợp lệ"
    from src.evaluate import read_hand_labels, validate_labels
    hand_labels = read_hand_labels(cfg)
    if hand_labels is not None and not hand_labels.empty:
        try:
            validate_labels(hand_labels, pd.read_parquet(path(cfg, "processed", "llm_sample.parquet")), cfg)
            valid_gold = True
            src_name = cfg["inputs"]["hand_labels"] if (cfg["_root"] / cfg["inputs"]["hand_labels"]).exists() else "data/samples/hand_labels_template.csv"
            counts = hand_labels["sentiment"].value_counts().to_dict()
            gold_evidence = f"{len(hand_labels)} dòng hợp lệ trong {src_name} (phân bố: {counts})"
        except ValueError as exc:
            gold_evidence = f"Lỗi xác thực nhãn tay: {exc}"
    add("Nhãn tay thật hợp lệ", valid_gold, gold_evidence)
    predictions = pd.read_parquet(path(cfg, "processed", "llm_results.parquet"))
    valid_count = int((predictions.sentiment.notna() & ~predictions.parse_error).sum())
    add("LLM đủ mẫu, JSON hợp lệ >98%", valid_count > cfg["llm"]["sample_size"] * .98, f"{valid_count}/{cfg['llm']['sample_size']} prediction hợp lệ; không có khóa/cache thì chưa đạt")
    metrics = pd.read_csv(path(cfg, "reports", "eval_metrics.csv"))
    add("Đánh giá LLM và baseline", bool(len(metrics)), f"{len(metrics)} dòng eval_metrics.csv")
    add("Chi phí có nguồn/giả định", path(cfg, "reports", "llm_cost_estimate.csv").exists(), "llm_cost_estimate.csv; scenario output token, chưa phải chi phí thật")
    fig_pdf_files = list(path(cfg, "figures").glob("fig_*.pdf"))
    fig_png_files = list(path(cfg, "figures").glob("fig_*.png"))
    add(
        "Đủ hình PDF cả ba góc độ",
        len(fig_pdf_files) >= 11,
        f"{len(fig_pdf_files)}/11 PDF vector; {len(fig_png_files)}/11 PNG xem trước trong figures/",
    )
    md_report = path(cfg, "reports", "report.md")
    add("Báo cáo Markdown hoàn chỉnh", md_report.exists() and md_report.stat().st_size > 1000, f"reports/report.md ({md_report.stat().st_size if md_report.exists() else 0:,} bytes)")
    pdf_report = path(cfg, "reports", "report.pdf")
    pdf_pages = 0
    pdf_error = ""
    if pdf_report.exists():
        try:
            from pypdf import PdfReader
            from pypdf.errors import PdfReadError
            pdf_pages = len(PdfReader(str(pdf_report)).pages)
        except (OSError, ValueError, PdfReadError) as exc:
            pdf_error = type(exc).__name__
    max_pages = int(cfg.get("report", {}).get("max_pages", 10))
    pdf_ok = pdf_report.exists() and 0 < pdf_pages <= max_pages and not pdf_error
    pdf_evidence = f"reports/report.pdf ({pdf_pages}/{max_pages} trang)" if pdf_report.exists() else "Thiếu reports/report.pdf"
    if pdf_error:
        pdf_evidence += f"; không đọc được PDF: {pdf_error}"
    add("Báo cáo PDF hợp lệ và không quá giới hạn", pdf_ok, pdf_evidence)
    from notebooks.tools.check_security import audit as security_audit
    sec = security_audit()
    add("Mẫu khóa/file nhạy cảm", not any(sec.get(k) for k in ("forbidden_tracked_files", "secret_pattern_paths", "secret_pattern_in_history")), "python notebooks/tools/check_security.py; chỉ kiểm các mẫu được hỗ trợ")
    status = subprocess.check_output(["git", "status", "--porcelain"], cwd=cfg["_root"], text=True)
    add("Git status sạch", not status.strip(), "git status --short; chưa commit các thay đổi")
    add("Tag final/push và commit báo cáo", False, "Chưa được xác nhận nộp; không tự tag/push")
    add("Repo riêng tư, mời giảng viên, điền liên kết", False, "Nhóm cần tự xác nhận trên GitHub/bảng tính")
    print(pd.DataFrame(rows).to_string(index=False))


if __name__ == "__main__":
    run(load_config("configs/Toronto.yaml"))
