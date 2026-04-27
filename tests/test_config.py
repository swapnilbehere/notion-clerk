"""Tests for configuration loading."""

import importlib


def test_config_loads_required_keys(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gk")
    monkeypatch.setenv("NOTION_API_KEY", "nk")
    monkeypatch.setenv("NOTION_PARENT_PAGE", "pp")

    from notion_clerk import config
    importlib.reload(config)

    assert config.GROQ_API_KEY == "gk"
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


def test_agent_model_defaults(monkeypatch):
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **kw: None)
    monkeypatch.delenv("AGENT_MODEL", raising=False)
    monkeypatch.delenv("FALLBACK_MODEL", raising=False)

    from notion_clerk import config
    importlib.reload(config)

    assert config.AGENT_MODEL == "llama-3.3-70b-versatile"
    assert config.FALLBACK_MODEL == "llama-3.1-8b-instant"
