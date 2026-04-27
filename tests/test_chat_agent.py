"""Tests for the Gemini function-calling agent loop."""

import importlib
from unittest.mock import MagicMock, patch


def _reload_agent():
    import notion_clerk.config
    importlib.reload(notion_clerk.config)
    import notion_clerk.chat_agent
    importlib.reload(notion_clerk.chat_agent)
    return notion_clerk.chat_agent


class TestToolRegistry:
    def test_read_registry_has_expected_keys(self):
        agent = _reload_agent()
        assert "get_notion_ids" in agent._READ_REGISTRY
        assert "get_database_schema" in agent._READ_REGISTRY
        assert "search_notion" in agent._READ_REGISTRY
        assert "query_database" in agent._READ_REGISTRY
        assert "fetch_page" in agent._READ_REGISTRY

    def test_write_registry_has_expected_keys(self):
        agent = _reload_agent()
        assert "create_database_item" in agent._DEFAULT_WRITE_REGISTRY
        assert "create_page_anywhere" in agent._DEFAULT_WRITE_REGISTRY
        assert "update_database_item" in agent._DEFAULT_WRITE_REGISTRY

    def test_write_tools_override_replaces_default(self):
        agent = _reload_agent()
        mock_fn = MagicMock(return_value={"id": "demo-1"})
        registry = {**agent._READ_REGISTRY, **agent._DEFAULT_WRITE_REGISTRY}
        registry.update({"create_database_item": mock_fn})
        result = agent._dispatch("create_database_item", {"database_id": "db-1", "properties": {}}, registry)
        mock_fn.assert_called_once_with(database_id="db-1", properties={})
        assert result == {"id": "demo-1"}


class TestDispatch:
    def test_returns_error_for_unknown_tool(self):
        agent = _reload_agent()
        result = agent._dispatch("nonexistent_tool", {}, {})
        assert "error" in result
        assert "nonexistent_tool" in result["error"]

    def test_returns_error_on_exception(self):
        agent = _reload_agent()
        def boom(**kwargs):
            raise ValueError("connection refused")
        registry = {"bad_tool": boom}
        result = agent._dispatch("bad_tool", {}, registry)
        assert "error" in result
        assert "connection refused" in result["error"]

    def test_calls_function_with_kwargs(self):
        agent = _reload_agent()
        mock_fn = MagicMock(return_value={"ok": True})
        registry = {"my_tool": mock_fn}
        result = agent._dispatch("my_tool", {"a": 1, "b": "x"}, registry)
        mock_fn.assert_called_once_with(a=1, b="x")
        assert result == {"ok": True}


class TestRunAgentTurn:
    def _make_text_response(self, text: str):
        """Build a mock Gemini response with a text part and no function calls."""
        part = MagicMock()
        part.text = text
        part.function_call = None

        content = MagicMock()
        content.parts = [part]

        candidate = MagicMock()
        candidate.content = content

        response = MagicMock()
        response.candidates = [candidate]
        return response

    def _make_tool_then_text_response(self, tool_name: str, tool_args: dict, final_text: str):
        """Build two mock responses: first a function call, then a text reply."""
        fc = MagicMock()
        fc.name = tool_name
        fc.args = tool_args

        fc_part = MagicMock()
        fc_part.text = None
        fc_part.function_call = fc

        fc_content = MagicMock()
        fc_content.parts = [fc_part]

        fc_candidate = MagicMock()
        fc_candidate.content = fc_content

        fc_response = MagicMock()
        fc_response.candidates = [fc_candidate]

        text_response = self._make_text_response(final_text)
        return [fc_response, text_response]

    @patch("notion_clerk.chat_agent.genai.Client")
    def test_returns_text_when_no_tool_calls(self, mock_client_cls):
        agent = _reload_agent()
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.models.generate_content.return_value = self._make_text_response("Hello!")

        text, new_history = agent.run_agent_turn("Hi", [])

        assert text == "Hello!"
        assert len(new_history) == 2  # user message + model response

    @patch("notion_clerk.chat_agent.genai.Client")
    def test_write_tool_override_is_called(self, mock_client_cls):
        agent = _reload_agent()
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client

        responses = self._make_tool_then_text_response(
            "create_database_item",
            {"database_id": "db-1", "properties": {"Name": "Test"}},
            "Done! Added 'Test'.",
        )
        mock_client.models.generate_content.side_effect = responses

        mock_write = MagicMock(return_value={"id": "demo-1"})
        text, _ = agent.run_agent_turn(
            "Add Test to my database",
            [],
            write_tools={"create_database_item": mock_write},
        )

        mock_write.assert_called_once_with(database_id="db-1", properties={"Name": "Test"})
        assert "Done" in text

    @patch("notion_clerk.chat_agent.genai.Client")
    def test_empty_history_does_not_crash(self, mock_client_cls):
        agent = _reload_agent()
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.models.generate_content.return_value = self._make_text_response("Ready.")

        text, new_history = agent.run_agent_turn("Hello", [])
        assert isinstance(text, str)
        assert isinstance(new_history, list)
