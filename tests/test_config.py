import json
from pathlib import Path


def _project_config() -> Path:
    return Path(__file__).resolve().parents[1] / "config.json"


def test_config_file_exists() -> None:
    config_path = _project_config()
    assert config_path.exists()

    with config_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    assert data["model"] == "local-model"


def test_config_manager_loads_defaults(tmp_path: Path) -> None:
    from config.manager import ConfigManager

    cfg = ConfigManager(config_path=tmp_path / "config.json")
    assert cfg.get("model") == "local-model"
    assert cfg.get("history_size") == 60
    assert cfg.validate() == []