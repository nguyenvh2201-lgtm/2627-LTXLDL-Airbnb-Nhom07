"""Đối chiếu các số chính đã chèn vào PDF với bảng tổng hợp."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import pandas as pd
from pypdf import PdfReader
from src.download import load_config
from src.download import path


def check(cfg: dict) -> int:
    """Kiểm giá trị nguồn và sự hiện diện chuỗi hiển thị trong PDF."""
    summary = pd.read_csv(path(cfg, "reports", "summary_numbers.csv")).set_index("key")
    manifest = json.loads(path(cfg, "reports", "report_numbers.json").read_text(encoding="utf-8"))
    reader = PdfReader(path(cfg, "reports", "report.pdf"))
    text = "\n".join(page.extract_text() for page in reader.pages)
    for row in manifest:
        value = summary.loc[row["key"], "value"]
        assert (pd.isna(value) and row["value"] is None) or abs(value - row["value"]) < 1e-8, row["key"]
        assert row["rendered"] in text, row["key"]
    assert len(reader.pages) <= cfg["report"]["max_pages"]
    return len(manifest)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/city.yaml")
    args = parser.parse_args()
    print("PASS report numbers:", check(load_config(args.config)))
