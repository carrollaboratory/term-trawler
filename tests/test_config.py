from pathlib import Path

import pytest

from shrimp import get_config


@pytest.fixture
def load_config() -> None:
    cfg = Path("config.yaml")
    return get_config(cfg)


def test_config(load_config):

    assert "warehouse" in load_config, "Invalid configuration"
