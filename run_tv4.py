"""Điểm vào riêng TV4, không thay thế run_pipeline.py của TV1."""
import importlib
import sys

COMMANDS = ("prepare", "annotate", "llm", "baseline", "evaluate", "summary", "estimate", "cache_audit")


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print("Cách dùng: python run_tv4.py {" + ",".join(COMMANDS) + "} [tùy chọn]")
        return 2
    try:
        module = "tv4_evaluation" if sys.argv[1] == "evaluate" else sys.argv[1]
        importlib.import_module("src." + module).main(sys.argv[2:])
        return 0
    except (ValueError, FileNotFoundError, RuntimeError) as error:
        print("Chưa chạy được:", error, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
