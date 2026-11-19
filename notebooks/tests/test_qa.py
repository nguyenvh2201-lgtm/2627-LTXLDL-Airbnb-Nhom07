import pandas as pd
import pytest
import subprocess
import sys
from pathlib import Path
import yaml
from src.qa import (
    check_available, check_categories, check_comments, check_duplicate_review,
    check_review_date, check_numeric_rules, run_qa_listings,
)
from src.download import read, path, money


@pytest.mark.parametrize("mode", ["script", "module"])
def test_qa_cli_reads_supplied_config(raw_fixture, mode):
    cfg = raw_fixture
    project = Path(__file__).resolve().parents[2]
    config_file = cfg["_root"] / "configs" / "test.yaml"
    config_file.parent.mkdir()
    config_file.write_text(yaml.safe_dump({
        key: value for key, value in cfg.items() if not key.startswith("_")
    }), encoding="utf-8")
    # Giữ tiếng Việt khi stdout được chuyển vào pipe trên Windows.
    command = ([sys.executable, "-X", "utf8", str(project / "src" / "qa.py")]
               if mode == "script" else [sys.executable, "-X", "utf8", "-m", "src.qa"])
    result = subprocess.run(
        command + ["--config", str(config_file)],
        cwd=cfg["_root"] if mode == "script" else project,
        capture_output=True, text=True, encoding="utf-8", timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report = pd.read_csv(path(cfg, "reports", "qa_report.csv"))
    assert set(report.snapshot_date) == set(cfg["snapshots"])


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
    reviews = read(cfg, "reviews_clean")
    for rule in ("review_after_scrape", "scraped_date_conflict",
                 "review_date_uncheckable"):
        assert rule in reviews.columns
        rows = report.loc[report.rule.eq(rule)]
        assert len(rows) == len(cfg["snapshots"])
        assert rows.reason.notna().all()
        assert rows.rows_flagged.eq(0).all()


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
    flags = run_qa_listings(
        frame,
        allowed_room_types=["Entire home/apt", "Private room"],
        allowed_areas=["A01"],
        min_nights_cap=365,
    )["row_flags"]
    # UNKNOWN chỉ có một giá: chưa đủ căn cứ IQR theo loại phòng.
    assert not bool(flags.loc[3, "price_iqr_checkable"])
    assert not bool(flags.loc[3, "price_outlier_iqr"])
    assert bool(flags.loc[3, "price_above_cap"])
    assert bool(flags.loc[3, "price_outlier"])
    assert bool(flags.loc[3, "invalid_minimum_nights"])
    assert bool(flags.loc[3, "category_mismatch"])


def test_category_scope_can_change_and_missing_values_are_flagged():
    frame = pd.DataFrame({
        "room_type": ["Entire home/apt", "Hotel room", None, "Private room"],
        "analysis_area": ["A01", "Zone-X", "Zone-X", None],
    }, index=[10, 20, 30, 40])
    original = frame.copy(deep=True)
    flags = check_categories(frame, ["Entire home/apt", "Private room"], ["A01"])
    assert flags.category_mismatch.tolist() == [False, True, True, True]
    changed = check_categories(frame, ["Hotel room"], ["Zone-X"])
    assert changed.category_mismatch.tolist() == [True, False, True, True]
    assert changed.index.equals(frame.index)
    assert not changed.isna().any().any()
    pd.testing.assert_frame_equal(frame, original)


def test_qa_uses_configured_room_types_and_assigned_areas(raw_fixture):
    from src.qa import run

    cfg = raw_fixture
    cfg["qa"]["room_types"] = ["Private room"]
    assignment = cfg["_root"] / cfg["inputs"]["listing_ids"]
    pd.DataFrame({
        "id": ["1", "2"], "analysis_area": ["Zone-X", "Zone-Y"],
    }).to_csv(assignment, index=False)
    run(cfg)

    listings = read(cfg, "listings_clean")
    assert len(listings) == 2 * len(cfg["snapshots"])
    assert listings.analysis_area_valid.all()
    assert listings.loc[listings.id.eq("1"), "category_mismatch"].all()
    assert not listings.loc[listings.id.eq("2"), "category_mismatch"].any()
    report = pd.read_csv(path(cfg, "reports", "qa_report.csv"))
    category_rows = report.loc[report.rule.eq("category_mismatch")]
    assert len(category_rows) == len(cfg["snapshots"])
    assert category_rows.rows_flagged.eq(1).all()
    assert category_rows.rows_removed.eq(0).all()


@pytest.mark.parametrize("column", ["minimum_nights", "maximum_nights", "availability_365"])
def test_numeric_missing_type_and_invalid_values_are_distinct(column):
    values = [None, pd.NA, "", "  ", "bad", "inf", "-inf", "1.5", "-1", " 2 "]
    frame = pd.DataFrame({
        "minimum_nights": [1] * len(values),
        "maximum_nights": [365] * len(values),
        "availability_365": [100] * len(values),
    }, index=range(20, 30))
    frame[column] = values
    original = frame.copy(deep=True)
    flags = check_numeric_rules(frame, min_nights_cap=365)
    assert flags[f"missing_{column}"].tolist() == [True] * 4 + [False] * 6
    assert flags[f"wrong_{column}_type"].tolist() == [False] * 4 + [True] + [False] * 5
    assert flags[f"invalid_{column}"].tolist() == [False] * 5 + [True] * 4 + [False]
    assert flags[f"{column}_valid"].tolist() == [False] * 9 + [True]
    assert flags.index.equals(frame.index)
    assert not flags.isna().any().any()
    pd.testing.assert_frame_equal(frame, original)


def test_numeric_boundaries_conflicts_and_configured_cap():
    frame = pd.DataFrame({
        "minimum_nights": [0, 1, 30, 31, 40, 2, 1],
        "maximum_nights": [365, 365, 365, 365, 20, "bad", 0],
        "availability_365": [0, 365, 366, -1, 100, 100, 100],
    })
    flags = check_numeric_rules(frame, min_nights_cap=30)
    assert flags.invalid_minimum_nights.tolist() == [True] + [False] * 6
    assert flags.minimum_nights_above_cap.tolist() == [False, False, False, True, True, False, False]
    assert flags.min_greater_max.tolist() == [False, False, False, False, True, False, False]
    assert flags.minimum_nights_valid.tolist() == [False, True, True, False, False, True, True]
    assert flags.invalid_availability_365.tolist() == [False, False, True, True, False, False, False]
    assert flags.invalid_maximum_nights.iloc[-1]
    assert check_numeric_rules(frame, min_nights_cap=60).minimum_nights_valid.iloc[3]


@pytest.mark.parametrize("cap", [0, -1, 2.5, float("inf"), float("nan"), True, "365", None])
def test_numeric_rejects_invalid_cap(cap):
    with pytest.raises(ValueError, match="qa.min_nights_cap"):
        check_numeric_rules(pd.DataFrame(), min_nights_cap=cap)


def test_numeric_flags_reach_reports_and_kpi(raw_fixture):
    from src.qa import run
    from src.kpi import compute

    cfg = raw_fixture
    cfg["qa"]["min_nights_cap"] = 35
    for snapshot in cfg["snapshots"]:
        source = path(cfg, "raw", f"{snapshot}/listings.csv.gz")
        raw = pd.read_csv(source)
        raw.loc[raw.id.eq(1), ["minimum_nights", "maximum_nights"]] = [40, 20]
        raw.to_csv(source, index=False)
    run(cfg)
    listings = read(cfg, "listings_clean")
    first = listings.loc[listings.id.eq("1")]
    assert len(first) == len(cfg["snapshots"])
    assert first.minimum_nights_above_cap.all()
    assert first.min_greater_max.all()
    assert not first.minimum_nights_valid.any()
    assert first.flag_outlier_minimum_nights.all()
    assert first.minimum_nights.eq(40).all()  # Giá trị gốc được giữ nguyên.
    report = pd.read_csv(path(cfg, "reports", "qa_report.csv"))
    for rule in ("minimum_nights_above_cap", "min_greater_max"):
        rows = report.loc[report.rule.eq(rule)]
        assert len(rows) == len(cfg["snapshots"])
        assert rows.rows_flagged.eq(1).all()
        assert rows.condition.notna().all()
    _, times = compute(cfg, listings, read(cfg, "calendar_clean"), read(cfg, "reviews_clean"))
    k4 = times.loc[times.kpi_id.eq("K4")]
    assert k4.n.eq(1).all()
    assert k4.value.eq(100).all()


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


def test_review_dates_handle_duplicates_conflicts_and_missing_dates():
    listings = pd.DataFrame({
        "listing_id": ["same", "same", "conflict", "conflict",
                       "partial", "partial", "invalid", None, " "],
        "last_scraped": ["2030-06-15 08:00", "2030-06-15 20:00",
                         "2030-06-15 08:00", "2030-06-16 08:00",
                         "2030-06-15 08:00", None, "bad",
                         "2030-06-15 08:00", "2030-06-15 08:00"],
    })
    reviews = pd.DataFrame({
        "listing_id": ["same", "same", "same", "conflict", "partial",
                       "invalid", "unknown", "same", "same", None, " "],
        "date": ["2030-06-14", "2030-06-15", "2030-06-16", "2030-06-20",
                 "2030-06-16", "2030-06-16", "2030-06-16", None, "bad",
                 "2030-06-16", "2030-06-16"],
    }, index=range(10, 21))
    original_listings = listings.copy(deep=True)
    original_reviews = reviews.copy(deep=True)
    flags = check_review_date(reviews, listings)
    assert flags.index.equals(reviews.index)
    assert flags.review_after_scrape.tolist() == [
        False, False, True, False, True, False, False, False, False, False, False,
    ]
    assert flags.scraped_date_conflict.tolist() == [
        False, False, False, True, False, False, False, False, False, False, False,
    ]
    assert flags.review_date_uncheckable.tolist() == [
        False, False, False, True, False, True, True, True, True, True, True,
    ]
    assert not flags.isna().any().any()
    pd.testing.assert_frame_equal(listings, original_listings)
    pd.testing.assert_frame_equal(reviews, original_reviews)


def test_review_dates_without_listing_lookup():
    reviews = pd.DataFrame({"listing_id": ["missing"], "date": ["2030-06-15"]})
    listings = pd.DataFrame(columns=["listing_id", "last_scraped"])
    flags = check_review_date(reviews, listings)
    assert flags.iloc[0].to_dict() == {
        "review_after_scrape": False,
        "scraped_date_conflict": False,
        "review_date_uncheckable": True,
    }
