"""Configuration — loads secrets from .env or environment."""

import os
from dotenv import load_dotenv

load_dotenv()

# --- Required ---
GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
NOTION_API_KEY: str = os.environ["NOTION_API_KEY"]
NOTION_PARENT_PAGE: str = os.environ["NOTION_PARENT_PAGE"]

# --- Notion constants ---
NOTION_VERSION: str = "2022-06-28"
NOTION_BASE_URL: str = "https://api.notion.com/v1"

# --- Models (Groq) ---
AGENT_MODEL: str = os.getenv("AGENT_MODEL", "llama-3.3-70b-versatile")
FALLBACK_MODEL: str = os.getenv("FALLBACK_MODEL", "llama-3.1-8b-instant")

# --- Demo mode ---
DEMO_MODE: bool = os.getenv("DEMO_MODE", "false").lower() == "true"

# --- Feedback database (set after creating the Notion feedback DB) ---
NOTION_FEEDBACK_DB_ID: str = os.getenv("NOTION_FEEDBACK_DB_ID", "")
