Problem Statement
Notion is meant to be a “second brain”, but for many users it becomes a messy, half-maintained database graveyard: keeping multiple databases (tasks, content, reading, habits) updated requires tedious, error-prone manual work, while existing conversational chatbots neither understand Notion’s structured schema nor can safely perform real edits—creating a gap between users’ desire for natural language, agentic workflows (“just tell the system what you want”) and the reality of managing a high-stakes personal or team workspace.

Solution: An Agentic Notion Workspace Manager
I’m building an agentic Notion workspace manager that lets users manage their Notion databases using natural language, while keeping the underlying structure safe, consistent, and verifiable.

At the center is a Root Orchestrator Agent that decides which specialized agent to use for each request:

NotionAgent – understands the Notion workspace and uses a schema-aware toolset to:

search for databases and pages
fetch and read content
create new pages
update existing pages
move pages within the workspace
Notion LoopAgent + Verifier Agent – handles multi-step and bulk operations safely.
For tasks like “normalize all statuses in my Content Calendar” or “fix any tasks missing due dates,” it repeatedly:

applies changes via the NotionAgent,
re-checks the workspace, and
only stops when the Verifier confirms that the user’s rules are satisfied.
SearchAgent (Google Search) – enriches Notion content with live, grounded information when needed.

Remote Fun Facts / FactsAgent (A2A) – generates curated “facts” and injects them into Notion pages or databases on demand.

From the user’s point of view, they simply talk to the system, for example:

“Add a task to my ‘Personal Tasks’ database: ‘Book dentist appointment next month’ with status ‘Todo’.”
“Clean up my Habit Tracker so every habit has a frequency and start date; use today if missing.”
“Create a ‘Weekly Reading’ page and add three fun facts about AI.”
The Root Orchestrator routes each request to the right agent or loop, uses tools only when necessary, and minimizes redundant calls—turning Notion into a reliable, conversational workspace that maintains itself.

The build combines:
Kaggle Notebook as the runtime environment

google-adk (Agentic Design Kit) for LlmAgent, LoopAgent, AgentTool, MCP integration, and A2A support

Gemini 2.5 Flash Lite as the core LLM for all agents

Notion API via both:

direct REST helpers (create_database_item, create_page_anywhere, etc.)
MCP (@notionhq/notion-mcp-server via npx) for structured Notion tools
A remote A2A “Facts” agent served with uvicorn and wrapped in RemoteA2A Agent

A multi-agent orchestration design:

RootAgent → NotionAgent, NotionLoopAgent, SearchAgent, FactsAgent
LoopAgent + Verifier pattern for safe Notion edits
And an ADK Web UI for interacting with the RootAgent visually.
All of this is wired together inside the notebook you provided, so the final system is a fully agentic Notion workspace manager running inside Kaggle.

Future Scope or What would be possible with more time:
Adding Memory and logging to Web UI. (Tried for 3 days but could not manage)
Additional Notion functionalities
Better Chat UI with possible voice mode for smoother interactions.
Extending AI Agent to manage Notion or any Calendar.
Improvements in managing Databases and Pages for Notion. (More robust user chat handling)
