import pandas as pd
from src import download, qa, kpi, llm, baseline, evaluate, viz
from src.download import run_filter as filter_run
from src.download import path
from src.llm import make_label_template as label_template


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
    report = pd.read_csv(path(cfg, "reports", "qa_report.csv"))
    assert {"rule", "condition", "reason", "action", "action_detail",
            "rows_checked", "rows_flagged", "metric_before", "metric_after"} <= set(report)
    assert report.loc[report.rule.eq("missing_price"), "reason"].notna().all()
    assert report.rule.eq("review_id_repeated").any()
    assert len(download.read(cfg, "listings_clean")) == 8
    assert not download.read(cfg, "calendar_clean").available.isna().any()
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
    assert len(pd.read_csv(path(cfg, "reports", "eval_metrics.csv"))) > 20
    assert len(list(path(cfg, "figures").glob("*.pdf"))) == 11
    assert not list(path(cfg, "figures").glob("*.png"))
    for duplicate in ("baseline_results.csv", "llm_results.csv", "kpi_summary.csv"):
        assert not path(cfg, "processed", duplicate).exists()

    from pypdf import PdfReader
    review_figure = path(cfg, "figures", "fig_time_03_reviews_per_quarter.pdf")
    figure_text = PdfReader(review_figure).pages[0].extract_text()
    assert "01/09/2029" in figure_text
    assert "10/09/2025" not in figure_text
