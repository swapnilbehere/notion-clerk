"""Tests for configuration loading."""

import importlib
import pytest


def test_config_loads_required_keys(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "gk")
    monkeypatch.setenv("NOTION_API_KEY", "nk")
    monkeypatch.setenv("NOTION_PARENT_PAGE", "pp")

    from notion_clerk import config
    importlib.reload(config)

    assert config.GOOGLE_API_KEY == "gk"
    assert config.NOTION_API_KEY == "nk"
    assert config.NOTION_PARENT_PAGE == "pp"


def test_config_demo_mode_defaults_false(monkeypatch):
    monkeypatch.delenv("DEMO_MODE", raising=False)

    from notion_clerk import config
    importlib.reload(config)

    assert config.DEMO_MODE is False


def test_config_demo_mode_true(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "true")

    from notion_clerk import config
    importlib.reload(config)

    assert config.DEMO_MODE is True


def test_config_fails_on_missing_required_key(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **kw: None)

    from notion_clerk import config
    with pytest.raises(KeyError):
        importlib.reload(config)
