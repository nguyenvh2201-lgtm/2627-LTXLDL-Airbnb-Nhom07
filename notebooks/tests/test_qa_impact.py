import pandas as pd
import pytest

from src.qa import check_price, check_numeric_rules, price_impact_rows
from src.download import read, path
from src.kpi import compute


def test_qa_exports_impact_for_all_snapshots(clean_fixture):
    report = pd.read_csv(path(clean_fixture, "reports", "qa_impact.csv"))
    assert set(report.snapshot_date) == set(clean_fixture["snapshots"])
    assert set(report.metric) == {"median", "mean"}
    assert report.currency.eq(clean_fixture["currency"]).all()
    assert report.n_before.eq(report.n_after + report.n_excluded).all()
    assert report.loc[report.scope.eq("snapshot"), "n_before"].eq(2).all()


def test_price_impact_measures_exclusion_without_changing_source():
    frame = pd.DataFrame({
        "price": [90, 95, 100, 105, 110, 500, None, 0, "inf"],
        "room_type": ["Private room"] * 9,
        "area": ["A"] * 9,
    })
    frame = pd.concat([frame, check_price(frame.price, frame.room_type)], axis=1)
    original = frame.copy(deep=True)
    result = pd.DataFrame(price_impact_rows(frame, "2030-01-01", "area", "CAD"))
    overall = result.loc[result.scope.eq("snapshot")].set_index("metric")
    median = overall.loc["median"]
    assert (median.n_before, median.n_after, median.n_excluded) == (6, 5, 1)
    assert median.n_invalid_or_missing == 3
    assert median.value_before == 102.5
    assert median.value_after == 100
    assert median.delta_pct == pytest.approx(-2.5 / 102.5 * 100)
    assert overall.loc["mean", "value_before"] == pytest.approx(1000 / 6)
    assert overall.loc["mean", "value_after"] == 100
    assert set(result.scope) == {"snapshot", "area", "room_type"}
    pd.testing.assert_frame_equal(frame, original)


def test_price_impact_keeps_uncheckable_prices_and_empty_metrics():
    frame = pd.DataFrame({"price": [20, 30, None],
                          "room_type": ["small"] * 3, "area": ["A", "A", "B"]})
    frame = pd.concat([frame, check_price(frame.price, frame.room_type)], axis=1)
    result = pd.DataFrame(price_impact_rows(frame, "2030-01-01", "area", "CAD"))
    overall = result.loc[result.scope.eq("snapshot")]
    assert overall.n_iqr_uncheckable.eq(2).all()
    assert overall.n_excluded.eq(0).all()
    assert overall.delta.eq(0).all()
    empty = result.loc[result.scope.eq("area") & result.group.eq("B")]
    assert empty.n_after.eq(0).all()
    assert empty[["value_before", "value_after", "delta", "delta_pct"]].isna().all().all()


def test_k4_uses_qa_validity_in_csv_and_compute(cfg):
    snapshot = cfg["snapshots"][-1]
    cfg["snapshots"] = [snapshot]
    frame = pd.DataFrame({
        "minimum_nights": [1, 30, 365, 366, 0, 1.5, "bad", None, 40],
        "maximum_nights": [400] * 8 + [20],
        "availability_365": [100] * 9,
    })
    flags = check_numeric_rules(frame, 365)
    frame = pd.concat([frame, flags], axis=1)
    frame["snapshot_date"] = snapshot
    frame["listing_id"] = [str(i) for i in range(9)]
    frame["price_cad"] = 100
    frame["price_valid"] = True
    frame["price_outlier"] = False
    frame["number_of_reviews"] = 1
    frame[cfg["kpi"]["area_col"]] = "A"
    target = path(cfg, "processed", f"{snapshot}/listings_clean.csv")
    target.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(target, index=False)
    listings = read(cfg, "listings_clean")
    assert listings.flag_outlier_minimum_nights.tolist() == [False] * 3 + [True] * 6
    # Simulate a stale legacy flag: compute must still honor the QA validity.
    listings["flag_outlier_minimum_nights"] = False
    calendar = pd.DataFrame({"listing_id": pd.Series(dtype=str),
                             "snapshot": pd.Series(dtype=str),
                             "date": pd.Series(dtype="datetime64[ns]"),
                             "available": pd.Series(dtype=float)})
    reviews = pd.DataFrame({"id": pd.Series(dtype=str),
                            "snapshot": pd.Series(dtype=str),
                            "date": pd.Series(dtype="datetime64[ns]")})
    area, times = compute(cfg, listings, calendar, reviews)
    for table in (area, times):
        k4 = table.loc[table.kpi_id.eq("K4")]
        assert k4.n.eq(3).all()
        assert k4.value.iloc[0] == pytest.approx(200 / 3)
