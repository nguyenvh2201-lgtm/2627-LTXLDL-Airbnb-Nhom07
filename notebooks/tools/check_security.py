"""Audit tên file và mẫu khóa, không in nội dung có thể chứa bí mật."""
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# Ghép mẫu để chính mã kiểm tra không trông giống khóa thật; loại trừ chuỗi giả test (AIza123456...).
PATTERNS = [re.compile("AIza" + r"(?!1234567890)[A-Za-z0-9_-]{35}"), re.compile("sk-" + r"[A-Za-z0-9_-]{32,}")]


def main() -> None:
    """Kiểm cả working tree văn bản và patch lịch sử Git, chỉ báo đường dẫn."""
    tracked = subprocess.check_output(["git", "ls-files"], cwd=ROOT, text=True).splitlines()
    forbidden = [p for p in tracked if p.startswith(("data/raw/", ".venv/")) or Path(p).name == ".env" or p.endswith(".key")]
    findings = []
    for directory in ("src", "configs", "notebooks", "data/samples"):
        for source in (ROOT / directory).rglob("*"):
            if source.is_file() and source.suffix in (".py", ".yaml", ".json", ".txt"):
                if any(pattern.search(source.read_text(encoding="utf-8")) for pattern in PATTERNS):
                    findings.append(str(source.relative_to(ROOT)))
    history = subprocess.check_output(["git", "log", "--all", "-p", "--format=commit %H"], cwd=ROOT)
    history_matches = any(pattern.search(history.decode("utf-8", errors="replace")) for pattern in PATTERNS)
    ignored = subprocess.run(["git", "check-ignore", ".env", "data/raw/placeholder", ".venv/placeholder"], cwd=ROOT, capture_output=True, text=True)
    result = {"forbidden_tracked_files": forbidden, "secret_pattern_paths": findings, "secret_pattern_in_history": history_matches, "ignored_paths": ignored.stdout.splitlines(), "scope": "pattern audit only; not proof no other secret formats exist"}
    (ROOT / "reports/security_check.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    if forbidden or findings or history_matches:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
