import pandas as pd

from src.qa import check_price


def test_iqr_uses_each_room_type_and_preserves_index():
    index = pd.Index(range(20, 32))
    raw = pd.Series([90, 95, 100, 105, 110, 500,
                     900, 950, 1000, 1050, 1100, 5000], index=index)
    rooms = pd.Series(["Private room"] * 6 + ["Entire home/apt"] * 6,
                      index=index)
    result = check_price(raw, rooms)
    assert result.index.equals(index)
    assert result.price_iqr_checkable.all()
    assert result.index[result.price_outlier].tolist() == [25, 31]
    assert raw.iloc[-1] == 5000


def test_iqr_skips_small_constant_and_unknown_groups():
    raw = pd.Series([10, 20, 1000, 50, 50, 50, 50, 999])
    rooms = pd.Series(["small"] * 3 + ["constant"] * 4 + [None])
    result = check_price(raw, rooms)
    assert result.price_valid.all()
    assert not result.price_iqr_checkable.any()
    assert not result.price_outlier.any()


def test_invalid_prices_do_not_affect_group_thresholds():
    raw = pd.Series([90, 95, 100, 105, 110, 500,
                     None, "bad", 0, -1, "inf", "-inf"])
    rooms = pd.Series(["Private room"] * len(raw))
    result = check_price(raw, rooms)
    assert result.index[result.price_outlier].tolist() == [5]
    assert result.price_valid.tolist() == [True] * 6 + [False] * 6
    assert result.index[result.invalid_price].tolist() == [8, 9, 10, 11]
    assert not result.price_iqr_checkable.iloc[6:].any()
