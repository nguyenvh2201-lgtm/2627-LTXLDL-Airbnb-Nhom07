from unittest.mock import Mock
import hashlib
import pandas as pd
import pytest
from src import download
from src.download import path


def test_retry_atomic_download(raw_fixture, tmp_path, monkeypatch):
    source = path(raw_fixture, "raw", raw_fixture["snapshots"][0] + "/reviews.csv.gz")
    content = source.read_bytes()
    response = Mock(is_redirect=False)
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    response.iter_content.return_value = [content[:10], content[10:]]
    get = Mock(side_effect=[download.requests.ConnectionError("offline"), response])
    monkeypatch.setattr(download.requests, "get", get)
    monkeypatch.setattr(download.time, "sleep", lambda _: None)
    dest = tmp_path / "reviews.csv.gz"
    download.download_file("https://data.insideairbnb.com/test/reviews.csv.gz", dest, raw_fixture["download"])
    assert dest.read_bytes() == content
    assert not dest.with_suffix(".gz.part").exists()
    assert get.call_count == 2


def test_unapproved_source_rejected(raw_fixture, tmp_path):
    with pytest.raises(ValueError, match="Chỉ tải"):
        download.download_file("https://airbnb.com/test", tmp_path / "reviews.csv.gz", raw_fixture["download"])


def test_neighbourhood_download_and_manifest(raw_fixture, monkeypatch):
    cfg = raw_fixture
    snapshot = cfg["snapshots"][0]
    source = path(cfg, "raw", f"{snapshot}/neighbourhoods.geojson")
    content = source.read_bytes()
    source.unlink()
    cfg["_options"]["skip_download"] = False
    response = Mock(is_redirect=False)
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    response.iter_content.return_value = [content]
    get = Mock(return_value=response)
    monkeypatch.setattr(download.requests, "get", get)
    download.run_download(cfg)
    assert source.read_bytes() == content
    assert get.call_args.args[0].endswith(
        f"/{snapshot}/visualisations/neighbourhoods.geojson"
    )
    manifest = pd.read_csv(path(cfg, "reports", "download_manifest.csv"))
    geo = manifest.loc[manifest.table.eq("neighbourhoods")]
    assert len(geo) == len(cfg["snapshots"])
    assert geo.sha256.eq(hashlib.sha256(content).hexdigest()).all()
    assert not source.with_suffix(".geojson.part").exists()


def test_neighbourhood_missing_when_skip_download(raw_fixture):
    cfg = raw_fixture
    source = path(cfg, "raw", f"{cfg['snapshots'][0]}/neighbourhoods.geojson")
    source.unlink()
    with pytest.raises(ValueError, match="neighbourhoods.geojson"):
        download.run_download(cfg)


@pytest.mark.parametrize("content", ["<html>error</html>", '{}',
    '{"type":"FeatureCollection","features":[]}',
    '{"type":"FeatureCollection","features":[{"type":"Feature","geometry":null}]}'])
def test_invalid_geojson_rejected(tmp_path, content):
    source = tmp_path / "neighbourhoods.geojson"
    source.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError):
        download.verify_file(source, "neighbourhoods")
