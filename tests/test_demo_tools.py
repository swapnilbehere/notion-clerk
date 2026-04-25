"""Tests for the demo-mode write interceptor."""

import pytest
from notion_clerk.demo_tools import make_write_tools, get_write_buffer


class TestMakeWriteToolsDemoMode:
    def setup_method(self):
        self.session = {}

    def test_create_database_item_buffers_entry(self):
        tools = make_write_tools(self.session, demo_mode=True)
        result = tools["create_database_item"]("db-1", {"Name": "My task"})
        assert result["object"] == "page"
        assert result["id"].startswith("demo-")
        buffer = get_write_buffer(self.session)
        assert len(buffer) == 1
        assert buffer[0]["database_id"] == "db-1"
        assert buffer[0]["properties"] == {"Name": "My task"}

    def test_create_page_anywhere_buffers_entry(self):
        tools = make_write_tools(self.session, demo_mode=True)
        result = tools["create_page_anywhere"]("My Page", content="Hello")
        assert result["object"] == "page"
        buffer = get_write_buffer(self.session)
        assert buffer[0]["title"] == "My Page"
        assert buffer[0]["content"] == "Hello"

    def test_update_database_item_buffers_entry(self):
        tools = make_write_tools(self.session, demo_mode=True)
        result = tools["update_database_item"]("page-123", {"Done": True})
        buffer = get_write_buffer(self.session)
        assert buffer[0]["type"] == "update"
        assert buffer[0]["id"] == "page-123"
        assert buffer[0]["properties"] == {"Done": True}

    def test_multiple_writes_accumulate(self):
        tools = make_write_tools(self.session, demo_mode=True)
        tools["create_database_item"]("db-1", {"Name": "A"})
        tools["create_database_item"]("db-1", {"Name": "B"})
        assert len(get_write_buffer(self.session)) == 2

    def test_each_entry_gets_unique_id(self):
        tools = make_write_tools(self.session, demo_mode=True)
        r1 = tools["create_database_item"]("db-1", {"Name": "A"})
        r2 = tools["create_database_item"]("db-1", {"Name": "B"})
        assert r1["id"] != r2["id"]

    def test_nothing_written_to_session_on_empty(self):
        assert get_write_buffer(self.session) == []


class TestMakeWriteToolsProductionMode:
    def test_returns_real_notion_functions(self):
        from notion_clerk import tools as notion_tools
        session = {}
        tools = make_write_tools(session, demo_mode=False)
        assert tools["create_database_item"] is notion_tools.create_database_item
        assert tools["create_page_anywhere"] is notion_tools.create_page_anywhere
        assert tools["update_database_item"] is notion_tools.update_database_item

    def test_no_entries_buffered_in_production_mode(self):
        session = {}
        tools = make_write_tools(session, demo_mode=False)
        assert "write_buffer" not in session
