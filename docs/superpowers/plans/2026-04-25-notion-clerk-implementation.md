# Notion Clerk Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild NotionAgent as Notion Clerk — a publicly accessible Notion AI chat agent backed by Gemini function calling, deployed on Streamlit Cloud.

**Architecture:** `notion_agent/` is renamed to `notion_clerk/`. The ADK/MCP/A2A layer is removed and replaced with a lean `chat_agent.py` using google-genai SDK directly. `tools.py` is preserved and extended with REST search/query/update functions. A `demo_tools.py` interceptor routes writes to `st.session_state` in demo mode. `streamlit_app.py` is the single entry point.

**Tech Stack:** Python 3.10+, google-genai >= 1.0, Streamlit >= 1.35, pytest, ruff, Docker, GitHub Actions

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `notion_agent/` → `notion_clerk/` | Rename dir | Python package |
| `notion_clerk/config.py` | Modify | Secrets, constants — remove ADK/A2A entries, add `DEMO_MODE`, `NOTION_FEEDBACK_DB_ID` |
| `notion_clerk/tools.py` | Modify | Remove ADK imports/functions, add `search_notion`, `query_database`, `fetch_page`, `update_database_item`, `submit_feedback`, `get_recent_feedback` |
| `notion_clerk/chat_agent.py` | Create | Gemini SDK function-calling loop, tool dispatch, system prompt |
| `notion_clerk/demo_tools.py` | Create | Write interceptor that buffers to `st.session_state` when `DEMO_MODE=true` |
| `notion_clerk/__init__.py` | Modify | Export `run_agent_turn` |
| `streamlit_app.py` | Create | Chat UI, session state, sidebar, feedback form |
| `.streamlit/config.toml` | Create | Theme and page config |
| `tests/conftest.py` | Modify | Update module paths, remove ADK fixture |
| `tests/test_tools.py` | Modify | Update imports `notion_agent` → `notion_clerk`, add tests for new functions |
| `tests/test_agents.py` | Delete + replace | ADK tests removed; replaced by `tests/test_chat_agent.py` |
| `tests/test_chat_agent.py` | Create | Tests for `run_agent_turn`, tool dispatch, tool registry |
| `tests/test_demo_tools.py` | Create | Tests for write interceptor and buffer merge |
| `pyproject.toml` | Modify | Rename project, swap deps (remove ADK/LiteLLM, add streamlit) |
| `.env.example` | Modify | Add `DEMO_MODE`, `NOTION_FEEDBACK_DB_ID`, remove ADK entries |
| `LICENSE` | Create | MIT license |
| `README.md` | Rewrite | Notion Clerk branding, setup, demo link |
| `Dockerfile` | Create | Pure Python, no Node.js |
| `docker-compose.yml` | Create | Single service |
| `.dockerignore` | Create | Exclude .env, __pycache__, .venv |
| `.github/workflows/ci.yml` | Create | ruff + pytest on push |

---

## Task 1: Rename Package and Update pyproject.toml

**Files:**
- Rename: `notion_agent/` → `notion_clerk/`
- Modify: `pyproject.toml`

- [ ] **Step 1: Rename the package directory**

```bash
mv notion_agent notion_clerk
```

- [ ] **Step 2: Verify the rename**

```bash
ls notion_clerk/
```
Expected: `__init__.py  agent.py  config.py  prompts.py  tools.py`

- [ ] **Step 3: Update pyproject.toml**

