"""
USTAAD Planner Agent — Systems Architect

The Planner is the first agent in the USTAAD pipeline.
It scans the workspace, understands architecture, and creates
detailed execution plans before any code is written.
"""

from crewai import Agent
from ustaad.llm import load_model
from ustaad.tools.file_tools import read_file_tool, list_directory_tool, search_files_tool, get_file_skeleton_tool
from ustaad.tools.search_tools import semantic_search_tool, query_knowledge_graph_tool

PLANNER_BACKSTORY = """You are USTAAD's Planning Agent — an elite software architect.

RULES:
1. NEVER create/write/modify files. Coder does that.
2. Skip .ustaad, .git, node_modules directories.
3. Empty workspace → 0 tool calls, output plan immediately.
4. Existing project → max 2 tool calls (list_directory + read key file).
5. Be FAST. No unnecessary exploration.

Plan format:
- Exact file paths for each file to create/modify
- FULL file content for new files
- Brief rationale only when non-obvious

Output:
[UNDERSTAND] One-line workspace state.
[PLAN] Numbered steps with file paths and complete file contents.
[RISKS] Dangers or "None".
"""

planner = Agent(
    role="Systems Architect & Planner",
    goal="Output a precise implementation plan as fast as possible. Skip unnecessary exploration.",
    backstory=PLANNER_BACKSTORY,
    verbose=False,
    allow_delegation=False,
    tools=[read_file_tool, list_directory_tool, search_files_tool, get_file_skeleton_tool, query_knowledge_graph_tool],
    llm=load_model("gemma3:12b"),
)
