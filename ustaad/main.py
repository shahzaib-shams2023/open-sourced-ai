"""
USTAAD Main Orchestration Engine

The autonomous execution loop:
SCAN -> INDEX -> UNDERSTAND -> PLAN -> EXECUTE -> TEST -> REPAIR -> REFLECT -> COMPLETE

Every phase is deliberate. Nothing is blind.
"""

import os
import time
from dotenv import load_dotenv
load_dotenv()
os.environ.setdefault("OPENAI_API_KEY", "na")

from crewai import Task, Crew
from rich.console import Console

from ustaad.agents.planner import planner
from ustaad.agents.coder import coder
from ustaad.agents.reviewer import reviewer
from ustaad.agents.researcher import researcher
from ustaad.agents.security import security_agent
from ustaad.agents.devops import devops_agent
from ustaad.agents.debugger import debugger

from ustaad.core.scanner import WorkspaceScanner
from ustaad.core.execution_mode import get_mode
from ustaad.engine.git import GitEngine
from ustaad.engine.testing import TestEngine
from ustaad.engine.search import SearchEngine
from ustaad.engine.reflection import ReflectionEngine
from ustaad.engine.context import ContextManager
from ustaad.engine.repo_index import RepoIndexer
from ustaad.engine.patch import PatchEngine
from ustaad.memory import ProjectMemory
from ustaad.tools.file_tools import write_file

console = Console()


# ---------------------------------------------------------------------------
# Task classification
# ---------------------------------------------------------------------------
def classify_task(prompt: str) -> str:
    p = prompt.lower()
    debug_kw = ["fix", "bug", "error", "crash", "failing", "broken", "debug",
                "traceback", "exception", "not working", "issue", "problem"]
    devops_kw = ["docker", "deploy", "ci/cd", "pipeline", "kubernetes", "k8s",
                 "nginx", "infrastructure", "dockerfile", "compose", "github actions"]
    research_kw = ["research", "investigate", "compare", "analyze", "what is",
                   "how does", "explain", "difference between"]
    review_kw = ["review", "audit", "check", "inspect", "validate"]
    test_kw = ["test", "spec", "coverage"]

    if any(k in p for k in debug_kw):
        return "debug"
    if any(k in p for k in devops_kw):
        return "devops"
    if any(k in p for k in research_kw):
        return "research"
    if any(k in p for k in review_kw):
        return "review"
    if any(k in p for k in test_kw):
        return "test"
    return "code"


