import pytest
from src.kpi import compute
from src.download import read


def test_hand_calculated_kpi(clean_fixture):
    cfg = clean_fixture
    area, times = compute(cfg, *[read(cfg, name + "_clean") for name in ("listings", "calendar", "reviews")])
    assert sorted(area.loc[area.kpi_id.eq("K1"), "value"]) == [100, 200]
    assert all(v == pytest.approx(200 / 3) for v in area.loc[area.kpi_id.eq("K2"), "value"])
    assert set(area.loc[area.kpi_id.eq("K4"), "value"]) == {0, 100}
    assert times.loc[times.kpi_id.eq("K5"), "value"].iloc[0] == 1.5
    assert {"currency", "unit", "n"} <= set(area)
    assert area.loc[area.kpi_id.eq("K1"), "currency"].eq(cfg["currency"]).all()


def test_citywide_calendar_keeps_missing_neighbourhood(clean_fixture):
    listings, calendar, reviews = [read(clean_fixture, n + "_clean") for n in ("listings", "calendar", "reviews")]
    listings["neighbourhood_cleansed"] = listings.id.map({"1": "Known"})
    calendar["available"] = calendar.listing_id.eq("2").astype(float)
    # Orphan calendar rows must still be excluded from city totals.
    import pandas as pd
    orphan = calendar.iloc[[0]].assign(listing_id="outside", available=0.0)
    calendar = pd.concat([calendar, orphan], ignore_index=True)
    area, times = compute(clean_fixture, listings, calendar, reviews)
    assert times.loc[times.kpi_id.isin(["K2", "K3"]), "value"].eq(50).all()
    assert area.loc[area.kpi_id.eq("K2"), "value"].eq(100).all()
