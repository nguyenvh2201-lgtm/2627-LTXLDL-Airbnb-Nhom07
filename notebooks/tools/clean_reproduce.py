"""Chuẩn bị clone cô lập với bản mã đang sửa, rồi so sánh bảng số liệu."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DEST = ROOT / "notebooks/.work/clean-repro"


def prepare() -> None:
    """Clone không checkout rồi phủ mã hiện tại; raw dùng hardlink chỉ đọc."""
    if DEST.exists():
        raise ValueError("Thư mục clean-repro đã tồn tại; không tự xóa dữ liệu")
    DEST.parent.mkdir(exist_ok=True)
    subprocess.run(["git", "clone", "--no-checkout", "--no-hardlinks", str(ROOT), str(DEST)], check=True)
    for folder in ("src", "notebooks", "configs", "data/samples"):
        shutil.copytree(ROOT / folder, DEST / folder, ignore=shutil.ignore_patterns("__pycache__", ".work", ".pytest_cache"))
    for name in ("run_pipeline.py", "requirements.txt", ".python-version", ".gitignore", ".env.example", "README.md", "AI_USAGE.md"):
        shutil.copy2(ROOT / name, DEST / name)
    for source in (ROOT / "data/raw").rglob("*.csv.gz"):
        target = DEST / source.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        os.link(source, target)
    subprocess.run([sys.executable, "-m", "venv", str(DEST / ".venv")], check=True)
    print("Prepared isolated clone + current working source:", DEST)


def compare() -> None:
    """So sánh nội dung số liệu, không so timestamp PDF/log."""
    names = ["data/processed/kpi_area.csv", "data/processed/kpi_time.csv", "data/processed/kpi_llm.csv", "reports/qa_report.csv", "reports/filter_checks.csv", "reports/summary_numbers.csv"]
    for name in names:
        expected, actual = pd.read_csv(ROOT / name), pd.read_csv(DEST / name)
        pd.testing.assert_frame_equal(expected, actual)
    result = {"status": "passed", "tables_equal": names, "source": "local git clone --no-checkout plus uncommitted working files", "environment": "isolated venv without system-site-packages", "raw": "verified preexisting files via hardlinks, no download network exercised", "llm": "skip; mocked separately in pytest", "limitations": "Not a remote clone of final commit; changes are not yet committed"}
    (ROOT / "reports/clean_reproduction.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--compare", action="store_true")
    args = parser.parse_args()
    if args.prepare:
        prepare()
    if args.compare:
        compare()
