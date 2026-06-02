# tests/unit/test_config.py
from pathlib import Path
from rtd_config.config import RuntimeConfig


def test_runtime_config_defaults_to_repo_data_dir(tmp_path):
    config = RuntimeConfig.from_dict({"project": str(tmp_path)})
    assert config.project == tmp_path
    assert config.family == "s32k3"
    assert config.device == "s32k344"
    assert config.rtd_version == "7_0_1"
    assert config.data_root == Path("data")
