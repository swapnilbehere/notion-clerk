"""Gemini SDK agent loop for Notion Clerk."""

import logging
from typing import Any, Callable

from google import genai
from google.genai import types

from .config import GOOGLE_API_KEY, AGENT_MODEL
from . import tools as notion_tools

_SYSTEM_INSTRUCTION = """You are Notion Clerk, an AI assistant embedded in Swapnil Behere's professional portfolio workspace.

This workspace belongs to Swapnil Sushil Behere — an AI/ML Software Engineer (M.S. Computer Science, Santa Clara University).
It contains his professional profile across 5 databases:
- Work Experience: his job history (SCU Frugal Innovation Hub, Riskpro Management Consulting)
- Projects: his portfolio projects (Notion Clerk, RAG System for Chromatography, TalkaWalk, Posture Estimation for Yoga Asanas)
- Skills: his technical skills organized by category and level
- Education: his academic background
- Feedback: where visitors leave messages

When visitors ask about Swapnil, his background, skills, projects, or experience — query the relevant database and answer from the data. Treat this like a living, queryable CV.

You have tools to:
- List available databases (call get_notion_ids first if you don't know which database to use)
- Get field names and types for a database (call get_database_schema when asked about fields or properties)
- Create items in databases with correctly typed properties
- Create freeform pages
- Search across the workspace
- Query and read database contents
- Fetch page details
- Update existing database items

Guidelines:
- Be concise and confident in responses
- When answering questions about Swapnil, query the database first — don't guess
- When creating items, confirm what was created and in which database
- For cleanup tasks, query the database first, then update items that need fixing
- Never expose database IDs in responses — use human-readable names
- If the user's intent is ambiguous, ask one clarifying question
"""

_TOOL_DECLARATIONS = types.Tool(
    function_declarations=[
        types.FunctionDeclaration(
            name="get_notion_ids",
            description="List all Notion databases the integration can access. Call this first to discover available databases before writing.",
            parameters=types.Schema(type=types.Type.OBJECT, properties={}),
        ),
        types.FunctionDeclaration(
            name="get_database_schema",
            description="Get the field names and their types for a Notion database. Call this when the user asks what fields or properties a database has.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "database_id": types.Schema(
                        type=types.Type.STRING,
                        description="The Notion database ID.",
                    ),
                },
                required=["database_id"],
            ),
        ),
        types.FunctionDeclaration(
            name="create_database_item",
            description="Create a new item (row) in a Notion database with correctly typed properties.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "database_id": types.Schema(
                        type=types.Type.STRING,
                        description="The Notion database ID.",
                    ),
                    "properties": types.Schema(
                        type=types.Type.OBJECT,
                        description='Flat dict of property name to value. E.g. {"Name": "Buy milk", "Due Date": "tomorrow", "Done": false}',
                    ),
                },
                required=["database_id", "properties"],
            ),
        ),
        types.FunctionDeclaration(
            name="create_page_anywhere",
            description="Create a new freeform Notion page (not in a database) under any parent page.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "title": types.Schema(type=types.Type.STRING, description="Page title"),
                    "parent_page_id": types.Schema(
                        type=types.Type.STRING,
                        description="Parent page ID. Omit to use the default.",
                    ),
                    "content": types.Schema(
                        type=types.Type.STRING,
                        description="Optional body text for the page.",
                    ),
                },
                required=["title"],
            ),
        ),
        types.FunctionDeclaration(
            name="search_notion",
            description="Search across all pages and databases in the Notion workspace.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "query": types.Schema(
                        type=types.Type.STRING,
                        description="Search query text.",
                    ),
                },
                required=["query"],
            ),
        ),
        types.FunctionDeclaration(
            name="query_database",
            description="Fetch all items in a Notion database. Use to read or audit database contents.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "database_id": types.Schema(
                        type=types.Type.STRING,
                        description="The database ID to query.",
                    ),
                },
                required=["database_id"],
            ),
        ),
        types.FunctionDeclaration(
            name="fetch_page",
            description="Fetch the full content and properties of a specific Notion page.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "page_id": types.Schema(
                        type=types.Type.STRING,
                        description="The page ID to fetch.",
                    ),
                },
                required=["page_id"],
            ),
        ),
        types.FunctionDeclaration(
            name="update_database_item",
            description="Update properties of an existing Notion database item.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "page_id": types.Schema(
                        type=types.Type.STRING,
                        description="The page ID of the item to update.",
                    ),
                    "properties": types.Schema(
                        type=types.Type.OBJECT,
                        description='Flat dict of property name to new value. E.g. {"Done": true, "Priority": "High"}',
                    ),
                },
                required=["page_id", "properties"],
            ),
        ),
    ]
)

# Read-only tools always use real Notion
_READ_REGISTRY: dict[str, Callable] = {
    "get_notion_ids": notion_tools.get_notion_ids,
    "get_database_schema": notion_tools.get_database_schema,
    "search_notion": notion_tools.search_notion,
    "query_database": notion_tools.query_database,
    "fetch_page": notion_tools.fetch_page,
}

# Write tools can be overridden (demo mode intercepts them)
_DEFAULT_WRITE_REGISTRY: dict[str, Callable] = {
    "create_database_item": notion_tools.create_database_item,
    "create_page_anywhere": notion_tools.create_page_anywhere,
    "update_database_item": notion_tools.update_database_item,
}


def _dispatch(name: str, args: dict[str, Any], registry: dict[str, Callable]) -> Any:
    fn = registry.get(name)
    if fn is None:
        return {"error": f"Unknown tool: {name}"}
    try:
        return fn(**args)
    except Exception as exc:
        logging.error("Tool %s failed: %s", name, exc)
        return {"error": str(exc)}


def run_agent_turn(
    user_message: str,
    gemini_history: list,
    write_tools: dict[str, Callable] | None = None,
) -> tuple[str, list]:
    """
    Run one conversational turn through the Gemini function-calling loop.

    Args:
        user_message: The user's input text.
        gemini_history: Prior turns as a list of types.Content objects.
        write_tools: Optional overrides for write functions (used in demo mode).

    Returns:
        (response_text, new_history_entries) where new_history_entries are
        the Content objects added this turn (to be appended to gemini_history).
    """
    registry = {**_READ_REGISTRY, **_DEFAULT_WRITE_REGISTRY}
    if write_tools:
        registry.update(write_tools)

    client = genai.Client(api_key=GOOGLE_API_KEY)

    contents = list(gemini_history)
    contents.append(types.Content(role="user", parts=[types.Part(text=user_message)]))

    new_entries: list = []
    new_entries.append(contents[-1])  # the user message

    while True:
        response = client.models.generate_content(
            model=AGENT_MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=_SYSTEM_INSTRUCTION,
                tools=[_TOOL_DECLARATIONS],
                temperature=0.1,
            ),
        )

        candidate = response.candidates[0]
        contents.append(candidate.content)
        new_entries.append(candidate.content)

        fn_calls = [p for p in candidate.content.parts if p.function_call is not None]

        if not fn_calls:
            break

        tool_parts = []
        for part in fn_calls:
            fc = part.function_call
            result = _dispatch(fc.name, dict(fc.args), registry)
            tool_parts.append(
                types.Part(
                    function_response=types.FunctionResponse(
                        name=fc.name,
                        response={"result": result},
                    )
                )
            )

        tool_content = types.Content(role="user", parts=tool_parts)
        contents.append(tool_content)
        new_entries.append(tool_content)

    response_text = "".join(
        p.text for p in candidate.content.parts if p.text is not None
    )
    return response_text, new_entries
