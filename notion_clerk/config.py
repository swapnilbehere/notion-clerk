"""Configuration module — replaces Kaggle UserSecretsClient with python-dotenv."""

import os
from dotenv import load_dotenv

load_dotenv()

# --- Required secrets (hard-fail if missing) ---
GOOGLE_API_KEY: str = os.environ["GOOGLE_API_KEY"]
NOTION_API_KEY: str = os.environ["NOTION_API_KEY"]
NOTION_PARENT_PAGE: str = os.environ["NOTION_PARENT_PAGE"]

# Set in environment for libraries that read from os.environ directly
os.environ.setdefault("GOOGLE_API_KEY", GOOGLE_API_KEY)

# --- Optional provider keys ---
# Set these in os.environ so LiteLLM can pick them up automatically
GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
if GROQ_API_KEY:
    os.environ["GROQ_API_KEY"] = GROQ_API_KEY

_ollama_base = os.getenv("OLLAMA_API_BASE", "")
if _ollama_base:
    os.environ["OLLAMA_API_BASE"] = _ollama_base

# --- Notion constants ---
NOTION_VERSION: str = "2022-06-28"
NOTION_BASE_URL: str = "https://api.notion.com/v1"

# --- A2A Facts Agent ---
FACTS_AGENT_HOST: str = os.getenv("FACTS_AGENT_HOST", "127.0.0.1")
FACTS_AGENT_PORT: int = int(os.getenv("FACTS_AGENT_PORT", "8001"))

# --- Model config ---
# AGENT_MODEL controls NotionAgent, RootAgent, and NotionVerifierAgent.
# Use any LiteLLM-compatible string:
#   gemini-2.5-flash-lite         → Gemini (default, free tier)
#   groq/llama-3.3-70b-versatile  → Groq API (recommended for production)
#   ollama_chat/qwen2.5:32b       → local Ollama (offline dev)
AGENT_MODEL: str = os.getenv("AGENT_MODEL", "gemini-2.5-flash-lite")

# SearchAgent is always Gemini — GoogleSearchTool is Gemini-only.
SEARCH_MODEL: str = "gemini-2.5-flash-lite"

# --- Gemini retry config ---
GEMINI_RETRY_ATTEMPTS: int = 5
GEMINI_RETRY_INITIAL_DELAY: float = 5.0
GEMINI_RETRY_MAX_DELAY: float = 60.0
GEMINI_RETRY_EXP_BASE: float = 2.0
