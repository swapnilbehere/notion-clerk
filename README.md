# Notion Clerk

Chat with your Notion workspace in plain English. No buttons, no database IDs — just natural conversation.

**[Live Demo →](https://notion-clerk.streamlit.app)** *(coming soon)*

## What it does

Notion Clerk is an AI chat agent backed by Gemini function calling. You type a request, and it:

1. Discovers your Notion databases
2. Creates, reads, updates, or searches — with correctly typed properties
3. Confirms what it did in plain English

**Example interactions:**
- *"Add a task called 'Book dentist appointment' with status Todo"*
- *"What projects am I currently working on?"*
- *"List all my databases"*

## Tech stack

| Layer | Technology |
|-------|-----------|
| Agent | Gemini SDK (`google-genai`) with native function calling |
| UI | Streamlit |
| Hosting | Streamlit Cloud |
| Notion | REST API v1 |

## Local setup

```bash
git clone https://github.com/swapnilbehere/NotionAgent
cd NotionAgent
pip install -e ".[dev]"
cp .env.example .env
# Fill in .env with your keys
streamlit run streamlit_app.py
```

**Required env vars:**
- `GOOGLE_API_KEY` — [Google AI Studio](https://aistudio.google.com)
- `NOTION_API_KEY` — [Notion integrations](https://www.notion.so/my-integrations)
- `NOTION_PARENT_PAGE` — Parent page ID for new pages

See `.env.example` for full reference.

## Project structure

```
notion_clerk/
├── config.py        # Secrets and constants
├── tools.py         # Notion REST helpers (search, query, create, update)
├── chat_agent.py    # Gemini SDK function-calling loop
└── demo_tools.py    # Write interceptor for demo mode

streamlit_app.py     # Chat UI with feedback sidebar
tests/               # 45 unit tests, no live API calls
```

## Demo mode

When `DEMO_MODE=true` (set on Streamlit Cloud), write operations are buffered in session state — nothing modifies the real Notion workspace. Reads always pull from the real demo workspace. Feedback form writes are real.

## Running tests

```bash
pytest -m "not integration" -v
```

## License

MIT — see [LICENSE](LICENSE).
