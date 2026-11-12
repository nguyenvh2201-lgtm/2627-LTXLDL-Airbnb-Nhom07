"""Fixtures tổng hợp chỉ dùng trong kiểm thử, không ghi vào dữ liệu thực."""
import copy
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import pandas as pd
import pytest
from src.download import load_config

PROJECT = Path(__file__).resolve().parents[2]


@pytest.fixture
def cfg(tmp_path):
    config = copy.deepcopy(load_config(PROJECT / "configs/city.yaml"))
    config["_root"] = tmp_path
    config["_options"] = {"skip_llm": True, "skip_download": True}
    config["snapshots"] = ["2030-01-01", "2030-04-01", "2030-07-01", "2030-10-01"]
    config["io"]["chunksize"] = 2
    config["io"]["calendar_days"] = 3
    config["llm"].update({"sample_size": 3, "batch_size": 2, "rate_limit_per_min": 1e9, "retries": 2, "backoff": 0})
    config["evaluation"].update({"min_hand_labels": 3, "bootstrap_iterations": 20})
    config["expected"] = {"listing_count": 2, "review_count": 3, "llm_count": 3, "hand_count": 3, "area_count": 2, "area_min": 1, "area_max": 1, "room_types": {"Entire home/apt": 1, "Private room": 1}, "by_snapshot": {s: {"zero_reviews": 0} for s in config["snapshots"]}}
    for folder in config["paths"].values():
        (tmp_path / folder).mkdir(parents=True, exist_ok=True)
    return config


@pytest.fixture
def raw_fixture(cfg):
    root = cfg["_root"]
    pd.DataFrame({"id": ["1", "2"], "analysis_area": ["A01", "A02"]}).to_csv(root / cfg["inputs"]["listing_ids"], index=False)
    pd.DataFrame({"id": ["1000000000000000001", "12", "13"], "in_llm_sample": [True] * 3, "in_hand_label": [True] * 3}).to_csv(root / cfg["inputs"]["review_ids"], index=False)
    pd.DataFrame({"area": ["A01", "A02"], "lat_min": [0, 1], "lat_max": [1, 2], "lon_min": [0, 1], "lon_max": [1, 2]}).to_csv(root / cfg["inputs"]["areas"], index=False)
    for snapshot in cfg["snapshots"]:
        folder = root / cfg["paths"]["raw"] / snapshot
        folder.mkdir()
        (folder / "neighbourhoods.geojson").write_text(json.dumps({
            "type": "FeatureCollection", "features": [{
                "type": "Feature", "properties": {"neighbourhood": "Test area"},
                "geometry": {"type": "Polygon", "coordinates": [
                    [[0, 0], [1, 0], [1, 1], [0, 0]],
                ]},
            }],
        }), encoding="utf-8")
        listings = pd.DataFrame({"id": ["1", "2", "3"], "room_type": ["Entire home/apt", "Private room", "Hotel room"], "price": ["$100.00", "$200.00", "$999.00"], "number_of_reviews": [2, 1, 0], "minimum_nights": [2, 30, 1], "maximum_nights": [365] * 3, "bedrooms": [1, None, 1], "beds": [1, 2, 1], "accommodates": [2, 4, 2], "property_type": ["Apartment"] * 3, "first_review": ["2029-01-01"] * 3, "last_review": ["2029-10-01"] * 3, "last_scraped": [snapshot] * 3, "review_scores_rating": [5, None, 4], "host_response_rate": ["100%", "bad", "80%"], "latitude": [0.5, 1.5, 3], "longitude": [0.5, 1.5, 3], "host_id": ["11", "22", "33"]})
        listings.to_csv(folder / "listings.csv.gz", index=False)
        calendar = pd.DataFrame([{"listing_id": str(i), "date": str(d.date()), "available": "t" if j == 0 else "f", "price": "$100", "minimum_nights": 1, "maximum_nights": 365} for i in (1, 2, 3) for j, d in enumerate(pd.date_range(snapshot, periods=3))])
        calendar.to_csv(folder / "calendar.csv.gz", index=False)
        reviews = pd.DataFrame({"id": ["1000000000000000001", "12", "13", "14"], "listing_id": ["1", "1", "2", "3"], "reviewer_id": ["a", "b", "c", "d"], "date": ["2029-09-01"] * 4, "comments": ["Great clean apartment and a very helpful host", "Good location but noisy and dirty room", "Terrible dirty room with a broken shower", "Excluded review"]})
        reviews.to_csv(folder / "reviews.csv.gz", index=False)
    return cfg


@pytest.fixture
def clean_fixture(raw_fixture):
    from src.download import run_filter as filter_run
    from src.qa import run as qa_run
    filter_run(raw_fixture)
    qa_run(raw_fixture)
    return raw_fixture
