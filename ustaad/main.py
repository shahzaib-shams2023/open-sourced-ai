"""
USTAAD Main Orchestration Engine

Implements the Claude Code-style execution loop:
SCAN → UNDERSTAND → PLAN → ASK IF DANGEROUS → EXECUTE → VERIFY → REFLECT → COMPLETE

This is NOT blind execution. Every phase is deliberate.
"""

import os
import time
from dotenv import load_dotenv
load_dotenv()
os.environ.setdefault("OPENAI_API_KEY", "na")

from crewai import Task, Crew

from ustaad.agents.planner import planner
from ustaad.agents.coder import coder
from ustaad.agents.reviewer import reviewer
from ustaad.agents.researcher import researcher
from ustaad.agents.security import security_agent
from ustaad.agents.devops import devops_agent

from ustaad.core.scanner import WorkspaceScanner
from ustaad.core.execution_mode import get_mode

from ustaad.tools.memory_tools import save_memory, search_memory
from ustaad.tools.shell_tools import run_command
from ustaad.tools.file_tools import write_file

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

console = Console()


# ---------------------------------------------------------------------------
# Task classification — determines which agents to involve
# ---------------------------------------------------------------------------
def classify_task(prompt: str) -> str:
    """
    Classify the user's prompt to determine the execution path.

    Returns one of:
      'code'     — standard code generation/modification
      'debug'    — debugging/fixing issues
      'devops'   — infrastructure/deployment tasks
      'research' — information gathering only
      'review'   — review existing code
    """
    prompt_lower = prompt.lower()

    debug_keywords = [
        "fix", "bug", "error", "crash", "failing", "broken", "debug",
        "traceback", "exception", "not working", "issue", "problem",
    ]
    devops_keywords = [
        "docker", "deploy", "ci/cd", "pipeline", "kubernetes", "k8s",
        "nginx", "infrastructure", "dockerfile", "compose", "github actions",
        "gitlab ci", "jenkins", "terraform", "ansible",
    ]
    research_keywords = [
        "research", "investigate", "compare", "analyze", "what is",
        "how does", "explain", "difference between", "pros and cons",
    ]
    review_keywords = [
        "review", "audit", "check", "inspect", "validate", "verify",
    ]

    if any(k in prompt_lower for k in debug_keywords):
        return "debug"
    if any(k in prompt_lower for k in devops_keywords):
        return "devops"
    if any(k in prompt_lower for k in research_keywords):
        return "research"
    if any(k in prompt_lower for k in review_keywords):
        return "review"

    return "code"


# ---------------------------------------------------------------------------
# Phase output helpers
# ---------------------------------------------------------------------------
def print_phase(phase: str, content: str = ""):
    """Print a structured phase header."""
    colours = {
        "SCAN": "bold cyan",
        "UNDERSTAND": "bold blue",
        "PLAN": "bold magenta",
        "EXECUTE": "bold green",
        "VERIFY": "bold yellow",
        "REFLECT": "bold white",
        "COMPLETE": "bold green",
        "MEMORY": "bold dim",
        "MODE": "bold cyan",
        "TASK": "bold white",
    }
    colour = colours.get(phase, "bold white")
    console.print(f"\n[{colour}][{phase}][/{colour}]")
    if content:
        console.print(content)


# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------
def run_task(user_prompt: str, workspace: str = None) -> str:
    """
    USTAAD main execution loop.

    SCAN → UNDERSTAND → PLAN → ASK → EXECUTE → VERIFY → REFLECT → COMPLETE
    """
    start_time = time.time()
    workspace = workspace or os.getcwd()
    mode = get_mode()

    # -----------------------------------------------------------------------
    # PHASE 0: MODE
    # -----------------------------------------------------------------------
    mode_label = []
    if mode.autonomous:
        mode_label.append("AUTONOMOUS")
    elif mode.safe:
        mode_label.append("SAFE")
    else:
        mode_label.append("SEMI-AUTONOMOUS")
    if mode.confirm_destructive:
        mode_label.append("CONFIRM-DESTRUCTIVE")

    print_phase("MODE", f"  {' | '.join(mode_label)}")

    # -----------------------------------------------------------------------
    # PHASE 1: SCAN
    # -----------------------------------------------------------------------
    print_phase("SCAN", f"  Scanning workspace: {workspace}")

    scanner = WorkspaceScanner(workspace)
    scan = scanner.scan()
    scan_context = scan.to_context_string()

    console.print(scan_context)

    # -----------------------------------------------------------------------
    # PHASE 2: UNDERSTAND (memory + git context)
    # -----------------------------------------------------------------------
    print_phase("UNDERSTAND")

    # Search previous memory
    try:
        memory_results = search_memory(user_prompt)
        if memory_results and memory_results.get("documents") and memory_results["documents"][0]:
            console.print("  Previous context found in memory")
            memory_context = "\n".join(memory_results["documents"][0][:3])
        else:
            console.print("  No previous context found")
            memory_context = "No previous context available."
    except Exception:
        console.print("  Memory system unavailable")
        memory_context = "Memory unavailable."

    # Git status
    git_context = ""
    if scan.has_git:
        git_result = run_command("git status --short")
        git_status = git_result.get("stdout", "").strip()
        if git_status:
            console.print(f"  Git changes detected:\n{git_status}")
            git_context = f"Git status:\n{git_status}"
        else:
            console.print("  Git: clean working tree")
            git_context = "Git: clean working tree"

    # -----------------------------------------------------------------------
    # PHASE 3: CLASSIFY TASK
    # -----------------------------------------------------------------------
    task_type = classify_task(user_prompt)
    print_phase("TASK", f"  Type: {task_type.upper()}")

    # -----------------------------------------------------------------------
    # Build comprehensive context for agents
    # -----------------------------------------------------------------------
    full_context = f"""
=== WORKSPACE SCAN ===
{scan_context}

=== GIT STATUS ===
{git_context}

=== PREVIOUS MEMORY ===
{memory_context}

=== USER REQUEST ===
{user_prompt}

=== WORKSPACE PATH ===
{workspace}

=== EXECUTION MODE ===
{' | '.join(mode_label)}
Dangerous operations will require user confirmation.
"""

    # -----------------------------------------------------------------------
    # PHASE 4: PLAN
    # -----------------------------------------------------------------------
    print_phase("PLAN", "  Creating implementation plan...")

    planning_task = Task(
        description=f"""
        You are operating inside USTAAD's planning phase.

        Analyze the workspace scan results, understand the existing architecture,
        and create a detailed implementation plan for the following request:

        {user_prompt}

        Workspace context:
        {full_context}

        IMPORTANT:
        - Use list_directory and read_file to inspect existing code BEFORE planning
        - Your plan must respect existing architecture and conventions
        - Flag any dangerous operations that will need user confirmation
        - Be specific about file paths, function names, and module structure
        """,
        expected_output="""
        A structured plan with:
        [UNDERSTAND] - Analysis of current state
        [PLAN] - Numbered steps with exact file paths
        [RISKS] - Dangerous operations or breaking changes
        """,
        agent=planner,
    )

    # -----------------------------------------------------------------------
    # PHASE 5: EXECUTE
    # -----------------------------------------------------------------------
    print_phase("EXECUTE", "  Implementing plan...")

    coding_task = Task(
        description=f"""
        You are operating inside USTAAD's execution phase.

        Implement the changes specified in the Planner's plan to fulfill:

        {user_prompt}

        RULES:
        - Read every file BEFORE modifying it
        - Follow the existing code style exactly
        - Write complete, production-ready code (no placeholders)
        - Create parent directories as needed
        - Preserve all existing comments and functionality in modified files

        Workspace: {workspace}
        """,
        expected_output="""
        All requested changes implemented with:
        [CREATING] - New files created
        [MODIFYING] - Existing files modified
        [COMPLETE] - Summary of all changes
        """,
        agent=coder,
        context=[planning_task],
    )

    # -----------------------------------------------------------------------
    # PHASE 6: VERIFY
    # -----------------------------------------------------------------------
    print_phase("VERIFY", "  Reviewing changes...")

    review_task = Task(
        description="""
        You are operating inside USTAAD's verification phase.

        Review ALL changes made by the Coder:
        1. Read every created/modified file
        2. Check for bugs, missing error handling, and edge cases
        3. Verify architectural consistency
        4. Run tests if a test framework is detected (pytest, jest, etc.)
        5. Run linters if configured (ruff, eslint, pylint, etc.)

        Provide a PASS or FAIL verdict.
        If FAIL, list specific issues that need fixing.
        """,
        expected_output="""
        [REVIEW] - File-by-file analysis
        [ISSUES] - Problems found (if any)
        [VERDICT] - PASS or FAIL
        """,
        agent=reviewer,
        context=[coding_task],
    )

    # -----------------------------------------------------------------------
    # Build agent list and task list based on task type
    # -----------------------------------------------------------------------
    agents = [planner, coder, reviewer]
    tasks = [planning_task, coding_task, review_task]

    # Add security agent for code tasks
    if task_type in ("code", "debug"):
        security_task = Task(
            description="""
            You are operating inside USTAAD's security verification phase.

            Scan ALL code changes for:
            1. Hardcoded secrets or credentials
            2. Injection vulnerabilities (SQL, command, XSS)
            3. Insecure configurations
            4. Missing input validation
            5. Dependency vulnerabilities

            Provide a SECURE or VULNERABLE verdict.
            """,
            expected_output="""
            [SECURITY SCAN] - Methodology and files scanned
            [FINDINGS] - Issues found with severity levels
            [SECURITY VERDICT] - SECURE or VULNERABLE
            """,
            agent=security_agent,
            context=[coding_task],
        )
        agents.append(security_agent)
        tasks.append(security_task)

    # Add DevOps agent for infrastructure tasks
    if task_type == "devops":
        devops_task = Task(
            description=f"""
            You are operating inside USTAAD's infrastructure phase.

            Handle the following infrastructure request:
            {user_prompt}

            Workspace: {workspace}
            Context: {full_context}
            """,
            expected_output="""
            [INFRASTRUCTURE] - Changes made
            [VERIFICATION] - How to verify changes work
            """,
            agent=devops_agent,
            context=[planning_task],
        )
        agents.append(devops_agent)
        # Insert devops task after planning but before review
        tasks.insert(1, devops_task)

    # Add researcher for debug/research tasks
    if task_type in ("debug", "research"):
        research_task = Task(
            description=f"""
            You are operating inside USTAAD's research phase.

            Research the following to help with:
            {user_prompt}

            Check existing project files, dependencies, error logs,
            and configuration to gather relevant intelligence.

            Workspace: {workspace}
            """,
            expected_output="""
            [RESEARCH] - Findings
            [RECOMMENDATIONS] - Actionable recommendations
            """,
            agent=researcher,
            context=[planning_task],
        )
        agents.append(researcher)
        # Insert research after planning
        tasks.insert(1, research_task)

    # -----------------------------------------------------------------------
    # Run Crew
    # -----------------------------------------------------------------------
    crew = Crew(
        agents=agents,
        tasks=tasks,
        verbose=True,
    )

    result = crew.kickoff()

    # -----------------------------------------------------------------------
    # PHASE 7: REFLECT
    # -----------------------------------------------------------------------
    elapsed = time.time() - start_time
    print_phase("REFLECT")
    console.print(f"  Task type:    {task_type.upper()}")
    console.print(f"  Agents used:  {len(agents)}")
    console.print(f"  Tasks run:    {len(tasks)}")
    console.print(f"  Duration:     {elapsed:.1f}s")

    # -----------------------------------------------------------------------
    # PHASE 8: COMPLETE — save memory and output
    # -----------------------------------------------------------------------
    print_phase("COMPLETE")

    # Save to memory
    try:
        save_memory(f"Task: {user_prompt}\nResult: {str(result)[:2000]}")
        console.print("  Memory saved ✓")
    except Exception:
        console.print("  [dim]Memory save skipped[/dim]")

    # Save output file
    output_path = os.path.join(workspace, "ustaad_output.md")
    write_file(output_path, str(result))
    console.print(f"  Output saved: {output_path}")

    return str(result)
