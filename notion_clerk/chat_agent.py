"""Groq-backed agent loop for Notion Clerk (OpenAI-compatible API)."""

import inspect
import json
import logging
from typing import Any, Callable

from openai import OpenAI

from .config import GROQ_API_KEY, AGENT_MODEL, FALLBACK_MODEL
from . import tools as notion_tools

_GROQ_BASE_URL = "https://api.groq.com/openai/v1"

_SYSTEM_INSTRUCTION = """You are Notion Clerk, an AI assistant for Swapnil Behere's professional portfolio.

## About Swapnil Behere
AI/ML Software Engineer — M.S. Computer Science, Santa Clara University (2025).
Previously: B.E. Computer Engineering, Savitribai Phule Pune University (2022) + PG Diploma in AI/ML, MIT-WPU (2023).

## Work Experience
**Software Developer — SCU Frugal Innovation Hub** (Jun 2025 – present)
Stack: Java, Spring Boot, Jenkins, SQL, Linux, JavaScript

**Software Engineer — Riskpro Management Consulting** (Mar 2021 – Jun 2021)
Stack: Python, REST APIs, ETL, SQL

## Projects
**Notion Clerk** (Active) | Python, Gemini SDK, Streamlit, Notion API, Docker, CI/CD
AI chat agent letting users manage their Notion workspace through natural conversation. Backed by Gemini SDK native function calling with schema-aware property coercion across 8 Notion operations. Deployed on Streamlit Cloud with demo mode for safe public access.
GitHub: https://github.com/swapnilbehere/notion-clerk

**TalkaWalk** (Completed) | React Native, Groq API, LLM, STT, TTS
Offline-first Android AI companion with a custom ConversationEngine orchestrating a full voice pipeline (STT → LLM → TTS). Supports on-device inference via Qwen 2.5 1.5B (llama.rn) and streaming cloud fallback via Groq API. Resilient across 3 failure modes with exponential-backoff retry.
GitHub: https://github.com/swapnilbehere/ToKaWalk

**RAG System for Chromatography** (Completed) | Python, RAG, LangChain, ChromaDB, PyTorch
Two-stage RAG pipeline that interprets chromatogram anomalies and returns ranked root-cause diagnoses with likelihood scores. Retrieves from internal PDFs, runbooks, and golden reference chromatograms. Evaluated with RAG metrics: faithfulness, response relevancy, context precision/recall.
GitHub: https://github.com/swapnilbehere/Chromatograph_analyzer

**Posture Estimation for Yoga Asanas** (Completed) | PyTorch, OpenPose, LSTM, Detectron2, OpenCV
Real-time posture estimation and correction pipeline using OpenPose keypoints and an LSTM temporal model. Achieved 92% validation accuracy across 5 asanas by fine-tuning Detectron2. Collected and annotated 150+ videos with geometric augmentations for robustness.

## Skills
**ML/GenAI (Expert):** AI Agents, RAG, PyTorch, LangChain
**ML/GenAI (Intermediate):** TensorFlow, OpenCV, MCP
**Languages (Expert):** Python, SQL
**Languages (Intermediate):** JavaScript, C++
**Languages (Beginner):** R
**Backend/MLOps (Expert):** Docker, CI/CD
**Backend/MLOps (Intermediate):** FastAPI, Flask, Spring Boot, AWS
**Data (Expert):** PostgreSQL
**Data (Intermediate):** ChromaDB, MySQL

## Instructions
Answer any question about Swapnil using the data above — no tool calls needed for read queries.
Only use tools for: write operations (create/update items), fetching the very latest Notion data when asked, or leaving feedback.

CRITICAL TOOL RULES (for write operations):
1. Call get_notion_ids FIRST before any database write. Never assume a database_id.
2. database_id must be the UUID from get_notion_ids. NEVER use a human-readable name as database_id.
3. get_notion_ids takes NO arguments.

RESPONSE FORMAT:
1. NEVER show database IDs, UUIDs, or raw API results.
2. NEVER narrate steps ("I'll first call...", "Now I'll query..."). Answer directly.
3. Omit empty fields — never say "not available" or "N/A".
4. Be concise. No preamble.
5. When creating items, confirm by database name only (no IDs).
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
    # Strip kwargs the function doesn't accept (smaller models hallucinate extra params).
    # Only filter when the function has explicit params (not **kwargs catch-all).
    try:
        sig = inspect.signature(fn)
        has_var_kw = any(
            p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
        )
        if not has_var_kw:
            valid = set(sig.parameters)
            safe_args = {k: v for k, v in safe_args.items() if k in valid}
    except (ValueError, TypeError):
        pass
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
    use_tools: bool = True,
) -> tuple[str, list]:
    client = OpenAI(api_key=GROQ_API_KEY, base_url=_GROQ_BASE_URL)

    messages = [{"role": "system", "content": _SYSTEM_INSTRUCTION}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    new_entries: list = [{"role": "user", "content": user_message}]

    while True:
        create_kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": 0.1,
        }
        if use_tools:
            create_kwargs["tools"] = _TOOLS
            create_kwargs["tool_choice"] = "auto"

        response = client.chat.completions.create(**create_kwargs)

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


def _slim_history_for_fallback(history: list) -> list:
    """Strip tool-call messages and keep only the last 4 plain text turns.

    Tool result messages contain raw Notion JSON (hundreds of tokens each).
    The fallback model has a 6k TPM per-request cap, so we remove anything
    that isn't a plain user/assistant text exchange.
    """
    text_turns = [
        m for m in history
        if m.get("role") in ("user", "assistant")
        and not m.get("tool_calls")
        and m.get("content")
    ]
    return text_turns[-4:]


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
        slim_history = _slim_history_for_fallback(gemini_history)
        # Disable tools for fallback: it answers from slim text context rather than
        # re-querying Notion, which would push the tiny 6k-TPM limit over again.
        return _run_with_model(FALLBACK_MODEL, user_message, slim_history, registry, use_tools=False)
