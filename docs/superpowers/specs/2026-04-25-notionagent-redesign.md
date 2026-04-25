# Notion Clerk Redesign: Portfolio-Grade Chat Demo
*Date: 2026-04-25 | Status: Approved*

---

## Executive Summary

Redesign Notion Clerk from a Google ADK local dev tool into a **turnkey, publicly accessible Notion AI chat agent** — deployed on Streamlit Cloud, usable by anyone without setup. The core asset (`tools.py` with schema-aware writes and property coercion) is preserved entirely. The ADK/A2A/MCP framework layer is replaced with a lean Gemini SDK + function calling stack that runs cleanly in a single Python process.

---

## Product Definition

> A chat UI where users type natural language — "add a task", "clean up this database", "what projects am I working on" — and the agent handles all Notion operations behind the scenes. No buttons, no database IDs, no API knowledge required.

**Differentiation from existing tools:**
- Notion's official MCP requires Claude Desktop or Cursor — not a standalone app
- All existing open-source tools (vibe-notion, notion-cli-agent) are CLIs for developers
- Nobody has built a **turnkey demo** a non-technical person can open in a browser and use immediately

**Three showcase interactions:**
1. Write tasks/entries in plain English → land correctly structured in Notion
2. Clean up a messy database → fix inconsistent fields automatically
3. Ask questions about content → search and answer from real Notion data

---

## Architecture

### Core Principle
`tools.py` is the real asset. Everything else is swappable wiring.

### Stack
| Layer | Technology | Reason |
|---|---|---|
| Chat UI | Streamlit | Free hosting, simple deployment, well-known |
| Agent | Gemini SDK + function calling | Single process, no framework overhead, ADK-free |
| Tools | `tools.py` (unchanged) | Schema-aware writes, 8-type coercion, verified |
| Demo mode | `demo_tools.py` | Session-isolated writes via `st.session_state` |
| Hosting | Streamlit Cloud | Free, shareable URL, deploys on push to `main` |
| CI/CD | GitHub Actions | Lint + test on every push |
| Containers | Docker + docker-compose | Local dev parity |

### What Gets Dropped
- `agent.py` — ADK LlmAgent/LoopAgent wiring
- `prompts.py` — ADK-specific instruction strings
- `scripts/start_facts_agent.py` — A2A uvicorn lifecycle
- `external/a2a-samples` — git submodule
- Node.js / `npx @notionhq/notion-mcp-server` dependency

### Repository Structure
```
Notion Clerk/
├── notion_clerk/
│   ├── config.py           # unchanged — dotenv secrets
│   ├── tools.py            # unchanged — the real asset
│   ├── chat_agent.py       # NEW: Gemini SDK + function calling loop
│   └── demo_tools.py       # NEW: write interceptor for demo mode
├── streamlit_app.py        # NEW: chat UI entry point
├── .streamlit/
│   └── config.toml         # theme + page config
├── tests/                  # keep all 44 tests + new ones
├── .github/
│   └── workflows/
│       └── ci.yml          # ruff lint + pytest on push
├── Dockerfile              # pure Python, no Node.js
├── docker-compose.yml      # local dev
├── .dockerignore
├── LICENSE                 # MIT
├── pyproject.toml          # updated deps (remove ADK, add streamlit, google-genai)
└── README.md               # updated setup + demo link
```

---

## Key Design Decisions

### Agent Layer (`chat_agent.py`)
- Gemini SDK (`google-genai`) with native function calling
- `tools.py` functions registered as Gemini function declarations
- Single synchronous loop: user message → Gemini → tool calls → response
- No framework, no async complexity, no subprocess dependencies

### Demo Mode (`demo_tools.py`)
- `DEMO_MODE=true` env var (set as Streamlit Secret in production)
- `create_database_item` and `create_page_anywhere` intercepted — writes go to `st.session_state["write_buffer"]` instead of real Notion
- All reads come from real demo Notion workspace
- Agent response reflects session state + real Notion (merged view) so queries after writes return accurate results
- No UI disclaimer — experience is seamless and confident

### Demo Notion Workspace
- Separate Notion workspace containing curated CV/portfolio data:
  - Projects database
  - Skills database  
  - Work Experience database
  - Reading List database
- Separate API key from personal workspace (zero risk to real data)
- Read-only from Notion's side in production (API key scoped to demo workspace only)

### Feedback Board
- Dedicated `Feedback` database in the demo Notion workspace
- Sidebar form: optional name + message (max 280 chars)
- Direct `create_database_item` call — **not** intercepted by demo mode, writes are real
- Rate limited: 1 submission per Streamlit session
- Visible to all visitors (read from Notion on page load)
- Validates input: strips HTML, max length enforced before API call

### Streamlit UI
```
┌─────────────────────────────────────────────────────┐
│  🗂 Notion Clerk                          [sidebar ▸] │
├─────────────────────────────────────────────────────┤
│                                                     │
│   Welcome! Ask me to manage your Notion workspace.  │
│   Try one of these:                                 │
│                                                     │
│   [📝 Add a task]  [🔍 Search projects]             │
│   [🧹 Clean up a database]                          │
│                                                     │
│   > Type your message...              [Send ↵]      │
└─────────────────────────────────────────────────────┘

Sidebar:
├── About this project
├── ⭐ GitHub link
├── Available databases (live list from Notion)
└── 💬 Leave Feedback
    ├── Name (optional)
    ├── Message (max 280 chars)
    └── [Submit] — 1 per session, real Notion write
```

