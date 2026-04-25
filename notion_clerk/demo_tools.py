"""Demo-mode write interceptor for Notion Clerk.

When DEMO_MODE=true, write operations are buffered in Streamlit session_state
instead of reaching the real Notion API. Reads always use real Notion data.
"""

from __future__ import annotations

import uuid
from typing import Callable

from . import tools as notion_tools


def make_write_tools(
    session_state: dict,
    demo_mode: bool,
) -> dict[str, Callable]:
    """
    Return write tool callables.

    In demo mode, create/update calls are stored in session_state["write_buffer"]
    and return a synthetic response. In production mode, they delegate to
    the real tools.py functions.

    Args:
        session_state: Streamlit st.session_state (or any dict for testing).
        demo_mode: If True, intercept writes.

    Returns:
        Dict mapping tool names to callables for create_database_item,
        create_page_anywhere, and update_database_item.
    """
    if not demo_mode:
        return {
            "create_database_item": notion_tools.create_database_item,
            "create_page_anywhere": notion_tools.create_page_anywhere,
            "update_database_item": notion_tools.update_database_item,
        }

    def _create_database_item(database_id: str, properties: dict) -> dict:
        entry_id = f"demo-{uuid.uuid4().hex[:8]}"
        entry = {
            "type": "database_item",
            "id": entry_id,
            "database_id": database_id,
            "properties": properties,
        }
        session_state.setdefault("write_buffer", []).append(entry)
        return {"id": entry_id, "object": "page"}

    def _create_page_anywhere(
        title: str,
        parent_page_id: str | None = None,
        content: str = "",
    ) -> dict:
        entry_id = f"demo-{uuid.uuid4().hex[:8]}"
        entry = {
            "type": "page",
            "id": entry_id,
            "title": title,
            "parent_page_id": parent_page_id,
            "content": content,
        }
        session_state.setdefault("write_buffer", []).append(entry)
        return {"id": entry_id, "object": "page"}

    def _update_database_item(page_id: str, properties: dict) -> dict:
        entry = {
            "type": "update",
            "id": page_id,
            "properties": properties,
        }
        session_state.setdefault("write_buffer", []).append(entry)
        return {"id": page_id, "object": "page"}

    return {
        "create_database_item": _create_database_item,
        "create_page_anywhere": _create_page_anywhere,
        "update_database_item": _update_database_item,
    }


def get_write_buffer(session_state: dict) -> list[dict]:
    """Return all buffered write operations for the current session."""
    return session_state.get("write_buffer", [])
