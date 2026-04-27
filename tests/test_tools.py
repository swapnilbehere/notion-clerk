"""Tests for Notion REST helpers and property coercion."""

import importlib
from datetime import date, timedelta
from unittest.mock import patch


def _reload_tools():
    """Force reimport of tools module to pick up mocked config."""
    import notion_clerk.config
    importlib.reload(notion_clerk.config)
    import notion_clerk.tools
    importlib.reload(notion_clerk.tools)
    return notion_clerk.tools


class TestNotionHeaders:
    def test_returns_correct_structure(self):
        tools = _reload_tools()
        headers = tools._notion_headers()
        assert headers["Authorization"] == "Bearer test-notion-key"
        assert headers["Notion-Version"] == "2022-06-28"
        assert headers["Content-Type"] == "application/json"


class TestCoercePropertyValue:
    def _coerce(self, prop_type, value):
        tools = _reload_tools()
        return tools._coerce_property_value({"type": prop_type}, value)

    def test_title(self):
        result = self._coerce("title", "My Title")
        assert result == {"title": [{"text": {"content": "My Title"}}]}

    def test_rich_text(self):
        result = self._coerce("rich_text", "Some text")
        assert result == {"rich_text": [{"text": {"content": "Some text"}}]}

    def test_date_iso_string(self):
        result = self._coerce("date", "2025-11-20")
        assert result == {"date": {"start": "2025-11-20"}}

    def test_date_today(self):
        result = self._coerce("date", "today")
        assert result["date"]["start"] == date.today().isoformat()

    def test_date_tomorrow(self):
        result = self._coerce("date", "tomorrow")
        expected = (date.today() + timedelta(days=1)).isoformat()
        assert result["date"]["start"] == expected

    def test_date_yesterday(self):
        result = self._coerce("date", "yesterday")
        expected = (date.today() - timedelta(days=1)).isoformat()
        assert result["date"]["start"] == expected

    def test_checkbox_true_values(self):
        for val in [True, "true", "yes", "y", "1", "checked", "done"]:
            result = self._coerce("checkbox", val)
            assert result == {"checkbox": True}, f"Failed for: {val}"

    def test_checkbox_false_values(self):
        for val in [False, "false", "no", "0"]:
            result = self._coerce("checkbox", val)
            assert result == {"checkbox": False}, f"Failed for: {val}"

    def test_select(self):
        result = self._coerce("select", "High")
        assert result == {"select": {"name": "High"}}

    def test_multi_select_single(self):
        result = self._coerce("multi_select", "Tag1")
        assert result == {"multi_select": [{"name": "Tag1"}]}

    def test_multi_select_list(self):
        result = self._coerce("multi_select", ["A", "B"])
        assert result == {"multi_select": [{"name": "A"}, {"name": "B"}]}

    def test_number(self):
        result = self._coerce("number", "42.5")
        assert result == {"number": 42.5}

    def test_number_invalid(self):
        result = self._coerce("number", "not-a-number")
        assert result == {"number": None}

    def test_url(self):
        result = self._coerce("url", "https://example.com")
        assert result == {"url": "https://example.com"}

    def test_unknown_type_fallback(self):
        result = self._coerce("unknown_type", "fallback")
        assert "rich_text" in result


class TestGetNotionIds:
    @patch("notion_clerk.tools.requests.post")
    def test_returns_databases(self, mock_post, mock_notion_response):
        tools = _reload_tools()
        mock_post.return_value = mock_notion_response(json_data={
            "results": [
                {
                    "object": "database",
                    "id": "db-1",
                    "title": [{"plain_text": "My DB"}],
                    "url": "https://notion.so/db-1",
                }
            ],
            "has_more": False,
        })
        result = tools.get_notion_ids()
        assert len(result["databases"]) == 1
        assert result["databases"][0]["title"] == "My DB"

    @patch("notion_clerk.tools.requests.post")
    def test_handles_pagination(self, mock_post, mock_notion_response):
        tools = _reload_tools()
        page1 = mock_notion_response(json_data={
            "results": [
                {"object": "database", "id": "db-1", "title": [{"plain_text": "DB1"}], "url": "u1"}
            ],
            "has_more": True,
            "next_cursor": "cursor-2",
        })
        page2 = mock_notion_response(json_data={
            "results": [
                {"object": "database", "id": "db-2", "title": [{"plain_text": "DB2"}], "url": "u2"}
            ],
            "has_more": False,
        })
        mock_post.side_effect = [page1, page2]
        result = tools.get_notion_ids()
        assert len(result["databases"]) == 2

    @patch("notion_clerk.tools.requests.post")
    def test_empty_results(self, mock_post, mock_notion_response):
        tools = _reload_tools()
        mock_post.return_value = mock_notion_response(json_data={
            "results": [],
            "has_more": False,
        })
        result = tools.get_notion_ids()
        assert result["databases"] == []


