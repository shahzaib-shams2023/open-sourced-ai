"""
USTAAD Main Orchestration Engine — v2.0

The autonomous execution loop, now with:
- Smart task routing (trivial/standard/complex)
- Shared single directory walk
- Cached repo indexing
- Premium progress display
- Integrated repair loop
- Per-agent context trimming
- Phase timing breakdown

Pipeline:
SCAN → INDEX → UNDERSTAND → ROUTE → PLAN → EXECUTE → TEST → REPAIR → REFLECT → COMPLETE
"""

import os
import sys
import time
import platform
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
from ustaad.core.task_router import route_task, TaskComplexity, TaskType
from ustaad.core.progress import (
    phase_header, phase_spinner, route_banner,
    completion_summary, PipelineProgress, PhaseTimer,
)
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
# Agent registry — maps role names to agent instances
# ---------------------------------------------------------------------------
AGENT_REGISTRY = {
    "planner": planner,
    "coder": coder,
    "reviewer": reviewer,
    "researcher": researcher,
    "security": security_agent,
    "devops": devops_agent,
    "debugger": debugger,
}


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------
def run_task(user_prompt: str, workspace: str = None) -> str:
    pipeline = PipelineProgress()
    pipeline.start_time = time.time()
    pipeline.task_description = user_prompt
    workspace = workspace or os.getcwd()
    mode = get_mode()

    # --- MODE ---
    mode_label = "AUTONOMOUS" if mode.autonomous else ("SAFE" if mode.safe else "SEMI-AUTO")

    # --- SCAN ---
    with phase_spinner("SCAN", workspace) as timer:
        scanner = WorkspaceScanner(workspace)
        scan = scanner.scan()
        scan_ctx = scan.to_context_string()
    pipeline.phases.append(timer)

    is_empty_workspace = scan.file_count == 0

    # --- ROUTE (before heavy indexing) ---
    route = route_task(
        user_prompt,
        file_count=scan.file_count,
        is_empty_workspace=is_empty_workspace,
    )
    pipeline.task_type = route.task_type.value
    pipeline.complexity = route.complexity.value
    pipeline.agent_count = route.agent_count

    route_banner(
        task_type=route.task_type.value,
        complexity=route.complexity.value,
        agent_count=route.agent_count,
        reason=route.reason,
    )

    # --- INDEX (conditional — skip for trivial/empty) ---
    idx_ctx = ""
    search_engine = None

    if route.skip_indexing or is_empty_workspace:
        phase = PhaseTimer(name="INDEX", status="skipped")
        pipeline.phases.append(phase)
    else:
        with phase_spinner("INDEX", "Building repository index...") as timer:
            try:
                indexer = RepoIndexer(workspace)
                # Use cached index if available and workspace hasn't changed
                repo_idx = indexer.load_or_rebuild()
                idx_ctx = repo_idx.to_context_string()
            except Exception:
                idx_ctx = ""
        pipeline.phases.append(timer)

    # --- SEARCH INDEX (conditional) ---
    if route.skip_search or is_empty_workspace:
        phase = PhaseTimer(name="SEARCH", status="skipped")
        pipeline.phases.append(phase)
    else:
        with phase_spinner("SEARCH", "Indexing code for semantic search...") as timer:
            try:
                search_engine = SearchEngine(workspace)
                chunks = search_engine.index_workspace()
            except Exception:
                search_engine = None
        pipeline.phases.append(timer)

    # --- UNDERSTAND ---
    with phase_spinner("UNDERSTAND", "Loading memory & git status...") as timer:
        memory = ProjectMemory(workspace)
        mem_ctx = memory.get_context_string(user_prompt)

        git_engine = GitEngine(workspace)
        git_status = git_engine.status()
        git_ctx = git_status.to_context_string()
    pipeline.phases.append(timer)

    # --- BUILD CONTEXT (trimmed per complexity) ---
    ctx = ContextManager(max_chars=route.context_budget)
    ctx.add("USER REQUEST", user_prompt, priority=1)
    ctx.add("PLATFORM", f"OS: {platform.system()} | Shell: {'PowerShell/CMD' if sys.platform == 'win32' else 'bash'} | IMPORTANT: Use write_file tool to create files, NEVER shell commands.", priority=2)
    ctx.add("WORKSPACE SCAN", scan_ctx, priority=5)
    ctx.add("WORKSPACE PATH", workspace, priority=6)

    # Only add heavy context for standard/complex tasks
    if route.complexity != TaskComplexity.TRIVIAL:
        ctx.add("REPOSITORY INDEX", idx_ctx, priority=10)
        ctx.add("GIT STATUS", git_ctx, priority=15)
        ctx.add("MEMORY", mem_ctx, priority=20)
        ctx.add("EXECUTION MODE", f"{mode_label} | Dangerous ops require confirmation.", priority=30)

        # Relevant search results
        if search_engine is not None:
            try:
                search_results = search_engine.search_formatted(user_prompt, n_results=3)
                if "No results" not in search_results:
                    ctx.add("RELEVANT CODE", search_results, priority=8)
            except Exception:
                pass

    full_context = ctx.build()

    # --- BUILD PIPELINE based on routing decision ---
    agents = []
    tasks = []

    for role_name in route.agents_needed:
        agent = AGENT_REGISTRY.get(role_name)
        if not agent:
            continue

        if role_name == "planner":
            if is_empty_workspace:
                plan_instructions = """
                The workspace is EMPTY. Do NOT use any tools. Do NOT explore.
                Immediately output your plan with full file contents for all files to create.
                The Coder agent will use write_file to create each file.
                """
            else:
                plan_instructions = """
                Use list_directory to understand the project, then output your plan.
                Do NOT create, write, or modify files. The Coder agent does that.
                For new files, include FULL file content. For edits, specify what to change.
                """
            task = Task(
                description=f"USTAAD Planning Phase. Create an implementation plan.\n{full_context}\n{plan_instructions}",
                expected_output="[UNDERSTAND] Analysis  [PLAN] Numbered steps with file paths and full file contents  [RISKS] Dangers",
                agent=agent,
            )

        elif role_name == "coder":
            context_tasks = [t for t in tasks]  # all prior tasks as context
            task = Task(
                description=f"""
                USTAAD Execution Phase. Implement the plan.
                Request: {user_prompt}
                Workspace: {workspace}
                Platform: {platform.system()}
                RULES:
                - Read existing files before modifying them.
                - Use `write_file` tool to create new files (pass path and full content).
                - Use `patch_file` tool for surgical edits to existing files.
                - NEVER use `run_command` to create or write files.
                - Write production-ready, complete code. No placeholders or TODOs.
                - Create ALL files specified in the plan.
                """,
                expected_output="[CREATING/MODIFYING/COMPLETE] Summary of all files created and modified",
                agent=agent,
                context=context_tasks if context_tasks else None,
            )

        elif role_name == "reviewer":
            task = Task(
                description="USTAAD Review Phase. Read all modified files. Run tests if available. PASS or FAIL verdict.",
                expected_output="[REVIEW] Analysis  [ISSUES] Problems  [VERDICT] PASS/FAIL",
                agent=agent,
                context=[tasks[-1]] if tasks else None,
            )

        elif role_name == "debugger":
            task = Task(
                description=f"USTAAD Debug Phase. Analyze error, find root cause, apply fix.\n{user_prompt}\nWorkspace: {workspace}",
                expected_output="[ROOT CAUSE]  [FIX]  [VERIFY]",
                agent=agent,
                context=[tasks[0]] if tasks else None,
            )

        elif role_name == "security":
            task = Task(
                description="USTAAD Security Phase. Scan for secrets, injection, insecure config.",
                expected_output="[SECURITY SCAN]  [FINDINGS]  [VERDICT]",
                agent=agent,
                context=[tasks[-1]] if tasks else None,
            )

        elif role_name == "devops":
            task = Task(
                description=f"USTAAD Infrastructure Phase.\n{user_prompt}\nWorkspace: {workspace}\n{full_context}",
                expected_output="[INFRASTRUCTURE]  [VERIFICATION]",
                agent=agent,
                context=[tasks[0]] if tasks else None,
            )

        elif role_name == "researcher":
            task = Task(
                description=f"USTAAD Research Phase. Gather intelligence for:\n{user_prompt}\nWorkspace: {workspace}",
                expected_output="[RESEARCH]  [RECOMMENDATIONS]",
                agent=agent,
                context=[tasks[0]] if tasks else None,
            )

        else:
            continue

        agents.append(agent)
        tasks.append(task)

    # --- RUN CREW ---
    agent_phase_name = "EXECUTE"
    if route.complexity == TaskComplexity.TRIVIAL:
        agent_phase_name = "EXECUTE"
    elif route.task_type == TaskType.DEBUG:
        agent_phase_name = "DEBUG"

    with phase_spinner(agent_phase_name, f"{len(agents)} agent(s) working...") as timer:
        crew = Crew(agents=agents, tasks=tasks, verbose=True)
        result = crew.kickoff()
    pipeline.phases.append(timer)

    # --- TEST ---
    if not route.skip_tests:
        with phase_spinner("TEST", "Running automated checks...") as timer:
            test_engine = TestEngine(workspace, scan)
            test_results = test_engine.run_tests()
            lint_results = test_engine.run_linters()
            tests_passed = all(t.passed for t in test_results) if test_results else True
            lints_passed = all(l.passed for l in lint_results) if lint_results else True
        pipeline.phases.append(timer)

        for tr in test_results:
            console.print(tr.to_context_string())
        for lr in lint_results:
            console.print(lr.to_context_string())

        if not test_results and not lint_results:
            console.print("[dim]   No tests or linters detected[/dim]")

        # --- REPAIR LOOP (if tests failed) ---
        if not tests_passed:
            phase_header("REPAIR", "Tests failed — entering repair loop...")
            repair_timer = PhaseTimer(name="REPAIR")
            repair_timer.start_time = time.time()
            repair_timer.status = "running"

            try:
                from ustaad.engine.repair import RepairLoop

                def repair_fn(failures, test_output):
                    """Use the coder agent to fix failures."""
                    fix_prompt = f"""
                    Fix the following test failures:
                    {chr(10).join(failures[:5])}

                    Test output:
                    {test_output[:2000]}
                    """
                    fix_task = Task(
                        description=fix_prompt,
                        expected_output="[FIX] Applied fixes  [VERIFY] Fix verification",
                        agent=coder,
                    )
                    fix_crew = Crew(agents=[coder], tasks=[fix_task], verbose=True)
                    return str(fix_crew.kickoff())

                repair_loop = RepairLoop(workspace, repair_fn, max_attempts=3)
                repair_session = repair_loop.run()
                tests_passed = repair_session.resolved
            except Exception as e:
                console.print(f"[dim]   Repair loop error: {e}[/dim]")

            repair_timer.end_time = time.time()
            repair_timer.status = "done"
            pipeline.phases.append(repair_timer)
    else:
        tests_passed = True
        lints_passed = True
        phase = PhaseTimer(name="TEST", status="skipped")
        pipeline.phases.append(phase)

    # --- REFLECT ---
    with phase_spinner("REFLECT", "Self-evaluating...") as timer:
        reflector = ReflectionEngine()
        report = reflector.reflect(
            task_description=user_prompt,
            files_modified=[],  # TODO: track from patch engine
            test_passed=tests_passed,
            lint_passed=lints_passed,
        )
    pipeline.phases.append(timer)

    # --- COMPLETE ---
    completion_summary(
        pipeline=pipeline,
        files_created=[],
        files_modified=[],
        test_passed=tests_passed,
        lint_passed=lints_passed,
        score=report.score,
    )

    # Save to memory
    memory.save(
        f"Task: {user_prompt}\nType: {route.task_type.value}\nComplexity: {route.complexity.value}\nResult: {str(result)[:1500]}",
        category="task",
    )

    output_path = os.path.join(workspace, "ustaad_output.md")
    write_file(output_path, str(result))
    console.print(f"[dim]   📄 Output saved: {output_path}[/dim]")

    return str(result)