def print_phase(phase: str, content: str = ""):
    colours = {
        "SCAN": "bold cyan", "INDEX": "bold cyan", "UNDERSTAND": "bold blue",
        "PLAN": "bold magenta", "EXECUTE": "bold green", "TEST": "bold yellow",
        "REPAIR": "bold red", "VERIFY": "bold yellow", "REFLECT": "bold white",
        "COMPLETE": "bold green", "MODE": "bold cyan", "TASK": "bold white",
        "SEARCH": "bold blue", "GIT": "bold magenta", "MEMORY": "dim",
    }
    colour = colours.get(phase, "bold white")
    console.print(f"\n[{colour}][{phase}][/{colour}]")
    if content:
        console.print(content)


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------
def run_task(user_prompt: str, workspace: str = None) -> str:
    start = time.time()
    workspace = workspace or os.getcwd()
    mode = get_mode()

    # --- MODE ---
    mode_label = "AUTONOMOUS" if mode.autonomous else ("SAFE" if mode.safe else "SEMI-AUTO")
    print_phase("MODE", f"  {mode_label} | confirm_destructive={mode.confirm_destructive}")

    # --- SCAN ---
    print_phase("SCAN", f"  Workspace: {workspace}")
    scanner = WorkspaceScanner(workspace)
    scan = scanner.scan()
    scan_ctx = scan.to_context_string()
    console.print(scan_ctx)

    # --- INDEX ---
    print_phase("INDEX", "  Building repository index...")
    try:
        indexer = RepoIndexer(workspace)
        repo_idx = indexer.build_index()
        idx_ctx = repo_idx.to_context_string()
        console.print(idx_ctx)
    except Exception:
        idx_ctx = "[INDEX] Indexing skipped"
        console.print("  Skipped (non-critical)")

    # --- SEARCH INDEX ---
    try:
        search_engine = SearchEngine(workspace)
        chunks = search_engine.index_workspace()
        print_phase("SEARCH", f"  Indexed {chunks} code chunks for semantic search")
    except Exception:
        console.print("  [dim]Search index skipped[/dim]")

    # --- UNDERSTAND ---
    print_phase("UNDERSTAND")
    memory = ProjectMemory(workspace)
    mem_ctx = memory.get_context_string(user_prompt)
    console.print(mem_ctx)

    git_engine = GitEngine(workspace)
    git_status = git_engine.status()
    git_ctx = git_status.to_context_string()
    console.print(git_ctx)

    # --- CLASSIFY ---
    task_type = classify_task(user_prompt)
    print_phase("TASK", f"  Type: {task_type.upper()}")

    # --- BUILD CONTEXT ---
    ctx = ContextManager()
    ctx.add("USER REQUEST", user_prompt, priority=1)
    ctx.add("WORKSPACE SCAN", scan_ctx, priority=5)
    ctx.add("REPOSITORY INDEX", idx_ctx, priority=10)
    ctx.add("GIT STATUS", git_ctx, priority=15)
    ctx.add("MEMORY", mem_ctx, priority=20)
    ctx.add("WORKSPACE PATH", workspace, priority=25)
    ctx.add("EXECUTION MODE", f"{mode_label} | Dangerous ops require confirmation.", priority=30)

    # Add relevant search results
    try:
        search_results = search_engine.search_formatted(user_prompt, n_results=3)
        if "No results" not in search_results:
            ctx.add("RELEVANT CODE", search_results, priority=8)
    except Exception:
        pass

    full_context = ctx.build()

    # --- PLAN ---
    print_phase("PLAN", "  Creating implementation plan...")
    planning_task = Task(
        description=f"""
        USTAAD Planning Phase. Analyze workspace and create implementation plan.
        {full_context}
        IMPORTANT: Use list_directory/read_file/semantic_search to inspect code BEFORE planning.
        Be specific about file paths. Flag dangerous operations.
        """,
        expected_output="[UNDERSTAND] Analysis  [PLAN] Numbered steps  [RISKS] Dangers",
        agent=planner,
    )

    # --- EXECUTE ---
    print_phase("EXECUTE", "  Implementing...")
    coding_task = Task(
        description=f"""
        USTAAD Execution Phase. Implement the plan.
        Request: {user_prompt}
        Workspace: {workspace}
        RULES: Read before write. Use patch_file for edits. Production-ready code only.
        """,
        expected_output="[CREATING/MODIFYING/COMPLETE] Summary of changes",
        agent=coder,
        context=[planning_task],
    )

    # --- VERIFY ---
    print_phase("VERIFY", "  Reviewing...")
    review_task = Task(
        description="USTAAD Review Phase. Read all modified files. Run tests if available. PASS or FAIL verdict.",
        expected_output="[REVIEW] Analysis  [ISSUES] Problems  [VERDICT] PASS/FAIL",
        agent=reviewer,
        context=[coding_task],
    )

    # Build pipeline based on task type
    agents = [planner, coder, reviewer]
    tasks = [planning_task, coding_task, review_task]

    if task_type == "debug":
        debug_task = Task(
            description=f"USTAAD Debug Phase. Analyze error, find root cause, apply fix.\n{user_prompt}\nWorkspace: {workspace}",
            expected_output="[ROOT CAUSE]  [FIX]  [VERIFY]",
            agent=debugger,
            context=[planning_task],
        )
        agents.insert(1, debugger)
        tasks.insert(1, debug_task)

    if task_type in ("code", "debug"):
        sec_task = Task(
            description="USTAAD Security Phase. Scan for secrets, injection, insecure config.",
            expected_output="[SECURITY SCAN]  [FINDINGS]  [VERDICT]",
            agent=security_agent,
            context=[coding_task],
        )
        agents.append(security_agent)
        tasks.append(sec_task)

    if task_type == "devops":
        ops_task = Task(
            description=f"USTAAD Infrastructure Phase.\n{user_prompt}\nWorkspace: {workspace}\n{full_context}",
            expected_output="[INFRASTRUCTURE]  [VERIFICATION]",
            agent=devops_agent,
            context=[planning_task],
        )
        agents.insert(1, devops_agent)
        tasks.insert(1, ops_task)

    if task_type in ("debug", "research"):
        res_task = Task(
            description=f"USTAAD Research Phase. Gather intelligence for:\n{user_prompt}\nWorkspace: {workspace}",
            expected_output="[RESEARCH]  [RECOMMENDATIONS]",
            agent=researcher,
            context=[planning_task],
        )
        agents.append(researcher)
        tasks.insert(1, res_task)

    # --- RUN CREW ---
    crew = Crew(agents=agents, tasks=tasks, verbose=True)
    result = crew.kickoff()

    # --- TEST ---
    print_phase("TEST", "  Running automated checks...")
    test_engine = TestEngine(workspace, scan)
    test_results = test_engine.run_tests()
    lint_results = test_engine.run_linters()
    tests_passed = all(t.passed for t in test_results) if test_results else True
    lints_passed = all(l.passed for l in lint_results) if lint_results else True

    for tr in test_results:
        console.print(tr.to_context_string())
    for lr in lint_results:
        console.print(lr.to_context_string())

    if not test_results and not lint_results:
        console.print("  No tests or linters detected")

    # --- REFLECT ---
    elapsed = time.time() - start
    print_phase("REFLECT")
    reflector = ReflectionEngine()
    report = reflector.reflect(
        task_description=user_prompt,
        files_modified=[],  # TODO: track from patch engine
        test_passed=tests_passed,
        lint_passed=lints_passed,
    )
    console.print(report.to_context_string())
    console.print(f"  Agents:   {len(agents)}")
    console.print(f"  Tasks:    {len(tasks)}")
    console.print(f"  Duration: {elapsed:.1f}s")

    # --- COMPLETE ---
    print_phase("COMPLETE")
    memory.save(f"Task: {user_prompt}\nType: {task_type}\nResult: {str(result)[:1500]}", category="task")
    console.print("  Memory saved")

    output_path = os.path.join(workspace, "ustaad_output.md")
    write_file(output_path, str(result))
    console.print(f"  Output: {output_path}")

    return str(result)
