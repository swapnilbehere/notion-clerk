"""Notion REST API helpers and MCP toolset factory."""

import logging
from datetime import datetime, date, timedelta
from typing import Any, Dict, Optional

import requests
from dateutil import parser as dateparser
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters
from google.adk.tools.tool_context import ToolContext

from .config import NOTION_API_KEY, NOTION_BASE_URL, NOTION_VERSION, NOTION_PARENT_PAGE


def _notion_headers() -> dict:
    """Build Notion REST API headers."""
    return {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def get_notion_ids() -> dict:
    """
    List all Notion databases this integration can see.

    Return shape:
    {
      "databases": [
        {"id": "...", "title": "...", "url": "..."},
        ...
      ]
    }
    """
    logging.info("get_notion_ids called")
    headers = _notion_headers()
    url = f"{NOTION_BASE_URL}/search"
    start_cursor = None
    databases = []

    while True:
        payload: Dict[str, Any] = {
            "page_size": 100,
            "filter": {"property": "object", "value": "database"},
        }
        if start_cursor:
            payload["start_cursor"] = start_cursor

        resp = requests.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()

        for db in data.get("results", []):
            if db.get("object") != "database":
                continue
            title_rich = db.get("title", []) or []
            title = "".join(rt.get("plain_text", "") for rt in title_rich) or "Untitled database"
            databases.append(
                {"id": db["id"], "title": title, "url": db.get("url")}
            )

        if not data.get("has_more"):
            break
        start_cursor = data.get("next_cursor")

    logging.info("get_notion_ids returning %d databases", len(databases))
    return {"databases": databases}


def _get_database_schema(database_id: str) -> dict:
    """Fetch a Notion database's schema (properties and their types)."""
    headers = _notion_headers()
    url = f"{NOTION_BASE_URL}/databases/{database_id}"
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    data = resp.json()
    return {
        "id": data.get("id"),
        "title": "".join(
            t.get("plain_text", "") for t in (data.get("title", []) or [])
        ),
        "properties": data.get("properties", {}),
    }


def _coerce_property_value(prop_schema: dict, value: Any) -> dict:
    """Coerce a simple Python value into the correct Notion property object."""
    ptype = prop_schema.get("type")

    def _as_str(v: Any) -> str:
        return v if isinstance(v, str) else str(v)

    if ptype == "title":
        return {"title": [{"text": {"content": _as_str(value)}}]}

    if ptype in ("rich_text", "text"):
        return {"rich_text": [{"text": {"content": _as_str(value)}}]}

    if ptype == "date":
        if isinstance(value, (datetime, date)):
            dt = value
        elif isinstance(value, str):
            text = value.strip().lower()
            if text in {"today", "now"}:
                dt = datetime.now()
            elif text == "tomorrow":
                dt = datetime.now() + timedelta(days=1)
            elif text == "yesterday":
                dt = datetime.now() - timedelta(days=1)
            else:
                try:
                    dt = dateparser.parse(value, fuzzy=True)
                except Exception:
                    dt = datetime.now()
        else:
            dt = datetime.now()
        date_str = dt.date().isoformat() if hasattr(dt, "date") else dt.isoformat()
        return {"date": {"start": date_str}}

    if ptype == "checkbox":
        if isinstance(value, bool):
            checked = value
        else:
            vlower = _as_str(value).strip().lower()
            checked = vlower in {"true", "yes", "y", "1", "checked", "done"}
        return {"checkbox": checked}

    if ptype == "select":
        return {"select": {"name": _as_str(value)}}

    if ptype == "multi_select":
        if isinstance(value, (list, tuple, set)):
            names = [_as_str(v) for v in value]
        else:
            names = [_as_str(value)]
        return {"multi_select": [{"name": n} for n in names]}

    if ptype == "number":
        try:
            num = float(value)
        except Exception:
            num = None
        return {"number": num}

    if ptype == "url":
        return {"url": _as_str(value)}

    # Fallback: treat as rich_text
    return {"rich_text": [{"text": {"content": _as_str(value)}}]}


def create_database_item(database_id: str, properties: Dict[str, Any]) -> dict:
    """
    Create a new page in ANY Notion database.

    Args:
      database_id: Notion database id.
      properties: simple dict like {"Name": "Daily Habit", "Date": "2025-11-20", "Done": True}

    Fetches the DB schema, coerces values into correct Notion property objects, and POSTs.
    """
    logging.info("create_database_item: db=%s, properties=%s", database_id, properties)

    schema = _get_database_schema(database_id)
    schema_props: dict = schema.get("properties", {})
    final_props: Dict[str, Any] = {}

    for prop_name, simple_value in properties.items():
        schema_entry = schema_props.get(prop_name)
        if not schema_entry:
            logging.warning("Property '%s' not in schema; using rich_text fallback.", prop_name)
            final_props[prop_name] = {
                "rich_text": [{"text": {"content": str(simple_value)}}]
            }
            continue
        final_props[prop_name] = _coerce_property_value(schema_entry, simple_value)

    # Ensure at least one title property is set
    if not any(
        pschema.get("type") == "title" and pname in final_props
        for pname, pschema in schema_props.items()
    ):
        for pname, pschema in schema_props.items():
            if pschema.get("type") == "title":
                final_props.setdefault(
                    pname,
                    {"title": [{"text": {"content": "New item"}}]},
                )
                break

    body = {"parent": {"database_id": database_id}, "properties": final_props}
    headers = _notion_headers()
    url = f"{NOTION_BASE_URL}/pages"
    resp = requests.post(url, headers=headers, json=body)
    resp.raise_for_status()

    data = resp.json()
    logging.info("create_database_item: created page %s", data.get("id"))
    return data


def create_page_anywhere(
    title: str,
    parent_page_id: Optional[str] = None,
    content: str = "",
) -> dict:
    """
    Create a new page under ANY existing Notion page (not in a database).

    If parent_page_id is None, the default NOTION_PARENT_PAGE is used.
    """
    if parent_page_id is None:
        parent_page_id = NOTION_PARENT_PAGE

    logging.info(
        "create_page_anywhere: parent_page_id=%s, title=%s, has_content=%s",
        parent_page_id, title, bool(content),
    )
    headers = _notion_headers()
    url = f"{NOTION_BASE_URL}/pages"

    properties = {
        "title": {"title": [{"text": {"content": title}}]}
    }

    body: Dict[str, Any] = {
        "parent": {"page_id": parent_page_id},
        "properties": properties,
    }

    if content:
        body["children"] = [
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [
                        {"type": "text", "text": {"content": content}}
                    ]
                },
            }
        ]

    resp = requests.post(url, headers=headers, json=body)
    resp.raise_for_status()

    data = resp.json()
    logging.info("create_page_anywhere: created page %s", data.get("id"))
    return data


def exit_notion_loop(tool_context: ToolContext):
    """Signal the LoopAgent that Notion verification passed."""
    print(f"[Tool Call] exit_notion_loop triggered by {tool_context.agent_name}")
    tool_context.actions.escalate = True
    return {"status": "ok"}


def create_notion_mcp_toolset(notion_api_key: str) -> McpToolset:
    """Create the Notion MCP toolset via @notionhq/notion-mcp-server."""
    tools = [
        "notion-search",
        "notion-fetch",
        "notion-create-pages",
        "notion-update-page",
        "notion-move-pages",
    ]
    return McpToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(
                command="npx",
                args=["-y", "@notionhq/notion-mcp-server"],
                tool_filter=tools,
                env={"NOTION_TOKEN": notion_api_key},
            ),
            timeout=30,
        )
    )
