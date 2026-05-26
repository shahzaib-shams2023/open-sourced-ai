"""
USTAAD Reviewer Agent — Code Quality & Security Review

The Reviewer validates all changes made by the Coder.
It checks for bugs, security vulnerabilities, performance issues,
and architecture violations.
"""

from crewai import Agent
from ustaad.llm import load_model
from ustaad.tools.file_tools import read_file_tool, list_directory_tool, search_files_tool
from ustaad.tools.shell_tools import run_command_tool
from ustaad.tools.test_tools import run_tests_tool, run_linters_tool, run_all_checks_tool
from ustaad.tools.search_tools import semantic_search_tool

REVIEWER_BACKSTORY = """You are USTAAD's Review Agent — a senior code reviewer and security engineer.

Process:
1. Read every created/modified file
2. Verify code implements what the plan specified
3. Check for bugs, edge cases, error handling gaps
4. Scan for security issues (injection, auth bypass, secrets)
5. Run tests and linters if available

Checklist: syntax, imports, error handling, no secrets, no injection,
input validation, project patterns, no duplication, performance, types.

Output:
[REVIEW] File-by-file analysis.
[ISSUES] Numbered problems (if any).
[VERDICT] PASS or FAIL with what needs fixing.
"""

reviewer = Agent(
    role="Senior Code Reviewer & Security Engineer",
    goal="Review all code for correctness, security, performance. Run tests. Block bad code.",
    backstory=REVIEWER_BACKSTORY,
    verbose=True,
    allow_delegation=False,
    tools=[
        read_file_tool, list_directory_tool, search_files_tool,
        run_command_tool, run_tests_tool, run_linters_tool,
        run_all_checks_tool, semantic_search_tool,
    ],
    llm=load_model("gemma3:12b"),
)
