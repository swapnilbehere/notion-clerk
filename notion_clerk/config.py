"""Configuration — loads secrets from .env or environment."""

import os
from dotenv import load_dotenv

load_dotenv()

# --- Required ---
GOOGLE_API_KEY: str = os.environ["GOOGLE_API_KEY"]
NOTION_API_KEY: str = os.environ["NOTION_API_KEY"]
NOTION_PARENT_PAGE: str = os.environ["NOTION_PARENT_PAGE"]

# Set for libraries that read from os.environ directly
os.environ.setdefault("GOOGLE_API_KEY", GOOGLE_API_KEY)

# --- Notion constants ---
NOTION_VERSION: str = "2022-06-28"
NOTION_BASE_URL: str = "https://api.notion.com/v1"

# --- Model ---
AGENT_MODEL: str = os.getenv("AGENT_MODEL", "gemini-2.5-flash-lite")

# --- Demo mode ---
DEMO_MODE: bool = os.getenv("DEMO_MODE", "false").lower() == "true"

# --- Feedback database (set after creating the Notion feedback DB) ---
NOTION_FEEDBACK_DB_ID: str = os.getenv("NOTION_FEEDBACK_DB_ID", "")
