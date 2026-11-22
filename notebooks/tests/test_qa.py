import pandas as pd
import pytest
from src.qa import (
    calendar_listing_summary,
    check_available,
    check_comments,
    check_duplicate_review,
    check_numeric_rules,
    check_price,
    check_rating,
    run_qa_listings,
    validate_schema,
)
from src.download import money


def test_money_and_available_normalization():
    values = money(pd.Series(["$1,234.00", "CA$20.50", None, "bad"]))
    assert values.iloc[0] == 1234
    assert values.iloc[1] == 20.5
    assert values.iloc[2:].isna().all()
    flags = check_available(pd.DataFrame({"available": [" t ", "F", "bad"]}))
    assert flags.available_valid.tolist() == [True, True, False]
    assert flags.available_true.tolist() == [True, False, False]


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


def test_numeric_missing_conversion_and_domain_flags_are_separate():
    frame = pd.DataFrame({
        "minimum_nights": [None, "bad", "0", "366", "1"],
        "maximum_nights": ["365", "bad", None, "2", "0"],
        "availability_365": [None, "bad", "0", "366", "365"],
    })
    flags = check_numeric_rules(frame)
    assert flags.missing_minimum_nights.tolist() == [True, False, False, False, False]
    assert flags.wrong_minimum_nights_type.tolist() == [False, True, False, False, False]
    assert flags.invalid_minimum_nights.tolist() == [False, False, True, True, False]
    assert flags.missing_maximum_nights.tolist() == [False, False, True, False, False]
    assert flags.wrong_maximum_nights_type.tolist() == [False, True, False, False, False]
    assert flags.invalid_maximum_nights.tolist() == [False, False, False, False, True]
    assert flags.missing_availability_365.tolist() == [True, False, False, False, False]
    assert flags.wrong_availability_365_type.tolist() == [False, True, False, False, False]
    assert flags.invalid_availability_365.tolist() == [False, False, False, True, False]

    rating = check_rating(pd.DataFrame({
        "review_scores_rating": [None, "bad", "0", "0.5", "1", "5", "6"],
    }))
    assert rating.missing_rating.tolist() == [True, False, False, False, False, False, False]
    assert rating.wrong_rating_type.tolist() == [False, True, False, False, False, False, False]
    assert rating.rating_valid.tolist() == [False, False, False, False, True, True, False]
    assert rating.invalid_rating.tolist() == [False, False, True, True, False, False, True]

    # 2. IQR tính riêng theo room_type bắt được giá cao bất thường của Private room
    prices = pd.Series(["$50", "$55", "$60", "$65", "$250", "$200", "$220", "$240", "$260", "$280"])
    rooms = pd.Series(["Private room"] * 5 + ["Entire home/apt"] * 5)
    p_flags = check_price(prices, room_type=rooms)
    assert bool(p_flags.loc[4, "price_outlier"])
    assert not bool(p_flags.loc[9, "price_outlier"])

    # 3. Kiểm tra cấu trúc đầu vào báo ValueError khi thiếu cột bắt buộc
    with pytest.raises(ValueError, match="thiếu cột bắt buộc"):
        validate_schema(pd.DataFrame({"id": ["1"]}), ["id", "price"], "listings")


def test_calendar_summary_excludes_duplicate_day_and_missing_key():
    calendar = pd.DataFrame({
        "listing_id": ["1", "1", "1", "2", None],
        "date_parsed": pd.to_datetime([
            "2030-01-01", "2030-01-01", "2030-01-02", "2030-01-01", "2030-01-01"
        ]),
        "available_valid": [True, True, True, True, True],
        "available_true": [True, True, False, True, True],
    })
    summary = calendar_listing_summary(calendar).set_index("listing_id")
    assert set(summary.index) == {"1", "2"}
    assert summary.loc["1", "n_calendar_days"] == 2
    assert summary.loc["1", "n_available_valid"] == 1
    assert summary.loc["1", "n_available"] == 0
