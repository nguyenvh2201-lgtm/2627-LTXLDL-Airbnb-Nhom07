import pandas as pd
import pytest
from src.download import filtered_chunks, run_filter as run, validate_snapshot, load_ids
from src.download import verify_file, build_url
from src.download import path, read


def test_chunk_filter_preserves_exact_ids(tmp_path):
    source = tmp_path / "calendar.csv.gz"
    values = ["9007199254740992", "9007199254740993", "001", "1", None,
              "1000000000000000001", "9007199254740993"]
    pd.DataFrame({"listing_id": values}).to_csv(source, index=False)
    ids = {"9007199254740993", "001", "1000000000000000001"}
    chunked, total = filtered_chunks(source, ids, "listing_id", 2)
    assert chunked.listing_id.tolist() == [values[i] for i in (1, 2, 5, 6)]
    assert total == len(values)
    for targets in ({"missing"}, set()):
        empty, total = filtered_chunks(source, targets, "listing_id", 2)
        assert empty.empty
        assert total == len(values)


def test_wrong_expected_stops(raw_fixture):
    raw_fixture["expected"]["listing_count"] = 999
    with pytest.raises(ValueError, match="Lọc sai"):
        run(raw_fixture)


def test_snapshot_expectations(raw_fixture):
    run(raw_fixture)
    snapshot = raw_fixture["snapshots"][0]
    tables = [read(raw_fixture, name) for name in
              ("listings_raw_filtered", "calendar_raw_filtered", "reviews_raw_filtered")]
    listings, calendar, reviews = [table.loc[table.snapshot.eq(snapshot)] for table in tables]
    raw_fixture["expected"]["listing_count"] = 999
    raw_fixture["expected"]["by_snapshot"][snapshot]["listing_count"] = 2
    checks = validate_snapshot(raw_fixture, snapshot, listings, calendar, reviews, load_ids(raw_fixture))
    assert next(row for row in checks if row["check"] == "listing_count")["passed"]
    raw_fixture["expected"]["by_snapshot"] = {}
    raw_fixture["expected"]["listing_count"] = 999
    run(raw_fixture)
    checks = pd.read_csv(path(raw_fixture, "reports", "filter_checks.csv"))
    assert set(checks.loc[~checks.passed, "severity"]) == {"warning"}


def test_verify_gzip(raw_fixture, tmp_path):
    source = path(raw_fixture, "raw", raw_fixture["snapshots"][0] + "/listings.csv.gz")
    assert len(verify_file(source, "listings")) == 64
    bad = tmp_path / "bad.csv.gz"
    bad.write_bytes(source.read_bytes()[:-5])
    with pytest.raises((EOFError, OSError)):
        verify_file(bad, "listings")
    assert "2030-01-01" in build_url(raw_fixture, "2030-01-01", "reviews")
