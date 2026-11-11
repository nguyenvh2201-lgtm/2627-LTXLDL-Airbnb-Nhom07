from unittest.mock import Mock
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
