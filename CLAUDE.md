# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

NotionAgent is an agentic Notion workspace manager that lets users manage their Notion databases using natural language, while keeping the underlying structure safe, consistent, and verifiable. Built with Google ADK (Agent Development Kit), Gemini 2.5 Flash Lite, Notion API (REST + MCP), and A2A protocol.

Example user interactions:
- "Add a task to my 'Personal Tasks' database: 'Book dentist appointment next month' with status 'Todo'."
- "Clean up my Habit Tracker so every habit has a frequency and start date; use today if missing."
- "Create a 'Weekly Reading' page and add three fun facts about AI."

## Build & Run Commands

```bash
# Install (editable with dev deps)
pip install -e ".[dev]"

# Run unit tests (no API keys needed)
pytest -m "not integration"

# Run all tests (requires .env with real keys)
pytest

# Run a single test file
pytest tests/test_tools.py -v

# Lint
ruff check .

# Start the full system (facts agent + ADK web UI)
python scripts/run.py

# Or just the ADK web UI
adk web .
```

## Project Structure

```
notion_agent/           # ADK-compatible agent package (adk web discovers root_agent here)
├── __init__.py         # exports root_agent for ADK discovery
├── config.py           # dotenv-based secrets + constants (replaces Kaggle UserSecretsClient)
├── tools.py            # Notion REST helpers, MCP toolset factory, exit_notion_loop
├── prompts.py          # All agent instruction strings
└── agent.py            # Agent definitions + wiring → exports root_agent

scripts/
├── start_facts_agent.py  # A2A facts agent lifecycle (install deps, start uvicorn, health check)
└── run.py                # CLI entry point: optionally starts facts agent + launches adk web

tests/                  # pytest suite (44 tests: 43 unit + 1 integration)
├── conftest.py         # Shared fixtures (mock env vars, mock Notion responses)
├── test_config.py      # Config loading tests
├── test_tools.py       # Property coercion, REST helpers, pagination
├── test_agents.py      # Agent wiring verification (no LLM calls)
└── test_a2a.py         # A2A connectivity tests

external/a2a-samples/   # Git submodule (google a2a-samples for facts agent)
```

## Architecture

### Agent Hierarchy

**RootAgent** (orchestrator) routes user queries to specialized agents:

- **NotionAgent** — Notion CRUD. Uses MCP tools (`notion-search`, `notion-fetch`) as read-only, and Python functions (`create_database_item`, `create_page_anywhere`, `get_notion_ids`) for writes.
- **SearchAgent** — Google Search grounding for live/trending queries.
- **FactsAgent** — Remote A2A agent on uvicorn (port 8001). Fun facts via A2A protocol.
- **NotionLoopAgent** — `LoopAgent` (max 3 iterations) wrapping NotionAgent + NotionVerifierAgent. For high-reliability or multi-step edits only.
  - **NotionVerifierAgent** — Read-only validation. Calls `exit_notion_loop` on success.

### Key Design Patterns

- **Agent-as-Tool**: Sub-agents wrapped in `AgentTool` for the RootAgent
- **MCP for reads, Python functions for writes**: MCP server provides search/fetch; dedicated functions handle writes with schema-aware property coercion
- **Write-then-verify loop**: LoopAgent where NotionAgent writes and NotionVerifierAgent validates
- **Config isolation**: Only `config.py` reads environment variables; all other modules import from it

### Key Files

- `notion_agent/tools.py` — Core business logic. All Notion REST helpers, `_coerce_property_value` (handles title, rich_text, date/NLP, checkbox, select, multi_select, number, url), and MCP factory.
- `notion_agent/agent.py` — Agent wiring. Imports tools/config/prompts and constructs the full agent hierarchy. ADK entry point via `root_agent`.
- `notion_agent/config.py` — All secrets and constants. Uses `python-dotenv`. Hard-fails on missing required keys.

## Configuration

Required environment variables (in `.env`):
- `GOOGLE_API_KEY` — Google AI Studio API key
- `NOTION_API_KEY` — Notion integration token
- `NOTION_PARENT_PAGE` — Default parent page ID for new pages

Optional:
- `AGENT_MODEL` (default: `gemini-2.5-flash-lite`) — controls NotionAgent, RootAgent, NotionVerifier
  - `groq/llama-3.3-70b-versatile` for Groq (production)
  - `ollama_chat/qwen2.5:32b` for local Ollama (offline dev)
- `GROQ_API_KEY` — required when `AGENT_MODEL=groq/...`
- `OLLAMA_API_BASE` (default: `http://localhost:11434`) — required when `AGENT_MODEL=ollama_chat/...`
- `FACTS_AGENT_HOST` (default: 127.0.0.1)
- `FACTS_AGENT_PORT` (default: 8001)

> **Note:** `SearchAgent` always uses Gemini (`gemini-2.5-flash-lite`) regardless of `AGENT_MODEL`
> because `GoogleSearchTool` is a Gemini-native feature and does not work with LiteLLM-backed models.

## Roadmap (from blueprint.md)

- [x] Phase 1: Refactor notebook into modular Python files + unit tests — **DONE**
  - Modular package (`notion_agent/`), scripts, 44 tests, full docs, ADK web UI working
- [ ] Phase 2: Docker + GitHub Actions CI/CD — **NOT STARTED**
  - No Dockerfile, docker-compose.yml, or `.github/workflows/` yet
- [ ] Phase 3: AWS deployment (ECS/Lambda) + CloudWatch monitoring — **NOT STARTED**
  - No infrastructure code (Terraform/CloudFormation/CDK)
- [ ] Phase 4: Streamlit demo using personal Notion workspace — **NOT STARTED**
  - No Streamlit app or dependencies
- [ ] Phase 5: OAuth for Google & Notion + multi-user support — **NOT STARTED**
  - No OAuth implementation

## Current Status

Phase 1 is complete. The project has been fully refactored from a single Kaggle notebook into a modular Python package with:
- 5 source modules (`config`, `tools`, `prompts`, `agent`, `__init__`)
- 2 scripts (`run.py`, `start_facts_agent.py`)
- 44 tests across 4 test files (43 unit + 1 integration)
- Full ADK compatibility (`adk web .` works)
- A2A remote agent support via git submodule
- README, CLAUDE.md, and project docs

**Next milestone:** Phase 2 (Docker + CI/CD)

## Future Scope (from project_details.md)

- Memory and logging for the Web UI
- Additional Notion functionalities and more robust user chat handling
- Voice mode for smoother interactions
- Extending the agent to manage calendars (Notion or external)
