import pandas as pd
from src.qa import check_available, check_comments, check_duplicate_review, run_qa_listings
from src.download import read, path, money


def test_money_and_available_normalization():
    values = money(pd.Series(["$1,234.00", "CA$20.50", None, "bad"]))
    assert values.iloc[0] == 1234
    assert values.iloc[1] == 20.5
    assert values.iloc[2:].isna().all()
    flags = check_available(pd.DataFrame({"available": [" t ", "F", "bad"]}))
    assert flags.available_valid.tolist() == [True, True, False]
    assert flags.available_true.tolist() == [True, False, False]


def test_qa_report_has_rule_explanations_and_clean_data(clean_fixture):
    cfg = clean_fixture
    report = pd.read_csv(path(cfg, "reports", "qa_report.csv"))
    assert {"rule", "condition", "reason", "action", "action_detail",
            "rows_checked", "rows_flagged", "metric_before", "metric_after"} <= set(report)
    assert report.loc[report.rule.eq("missing_price"), "reason"].notna().all()
    assert report.rule.eq("review_id_repeated").any()
    listings = read(cfg, "listings_clean")
    assert len(listings) == 8
    assert set(listings.snapshot) == set(cfg["snapshots"])
    assert not read(cfg, "calendar_clean").available.isna().any()


def test_outlier_and_category_flags():
    frame = pd.DataFrame({
        "listing_id": ["1", "2", "3", "4"],
        "price": ["$100", "$100", "$100", "$99999"],
        "minimum_nights": [1, 1, 1, 0],
        "maximum_nights": [365] * 4,
        "availability_365": [100] * 4,
        "room_type": ["Entire home/apt"] * 3 + ["UNKNOWN"],
        "analysis_area": ["A01"] * 4,
        "review_scores_rating": [5.0] * 4,
    })
    flags = run_qa_listings(frame)["row_flags"]
    assert bool(flags.loc[3, "price_outlier"])
    assert bool(flags.loc[3, "invalid_minimum_nights"])
    assert bool(flags.loc[3, "category_mismatch"])


def test_empty_review_and_duplicate_flags():
    frame = pd.DataFrame({
        "review_id": ["1", "2", "2"],
        "comments": ["  ", "<br>Good stay", "<br>Good stay"],
    })
    comments = check_comments(frame)
    duplicates = check_duplicate_review(frame)
    assert bool(comments.loc[0, "comment_empty"])
    assert comments.loc[1, "comment_clean"] == "Good stay"
    assert duplicates.duplicate_id.tolist() == [False, True, True]
