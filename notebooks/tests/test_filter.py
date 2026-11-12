import pandas as pd
import pytest
from src.download import filtered_chunks, run_filter as run, validate_snapshot, load_ids
from src.download import verify_file, build_url
from src.download import path, read


def test_chunk_equivalence(raw_fixture):
    cfg = raw_fixture
    source = path(cfg, "raw", cfg["snapshots"][0] + "/calendar.csv.gz")
    chunked, total = filtered_chunks(source, {"1", "2"}, "listing_id", 2, ["listing_id", "date", "available"])
    full = pd.read_csv(source, dtype={"listing_id": "string"}, usecols=["listing_id", "date", "available"])
    pd.testing.assert_frame_equal(chunked, full.loc[full.listing_id.isin(["1", "2"])].reset_index(drop=True))
    assert total == 9


def test_filter_and_big_id(raw_fixture):
    run(raw_fixture)
    listings = read(raw_fixture, "listings_raw_filtered")
    reviews = read(raw_fixture, "reviews_raw_filtered")
    assert len(listings) == 8
    assert "1000000000000000001" in set(reviews.id)
    checks = pd.read_csv(path(raw_fixture, "reports", "filter_checks.csv"))
    assert checks.passed.all()


def test_wrong_expected_stops(raw_fixture):
    raw_fixture["expected"]["listing_count"] = 999
    with pytest.raises(ValueError, match="Lọc sai"):
        run(raw_fixture)


def test_unknown_snapshot_warns(raw_fixture):
    raw_fixture["expected"]["by_snapshot"] = {}
    raw_fixture["expected"]["listing_count"] = 999
    run(raw_fixture)
    checks = pd.read_csv(path(raw_fixture, "reports", "filter_checks.csv"))
    assert set(checks.loc[~checks.passed, "severity"]) == {"warning"}


def test_snapshot_expected_overrides_global_counts(raw_fixture):
    run(raw_fixture)
    snapshot = raw_fixture["snapshots"][0]
    tables = [read(raw_fixture, name) for name in
              ("listings_raw_filtered", "calendar_raw_filtered", "reviews_raw_filtered")]
    listings, calendar, reviews = [table.loc[table.snapshot.eq(snapshot)] for table in tables]
    raw_fixture["expected"]["listing_count"] = 999
    raw_fixture["expected"]["by_snapshot"][snapshot]["listing_count"] = 2
    checks = validate_snapshot(raw_fixture, snapshot, listings, calendar, reviews, load_ids(raw_fixture))
    assert next(row for row in checks if row["check"] == "listing_count")["passed"]


def test_verify_gzip(raw_fixture, tmp_path):
    source = path(raw_fixture, "raw", raw_fixture["snapshots"][0] + "/listings.csv.gz")
    assert len(verify_file(source, "listings")) == 64
    bad = tmp_path / "bad.csv.gz"
    bad.write_bytes(source.read_bytes()[:-5])
    with pytest.raises((EOFError, OSError)):
        verify_file(bad, "listings")
    assert "2030-01-01" in build_url(raw_fixture, "2030-01-01", "reviews")
