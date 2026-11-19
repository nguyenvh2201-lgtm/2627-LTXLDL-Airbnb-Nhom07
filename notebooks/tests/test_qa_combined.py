import pandas as pd
import pytest

from src.qa import check_price, run_qa_listings, prepare_listings, price_impact_rows
from src.download import path, read


def test_cap_is_distinct_from_iqr_and_can_be_disabled():
    prices = pd.Series([100, 100, 3000])
    rooms = pd.Series(["Private room"] * 3)
    flags = check_price(prices, room_type=rooms)
    assert not flags.price_iqr_checkable.any()
    assert not flags.price_outlier_iqr.any()
    assert flags.price_above_cap.tolist() == [False, False, True]
    assert check_price(prices, room_type=rooms, qa_cfg={"price_max": None}).price_outlier.eq(False).all()


def test_iqr_thresholds_follow_config_and_aliases():
    prices = pd.Series([90, 95, 100, 105, 110, 500])
    rooms = pd.Series([" private room ", "Private room", "PRIVATE ROOM"] * 2)
    flags = check_price(prices, room_type=rooms, qa_cfg={"price_max": None})
    assert flags.price_iqr_checkable.all()
    assert flags.price_iqr_low.eq(77.5).all()
    assert flags.price_iqr_high.eq(127.5).all()
    assert flags.price_outlier_iqr.tolist() == [False] * 5 + [True]
    wide = check_price(prices, room_type=rooms, qa_cfg={"iqr_multiplier": 40, "price_max": None})
    assert not wide.price_outlier.any()
    small = check_price(prices, room_type=rooms, qa_cfg={"iqr_min_group_size": 7, "price_max": None})
    assert not small.price_iqr_checkable.any()


def test_blank_prices_are_missing_not_type_errors():
    flags = check_price(pd.Series([None, "", " ", "bad", "inf", -1]), room_type=pd.Series(["Private room"] * 6))
    assert flags.missing_price.tolist() == [True, True, True, False, False, False]
    assert flags.wrong_price_type.tolist() == [False, False, False, True, False, False]
    assert flags.invalid_price.tolist() == [False] * 4 + [True, True]


@pytest.mark.parametrize("settings", [
    {"iqr_multiplier": 0}, {"iqr_multiplier": float("inf")},
    {"iqr_min_group_size": 3}, {"iqr_min_group_size": 4.5},
    {"price_max": -1}, {"price_max": True},
])
def test_reject_invalid_price_settings(settings):
    with pytest.raises(ValueError, match="qa\\."):
        check_price(pd.Series([100]), qa_cfg=settings)


def test_assignment_duplicate_does_not_multiply_rows_and_conflicts_fail():
    raw = pd.DataFrame({"id": ["1"]})
    same = pd.DataFrame({"listing_id": ["1", "1"], "analysis_area": ["A", "A"]})
    assert len(prepare_listings(raw, same, "2030-01-01")) == 1
    same.loc[1, "analysis_area"] = "B"
    with pytest.raises(ValueError, match="analysis_area"):
        prepare_listings(raw, same, "2030-01-01")


def test_combined_outputs_and_unique_flagged_rows(clean_fixture):
    cfg = clean_fixture
    report = pd.read_csv(path(cfg, "reports", "qa_report.csv"))
    assert {"rows_with_any_flag", "room_change"} <= set(report.rule)
    for snapshot in cfg["snapshots"]:
        frame = pd.read_csv(path(cfg, "processed", f"{snapshot}/listings_clean.csv"))
        assert {"price_iqr_low", "price_iqr_high", "price_above_cap", "room_type_normalized", "missing_rating"} <= set(frame)
        rules = report.loc[report.snapshot_date.eq(snapshot) & report.table.eq("listings")]
        # Active rule rows exclude summary metrics and comparisons between snapshots.
        active = rules.loc[rules.action.eq("flag_only"), "rule"].tolist()
        expected = frame[active].fillna(False).astype(bool).any(axis=1).sum()
        actual = rules.loc[rules.rule.eq("rows_with_any_flag"), "rows_flagged"].iloc[0]
        assert actual == expected
    for filename in ["qa_impact.csv", "data_dictionary.csv", "cross_snapshot_duplicates.csv"]:
        assert path(cfg, "reports", filename).exists()
    calendar = read(cfg, "calendar_clean")
    assert len(calendar) == 24
    assert path(cfg, "processed", "calendar_clean.parquet").exists()
    assert not path(cfg, "processed", f"{cfg['snapshots'][0]}/calendar_flagged.csv").exists()
