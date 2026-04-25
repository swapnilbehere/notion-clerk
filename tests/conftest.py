"""Shared pytest fixtures."""

import pytest
from unittest.mock import MagicMock


@pytest.fixture(autouse=True)
def mock_env_vars(monkeypatch):
    """Ensure tests never use real API keys."""
    monkeypatch.setenv("GOOGLE_API_KEY", "test-google-key")
    monkeypatch.setenv("NOTION_API_KEY", "test-notion-key")
    monkeypatch.setenv("NOTION_PARENT_PAGE", "test-parent-page-id")
    monkeypatch.setenv("NOTION_FEEDBACK_DB_ID", "test-feedback-db-id")
    monkeypatch.setenv("DEMO_MODE", "false")


@pytest.fixture
def mock_notion_response():
    """Factory for mock Notion API responses."""
    def _make(status_code=200, json_data=None):
        resp = MagicMock()
        resp.status_code = status_code
        resp.json.return_value = json_data or {}
        resp.raise_for_status = MagicMock()
        return resp
    return _make


@pytest.fixture
def sample_database_schema():
    """A realistic Notion database schema for testing property coercion."""
    return {
        "id": "db-123",
        "title": [{"plain_text": "Test DB"}],
        "properties": {
            "Name": {"type": "title"},
            "Description": {"type": "rich_text"},
            "Due Date": {"type": "date"},
            "Done": {"type": "checkbox"},
            "Priority": {"type": "select"},
            "Tags": {"type": "multi_select"},
            "Score": {"type": "number"},
            "Link": {"type": "url"},
        },
    }
