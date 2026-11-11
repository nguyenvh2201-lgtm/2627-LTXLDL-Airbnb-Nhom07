import pandas as pd
from src.qa import clean_table, REPORT_COLUMNS, metric
from src.download import read, path, money


def test_money_and_raw_boolean_metric():
    values = money(pd.Series(["$1,234.00", "CA$20.50", None, "bad"]))
    assert values.iloc[0] == 1234
    assert values.iloc[1] == 20.5
    assert values.iloc[2:].isna().all()
    assert metric(pd.DataFrame({"available": ["t", "f", "bad"]}))[1] == 50


def test_qa_schema_and_flags(clean_fixture):
    cfg = clean_fixture
    report = pd.read_csv(path(cfg, "reports", "qa_report.csv"))
    assert list(report.columns) == REPORT_COLUMNS
    listings = read(cfg, "listings_clean")
    assert listings.loc[listings.snapshot.ne(cfg["snapshots"][-1]), "price"].isna().all()
    assert listings.flag_missing_bedrooms.sum() == 4
    assert listings.flag_invalid_host_response_rate.sum() == 4
    assert not read(cfg, "calendar_clean").available.isna().any()


def test_outlier_category_cross_consistency(clean_fixture):
    cfg = clean_fixture
    refs = {name: read(cfg, name + "_raw_filtered") for name in ("listings", "calendar", "reviews")}
    frame = refs["listings"].loc[lambda x: x.snapshot.eq(cfg["snapshots"][-1])].copy().reset_index(drop=True)
    frame.loc[0, ["price", "minimum_nights", "beds", "accommodates"]] = [99999, 999, 999, 0]
    frame.loc[0, "room_type"] = "UNKNOWN"
    frame.loc[0, "first_review"] = "2040-01-01"
    frame.loc[0, "number_of_reviews"] = 0
    clean, _ = clean_table(cfg, "listings", frame, refs)
    for flag in ("outlier_price", "outlier_minimum_nights", "outlier_beds", "outlier_accommodates", "room_type_variant", "review_date_order", "review_count_lower_than_sample"):
        assert clean.loc[0, "flag_" + flag], flag
    assert clean.loc[0, "room_type"] == "Other"


def test_empty_review_and_duplicate(clean_fixture):
    cfg = clean_fixture
    frame = read(cfg, "reviews_raw_filtered").head(2).copy()
    frame.loc[frame.index[0], "comments"] = " "
    frame = pd.concat([frame, frame.iloc[[1]]], ignore_index=True)
    clean, report = clean_table(cfg, "reviews", frame, {})
    assert len(clean) == 2
    assert clean.flag_empty_comment.sum() == 1
    assert any(r["rows_after"] < r["rows_before"] for r in report)
