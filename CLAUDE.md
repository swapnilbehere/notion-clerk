# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Notion Clerk** — chat with your Notion workspace in plain English. Backed by Gemini SDK function calling, deployed on Streamlit Cloud. No ADK, no MCP, no Node.js.

Example user interactions:
- "Add a task to my 'Personal Tasks' database: 'Book dentist appointment next month' with status 'Todo'."
- "Clean up my Habit Tracker so every habit has a frequency and start date; use today if missing."
- "Create a 'Weekly Reading' page and add three fun facts about AI."

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
├── tools.py          # Notion REST helpers: search, query, fetch, create, update, feedback
├── chat_agent.py     # Gemini SDK function-calling loop, tool registry, run_agent_turn
└── demo_tools.py     # Write interceptor: buffers writes to st.session_state in demo mode

streamlit_app.py      # Streamlit chat UI, sidebar, feedback form
.streamlit/
└── config.toml       # Neutral black/white theme

tests/
├── conftest.py       # Shared fixtures (mock env vars, mock Notion responses)
├── test_config.py    # Config loading tests
├── test_tools.py     # Property coercion, REST helpers, pagination
├── test_chat_agent.py  # Agent loop, dispatch, tool registry
└── test_demo_tools.py  # Write interceptor and buffer accumulation
```

## Architecture

**Single agent loop** (`chat_agent.py`):
- User message → Gemini SDK with 7 function declarations → model decides which tools to call
- Tool calls dispatched via `_dispatch()` to either real Notion REST functions or demo interceptors
- Loop continues until model returns a text-only response

**Demo mode** (`DEMO_MODE=true` on Streamlit Cloud):
- `make_write_tools(session_state, demo_mode=True)` returns closures that buffer to `st.session_state["write_buffer"]`
- Reads (search, query, fetch) always hit real Notion
- Feedback form bypasses demo mode — writes directly to the Notion feedback database

**Key files:**
- `notion_clerk/tools.py` — Core business logic. `_coerce_property_value` handles 8 Notion property types (title, rich_text, date, checkbox, select, multi_select, number, url). New: `search_notion`, `query_database`, `fetch_page`, `update_database_item`, `submit_feedback`, `get_recent_feedback`.
- `notion_clerk/chat_agent.py` — `run_agent_turn(user_message, gemini_history, write_tools)` returns `(response_text, new_history_entries)`.
- `notion_clerk/demo_tools.py` — `make_write_tools(session_state, demo_mode)` returns the write registry.

## Configuration

Required environment variables (in `.env`):
- `GOOGLE_API_KEY` — Google AI Studio API key
- `NOTION_API_KEY` — Notion integration token
- `NOTION_PARENT_PAGE` — Default parent page ID for new pages

Optional:
- `AGENT_MODEL` (default: `gemini-2.5-flash-lite`)
- `DEMO_MODE` (default: `false`) — set `true` on Streamlit Cloud
- `NOTION_FEEDBACK_DB_ID` — Notion feedback database ID (see Task 12 in implementation plan)

## Current Status

All code implemented. 45 tests passing. Ruff clean.

**Next steps:** Push to GitHub → deploy to Streamlit Cloud → set `DEMO_MODE=true` + secrets in Streamlit Cloud dashboard.
