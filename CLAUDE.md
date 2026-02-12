# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

NotionAgent is an agentic Notion workspace manager that lets users manage their Notion databases using natural language, while keeping the underlying structure safe, consistent, and verifiable. It solves the problem of Notion becoming a "messy, half-maintained database graveyard" by replacing tedious manual work with conversational, schema-aware agent workflows.

Built as a Kaggle Notebook using Google ADK (Agent Development Kit), Gemini 2.5 Flash Lite, Notion API (REST + MCP), and A2A protocol. The entire implementation lives in a single Jupyter notebook: `custom-notion-agent (1).ipynb` — it writes `agent.py` to `/kaggle/working/notion_agent/` at runtime. No traditional Python package structure yet.

Example user interactions:
- "Add a task to my 'Personal Tasks' database: 'Book dentist appointment next month' with status 'Todo'."
- "Clean up my Habit Tracker so every habit has a frequency and start date; use today if missing."
- "Create a 'Weekly Reading' page and add three fun facts about AI."

## Running the Project

This project runs in the **Kaggle Notebooks** environment:

1. Configure Kaggle Secrets: `GOOGLE_API_KEY`, `NOTION_API_KEY`, `NOTION_PARENT_PAGE`
2. Execute notebook cells sequentially — they install dependencies, start the A2A facts agent server, write `agent.py`, and optionally launch the ADK web UI
3. Web UI (optional): `adk web --url_prefix {url_prefix} /kaggle/working/` starts on port 8000

**Key dependencies** (installed inline via pip):
- `google-adk[a2a]`, `a2a-sdk` — Agent orchestration and A2A protocol
- `google-genai` — Gemini API (model: `gemini-2.5-flash-lite`)
- `@notionhq/notion-mcp-server` — Notion MCP server (via npx)
- `httpx`, `requests`, `dateutil`

There is no `requirements.txt`, `pyproject.toml`, test suite, or CI pipeline yet.

## Architecture

### Agent Hierarchy

**RootAgent** (orchestrator) routes user queries to specialized agents:

- **NotionAgent** — Notion CRUD operations. Uses MCP tools (`notion-search`, `notion-fetch`) as read-only, and dedicated Python functions (`create_database_item`, `create_page_anywhere`, `get_notion_ids`) for all writes. Never exposes raw Notion IDs to users.
- **SearchAgent** — Google Search grounding for live/trending queries. Uses `GoogleSearchTool`.
- **FactsAgent** — Remote A2A agent running on uvicorn (port 8001). Provides fun facts via the A2A protocol.
- **NotionLoopAgent** — `LoopAgent` (max 3 iterations) wrapping NotionAgent + NotionVerifierAgent. Used only for high-reliability or multi-step Notion edits.
  - **NotionVerifierAgent** — Read-only validation sub-agent. Calls `exit_notion_loop` to signal success or outputs error description to trigger retry.

### Key Design Patterns

- **Agent-as-Tool**: Each sub-agent is wrapped in `AgentTool` and exposed as a callable tool to the RootAgent
- **MCP for reads, Python functions for writes**: MCP server provides search/fetch; dedicated functions handle writes with schema-aware property coercion (dates, checkboxes, selects, etc.)
- **Write-then-verify loop**: `LoopAgent` pattern where NotionAgent writes and NotionVerifierAgent validates, retrying on mismatch
- **Property coercion**: `create_database_item` auto-fetches the database schema and coerces simple values (strings, booleans, dates including NLP like "today"/"tomorrow") into correct Notion property format

### Notion REST Helpers

- `get_notion_ids()` — Paginated search listing all accessible databases
- `create_database_item(database_id, properties)` — Schema-aware row creation with type coercion
- `create_page_anywhere(title, parent_page_id, content)` — Creates pages under other pages (not databases)
- `_notion_headers()` — Builds auth headers (Notion API version: `2022-06-28`)

## Roadmap (from blueprint.md)

Phase 1: Refactor notebook into modular Python files (`agents.py`, `tools.py`, `main.py`) + unit tests
Phase 2: Docker + GitHub Actions CI/CD
Phase 3: AWS deployment (ECS/Lambda) + CloudWatch monitoring
Phase 4: Streamlit demo using personal Notion workspace
Phase 5: OAuth for Google & Notion + multi-user support

## Future Scope (from project_details.md)

- Memory and logging for the Web UI
- Additional Notion functionalities and more robust user chat handling
- Voice mode for smoother interactions
- Extending the agent to manage calendars (Notion or external)
- Improvements in database and page management
