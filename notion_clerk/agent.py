"""Agent definitions for the NotionAgent system."""

from google.adk.agents import LlmAgent, LoopAgent
from google.adk.models.google_llm import Gemini
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools.agent_tool import AgentTool
from google.adk.tools.google_search_tool import GoogleSearchTool
from google.genai.types import HttpRetryOptions
from google.adk.agents.remote_a2a_agent import (
    RemoteA2aAgent,
    AGENT_CARD_WELL_KNOWN_PATH,
)

from .config import (
    NOTION_API_KEY,
    FACTS_AGENT_HOST,
    FACTS_AGENT_PORT,
    AGENT_MODEL,
    SEARCH_MODEL,
    GEMINI_RETRY_ATTEMPTS,
    GEMINI_RETRY_INITIAL_DELAY,
    GEMINI_RETRY_MAX_DELAY,
    GEMINI_RETRY_EXP_BASE,
)
from .tools import (
    get_notion_ids,
    create_database_item,
    create_page_anywhere,
    exit_notion_loop,
    create_notion_mcp_toolset,
)
from .prompts import (
    SEARCH_AGENT_INSTRUCTION,
    NOTION_AGENT_INSTRUCTION,
    NOTION_VERIFIER_INSTRUCTION,
    ROOT_AGENT_INSTRUCTION,
)

# --- Shared resources ---
gemini_retry = HttpRetryOptions(
    attempts=GEMINI_RETRY_ATTEMPTS,
    initial_delay=GEMINI_RETRY_INITIAL_DELAY,
    max_delay=GEMINI_RETRY_MAX_DELAY,
    exp_base=GEMINI_RETRY_EXP_BASE,
)

notion_mcp_server = create_notion_mcp_toolset(NOTION_API_KEY)


def _build_model(model_str: str):
    """Return the right ADK model object for the given model string.

    Gemini/Gemma strings → Gemini() with retry config.
    Everything else (groq/..., ollama_chat/...) → LiteLlm().
    """
    if model_str.startswith("gemini") or model_str.startswith("gemma"):
        return Gemini(model=model_str, retry_options=gemini_retry)
    return LiteLlm(model=model_str)


# Model for NotionAgent, NotionVerifierAgent, RootAgent — configurable via AGENT_MODEL.
# Default: gemini-2.5-flash-lite
# Production: AGENT_MODEL=groq/llama-3.3-70b-versatile
# Local dev:  AGENT_MODEL=ollama_chat/qwen2.5:32b  (requires Ollama running)
notion_model = _build_model(AGENT_MODEL)

# SearchAgent always uses Gemini — GoogleSearchTool is a Gemini-native feature
# and does not work with LiteLLM-backed models.
search_model = Gemini(model=SEARCH_MODEL, retry_options=gemini_retry)

# --- Agent definitions ---
search_agent = LlmAgent(
    model=search_model,
    name="SearchAgent",
    instruction=SEARCH_AGENT_INSTRUCTION,
    tools=[GoogleSearchTool()],
)

notion_agent = LlmAgent(
    model=notion_model,
    name="NotionAgent",
    instruction=NOTION_AGENT_INSTRUCTION,
    tools=[
        notion_mcp_server,
        get_notion_ids,
        create_database_item,
        create_page_anywhere,
    ],
)

notion_verifier_agent = LlmAgent(
    name="NotionVerifierAgent",
    model=notion_model,
    instruction=NOTION_VERIFIER_INSTRUCTION,
    tools=[notion_mcp_server, exit_notion_loop],
    output_key="notion_validation_feedback",
)

notion_loop_agent = LoopAgent(
    name="NotionTasks",
    sub_agents=[notion_agent, notion_verifier_agent],
    max_iterations=3,
)

facts_agent = RemoteA2aAgent(
    name="adk_facts_remote",
    description="Remote ADK Facts search agent",
    agent_card=f"http://{FACTS_AGENT_HOST}:{FACTS_AGENT_PORT}{AGENT_CARD_WELL_KNOWN_PATH}",
)

# --- Root orchestrator (ADK entry point) ---
root_agent = LlmAgent(
    name="RootAgent",
    model=notion_model,
    instruction=ROOT_AGENT_INSTRUCTION,
    tools=[
        AgentTool(agent=search_agent),
        AgentTool(agent=notion_agent),
        AgentTool(agent=notion_loop_agent),
        AgentTool(agent=facts_agent),
    ],
)
