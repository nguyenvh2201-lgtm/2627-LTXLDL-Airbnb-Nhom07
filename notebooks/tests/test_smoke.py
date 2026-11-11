import json
import pandas as pd
from src import download, qa, kpi, llm, baseline, evaluate, viz
from src.download import run_filter as filter_run
from src.download import path, read
from notebooks.tools.check_report_numbers import check
from src.evaluate import make_label_template as label_template


def test_full_pipeline_with_mock_api(raw_fixture, monkeypatch):
    cfg = raw_fixture
    cfg["_options"]["skip_llm"] = False
    monkeypatch.setenv(cfg["llm"]["api_key_env"], "mock-only")
    def generate(self, batch, prompt):
        return [{"review_id": row["review_id"], "sentiment": "positive", "aspects_praise": ["cleanliness"], "aspects_complaint": [], "language": "en"} for row in batch]
    monkeypatch.setattr(llm.GeminiClient, "generate", generate)
    for module in (download,):
        module.run_download(cfg)
    filter_run(cfg)
    qa.run(cfg)
    kpi.run(cfg)
    llm.run(cfg)
    baseline.run(cfg)
    template = pd.read_csv(label_template(cfg), dtype={"review_id": str})
    assert template.sentiment.isna().all()
    # Gold tổng hợp chỉ ở thư mục tạm pytest; tuyệt đối không ghi vào mẫu thật.
    template["sentiment"] = ["positive", "mixed", "negative"]
    template["language"] = "en"
    template["aspects_praise"] = '["cleanliness"]'
    template["aspects_complaint"] = '[]'
    template.to_csv(cfg["_root"] / cfg["inputs"]["hand_labels"], index=False)
    evaluate.run(cfg)
    kpi.run(cfg)
    viz.run(cfg)
    assert check(cfg) > 0
    assert len(pd.read_csv(path(cfg, "reports", "eval_metrics.csv"))) > 20
    assert len(list(path(cfg, "figures").glob("*.png"))) == 11
    for duplicate in ("baseline_results.csv", "llm_results.csv", "kpi_summary.csv"):
        assert not path(cfg, "processed", duplicate).exists()
