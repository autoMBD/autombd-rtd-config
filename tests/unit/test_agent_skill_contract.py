# tests/unit/test_agent_skill_contract.py
from pathlib import Path


def test_rtd_config_skill_names_public_cli_and_m1_scope():
    skill = Path(".skills/rtd-config/SKILL.md").read_text(encoding="utf-8")
    assert "RTD CfgFile CLI" in skill
    assert "rtd-config inspect" in skill
    assert "rtd-config pin-options" in skill
    assert "Milestone 1" in skill
    assert "DMA" in skill
    assert "not in Milestone 1" in skill