class TestGetDatabaseSchema:
    @patch("notion_clerk.tools.requests.get")
    def test_returns_property_names_and_types(self, mock_get, mock_notion_response, sample_database_schema):
        tools = _reload_tools()
        mock_get.return_value = mock_notion_response(json_data=sample_database_schema)
        result = tools.get_database_schema("db-123")
        assert result["title"] == "Test DB"
        assert result["properties"]["Name"] == "title"
        assert result["properties"]["Due Date"] == "date"
        assert result["properties"]["Done"] == "checkbox"

    @patch("notion_clerk.tools.requests.get")
    def test_empty_properties(self, mock_get, mock_notion_response):
        tools = _reload_tools()
        mock_get.return_value = mock_notion_response(json_data={
            "id": "db-empty",
            "title": [{"plain_text": "Empty DB"}],
            "properties": {},
        })
        result = tools.get_database_schema("db-empty")
        assert result["properties"] == {}


class TestCreateDatabaseItem:
    @patch("notion_clerk.tools.requests.post")
    @patch("notion_clerk.tools.requests.get")
    def test_creates_item_with_schema_coercion(
        self, mock_get, mock_post, mock_notion_response, sample_database_schema
    ):
        tools = _reload_tools()
        mock_get.return_value = mock_notion_response(json_data=sample_database_schema)
        mock_post.return_value = mock_notion_response(
            json_data={"id": "page-new", "object": "page"}
        )
        result = tools.create_database_item("db-123", {"Name": "Test Item", "Done": True})
        assert result["id"] == "page-new"
        mock_post.assert_called_once()

    @patch("notion_clerk.tools.requests.post")
    @patch("notion_clerk.tools.requests.get")
    def test_adds_default_title_if_missing(
        self, mock_get, mock_post, mock_notion_response, sample_database_schema
    ):
        tools = _reload_tools()
        mock_get.return_value = mock_notion_response(json_data=sample_database_schema)
        mock_post.return_value = mock_notion_response(
            json_data={"id": "page-new", "object": "page"}
        )
        # Pass only a non-title property
        tools.create_database_item("db-123", {"Done": True})
        call_body = mock_post.call_args[1]["json"]
        # Should have auto-added Name as title
        assert "Name" in call_body["properties"]


class TestCreatePageAnywhere:
    @patch("notion_clerk.tools.requests.post")
    def test_creates_page_with_content(self, mock_post, mock_notion_response):
        tools = _reload_tools()
        mock_post.return_value = mock_notion_response(json_data={"id": "page-abc"})
        result = tools.create_page_anywhere("Test Page", content="Hello world")
        assert result["id"] == "page-abc"
        call_body = mock_post.call_args[1]["json"]
        assert "children" in call_body

    @patch("notion_clerk.tools.requests.post")
    def test_creates_page_without_content(self, mock_post, mock_notion_response):
        tools = _reload_tools()
        mock_post.return_value = mock_notion_response(json_data={"id": "page-abc"})
        tools.create_page_anywhere("Test Page")
        call_body = mock_post.call_args[1]["json"]
        assert "children" not in call_body

    @patch("notion_clerk.tools.requests.post")
    def test_uses_default_parent_page(self, mock_post, mock_notion_response):
        tools = _reload_tools()
        mock_post.return_value = mock_notion_response(json_data={"id": "page-abc"})
        tools.create_page_anywhere("Test Page")
        call_body = mock_post.call_args[1]["json"]
        assert call_body["parent"]["page_id"] == "test-parent-page-id"
