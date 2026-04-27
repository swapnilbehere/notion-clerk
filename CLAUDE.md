# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

## Project Overview

**Notion Clerk** — chat with Swapnil Behere's Notion portfolio workspace in plain English.
Backed by Groq (Llama 3.3 70B) via OpenAI-compatible function calling. Deployed on Streamlit Cloud.

## Build & Run Commands

```bash
# Install (editable with dev deps)
pip install -e ".[dev]"

# Run the Streamlit app
streamlit run streamlit_app.py

# Run unit tests (no API keys needed)
pytest -m "not integration"

# Run a single test file
pytest tests/test_tools.py -v

# Lint
ruff check .
```

## Project Structure

```
notion_clerk/
├── __init__.py       # exports run_agent_turn
├── config.py         # dotenv-based secrets + constants
├── tools.py          # Notion REST helpers; query_database returns flat dicts (not raw Notion JSON)
├── chat_agent.py     # Groq function-calling loop, primary/fallback model, run_agent_turn
└── demo_tools.py     # Write interceptor: buffers writes to st.session_state in demo mode

streamlit_app.py      # Streamlit chat UI, sidebar, feedback form
.streamlit/
└── config.toml       # Dark theme (#0D0D0D background)

tests/
├── conftest.py       # Shared fixtures (mock env vars, mock Notion responses)
├── test_config.py    # Config loading tests
├── test_tools.py     # Property coercion, REST helpers, flat output
├── test_chat_agent.py  # Agent loop, dispatch, fallback, tool registry
└── test_demo_tools.py  # Write interceptor and buffer accumulation
```

## Architecture

**Single agent loop** (`chat_agent.py`):
- User message → Groq with 8 function declarations → model decides which tools to call
- Tool calls dispatched via `_dispatch()` to either real Notion REST functions or demo interceptors
- Loop continues until model returns a text-only response
- Falls back to `llama-3.1-8b-instant` (no tools, slim history) if primary hits quota

**CV data embedded in system prompt:**
- All read queries (projects, skills, experience, education) are answered from the system prompt
- Tools only used for: write operations, feedback submission, fetching latest Notion data when requested
- This avoids burning Groq's 100k TPD on every read query

**Demo mode** (`DEMO_MODE=true` on Streamlit Cloud):
- `make_write_tools(session_state, demo_mode=True)` returns closures that buffer to `st.session_state["write_buffer"]`
- Reads always hit real Notion; feedback form writes are real

**Key files:**
- `notion_clerk/tools.py` — `query_database` and `fetch_page` return flat `{property: value}` dicts. `_coerce_property_value` handles 8 Notion property types for writes.
- `notion_clerk/chat_agent.py` — `run_agent_turn(user_message, history, write_tools)` → `(response_text, new_history_entries)`. `_slim_history_for_fallback` strips tool messages before fallback.
- `notion_clerk/demo_tools.py` — `make_write_tools(session_state, demo_mode)` returns the write registry.

## Configuration

Required environment variables (in `.env`):
- `GROQ_API_KEY` — Groq Console API key
- `NOTION_API_KEY` — Notion integration token
- `NOTION_PARENT_PAGE` — Default parent page ID for new pages

Optional:
- `AGENT_MODEL` (default: `llama-3.3-70b-versatile`)
- `FALLBACK_MODEL` (default: `llama-3.1-8b-instant`)
- `DEMO_MODE` (default: `false`) — set `true` on Streamlit Cloud
- `NOTION_FEEDBACK_DB_ID` — Notion feedback database ID

## Current Status

61 tests passing. Ruff clean. Deployed at https://notion-clerk.streamlit.app