Replace the entire file with:

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "notion-clerk"
version = "0.1.0"
description = "Chat with your Notion workspace in plain English"
readme = "README.md"
requires-python = ">=3.10"
dependencies = [
    "google-genai>=1.0.0",
    "requests>=2.31.0",
    "python-dateutil>=2.9.0",
    "python-dotenv>=1.0.0",
    "streamlit>=1.35.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-mock>=3.14.0",
    "responses>=0.25.0",
    "ruff>=0.5.0",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
markers = [
    "integration: marks tests that require live API keys (deselect with '-m not integration')",
]

[tool.ruff]
line-length = 100
target-version = "py310"
exclude = ["_archive/", "*.ipynb"]
```

- [ ] **Step 4: Reinstall dependencies**

```bash
pip install -e ".[dev]"
```

Expected: Installs without errors. ADK/LiteLLM no longer installed.

- [ ] **Step 5: Commit**

```bash
git add notion_clerk/ pyproject.toml
git rm -r notion_agent/
git commit -m "refactor: rename package notion_agent → notion_clerk, swap deps to google-genai + streamlit"
```

---

## Task 2: Clean Up config.py

**Files:**
- Modify: `notion_clerk/config.py`

- [ ] **Step 1: Rewrite config.py**

Replace the entire file:

```python
"""Configuration — loads secrets from .env or environment."""

import os
from dotenv import load_dotenv

load_dotenv()

# --- Required ---
GOOGLE_API_KEY: str = os.environ["GOOGLE_API_KEY"]
NOTION_API_KEY: str = os.environ["NOTION_API_KEY"]
NOTION_PARENT_PAGE: str = os.environ["NOTION_PARENT_PAGE"]

# Set for libraries that read from os.environ directly
os.environ.setdefault("GOOGLE_API_KEY", GOOGLE_API_KEY)

# --- Notion constants ---
NOTION_VERSION: str = "2022-06-28"
NOTION_BASE_URL: str = "https://api.notion.com/v1"

# --- Model ---
AGENT_MODEL: str = os.getenv("AGENT_MODEL", "gemini-2.5-flash-lite")

# --- Demo mode ---
DEMO_MODE: bool = os.getenv("DEMO_MODE", "false").lower() == "true"

# --- Feedback database (set after creating the Notion feedback DB) ---
NOTION_FEEDBACK_DB_ID: str = os.getenv("NOTION_FEEDBACK_DB_ID", "")
```

- [ ] **Step 2: Verify import works**

```bash
python -c "from notion_clerk.config import GOOGLE_API_KEY, DEMO_MODE; print('ok')"
```

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add notion_clerk/config.py
git commit -m "refactor: clean up config.py — remove ADK/A2A/LiteLLM, add DEMO_MODE and NOTION_FEEDBACK_DB_ID"
```

---

## Task 3: Update tools.py

Remove ADK-specific functions (`exit_notion_loop`, `create_notion_mcp_toolset`) and add four new REST functions needed for the three showcase interactions.

**Files:**
- Modify: `notion_clerk/tools.py`

- [ ] **Step 1: Remove ADK imports and functions**

Open `notion_clerk/tools.py`. Remove these imports:
```python
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters
from google.adk.tools.tool_context import ToolContext
```

Remove the `exit_notion_loop` and `create_notion_mcp_toolset` functions entirely.

- [ ] **Step 2: Add new REST functions at the end of tools.py**

Append to `notion_clerk/tools.py`:

```python
def search_notion(query: str) -> dict:
    """Search across all Notion pages and databases."""
    headers = _notion_headers()
    url = f"{NOTION_BASE_URL}/search"
    resp = requests.post(url, headers=headers, json={"query": query, "page_size": 10})
    resp.raise_for_status()
    return resp.json()


def query_database(database_id: str) -> dict:
    """Query all items in a Notion database (up to 50 rows)."""
    headers = _notion_headers()
    url = f"{NOTION_BASE_URL}/databases/{database_id}/query"
    resp = requests.post(url, headers=headers, json={"page_size": 50})
    resp.raise_for_status()
    return resp.json()


def fetch_page(page_id: str) -> dict:
    """Fetch a Notion page's properties and its top-level content blocks."""
    headers = _notion_headers()
    page_resp = requests.get(f"{NOTION_BASE_URL}/pages/{page_id}", headers=headers)
    page_resp.raise_for_status()
    blocks_resp = requests.get(
        f"{NOTION_BASE_URL}/blocks/{page_id}/children", headers=headers
    )
    blocks_resp.raise_for_status()
    return {"page": page_resp.json(), "blocks": blocks_resp.json()}


def update_database_item(page_id: str, properties: dict) -> dict:
    """
    Update properties of an existing Notion database item.

    Fetches the item's parent database schema to coerce values correctly.
    """
    headers = _notion_headers()
    page_resp = requests.get(f"{NOTION_BASE_URL}/pages/{page_id}", headers=headers)
    page_resp.raise_for_status()
    page_data = page_resp.json()
    database_id = page_data["parent"]["database_id"]

    schema = _get_database_schema(database_id)
    schema_props = schema.get("properties", {})
    final_props: dict = {}

    for prop_name, simple_value in properties.items():
        schema_entry = schema_props.get(prop_name)
        if not schema_entry:
            final_props[prop_name] = {
                "rich_text": [{"text": {"content": str(simple_value)}}]
            }
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
    from datetime import datetime
    from .config import NOTION_FEEDBACK_DB_ID

    if not NOTION_FEEDBACK_DB_ID:
        return {"error": "NOTION_FEEDBACK_DB_ID not configured"}

    return create_database_item(
        NOTION_FEEDBACK_DB_ID,
        {
            "Name": (name or "Anonymous").strip()[:50],
            "Message": message.strip()[:280],
            "Timestamp": datetime.now().isoformat(),
        },
    )


def get_recent_feedback(limit: int = 10) -> list[dict]:
    """Fetch the most recent feedback entries for display in the sidebar."""
    from .config import NOTION_FEEDBACK_DB_ID

    if not NOTION_FEEDBACK_DB_ID:
        return []

    headers = _notion_headers()
    url = f"{NOTION_BASE_URL}/databases/{NOTION_FEEDBACK_DB_ID}/query"
    resp = requests.post(
        url,
        headers=headers,
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
```

- [ ] **Step 3: Verify tools.py imports cleanly**

```bash
python -c "from notion_clerk.tools import search_notion, query_database, fetch_page, update_database_item; print('ok')"
```

Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add notion_clerk/tools.py
git commit -m "refactor: remove ADK functions from tools.py, add search/query/fetch/update/feedback REST helpers"
```

---

## Task 4: Update Test Suite

Replace ADK-specific tests, update all import paths from `notion_agent` to `notion_clerk`.

**Files:**
- Modify: `tests/conftest.py`
- Modify: `tests/test_tools.py`
- Modify: `tests/test_config.py`
- Delete: `tests/test_agents.py`
- Delete: `tests/test_a2a.py`

- [ ] **Step 1: Update conftest.py**

Replace entirely:

```python
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
```

- [ ] **Step 2: Update import paths in test_tools.py**

Replace every occurrence of `notion_agent` with `notion_clerk` in `tests/test_tools.py`:

```bash
sed -i '' 's/notion_agent/notion_clerk/g' tests/test_tools.py
```

- [ ] **Step 3: Update import paths in test_config.py**

```bash
sed -i '' 's/notion_agent/notion_clerk/g' tests/test_config.py
```

- [ ] **Step 4: Remove ADK-specific test files**

```bash
rm tests/test_agents.py tests/test_a2a.py
```

- [ ] **Step 5: Verify existing tests pass**

```bash
pytest -m "not integration" -v
```

Expected: All tests in `test_config.py` and `test_tools.py` pass. No ADK import errors.

- [ ] **Step 6: Commit**

```bash
git add tests/
git commit -m "test: update imports to notion_clerk, remove ADK/A2A test files"
```

---

## Task 5: Add LICENSE and Update .env.example

**Files:**
- Create: `LICENSE`
- Modify: `.env.example`

- [ ] **Step 1: Create LICENSE**

```
MIT License

Copyright (c) 2026 Swapnil Behere

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 2: Rewrite .env.example**

```bash
# Required
GOOGLE_API_KEY=your-google-api-key-here
NOTION_API_KEY=your-notion-integration-token-here
NOTION_PARENT_PAGE=your-notion-parent-page-id-here

# Model (default: gemini-2.5-flash-lite — free Google AI Studio tier)
AGENT_MODEL=gemini-2.5-flash-lite

# Demo mode — set true on Streamlit Cloud to intercept writes to session state
DEMO_MODE=false

# Feedback database — create a Notion DB with Name/Message/Timestamp properties
# then paste its ID here
NOTION_FEEDBACK_DB_ID=your-feedback-database-id-here
```

- [ ] **Step 3: Commit**

```bash
git add LICENSE .env.example
git commit -m "docs: add MIT license, update .env.example for Notion Clerk"
```

---

## Task 6: Write chat_agent.py

**Files:**
- Create: `notion_clerk/chat_agent.py`

- [ ] **Step 1: Create the file**

```python
"""Gemini SDK agent loop for Notion Clerk."""

import logging
from typing import Any, Callable

from google import genai
from google.genai import types

from .config import GOOGLE_API_KEY, AGENT_MODEL
from . import tools as notion_tools

_SYSTEM_INSTRUCTION = """You are Notion Clerk, an AI assistant that helps users manage their Notion workspace through natural conversation.

You have tools to:
- List available databases (always call get_notion_ids first if you don't know which database to use)
- Create items in databases with correctly typed properties
- Create freeform pages
- Search across the workspace
- Query and read database contents
- Fetch page details
- Update existing database items

Guidelines:
- Be concise and confident in responses
- When creating items, confirm what was created and in which database
- For cleanup tasks, query the database first, then update items that need fixing
- Never expose database IDs in responses — use human-readable names
- If the user's intent is ambiguous, ask one clarifying question
"""

_TOOL_DECLARATIONS = types.Tool(
    function_declarations=[
        types.FunctionDeclaration(
            name="get_notion_ids",
            description="List all Notion databases the integration can access. Call this first to discover available databases before writing.",
            parameters=types.Schema(type=types.Type.OBJECT, properties={}),
        ),
        types.FunctionDeclaration(
            name="create_database_item",
            description="Create a new item (row) in a Notion database with correctly typed properties.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "database_id": types.Schema(
                        type=types.Type.STRING,
                        description="The Notion database ID.",
                    ),
                    "properties": types.Schema(
                        type=types.Type.OBJECT,
                        description='Flat dict of property name to value. E.g. {"Name": "Buy milk", "Due Date": "tomorrow", "Done": false}',
                    ),
                },
                required=["database_id", "properties"],
            ),
        ),
        types.FunctionDeclaration(
            name="create_page_anywhere",
            description="Create a new freeform Notion page (not in a database) under any parent page.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "title": types.Schema(type=types.Type.STRING, description="Page title"),
                    "parent_page_id": types.Schema(
                        type=types.Type.STRING,
                        description="Parent page ID. Omit to use the default.",
                    ),
                    "content": types.Schema(
                        type=types.Type.STRING,
                        description="Optional body text for the page.",
                    ),
                },
                required=["title"],
            ),
        ),
        types.FunctionDeclaration(
            name="search_notion",
            description="Search across all pages and databases in the Notion workspace.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "query": types.Schema(
                        type=types.Type.STRING,
                        description="Search query text.",
                    ),
                },
                required=["query"],
            ),
        ),
        types.FunctionDeclaration(
            name="query_database",
            description="Fetch all items in a Notion database. Use to read or audit database contents.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "database_id": types.Schema(
                        type=types.Type.STRING,
                        description="The database ID to query.",
                    ),
                },
                required=["database_id"],
            ),
        ),
        types.FunctionDeclaration(
            name="fetch_page",
            description="Fetch the full content and properties of a specific Notion page.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "page_id": types.Schema(
                        type=types.Type.STRING,
                        description="The page ID to fetch.",
                    ),
                },
                required=["page_id"],
            ),
        ),
        types.FunctionDeclaration(
            name="update_database_item",
            description="Update properties of an existing Notion database item.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "page_id": types.Schema(
                        type=types.Type.STRING,
                        description="The page ID of the item to update.",
                    ),
                    "properties": types.Schema(
                        type=types.Type.OBJECT,
                        description='Flat dict of property name to new value. E.g. {"Done": true, "Priority": "High"}',
                    ),
                },
                required=["page_id", "properties"],
            ),
        ),
    ]
)

# Read-only tools always use real Notion
_READ_REGISTRY: dict[str, Callable] = {
    "get_notion_ids": notion_tools.get_notion_ids,
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


def _dispatch(name: str, args: dict[str, Any], registry: dict[str, Callable]) -> Any:
    fn = registry.get(name)
    if fn is None:
        return {"error": f"Unknown tool: {name}"}
    try:
        return fn(**args)
    except Exception as exc:
        logging.error("Tool %s failed: %s", name, exc)
        return {"error": str(exc)}


def run_agent_turn(
    user_message: str,
    gemini_history: list,
    write_tools: dict[str, Callable] | None = None,
) -> tuple[str, list]:
    """
    Run one conversational turn through the Gemini function-calling loop.

    Args:
        user_message: The user's input text.
        gemini_history: Prior turns as a list of types.Content objects.
        write_tools: Optional overrides for write functions (used in demo mode).

    Returns:
        (response_text, new_history_entries) where new_history_entries are
        the Content objects added this turn (to be appended to gemini_history).
    """
    registry = {**_READ_REGISTRY, **_DEFAULT_WRITE_REGISTRY}
    if write_tools:
        registry.update(write_tools)

    client = genai.Client(api_key=GOOGLE_API_KEY)

    contents = list(gemini_history)
    contents.append(types.Content(role="user", parts=[types.Part(text=user_message)]))

    new_entries: list = []
    new_entries.append(contents[-1])  # the user message

    while True:
        response = client.models.generate_content(
            model=AGENT_MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=_SYSTEM_INSTRUCTION,
                tools=[_TOOL_DECLARATIONS],
                temperature=0.1,
            ),
        )

        candidate = response.candidates[0]
        contents.append(candidate.content)
        new_entries.append(candidate.content)

        fn_calls = [p for p in candidate.content.parts if p.function_call is not None]

        if not fn_calls:
            break

        tool_parts = []
        for part in fn_calls:
            fc = part.function_call
            result = _dispatch(fc.name, dict(fc.args), registry)
            tool_parts.append(
                types.Part(
                    function_response=types.FunctionResponse(
                        name=fc.name,
                        response={"result": result},
                    )
                )
            )

        tool_content = types.Content(role="user", parts=tool_parts)
        contents.append(tool_content)
        new_entries.append(tool_content)

    response_text = "".join(
        p.text for p in candidate.content.parts if p.text is not None
    )
    return response_text, new_entries
```

- [ ] **Step 2: Update `notion_clerk/__init__.py`**

```python
"""Notion Clerk — chat agent package."""

from .chat_agent import run_agent_turn

__all__ = ["run_agent_turn"]
```

- [ ] **Step 3: Verify module imports without errors**

```bash
python -c "from notion_clerk import run_agent_turn; print('ok')"
```

Expected: `ok` (no import errors; no real API calls made at import time)

- [ ] **Step 4: Commit**

```bash
git add notion_clerk/chat_agent.py notion_clerk/__init__.py
git commit -m "feat: add chat_agent.py — Gemini SDK function-calling loop replacing ADK"
```

---

## Task 7: Tests for chat_agent.py

**Files:**
- Create: `tests/test_chat_agent.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_chat_agent.py`:

```python
"""Tests for the Gemini function-calling agent loop."""

import importlib
import pytest
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
        # First response: function call
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

        # Second response: text
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
```

- [ ] **Step 2: Run tests — expect them to fail**

```bash
pytest tests/test_chat_agent.py -v
```

Expected: FAIL — `chat_agent.py` not yet fully wired (or passes if Step 1 in Task 6 is done)

- [ ] **Step 3: Run tests — expect pass after Task 6 is complete**

```bash
pytest tests/test_chat_agent.py -v
```

Expected: All 8 tests PASS

- [ ] **Step 4: Run full test suite**

```bash
pytest -m "not integration" -v
```

Expected: All tests pass.

- [ ] **Step 5: Commit**

```bash
git add tests/test_chat_agent.py
git commit -m "test: add test_chat_agent.py covering dispatch, registry, and run_agent_turn"
```

---

## Task 8: Write demo_tools.py

**Files:**
- Create: `notion_clerk/demo_tools.py`

- [ ] **Step 1: Create the file**

```python
"""Demo-mode write interceptor for Notion Clerk.

When DEMO_MODE=true, write operations are buffered in Streamlit session_state
instead of reaching the real Notion API. Reads always use real Notion data.
"""

from __future__ import annotations

import uuid
from typing import Any, Callable

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
```

- [ ] **Step 2: Verify import**

```bash
python -c "from notion_clerk.demo_tools import make_write_tools; print('ok')"
```

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add notion_clerk/demo_tools.py
git commit -m "feat: add demo_tools.py — session-state write interceptor for demo mode"
```

---

## Task 9: Tests for demo_tools.py

**Files:**
- Create: `tests/test_demo_tools.py`

- [ ] **Step 1: Write the tests**

```python
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
        # Even calling the tools (via the real functions) doesn't touch write_buffer
        assert "write_buffer" not in session
```

- [ ] **Step 2: Run the tests**

```bash
pytest tests/test_demo_tools.py -v
```

Expected: All 8 tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_demo_tools.py
git commit -m "test: add test_demo_tools.py — write interceptor and buffer accumulation"
```

---

## Task 10: Write streamlit_app.py

**Files:**
- Create: `streamlit_app.py`

- [ ] **Step 1: Create the file**

```python
"""Notion Clerk — Streamlit chat interface."""

import html
import streamlit as st

from notion_clerk import run_agent_turn
from notion_clerk.config import DEMO_MODE, NOTION_FEEDBACK_DB_ID
from notion_clerk.demo_tools import make_write_tools
from notion_clerk.tools import submit_feedback, get_recent_feedback

st.set_page_config(
    page_title="Notion Clerk",
    page_icon="🗂",
    layout="centered",
    initial_sidebar_state="expanded",
)


def _init_session() -> None:
    defaults = {
        "messages": [],
        "gemini_history": [],
        "write_buffer": [],
        "feedback_submitted": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _render_sidebar() -> None:
    with st.sidebar:
        st.title("🗂 Notion Clerk")
        st.markdown(
            "Manage your Notion workspace through natural conversation — "
            "no buttons, no database IDs."
        )
        st.markdown("[⭐ View on GitHub](https://github.com/swapnilbehere/NotionAgent)")

        st.divider()

        st.subheader("💬 Leave Feedback")
        if st.session_state.feedback_submitted:
            st.success("Thanks! Your feedback was saved to Notion.")
        elif not NOTION_FEEDBACK_DB_ID:
            st.caption("Feedback not configured yet.")
        else:
            name = st.text_input("Your name (optional)", max_chars=50, key="fb_name")
            message = st.text_area(
                "Message", max_chars=280, placeholder="What did you think?", key="fb_msg"
            )
            if st.button("Submit Feedback"):
                clean_msg = html.escape(message.strip())
                if clean_msg:
                    with st.spinner("Saving..."):
                        submit_feedback(name, clean_msg)
                    st.session_state.feedback_submitted = True
                    st.rerun()
                else:
                    st.warning("Please enter a message.")

        st.divider()

        if NOTION_FEEDBACK_DB_ID:
            st.subheader("🗣 Recent Feedback")
            with st.spinner(""):
                entries = get_recent_feedback(limit=5)
            if entries:
                for entry in entries:
                    st.markdown(f"**{entry['name']}** — {entry['message']}")
            else:
                st.caption("No feedback yet. Be the first!")


def _handle_message(prompt: str) -> None:
    st.session_state.messages.append({"role": "user", "content": prompt})

    write_tools = make_write_tools(
        session_state=st.session_state,
        demo_mode=DEMO_MODE,
    )

    with st.spinner(""):
        response, new_entries = run_agent_turn(
            user_message=prompt,
            gemini_history=st.session_state.gemini_history,
            write_tools=write_tools,
        )

    st.session_state.messages.append({"role": "assistant", "content": response})
    st.session_state.gemini_history.extend(new_entries)


def main() -> None:
    _init_session()
    _render_sidebar()

    st.title("Notion Clerk")
    st.caption("Chat with your Notion workspace in plain English.")

    # Suggested prompts — shown only on first load
    if not st.session_state.messages:
        st.markdown("**Try one of these:**")
        cols = st.columns(3)
        quick_prompts = [
            ("📝 Add a task", "Add a task called 'Review project proposal' with status 'Todo'"),
            ("🔍 Search workspace", "What projects am I currently working on?"),
            ("🧹 Show databases", "List all my Notion databases"),
        ]
        for col, (label, prompt) in zip(cols, quick_prompts):
            with col:
                if st.button(label, use_container_width=True):
                    st.session_state.pending_prompt = prompt
                    st.rerun()

    # Handle a prompt queued by a button click
    if "pending_prompt" in st.session_state:
        queued = st.session_state.pop("pending_prompt")
        _handle_message(queued)

    # Render chat history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Chat input
    if user_input := st.chat_input("Ask me to manage your Notion workspace..."):
        _handle_message(user_input)
        st.rerun()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run locally and verify it starts**

```bash
streamlit run streamlit_app.py
```

Expected: Browser opens, chat UI loads, no Python errors in terminal.

- [ ] **Step 3: Smoke test — quick prompt button**

Click "📝 Add a task" in the browser.
Expected: A message appears in the chat and the agent responds (may fail on API call if `.env` not set — that's ok at this stage).

- [ ] **Step 4: Commit**

```bash
git add streamlit_app.py
git commit -m "feat: add streamlit_app.py — chat UI with session state, suggested prompts, and feedback sidebar"
```

---

## Task 11: Streamlit Config

**Files:**
- Create: `.streamlit/config.toml`

- [ ] **Step 1: Create the directory and file**

```bash
mkdir -p .streamlit
```

Create `.streamlit/config.toml`:

```toml
[theme]
primaryColor = "#000000"
backgroundColor = "#FFFFFF"
secondaryBackgroundColor = "#F5F5F5"
textColor = "#1A1A1A"
font = "sans serif"

[server]
headless = true
enableCORS = false

[browser]
gatherUsageStats = false
```

- [ ] **Step 2: Restart and verify theme applies**

```bash
streamlit run streamlit_app.py
```

Expected: Clean dark-on-white theme, no default Streamlit salmon color.

- [ ] **Step 3: Commit**

```bash
git add .streamlit/config.toml
git commit -m "feat: add .streamlit/config.toml with clean neutral theme"
```

---

## Task 12: Feedback Board — Notion Setup

This task sets up the real Notion feedback database and configures the env var. It requires manual Notion steps.

**Files:**
- Modify: `.env` (local only, gitignored)

- [ ] **Step 1: Create a Notion integration for the demo workspace**

1. Go to https://www.notion.so/my-integrations
2. Click "New integration"
3. Name it "Notion Clerk Demo"
4. Select the demo workspace
5. Copy the API key (starts with `ntn_`)
6. Set `NOTION_API_KEY=ntn_...` in `.env`

- [ ] **Step 2: Create the Feedback database in Notion**

In the demo Notion workspace:
1. Create a new full-page database called "Feedback"
2. Add these properties:
   - `Name` (Title — already exists by default)
   - `Message` (Text)
   - `Timestamp` (Date)
3. Share the database with the "Notion Clerk Demo" integration

- [ ] **Step 3: Get the Feedback database ID**

Open the Feedback database in Notion. Copy the ID from the URL:
`https://www.notion.so/{workspace}/{DATABASE_ID}?v=...`

Set in `.env`:
```
NOTION_FEEDBACK_DB_ID=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

- [ ] **Step 4: Test feedback submission**

```bash
python -c "
from notion_clerk.tools import submit_feedback
result = submit_feedback('Test User', 'This is a test feedback entry')
print(result.get('id', 'ERROR'))
"
```

Expected: A page ID is printed and the entry appears in the Notion Feedback database.

- [ ] **Step 5: Test feedback read**

```bash
python -c "
from notion_clerk.tools import get_recent_feedback
entries = get_recent_feedback()
print(entries)
"
```

Expected: List containing the entry from Step 4.

---

## Task 13: Dockerfile and docker-compose

**Files:**
- Create: `Dockerfile`
- Create: `docker-compose.yml`
- Create: `.dockerignore`

- [ ] **Step 1: Create Dockerfile**

```dockerfile
FROM python:3.12-slim AS base
WORKDIR /app

FROM base AS deps
COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[dev]"

FROM deps AS app
COPY . .
EXPOSE 8501
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1
CMD ["streamlit", "run", "streamlit_app.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

- [ ] **Step 2: Create docker-compose.yml**

```yaml
services:
  notion-clerk:
    build: .
    ports:
      - "8501:8501"
    env_file:
      - .env
    restart: unless-stopped
```

- [ ] **Step 3: Create .dockerignore**

```
.env
.venv/
__pycache__/
*.pyc
*.egg-info/
.pytest_cache/
_archive/
.git/
.github/
*.ipynb
.DS_Store
```

- [ ] **Step 4: Build and verify**

```bash
docker compose build
```

Expected: Build completes without errors.

- [ ] **Step 5: Run locally with Docker**

```bash
docker compose up
```

Expected: App available at http://localhost:8501

- [ ] **Step 6: Commit**

```bash
git add Dockerfile docker-compose.yml .dockerignore
git commit -m "feat: add Dockerfile and docker-compose for local dev and deployment"
```

---

## Task 14: GitHub Actions CI

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Create the workflow file**

```bash
mkdir -p .github/workflows
```

Create `.github/workflows/ci.yml`:

```yaml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: "pip"

      - name: Install dependencies
        run: pip install -e ".[dev]"

      - name: Lint
        run: ruff check .

      - name: Test
        env:
          GOOGLE_API_KEY: test-google-key
          NOTION_API_KEY: test-notion-key
          NOTION_PARENT_PAGE: test-parent-page-id
          NOTION_FEEDBACK_DB_ID: test-feedback-db-id
          DEMO_MODE: "false"
        run: pytest -m "not integration" -v
```

- [ ] **Step 2: Commit**

```bash
git add .github/
git commit -m "ci: add GitHub Actions workflow — ruff lint + pytest on push"
```

---

## Task 15: Commit All Phase 1 Code and Push

- [ ] **Step 1: Stage all untracked project files**

```bash
git add notion_clerk/ tests/ scripts/ README.md CLAUDE.md current_state.md .env.example pyproject.toml
git status --short
```

Expected: All project files staged.

- [ ] **Step 2: Commit**

```bash
git commit -m "feat: add notion_clerk package, tests, and scripts — Phase 1 complete"
```

- [ ] **Step 3: Push to GitHub**

```bash
git push origin master
```

Expected: CI runs on GitHub Actions. Check the Actions tab at `https://github.com/<your-repo>/actions`.

- [ ] **Step 4: Verify CI passes**

Go to GitHub → Actions tab.
Expected: Green checkmark on the CI workflow.

---

## Task 16: Deploy to Streamlit Cloud

- [ ] **Step 1: Make the repo public on GitHub**

Go to repo Settings → Danger Zone → Change visibility → Public.

- [ ] **Step 2: Connect to Streamlit Cloud**

1. Go to https://share.streamlit.io
2. Click "New app"
3. Select the `NotionAgent` repo, `master` branch, `streamlit_app.py` as the main file
4. Click "Advanced settings"

- [ ] **Step 3: Set Streamlit Secrets**

In "Advanced settings" → "Secrets", paste:

```toml
GOOGLE_API_KEY = "your-real-google-api-key"
NOTION_API_KEY = "your-demo-workspace-notion-token"
NOTION_PARENT_PAGE = "your-demo-parent-page-id"
NOTION_FEEDBACK_DB_ID = "your-feedback-database-id"
DEMO_MODE = "true"
AGENT_MODEL = "gemini-2.5-flash-lite"
```

- [ ] **Step 4: Deploy**

Click "Deploy". Wait for build to complete (2-3 minutes).

- [ ] **Step 5: Smoke test the live URL**

Test all three showcase interactions:
1. Click "📝 Add a task" → agent responds and confirms
2. Type "What projects am I working on?" → agent searches and replies
3. Type "List my databases" → agent calls get_notion_ids and lists them
4. Submit feedback in the sidebar → appears in Notion

- [ ] **Step 6: Update README with live demo badge**

Add to the top of README.md:

```markdown
[![Demo](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://your-app.streamlit.app)
```

- [ ] **Step 7: Commit and push**

```bash
git add README.md
git commit -m "docs: add Streamlit Cloud demo badge"
git push origin master
```

---

## Phase 7: Eval Harness (Deferred — implement after Phase 6 is live)

The eval harness is planned but not yet implemented. It will be covered in a separate implementation plan. High-level scope:

- **Golden dataset** (`tests/evals/golden.json`) — 20–30 input/expected-output pairs
- **Functional evals** — assert correct tool calls and output structure
- **LLM-as-judge** — Gemini scores each response on helpfulness, accuracy, conciseness (1–5)
- **Eval runner** (`scripts/run_evals.py`) — generates JSON + markdown report
- **CI integration** — eval suite runs on push to `main`, results posted as PR comment
- **Regression guard** — CI fails if mean score drops below baseline

---

## Self-Review Checklist

- [x] Spec section "What Gets Dropped" covered — ADK/MCP/A2A removed in Tasks 1, 3, 4
- [x] `chat_agent.py` covers all 7 tools from spec
- [x] Demo mode write interceptor covers all 3 write functions
- [x] Feedback board: Notion setup (Task 12), sidebar UI (Task 10), direct write bypassing demo mode (tools.py `submit_feedback`)
- [x] CI/CD covered in Task 14
- [x] Docker covered in Task 13
- [x] Deploy covered in Task 16
- [x] Phase 7 deferred with scope documented
- [x] No TBDs or placeholders in Tasks 1–16
- [x] Type signatures consistent across chat_agent.py, demo_tools.py, and streamlit_app.py
- [x] All import paths use `notion_clerk` (not `notion_agent`)
