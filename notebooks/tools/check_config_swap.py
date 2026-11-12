"""Kiểm ngày/thành phố không ghi cứng trong src và chạy fixtures mốc mới."""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    """Fixtures dùng bốn ngày khác dữ liệu thực, chạy filter/QA/KPI và toàn pipeline."""
    issues = []
    for source in (ROOT / "src").glob("*.py"):
        text = source.read_text(encoding="utf-8")
        if re.search(r"\b20\d{2}-\d{2}-\d{2}\b|\btoronto\b", text, flags=re.I):
            issues.append(str(source.relative_to(ROOT)))
    if issues:
        print("FAIL hardcoded city/date:", issues)
        return 1
    print("PASS no hardcoded city/date in src")
    return subprocess.call([sys.executable, "-m", "pytest", "-q", "-c", "notebooks/pytest.ini", "notebooks/tests/test_config.py", "notebooks/tests/test_kpi.py", "notebooks/tests/test_smoke.py"], cwd=ROOT)


if __name__ == "__main__":
    sys.exit(main())
