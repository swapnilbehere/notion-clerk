"""Notion REST API helpers."""

import logging
from datetime import datetime, date, timedelta
from typing import Any, Dict, Optional

import requests
from dateutil import parser as dateparser

from .config import NOTION_API_KEY, NOTION_BASE_URL, NOTION_VERSION, NOTION_PARENT_PAGE


def _notion_headers() -> dict:
    return {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def get_notion_ids() -> dict:
    """List all Notion databases this integration can see."""
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
            databases.append({"id": db["id"], "title": title, "url": db.get("url")})

        if not data.get("has_more"):
            break
        start_cursor = data.get("next_cursor")

    return {"databases": databases}


def _get_database_schema(database_id: str) -> dict:
    """Fetch a Notion database's schema (properties and their types)."""
    headers = _notion_headers()
    resp = requests.get(f"{NOTION_BASE_URL}/databases/{database_id}", headers=headers)
    resp.raise_for_status()
    data = resp.json()
    return {
        "id": data.get("id"),
        "title": "".join(t.get("plain_text", "") for t in (data.get("title", []) or [])),
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
            checked = _as_str(value).strip().lower() in {"true", "yes", "y", "1", "checked", "done"}
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

    return {"rich_text": [{"text": {"content": _as_str(value)}}]}


def get_database_schema(database_id: str) -> dict:
    """Return the property names and types for a Notion database."""
    schema = _get_database_schema(database_id)
    properties = {name: prop.get("type") for name, prop in schema.get("properties", {}).items()}
    return {"title": schema.get("title"), "properties": properties}


def create_database_item(database_id: str, properties: Dict[str, Any]) -> dict:
    """Create a new page in a Notion database."""
    logging.info("create_database_item: db=%s, properties=%s", database_id, properties)

    schema = _get_database_schema(database_id)
    schema_props: dict = schema.get("properties", {})
    final_props: Dict[str, Any] = {}

    for prop_name, simple_value in properties.items():
        schema_entry = schema_props.get(prop_name)
        if not schema_entry:
            final_props[prop_name] = {"rich_text": [{"text": {"content": str(simple_value)}}]}
            continue
        final_props[prop_name] = _coerce_property_value(schema_entry, simple_value)

    if not any(
        pschema.get("type") == "title" and pname in final_props
        for pname, pschema in schema_props.items()
    ):
        for pname, pschema in schema_props.items():
            if pschema.get("type") == "title":
                final_props.setdefault(pname, {"title": [{"text": {"content": "New item"}}]})
                break

    body = {"parent": {"database_id": database_id}, "properties": final_props}
    resp = requests.post(f"{NOTION_BASE_URL}/pages", headers=_notion_headers(), json=body)
    resp.raise_for_status()
    return resp.json()


def create_page_anywhere(
    title: str,
    parent_page_id: Optional[str] = None,
    content: str = "",
) -> dict:
    """Create a new page under any Notion page."""
    if parent_page_id is None:
        parent_page_id = NOTION_PARENT_PAGE

    body: Dict[str, Any] = {
        "parent": {"page_id": parent_page_id},
        "properties": {"title": {"title": [{"text": {"content": title}}]}},
    }
    if content:
        body["children"] = [
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {"rich_text": [{"type": "text", "text": {"content": content}}]},
            }
        ]

    resp = requests.post(f"{NOTION_BASE_URL}/pages", headers=_notion_headers(), json=body)
    resp.raise_for_status()
    return resp.json()


def search_notion(query: str) -> dict:
    """Search across all Notion pages and databases."""
    resp = requests.post(
        f"{NOTION_BASE_URL}/search",
        headers=_notion_headers(),
        json={"query": query, "page_size": 10},
    )
    resp.raise_for_status()
    return resp.json()


def query_database(database_id: str) -> dict:
    """Query all items in a Notion database (up to 50 rows)."""
    resp = requests.post(
        f"{NOTION_BASE_URL}/databases/{database_id}/query",
        headers=_notion_headers(),
        json={"page_size": 50},
    )
    resp.raise_for_status()
    return resp.json()


def fetch_page(page_id: str) -> dict:
    """Fetch a Notion page's properties and its top-level content blocks."""
    headers = _notion_headers()
    page_resp = requests.get(f"{NOTION_BASE_URL}/pages/{page_id}", headers=headers)
    page_resp.raise_for_status()
    blocks_resp = requests.get(f"{NOTION_BASE_URL}/blocks/{page_id}/children", headers=headers)
    blocks_resp.raise_for_status()
    return {"page": page_resp.json(), "blocks": blocks_resp.json()}


def update_database_item(page_id: str, properties: dict) -> dict:
    """Update properties of an existing Notion database item."""
    headers = _notion_headers()
    page_data = requests.get(f"{NOTION_BASE_URL}/pages/{page_id}", headers=headers)
    page_data.raise_for_status()
    database_id = page_data.json()["parent"]["database_id"]

    schema = _get_database_schema(database_id)
    schema_props = schema.get("properties", {})
    final_props: dict = {}

    for prop_name, simple_value in properties.items():
        schema_entry = schema_props.get(prop_name)
        if not schema_entry:
            final_props[prop_name] = {"rich_text": [{"text": {"content": str(simple_value)}}]}
            continue
        final_props[prop_name] = _coerce_property_value(schema_entry, simple_value)

    resp = requests.patch(
        f"{NOTION_BASE_URL}/pages/{page_id}",
        headers=headers,
        json={"properties": final_props},
    )
    resp.raise_for_status()
    return resp.json()


def submit_feedback(name: str, message: str) -> dict:
    """Write a feedback entry to the dedicated Notion feedback database."""
    from .config import NOTION_FEEDBACK_DB_ID

    if not NOTION_FEEDBACK_DB_ID:
        return {"error": "NOTION_FEEDBACK_DB_ID not configured"}

    return create_database_item(
        NOTION_FEEDBACK_DB_ID,
        {
            "Name": (name or "Anonymous").strip()[:50],
            "Message": message.strip()[:280],
            "Date": datetime.now().isoformat(),
        },
    )


def get_recent_feedback(limit: int = 10) -> list[dict]:
    """Fetch the most recent feedback entries."""
    from .config import NOTION_FEEDBACK_DB_ID

    if not NOTION_FEEDBACK_DB_ID:
        return []

    resp = requests.post(
        f"{NOTION_BASE_URL}/databases/{NOTION_FEEDBACK_DB_ID}/query",
        headers=_notion_headers(),
        json={
            "page_size": limit,
            "sorts": [{"timestamp": "created_time", "direction": "descending"}],
        },
    )
    resp.raise_for_status()

    feedback = []
    for page in resp.json().get("results", []):
        props = page.get("properties", {})
        name = ""
        message = ""
        for pvalue in props.values():
            if pvalue.get("type") == "title":
                name = "".join(t.get("plain_text", "") for t in pvalue.get("title", []))
            elif pvalue.get("type") == "rich_text":
                message = "".join(t.get("plain_text", "") for t in pvalue.get("rich_text", []))
        if message:
            feedback.append({"name": name or "Anonymous", "message": message})
    return feedback
