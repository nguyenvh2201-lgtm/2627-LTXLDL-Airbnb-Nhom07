"""Checklist trung thực, phân biệt mã đã làm và dữ liệu còn thiếu."""
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import pandas as pd
from pypdf import PdfReader
from src.download import load_config
from src.download import path, csv_report


def run(cfg: dict) -> None:
    """Ghi bằng chứng, không tự tạo tag/push hoặc nhãn tay."""
    rows = []
    def add(item, passed, evidence):
        rows.append({"item": item, "status": "Đạt" if passed else "Chưa đạt", "evidence": evidence})
    tests = path(cfg, "reports", "test_results.xml")
    if tests.exists():
        suites = ET.parse(tests).getroot().findall("testsuite")
        total = sum(int(s.get("tests", 0)) for s in suites)
        errors = sum(int(s.get("errors", 0)) + int(s.get("failures", 0)) for s in suites)
        add("pytest", total > 0 and errors == 0, f"{total} tests, {errors} failures/errors; python -m pytest -c notebooks/pytest.ini -q --junitxml=reports/test_results.xml")
    checks = pd.read_csv(path(cfg, "reports", "filter_checks.csv"))
    add("Kiểm dữ liệu bắt buộc", not ((~checks.passed) & checks.severity.eq("error")).any(), f"{len(checks)} checks; {int((~checks.passed).sum())} warnings; reports/filter_checks.csv")
    add("Khớp toàn bộ kỳ vọng bộ mốc gốc", bool(checks.passed.all()), "Mốc mới được người dùng giữ dù thiếu 72 listing, 235 review; missing_ids.csv")
    size = sum(p.stat().st_size for p in path(cfg, "processed").glob("*") if p.is_file()) / 1e6
    add("processed < giới hạn", size < cfg["io"]["processed_max_mb"], f"{size:.2f} MB / {cfg['io']['processed_max_mb']} MB")
    gold_path = cfg["_root"] / cfg["inputs"]["hand_labels"]
    valid_gold = False
    if gold_path.exists():
        from src.evaluate import validate_labels
        try:
            validate_labels(pd.read_csv(gold_path, dtype={"review_id": str}), pd.read_parquet(path(cfg, "processed", "llm_sample.parquet")), cfg)
            valid_gold = True
        except ValueError:
            pass
    add("Nhãn tay thật hợp lệ", valid_gold, "hand_labels.csv do nhóm tự gán; template không tính là gold")
    predictions = pd.read_parquet(path(cfg, "processed", "llm_results.parquet"))
    valid_count = int((predictions.sentiment.notna() & ~predictions.parse_error).sum())
    add("LLM đủ mẫu, JSON hợp lệ >98%", valid_count > cfg["llm"]["sample_size"] * .98, f"{valid_count}/{cfg['llm']['sample_size']} prediction hợp lệ; không có khóa/cache thì chưa đạt")
    metrics = pd.read_csv(path(cfg, "reports", "eval_metrics.csv"))
    add("Đánh giá LLM và baseline", bool(len(metrics)), f"{len(metrics)} dòng eval_metrics.csv")
    add("Chi phí có nguồn/giả định", path(cfg, "reports", "llm_cost_estimate.csv").exists(), "llm_cost_estimate.csv; scenario output token, chưa phải chi phí thật")
    figures = pd.read_csv(path(cfg, "reports", "figure_status.csv"))
    add("Đủ hình cả ba góc độ", figures.status.eq("created").all(), f"{int(figures.status.eq('created').sum())}/{len(figures)} hình; LLM cần dữ liệu thật")
    pages = len(PdfReader(path(cfg, "reports", "report.pdf")).pages)
    add("PDF <=10 trang", pages <= cfg["report"]["max_pages"], f"{pages} trang; bản nháp thiếu nhận định/gold/LLM")
    security = path(cfg, "reports", "security_check.json")
    audit = json.loads(security.read_text()) if security.exists() else {}
    add("Mẫu khóa/file nhạy cảm", bool(audit) and not any(audit.get(k) for k in ("forbidden_tracked_files", "secret_pattern_paths", "secret_pattern_in_history")), "python notebooks/tools/check_security.py; chỉ kiểm các mẫu được hỗ trợ")
    reproduction = path(cfg, "reports", "clean_reproduction.json")
    add("Tái lập môi trường cô lập", reproduction.exists(), "clean_reproduction.json; bản làm việc chưa commit, không phải remote final")
    status = subprocess.check_output(["git", "status", "--porcelain"], cwd=cfg["_root"], text=True)
    add("Git status sạch", not status.strip(), "git status --short; chưa commit các thay đổi")
    add("Tag final/push và commit báo cáo", False, "Chưa được xác nhận nộp; không tự tag/push")
    add("Repo riêng tư, mời giảng viên, điền liên kết", False, "Nhóm cần tự xác nhận trên GitHub/bảng tính")
    csv_report(cfg, rows, "submission_checklist.csv")
    print(pd.DataFrame(rows).to_string(index=False))


if __name__ == "__main__":
    run(load_config("configs/city.yaml"))
