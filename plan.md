──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
Ready to code?

Here is Claude's plan:
╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌
Plan: Refactor NotionAgent Notebook into Modular Python Project

Context

The entire NotionAgent system lives in a single Kaggle Jupyter notebook (custom-notion-agent (1).ipynb). It's tightly coupled to Kaggle (UserSecretsClient, /kaggle/
paths). Blueprint Phase 1 requires breaking it into modular Python files with unit tests that run outside the notebook, setting the foundation for Docker/CI (Phase 2),
AWS deployment (Phase 3), and Streamlit demo (Phase 4).

Target Directory Structure

NotionAgent/
├── .env.example
├── .gitignore
├── pyproject.toml
├── requirements.txt
├── README.md
├── CLAUDE.md # existing
├── blueprint.md # existing
├── project_details.md # existing
├── custom-notion-agent (1).ipynb # existing, untouched
│
├── notion_agent/ # ADK-compatible package
│ ├── **init**.py # exports root_agent for ADK discovery
│ ├── config.py # dotenv-based config (replaces Kaggle secrets)
│ ├── tools.py # Notion REST helpers + MCP factory
│ ├── prompts.py # Agent instruction strings
│ └── agent.py # Agent definitions + wiring
│
├── scripts/
│ ├── start_facts_agent.py # A2A facts agent lifecycle manager
│ └── run.py # CLI: starts facts agent + adk web
│
├── external/
│ └── a2a-samples/ # git submodule
│
└── tests/
├── **init**.py
├── conftest.py # shared fixtures, mock env vars
├── test_config.py
├── test_tools.py # property coercion, REST helpers
├── test_agents.py # agent wiring verification
└── test_a2a.py

Implementation Steps

Step 1: Project scaffolding

- Create .gitignore (.env, pycache, .venv, \*.log, external/a2a-samples/.../.env)
- Create .env.example with GOOGLE_API_KEY, NOTION_API_KEY, NOTION_PARENT_PAGE
- Create pyproject.toml (hatchling build, deps: google-adk[a2a], a2a-sdk, google-genai, httpx, requests, python-dateutil, python-dotenv; dev deps: pytest, pytest-mock,
  responses, ruff)
- Create requirements.txt (flat version of deps)
- Init git repo, add a2a-samples as git submodule at external/a2a-samples

Step 2: notion_agent/config.py

- Replace kaggle_secrets.UserSecretsClient with python-dotenv + os.environ
- Hard-fail on missing required keys (GOOGLE_API_KEY, NOTION_API_KEY, NOTION_PARENT_PAGE)
- Optional keys with defaults: FACTS_AGENT_HOST (127.0.0.1), FACTS_AGENT_PORT (8001)
- All constants: NOTION_VERSION, NOTION_BASE_URL, retry config

Step 3: notion_agent/tools.py

Extract from notebook cell 12:

- \_notion_headers() — unchanged
- get_notion_ids() — unchanged, imports config
- \_get_database_schema() — extracted from inside create_database_item for testability
- \_coerce_property_value() — extracted from inside create_database_item for testability
- create_database_item() — uses extracted helpers
- create_page_anywhere() — unchanged, default parent from config
- exit_notion_loop() — unchanged
- create_notion_mcp_toolset() — renamed factory, returns McpToolset instance

Step 4: notion_agent/prompts.py

Extract all agent instruction strings as named constants:

- SEARCH_AGENT_INSTRUCTION, NOTION_AGENT_INSTRUCTION, NOTION_VERIFIER_INSTRUCTION, ROOT_AGENT_INSTRUCTION

Step 5: notion_agent/agent.py + **init**.py

- Import tools, prompts, config
- Define all 6 agents exactly as in notebook: search_agent, notion_agent, notion_verifier_agent, notion_loop_agent, facts_agent, root_agent
- Wrap sub-agents in AgentTool for root_agent
- **init**.py: from .agent import root_agent
- Verify adk web . from project root discovers the agent

Step 6: scripts/start_facts_agent.py + scripts/run.py

- start_facts_agent.py: install deps from submodule, write .env, start uvicorn, health-check loop
- run.py: load dotenv, optionally start facts agent, launch adk web ., cleanup on exit

Step 7: Tests

- conftest.py: autouse fixture to set mock env vars, fixtures for mock Notion responses and mock ToolContext
- test_config.py: required keys load, optional defaults work, missing key raises KeyError
- test_tools.py: test every property coercion type (title, rich_text, date/today/tomorrow, checkbox, select, multi_select, number, url, fallback), test get_notion_ids
  with mocked pagination, test create_database_item with mocked schema+POST, test exit_notion_loop sets escalate flag
- test_agents.py: verify agent names, tool counts, loop agent max_iterations=3, sub-agent wiring, facts_agent URL format (no LLM calls — inspect objects only)
- test_a2a.py: mock health check + integration test (marked @pytest.mark.integration)

Step 8: Update README.md and CLAUDE.md

- README.md: setup instructions (clone, submodule init, .env, pip install, run)
- Update CLAUDE.md with new project structure and commands

Key Design Decisions

1.  Config: python-dotenv replaces Kaggle secrets. Only config.py reads env vars.
2.  MCP read / Python write: Pattern preserved exactly from notebook.
3.  Extracted nested helpers: \_coerce_property_value and \_get_database_schema become module-level private functions in tools.py for direct unit testing.
4.  A2A: Git submodule at external/a2a-samples. Optional — system works without it.
5.  ADK compatibility: notion_agent/**init**.py exports root_agent, so adk web . works from repo root.

Verification

1.  pip install -e ".[dev]" — installs without errors
2.  pytest -m "not integration" — all unit tests pass
3.  adk web . — launches web UI, agent responds to queries
4.  python scripts/run.py — starts facts agent + web UI end-to-end
