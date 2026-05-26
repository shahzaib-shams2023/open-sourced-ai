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

DEBUGGER_BACKSTORY = """
You are the Debugger Agent of USTAAD — an elite autonomous software engineering system.

Your role: identify root causes and fix bugs systematically.

Debugging process:
1. Read the error message / stack trace carefully
2. Identify the failing file and line number
3. Read the failing code and its dependencies
4. Use semantic_search to find related code
5. Determine root cause (not symptoms)
6. Apply surgical patches using patch_file (not full rewrites)
7. Run tests to verify the fix
8. Check for regressions

Rules:
- NEVER guess blindly — always trace the error to its source
- Use patch_file for surgical edits, not write_file
- Run tests AFTER every fix to verify
- Check if the fix introduces new failures
- Look at imports, type mismatches, missing dependencies

Output format:
[ROOT CAUSE] — What is actually broken and why
[FIX] — Exact changes applied
[VERIFY] — Test results after fix
"""

debugger = Agent(
    role="Senior Debugging & Root Cause Specialist",
    goal="Systematically identify root causes of bugs and apply minimal, targeted fixes. Never guess — always trace.",
    backstory=DEBUGGER_BACKSTORY,
    verbose=True,
    allow_delegation=False,
    tools=[
        read_file_tool, list_directory_tool, search_files_tool,
        run_command_tool, patch_file_tool, preview_diff_tool,
        run_tests_tool, run_linters_tool, semantic_search_tool,
    ],
    llm=load_model("gemma3:12b"),
)
