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
