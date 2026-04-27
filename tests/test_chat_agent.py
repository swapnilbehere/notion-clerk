"""Tests for the Groq function-calling agent loop."""

import importlib
import json
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

    def test_returns_error_on_exception(self):
        agent = _reload_agent()
        def boom(**kwargs):
            raise ValueError("connection refused")
        result = agent._dispatch("bad_tool", {}, {"bad_tool": boom})
        assert "error" in result
        assert "connection refused" in result["error"]

    def test_calls_function_with_kwargs(self):
        agent = _reload_agent()
        mock_fn = MagicMock(return_value={"ok": True})
        result = agent._dispatch("my_tool", {"a": 1, "b": "x"}, {"my_tool": mock_fn})
        mock_fn.assert_called_once_with(a=1, b="x")
        assert result == {"ok": True}


def _make_text_response(text: str):
    """Mock OpenAI response with a text reply and no tool calls."""
    msg = MagicMock()
    msg.content = text
    msg.tool_calls = None

    choice = MagicMock()
    choice.message = msg

    resp = MagicMock()
    resp.choices = [choice]
    return resp


def _make_tool_response(tool_name: str, tool_args: dict, call_id: str = "call-1"):
    """Mock OpenAI response with a single tool call."""
    tc = MagicMock()
    tc.id = call_id
    tc.function.name = tool_name
    tc.function.arguments = json.dumps(tool_args)

    msg = MagicMock()
    msg.content = None
    msg.tool_calls = [tc]

    choice = MagicMock()
    choice.message = msg

    resp = MagicMock()
    resp.choices = [choice]
    return resp


class TestRunAgentTurn:
    def _make_mock_client(self):
        mock_client = MagicMock()
        return mock_client

    def test_returns_text_when_no_tool_calls(self):
        agent = _reload_agent()
        mock_client = self._make_mock_client()
        mock_client.chat.completions.create.return_value = _make_text_response("Hello!")

        with patch.object(agent, "OpenAI", return_value=mock_client):
            text, new_history = agent.run_agent_turn("Hi", [])

        assert text == "Hello!"
        assert len(new_history) == 2  # user message + assistant response

    def test_write_tool_override_is_called(self):
        agent = _reload_agent()
        mock_client = self._make_mock_client()
        mock_client.chat.completions.create.side_effect = [
            _make_tool_response("create_database_item", {"database_id": "db-1", "properties": {"Name": "Test"}}),
            _make_text_response("Done! Added 'Test'."),
        ]

        mock_write = MagicMock(return_value={"id": "demo-1"})
        with patch.object(agent, "OpenAI", return_value=mock_client):
            text, _ = agent.run_agent_turn(
                "Add Test to my database",
                [],
                write_tools={"create_database_item": mock_write},
            )

        mock_write.assert_called_once_with(database_id="db-1", properties={"Name": "Test"})
        assert "Done" in text

    def test_empty_history_does_not_crash(self):
        agent = _reload_agent()
        mock_client = self._make_mock_client()
        mock_client.chat.completions.create.return_value = _make_text_response("Ready.")

        with patch.object(agent, "OpenAI", return_value=mock_client):
            text, new_history = agent.run_agent_turn("Hello", [])

        assert isinstance(text, str)
        assert isinstance(new_history, list)

    def test_falls_back_to_secondary_model_on_error(self):
        agent = _reload_agent()
        mock_client = self._make_mock_client()
        mock_client.chat.completions.create.side_effect = [
            Exception("quota exceeded"),
            _make_text_response("Fallback response."),
        ]

        with patch.object(agent, "OpenAI", return_value=mock_client):
            text, _ = agent.run_agent_turn("Hi", [])

        assert text == "Fallback response."
        assert mock_client.chat.completions.create.call_count == 2

    def test_fallback_strips_tool_messages_and_truncates(self):
        agent = _reload_agent()
        mock_client = self._make_mock_client()
        mock_client.chat.completions.create.side_effect = [
            Exception("quota exceeded"),
            _make_text_response("Fallback response."),
        ]

        # History with tool-call noise and 6 plain text turns
        long_history = [
            {"role": "user", "content": "What projects?"},
            {"role": "assistant", "content": "", "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "query_database", "arguments": "{}"}}]},
            {"role": "tool", "tool_call_id": "c1", "content": '{"results": [{"huge": "json payload"}]}'},
            {"role": "assistant", "content": "Swapnil has 4 projects."},
            {"role": "user", "content": "Elaborate on Notion Clerk"},
            {"role": "assistant", "content": "", "tool_calls": [{"id": "c2", "type": "function", "function": {"name": "query_database", "arguments": "{}"}}]},
            {"role": "tool", "tool_call_id": "c2", "content": '{"results": [{"more": "big json"}]}'},
            {"role": "assistant", "content": "Notion Clerk is a chat agent."},
        ]
        with patch.object(agent, "OpenAI", return_value=mock_client):
            text, _ = agent.run_agent_turn("Tell me more", long_history)

        assert text == "Fallback response."
        fallback_messages = mock_client.chat.completions.create.call_args_list[1][1]["messages"]
        # Only plain text turns survive: "What projects?" + "4 projects" + "Elaborate" + "Notion Clerk is..."
        # = 4 text turns + system(1) + current user(1) + assistant reply(1) = 7
        assert len(fallback_messages) == 7
        roles = [m["role"] for m in fallback_messages]
        assert "tool" not in roles
        # No assistant messages with tool_calls
        assert all(not m.get("tool_calls") for m in fallback_messages)
