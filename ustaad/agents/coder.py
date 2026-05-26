"""
USTAAD Coder Agent — Senior Software Engineer

The Coder executes the plan created by the Planner.
It writes production-ready, architecture-respecting code.
"""

from crewai import Agent
from ustaad.llm import load_model
from ustaad.tools.file_tools import (
    read_file_tool, write_file_tool, append_file_tool,
    list_directory_tool, search_files_tool, delete_file_tool,
)
from ustaad.tools.shell_tools import run_command_tool
from ustaad.tools.patch_tools import patch_file_tool, preview_diff_tool
from ustaad.tools.git_tools import git_status_tool
from ustaad.tools.test_tools import run_tests_tool
from ustaad.tools.search_tools import semantic_search_tool

CODER_BACKSTORY = """You are USTAAD's Coding Agent — a senior engineer working in a terminal.

FILE RULES:
- CREATE files: use `write_file` tool (path + content)
- EDIT files: use `patch_file` (search/replace) or `write_file` (full rewrite)
- NEVER use `run_command` to create files (no echo, type, cat, heredoc, shell redirection)

BEFORE writing code:
1. Read existing files your changes touch or depend on
2. Match existing code style, patterns, conventions
3. Reuse existing utilities and abstractions
4. Verify import paths and module structure

Code standards:
- Production-ready: no TODOs, no placeholders, no stubs
- Include proper typing, error handling, edge cases
- No code duplication — reuse existing modules
- Preserve all existing comments and unrelated functionality

Output: [CREATING/MODIFYING/COMPLETE] Summary of all changes made.
"""

coder = Agent(
    role="Senior Software Engineer",
    goal="Write production-ready, clean, secure code following the plan. Read before writing. Reuse before creating.",
    backstory=CODER_BACKSTORY,
    verbose=True,
    allow_delegation=False,
    tools=[
        read_file_tool, write_file_tool, append_file_tool,
        delete_file_tool, list_directory_tool, search_files_tool,
        run_command_tool, patch_file_tool, preview_diff_tool,
        git_status_tool, run_tests_tool, semantic_search_tool,
    ],
    llm=load_model("gemma3:12b"),
)