---

## Build Phases

### Phase 0 — Repo Hygiene *(~2 hours)*
- Commit all Phase 1 code (currently untracked)
- Remove git submodule (`external/a2a-samples`)
- Add `LICENSE` (MIT)
- Update `.gitignore` (add `.DS_Store`, `node_modules`, `.streamlit/secrets.toml`)
- Update `pyproject.toml`: remove ADK/A2A deps, add `streamlit`, `google-genai`
- Update `README.md` with new architecture and demo link placeholder

### Phase 1 — New Agent Layer *(~1 day)*
- Write `notion_clerk/chat_agent.py`
  - Register all `tools.py` functions as Gemini function declarations
  - Implement tool dispatch loop
  - System prompt: Notion workspace manager persona
- Remove `notion_clerk/agent.py` and `notion_clerk/prompts.py`
- Remove `scripts/start_facts_agent.py`
- Update `notion_clerk/__init__.py` to export new agent
- Update/add unit tests for `chat_agent.py`

### Phase 2 — Demo Mode *(~half day)*
- Write `notion_clerk/demo_tools.py`
  - `DemoToolInterceptor` class wrapping write functions
  - `get_write_buffer(session_state)` — returns pending writes
  - `merge_notion_with_buffer(notion_data, buffer)` — merged read view
- `DEMO_MODE` flag in `config.py`
- Unit tests for interceptor and merge logic

### Phase 3 — Streamlit UI *(~1 day)*
- Write `streamlit_app.py`
  - Chat message history via `st.session_state["messages"]`
  - `st.chat_input` + `st.chat_message` components
  - Suggested prompt buttons
  - Session state initialization on first load
- Write `.streamlit/config.toml` (theme, page title, layout)
- Manual smoke test: all three showcase interactions work end-to-end

### Phase 4 — Feedback Board *(~3 hours)*
- Create `Feedback` database in demo Notion workspace
  - Properties: Name (title), Message (rich_text), Timestamp (date), Visible (checkbox)
- Add feedback form to Streamlit sidebar
  - Input validation (strip HTML, max 280 chars)
  - 1-per-session rate limit via `st.session_state["feedback_submitted"]`
  - Display recent feedback (last 10 entries, read from Notion)
- Unit tests for validation logic

### Phase 5 — Docker + CI/CD *(~half day)*
- Write `Dockerfile` (pure Python, multi-stage)
- Write `docker-compose.yml` (single service, env_file)
- Write `.dockerignore`
- Write `.github/workflows/ci.yml`
  - Triggers: push to `main` and `develop`, all PRs
  - Steps: `ruff check .` → `pytest -m "not integration"`
  - Uses mock env vars (same pattern as `conftest.py`)

### Phase 6 — Deploy *(~2 hours)*
- Push to GitHub (public repo)
- Connect Streamlit Cloud to repo
- Set secrets: `GOOGLE_API_KEY`, `NOTION_API_KEY`, `NOTION_PARENT_PAGE`, `DEMO_MODE=true`
- Verify live URL: all three showcase interactions, feedback submission
- Update `README.md` with live demo badge + URL

---

## Phase 7 — Eval Harness *(deferred — after Phase 6 is live)*

> Phase 0–6 ships a working demo. Phase 7 elevates it to a production AI system — the resume differentiator.

### What gets built
- **Golden dataset** (`tests/evals/golden.json`) — 20-30 input/expected-output pairs covering: task creation, database cleanup, Q&A, edge cases (missing fields, ambiguous dates)
- **Functional evals** — run agent against golden dataset, assert tool calls and output structure match expectations
- **LLM-as-judge** — secondary Gemini call scores each response: helpfulness (1-5), accuracy (1-5), conciseness (1-5)
- **Eval runner** (`scripts/run_evals.py`) — generates JSON + markdown report
- **CI integration** — eval suite runs on push to `main`, results posted as PR comment
- **Regression guard** — CI fails if mean score drops below threshold vs. baseline

### Why this matters for the portfolio
Eval harnesses are what separate "I built a chatbot" from "I built a production AI system." They demonstrate: measurement-driven development, awareness of LLM non-determinism, and the ability to maintain quality as the system evolves.

---

## Success Criteria

**Phase 0–6 done when:**
- [ ] CI passes on every push (ruff + pytest)
- [ ] Live Streamlit Cloud URL works
- [ ] All three showcase interactions complete successfully
- [ ] Feedback form submits and appears in Notion
- [ ] Session state resets on tab close

**Phase 7 done when:**
- [ ] 20+ golden test cases covering all tool types
- [ ] LLM-as-judge scoring operational
- [ ] Eval report auto-generated on push to `main`
- [ ] Baseline score established and regression guard active

---

## What This Looks Like on a Resume

> *Built a production Notion AI agent (GitHub, live demo) — natural language chat interface backed by schema-aware Gemini function calling. Session-isolated demo mode, public feedback board writing to real Notion, CI/CD with ruff + pytest, and an LLM-as-judge eval harness measuring response quality on every push.*
