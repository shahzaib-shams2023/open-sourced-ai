"""
USTAAD Debugger Agent — Error Analysis & Root Cause Specialist

Analyzes stack traces, inspects logs, identifies root causes,
and implements targeted fixes.
"""

from crewai import Agent
from ustaad.llm import load_model
from ustaad.tools.file_tools import read_file_tool, list_directory_tool, search_files_tool
from ustaad.tools.shell_tools import run_command_tool
from ustaad.tools.patch_tools import patch_file_tool, preview_diff_tool
from ustaad.tools.test_tools import run_tests_tool, run_linters_tool
from ustaad.tools.search_tools import semantic_search_tool

DEBUGGER_BACKSTORY = """You are USTAAD's Debugger — a root cause specialist.

Process:
1. Read the error/stack trace carefully
2. Identify failing file and line
3. Read failing code and its dependencies
4. Use semantic_search for related code
5. Determine root cause (not symptoms)
6. Apply surgical patches via patch_file
7. Run tests to verify fix
8. Check for regressions

Rules: NEVER guess — trace to source. Use patch_file, not write_file.
Run tests AFTER every fix. Check for new failures.

Output: [ROOT CAUSE] [FIX] [VERIFY]
"""

debugger = Agent(
    role="Senior Debugging & Root Cause Specialist",
    goal="Systematically identify root causes and apply minimal, targeted fixes. Never guess — always trace.",
    backstory=DEBUGGER_BACKSTORY,
    verbose=False,
    allow_delegation=False,
    tools=[
        read_file_tool, list_directory_tool, search_files_tool,
        run_command_tool, patch_file_tool, preview_diff_tool,
        run_tests_tool, run_linters_tool, semantic_search_tool,
    ],
    llm=load_model("gemma3:12b"),
)
