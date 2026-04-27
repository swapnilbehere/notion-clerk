"""Groq-backed agent loop for Notion Clerk (OpenAI-compatible API)."""

import json
import logging
from typing import Any, Callable

from openai import OpenAI

from .config import GROQ_API_KEY, AGENT_MODEL, FALLBACK_MODEL
from . import tools as notion_tools

_GROQ_BASE_URL = "https://api.groq.com/openai/v1"

_SYSTEM_INSTRUCTION = """You are Notion Clerk, an AI assistant embedded in Swapnil Behere's professional portfolio workspace.

This workspace belongs to Swapnil Sushil Behere — an AI/ML Software Engineer (M.S. Computer Science, Santa Clara University).
It contains his professional profile across 5 databases:
- Work Experience: his job history (SCU Frugal Innovation Hub, Riskpro Management Consulting)
- Projects: his portfolio projects (Notion Clerk, RAG System for Chromatography, TalkaWalk, Posture Estimation for Yoga Asanas)
- Skills: his technical skills organized by category and level
- Education: his academic background
- Feedback: where visitors leave messages

When visitors ask about Swapnil, his background, skills, projects, or experience — query the relevant database and answer from the data. Treat this like a living, queryable CV.

CRITICAL TOOL RULES:
1. ALWAYS call get_notion_ids FIRST before any database operation. Never assume a database_id.
2. database_id must be the UUID returned by get_notion_ids (e.g. "34f7b163-d75a-8085-8c9b-c8eec22d5701"). NEVER use a human-readable name like "Projects" as a database_id.
3. get_notion_ids takes NO arguments — call it as an empty call.

You have tools to:
- List available databases and get their UUIDs (call get_notion_ids first — always)
- Get field names and types for a database (get_database_schema)
- Create items in databases with correctly typed properties
- Create freeform pages
- Search across the workspace
- Query and read database contents
- Fetch page details
- Update existing database items

Guidelines:
- Be concise and confident in responses
- When answering questions about Swapnil, call get_notion_ids then query_database — don't guess
- When creating items, confirm what was created and in which database
- Never expose database IDs in responses — use human-readable names
- If the user's intent is ambiguous, ask one clarifying question
"""

