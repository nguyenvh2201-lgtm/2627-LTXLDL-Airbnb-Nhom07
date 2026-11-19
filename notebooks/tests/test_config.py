import yaml
import pytest
from src.download import load_config
from conftest import PROJECT


def test_config():
    cfg = load_config(PROJECT / "configs/city.yaml")
    assert len(cfg["snapshots"]) == 4
    assert cfg["snapshots"] == sorted(cfg["snapshots"])


@pytest.mark.parametrize("failure", ["missing", "duplicate", "absolute", "invalid_date"])
def test_bad_config(tmp_path, failure):
    cfg = yaml.safe_load((PROJECT / "configs/city.yaml").read_text(encoding="utf-8"))
    if failure == "missing":
        del cfg["currency"]
    elif failure == "duplicate":
        cfg["snapshots"][1] = cfg["snapshots"][0]
    elif failure == "absolute":
        cfg["paths"]["raw"] = str(tmp_path.resolve())
    else:
        cfg["snapshots"][0] = "2030-02-30"
    source = tmp_path / "config.yaml"
    source.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    with pytest.raises(ValueError):
        load_config(source)
