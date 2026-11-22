import yaml
import pytest
from src.download import load_config
from conftest import PROJECT
from run_pipeline import validate_limited_run


def test_config():
    cfg = load_config(PROJECT / "configs/Toronto.yaml")
    assert len(cfg["snapshots"]) == 4
    assert cfg["snapshots"] == sorted(cfg["snapshots"])


def test_legacy_city_config_name_uses_toronto():
    cfg = load_config(PROJECT / "configs/city.yaml")
    assert cfg["_config_path"].name == "Toronto.yaml"


def test_limit_requires_isolated_llm_or_baseline_steps():
    validate_limited_run(["llm", "baseline"], explicit_only=True, limit=20)
    with pytest.raises(ValueError, match="--only llm,baseline"):
        validate_limited_run(["llm", "baseline", "evaluate"], explicit_only=True, limit=20)
    with pytest.raises(ValueError, match="--only llm,baseline"):
        validate_limited_run(["llm"], explicit_only=False, limit=20)
    with pytest.raises(ValueError, match="số nguyên dương"):
        validate_limited_run(["llm"], explicit_only=True, limit=0)


@pytest.mark.parametrize("failure", ["missing", "duplicate", "absolute", "invalid_date"])
def test_bad_config(tmp_path, failure):
    cfg = yaml.safe_load((PROJECT / "configs/Toronto.yaml").read_text(encoding="utf-8"))
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
