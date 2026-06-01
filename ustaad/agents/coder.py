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
    get_file_skeleton_tool, find_symbol_tool, ast_refactor_tool,
    analyze_dependencies_tool
)
from ustaad.tools.shell_tools import run_command_tool, ripgrep_search_tool
from ustaad.tools.patch_tools import patch_file_tool, preview_diff_tool, unified_diff_patch_tool
from ustaad.tools.git_tools import git_status_tool
from ustaad.tools.test_tools import run_tests_tool
from ustaad.tools.search_tools import semantic_search_tool, query_knowledge_graph_tool

CODER_BACKSTORY = """You are USTAAD's Coding Agent — a senior engineer working in a terminal.

FILE RULES:
- CREATE files: use `write_file` tool (path + content)
- EDIT files: use `unified_diff_patch` or `patch_file` for surgical edits, or `write_file` (full rewrite)
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
- VERIFY YOUR CODE: Use `run_tests` or `run_command` (e.g. `pytest`) to verify your work before completing the task. Do not just wait for the final testing phase. Fix errors immediately if tests fail.

Output: [CREATING/MODIFYING/COMPLETE] Summary of all changes made.
"""

coder = Agent(
    role="Senior Software Engineer",
    goal="Write production-ready, clean, secure code following the plan. Read before writing. Reuse before creating.",
    backstory=CODER_BACKSTORY,
    verbose=False,
    allow_delegation=False,
    tools=[
        read_file_tool, write_file_tool, append_file_tool,
        delete_file_tool, list_directory_tool, search_files_tool,
        get_file_skeleton_tool, find_symbol_tool, ast_refactor_tool, analyze_dependencies_tool,
        run_command_tool, ripgrep_search_tool, patch_file_tool, preview_diff_tool, unified_diff_patch_tool,
        git_status_tool, run_tests_tool, semantic_search_tool, query_knowledge_graph_tool,
    ],
    llm=load_model("gemma3:12b"),
)