_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_notion_ids",
            "description": "List all Notion databases the integration can access. Call this first to discover available databases before writing.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_database_schema",
            "description": "Get the field names and their types for a Notion database. Call this when the user asks what fields or properties a database has.",
            "parameters": {
                "type": "object",
                "properties": {
                    "database_id": {"type": "string", "description": "The Notion database ID."},
                },
                "required": ["database_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_database_item",
            "description": "Create a new item (row) in a Notion database with correctly typed properties.",
            "parameters": {
                "type": "object",
                "properties": {
                    "database_id": {"type": "string", "description": "The Notion database ID."},
                    "properties": {
                        "type": "object",
                        "description": 'Flat dict of property name to value. E.g. {"Name": "Buy milk", "Due Date": "tomorrow", "Done": false}',
                    },
                },
                "required": ["database_id", "properties"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_page_anywhere",
            "description": "Create a new freeform Notion page (not in a database) under any parent page.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Page title."},
                    "parent_page_id": {"type": "string", "description": "Parent page ID. Omit to use the default."},
                    "content": {"type": "string", "description": "Optional body text for the page."},
                },
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_notion",
            "description": "Search across all pages and databases in the Notion workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query text."},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_database",
            "description": "Fetch all items in a Notion database. Use to read or audit database contents.",
            "parameters": {
                "type": "object",
                "properties": {
                    "database_id": {"type": "string", "description": "The database ID to query."},
                },
                "required": ["database_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_page",
            "description": "Fetch the full content and properties of a specific Notion page.",
            "parameters": {
                "type": "object",
                "properties": {
                    "page_id": {"type": "string", "description": "The page ID to fetch."},
                },
                "required": ["page_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_database_item",
            "description": "Update properties of an existing Notion database item.",
            "parameters": {
                "type": "object",
                "properties": {
                    "page_id": {"type": "string", "description": "The page ID of the item to update."},
                    "properties": {
                        "type": "object",
                        "description": 'Flat dict of property name to new value. E.g. {"Done": true, "Priority": "High"}',
                    },
                },
                "required": ["page_id", "properties"],
            },
        },
    },
]

# Read-only tools always use real Notion
_READ_REGISTRY: dict[str, Callable] = {
    "get_notion_ids": notion_tools.get_notion_ids,
    "get_database_schema": notion_tools.get_database_schema,
    "search_notion": notion_tools.search_notion,
    "query_database": notion_tools.query_database,
    "fetch_page": notion_tools.fetch_page,
}

# Write tools can be overridden (demo mode intercepts them)
_DEFAULT_WRITE_REGISTRY: dict[str, Callable] = {
    "create_database_item": notion_tools.create_database_item,
    "create_page_anywhere": notion_tools.create_page_anywhere,
    "update_database_item": notion_tools.update_database_item,
}


def _resolve_database_id(db_ref: str) -> str:
    """If db_ref looks like a name rather than a UUID, resolve it via get_notion_ids."""
    # UUID format: 32 hex chars possibly with hyphens
    cleaned = db_ref.replace("-", "")
    if len(cleaned) == 32 and all(c in "0123456789abcdefABCDEF" for c in cleaned):
        return db_ref
    # Treat as a human-readable name — look it up
    try:
        dbs = notion_tools.get_notion_ids().get("databases", [])
        for db in dbs:
            if db["title"].lower() == db_ref.lower():
                return db["id"]
    except Exception:
        pass
    return db_ref  # return as-is; Notion API will give a clear 404


def _dispatch(name: str, args: dict[str, Any], registry: dict[str, Callable]) -> Any:
    fn = registry.get(name)
    if fn is None:
        return {"error": f"Unknown tool: {name}"}
    safe_args = args or {}
    # Auto-resolve database names to UUIDs so Llama's name-based calls still work
    if "database_id" in safe_args:
        safe_args = {**safe_args, "database_id": _resolve_database_id(safe_args["database_id"])}
    try:
        return fn(**safe_args)
    except Exception as exc:
        logging.error("Tool %s failed: %s", name, exc)
        return {"error": str(exc)}


def _run_with_model(
    model: str,
    user_message: str,
    history: list,
    registry: dict[str, Callable],
) -> tuple[str, list]:
    client = OpenAI(api_key=GROQ_API_KEY, base_url=_GROQ_BASE_URL)

    messages = [{"role": "system", "content": _SYSTEM_INSTRUCTION}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    new_entries: list = [{"role": "user", "content": user_message}]

    while True:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=_TOOLS,
            tool_choice="auto",
            temperature=0.1,
        )

        msg = response.choices[0].message

        msg_dict: dict[str, Any] = {"role": "assistant", "content": msg.content or ""}
        if msg.tool_calls:
            msg_dict["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in msg.tool_calls
            ]
        messages.append(msg_dict)
        new_entries.append(msg_dict)

        if not msg.tool_calls:
            break

        for tc in msg.tool_calls:
            raw = tc.function.arguments or "{}"
            args = json.loads(raw) or {}
            result = _dispatch(tc.function.name, args, registry)
            tool_msg = {
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(result),
            }
            messages.append(tool_msg)
            new_entries.append(tool_msg)

    return msg.content or "", new_entries


def run_agent_turn(
    user_message: str,
    gemini_history: list,
    write_tools: dict[str, Callable] | None = None,
) -> tuple[str, list]:
    """
    Run one conversational turn through the Groq function-calling loop.
    Falls back to FALLBACK_MODEL if the primary model raises an error.

    Returns:
        (response_text, new_history_entries)
    """
    registry = {**_READ_REGISTRY, **_DEFAULT_WRITE_REGISTRY}
    if write_tools:
        registry.update(write_tools)

    try:
        return _run_with_model(AGENT_MODEL, user_message, gemini_history, registry)
    except Exception as exc:
        logging.warning(
            "Primary model %s failed (%s), retrying with fallback %s",
            AGENT_MODEL, exc, FALLBACK_MODEL,
        )
        return _run_with_model(FALLBACK_MODEL, user_message, gemini_history, registry)
