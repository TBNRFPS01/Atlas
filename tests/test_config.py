import json
from pathlib import Path


def test_config_file_exists() -> None:
    config_path = Path("C:/Users/tbn/ATLAS/config.json")
    assert config_path.exists()

    with config_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    assert data["model"] == "local-model"
