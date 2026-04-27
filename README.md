# Notion Clerk

[![CI](https://github.com/swapnilbehere/notion-clerk/actions/workflows/ci.yml/badge.svg)](https://github.com/swapnilbehere/notion-clerk/actions/workflows/ci.yml)

Chat with your Notion workspace in plain English. No buttons, no database IDs — just natural conversation.

**[Live Demo →](https://notion-clerk.streamlit.app)**

## What it does

Notion Clerk is an AI chat agent backed by Groq (Llama 3.3 70B) with function calling. It's deployed as a portfolio showcase — ask about Swapnil Behere's projects, skills, and experience, or leave feedback.

**Example interactions:**
- *"What projects has Swapnil built?"*
- *"What's the tech stack for TalkaWalk?"*
- *"Show his work experience"*
- *"What are his top ML skills?"*

## Tech stack

| Layer | Technology |
|-------|-----------|
| Agent | Groq API (`llama-3.3-70b-versatile`) via OpenAI-compatible client |
| Fallback | `llama-3.1-8b-instant` (quota guard) |
| UI | Streamlit |
| Hosting | Streamlit Cloud |
| Notion | REST API v1 |

## Local setup

```bash
git clone https://github.com/swapnilbehere/notion-clerk
cd notion-clerk
pip install -e ".[dev]"
cp .env.example .env
# Fill in .env with your keys
streamlit run streamlit_app.py
```

**Required env vars:**
- `GROQ_API_KEY` — [Groq Console](https://console.groq.com/keys)
- `NOTION_API_KEY` — [Notion integrations](https://www.notion.so/my-integrations)
- `NOTION_PARENT_PAGE` — Parent page ID for new pages

See `.env.example` for full reference.

## Project structure

```
notion_clerk/
├── config.py        # Secrets and constants
├── tools.py         # Notion REST helpers (search, query, create, update, feedback)
├── chat_agent.py    # Groq function-calling loop with primary/fallback model
└── demo_tools.py    # Write interceptor for demo mode

streamlit_app.py     # Chat UI with feedback sidebar
tests/               # 61 unit tests, no live API calls
```

## Demo mode

When `DEMO_MODE=true` (set on Streamlit Cloud), write operations are buffered in session state — nothing modifies the real Notion workspace. Reads always pull from the real demo workspace. Feedback form writes are real.

## Running tests

```bash
pytest -m "not integration" -v
```

## License

MIT — see [LICENSE](LICENSE).
