"""
USTAAD Main Orchestration Engine — v3.0

The autonomous execution loop with full lifecycle event system:
- Event-driven lifecycle hooks (PreToolUse, PostToolUse, etc.)
- Session history & conversation context
- Audit logging for all operations
- Instruction cascade (AGENTS.md hierarchy)
- Secret detection on file writes
- Permission-checked tool invocations
- Smart task routing (trivial/standard/complex)
- Cached repo indexing
- Integrated repair loop
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
from ustaad.llm import load_model_for_role_and_complexity

# New v3.0 systems
from ustaad.core.events import get_event_bus, EventType
from ustaad.core.session import get_session_manager
from ustaad.core.audit import get_audit_logger
from ustaad.core.instructions import InstructionCascade
from ustaad.core.secrets import get_secret_scanner

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
    from ustaad.vscode.vscode_server import send_progress_update
    from ustaad.core.prompt_library import PromptOptimizer
    optimizer = PromptOptimizer()
    pipeline = PipelineProgress()
    pipeline.start_time = time.time()
    pipeline.task_description = user_prompt
    workspace = workspace or os.getcwd()
    mode = get_mode()

    # Initialize v3.0 systems
    event_bus = get_event_bus()
    session = get_session_manager(workspace)
    audit = get_audit_logger(workspace, session.state.session_id)
    secret_scanner = get_secret_scanner()

    # Load workspace hooks
    event_bus.load_hooks_from_config(workspace)

    # Sanitize prompt
    from ustaad.core.safety import SafetyScanner
    user_prompt = SafetyScanner.sanitize(user_prompt)

    # Emit session/task events
    event_bus.emit(EventType.TASK_CREATED, data={"prompt": user_prompt, "workspace": workspace})
    session.add_user_message(user_prompt)
    audit.log_agent_action("orchestrator", "task_created", user_prompt[:200])

    # Create safety git checkpoint before agent touches files
    from ustaad.engine.git import GitEngine
    git = GitEngine(workspace)
    safe_prompt = user_prompt[:50].replace('\n', ' ')
    git.checkpoint(f"Task: {safe_prompt}...")

    # Defaults for verification
    tests_passed = True
    lints_passed = True

    # --- MODE ---
    if mode.agentic:
        mode_label = "AGENTIC LOOP"
    elif mode.autonomous:
        mode_label = "AUTONOMOUS"
    else:
        mode_label = "SAFE" if mode.safe else "SEMI-AUTO"

    # --- SCAN ---
    send_progress_update("SCAN", "Scanning workspace structure...")
    with phase_spinner("SCAN", workspace) as timer:
        scanner = WorkspaceScanner(workspace)
        scan = scanner.scan()
        scan_ctx = scan.to_context_string()
    pipeline.phases.append(timer)

    is_empty_workspace = scan.file_count == 0

    # --- ROUTE (before heavy indexing) ---
    send_progress_update("ROUTE", "Evaluating task complexity & routing agents...")
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
        send_progress_update("INDEX", "Analyzing codebase structure & building AST index...")
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
        send_progress_update("SEARCH", "Vectorizing code blocks for semantic context search...")
        with phase_spinner("SEARCH", "Indexing code for semantic search...") as timer:
            try:
                search_engine = SearchEngine(workspace)
                chunks = search_engine.index_workspace()
            except Exception:
                search_engine = None
        pipeline.phases.append(timer)

    # --- UNDERSTAND ---
    with phase_spinner("UNDERSTAND", "Loading memory, git status & docs...") as timer:
        memory = ProjectMemory(workspace)
        mem_ctx = memory.get_context_string(user_prompt)

        git_engine = GitEngine(workspace)
        git_status = git_engine.status()
        git_ctx = git_status.to_context_string()

        # Dynamic RAG Documentation Query
        rag_ctx = ""
        try:
            docs_dir = os.path.join(workspace, "docs")
            if os.path.isdir(docs_dir):
                from ustaad.rag.rag_system import RAGSystem
                rag = RAGSystem(docs_dir=docs_dir)
                rag_results = rag.query(user_prompt)
                if rag_results and "No documentation files" not in rag_results and "No matching documentation" not in rag_results:
                    rag_ctx = rag_results
        except Exception:
            pass
    pipeline.phases.append(timer)

    # --- BUILD CONTEXT (trimmed per complexity) ---
    from ustaad.core.skills import ContextBuilder, SkillManager
    
    # v3.0: Use instruction cascade instead of simple ContextBuilder
    cascade = InstructionCascade(workspace)
    cascaded_instructions = cascade.load_all()
    
    # Fallback to legacy ContextBuilder for backwards compatibility
    context_builder = ContextBuilder(workspace)
    agents_md = context_builder.load_agents_md()
    ai_md = context_builder.load_ai_md()
    
    skill_manager = SkillManager(workspace)
    skill_manager.index_skills()
    active_skills = skill_manager.retrieve_skills(user_prompt)
    
    skills_ctx = ""
    if active_skills:
        skill_docs = []
        for s in active_skills:
            skill_docs.append(f"--- SKILL: {s['name']} ---\n{s['body']}")
        skills_ctx = "\n\n".join(skill_docs)

    # v3.0: Include session history for conversation continuity
    session_ctx = session.get_context_string(max_messages=10)

    ctx = ContextManager(max_chars=route.context_budget)
    ctx.add("USER REQUEST", user_prompt, priority=1)
    
    # Use cascaded instructions (AGENTS.md hierarchy) if available, fallback to legacy
    if cascaded_instructions:
        ctx.add("PROJECT INSTRUCTIONS (Cascaded)", cascaded_instructions, priority=2)
    else:
        if agents_md:
            ctx.add("AGENT INSTRUCTIONS (AGENTS.md)", agents_md, priority=2)
        if ai_md:
            ctx.add("PROJECT CONVENTIONS (AI.md)", ai_md, priority=3)

    if skills_ctx:
        ctx.add("ACTIVE SKILLS", skills_ctx, priority=4)
    if session_ctx:
        ctx.add("SESSION HISTORY", session_ctx, priority=5)
        
    ctx.add("PLATFORM", f"OS: {platform.system()} | Shell: {'PowerShell/CMD' if sys.platform == 'win32' else 'bash'} | IMPORTANT: Use write_file tool to create files, NEVER shell commands.", priority=6)
    ctx.add("WORKSPACE SCAN", scan_ctx, priority=7)
    ctx.add("WORKSPACE PATH", workspace, priority=8)

    # Only add heavy context for standard/complex tasks
    if route.complexity != TaskComplexity.TRIVIAL:
        ctx.add("REPOSITORY INDEX", idx_ctx, priority=10)
        ctx.add("GIT STATUS", git_ctx, priority=15)
        ctx.add("MEMORY", mem_ctx, priority=20)
        if rag_ctx:
            ctx.add("WORKSPACE DOCUMENTATION", rag_ctx, priority=9)
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

    # Load dynamic plugins and extend tools for the coder agent
    try:
        from ustaad.core.plugin_system import PluginSystem
        plugin_system = PluginSystem(workspace)
        loaded_count = plugin_system.load_all_plugins()
        if loaded_count > 0:
            console.print(f"[bold green]✓ Loaded {loaded_count} dynamic plugin(s) with {len(plugin_system.loaded_tools)} tools.[/bold green]")
            dynamic_tools = plugin_system.get_all_tools()
            for dt in dynamic_tools:
                if dt not in coder.tools:
                    coder.tools.append(dt)
    except Exception as e:
        console.print(f"[yellow]   ⚠ Failed to load dynamic plugins: {e}[/yellow]")

    # Load MCP Servers
    try:
        from ustaad.mcp.client import MCPClientManager
        mcp_manager = MCPClientManager(workspace)
        mcp_manager.connect_all()
        if mcp_manager.tools:
            for tool in mcp_manager.tools:
                if tool not in coder.tools:
                    coder.tools.append(tool)
    except ImportError:
        pass # MCP SDK not installed
    except Exception as e:
        console.print(f"[yellow]   ⚠ Failed to connect to MCP Servers: {e}[/yellow]")

    # --- BUILD PIPELINE based on routing decision ---
    agents = []
    tasks = []

    for role_name in route.agents_needed:
        if role_name == "browser":
            from ustaad.browser.browser_agent import get_browser_agent
            agent = get_browser_agent(llm=load_model_for_role_and_complexity(role_name, route.complexity.value))
        else:
            agent = AGENT_REGISTRY.get(role_name)
            if not agent:
                continue

            # Dynamically assign the complexity-specific local model for optimal speed & power
            agent.llm = load_model_for_role_and_complexity(role_name, route.complexity.value)

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
            optimized_rules = optimizer.compile_instructions("CODE")
            
            agentic_instructions = ""
            if mode.agentic:
                agentic_instructions = """
                [AGENTIC MODE ENABLED]
                You are the sole Lead Agent operating in a continuous ReAct loop.
                You must:
                1. Explore the codebase using `ripgrep_search` and `run_command` (e.g., ls, cat, etc).
                2. Plan your approach internally.
                3. Write or patch files.
                4. RUN TESTS using `run_command` to verify your code. Do NOT complete the task until tests pass.
                5. If tests fail, diagnose and fix them iteratively.
                """

            task = Task(
                description=f"""
                USTAAD Execution Phase. Implement the plan.
                Request: {user_prompt}
                Workspace: {workspace}
                Platform: {platform.system()}
                
                {optimized_rules}
                {agentic_instructions}
                
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
            optimized_rules = optimizer.compile_instructions("DEBUG")
            task = Task(
                description=f"USTAAD Debug Phase. Analyze error, find root cause, apply fix.\n{user_prompt}\nWorkspace: {workspace}\n\n{optimized_rules}",
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
            optimized_rules = optimizer.compile_instructions("RESEARCH")
            task = Task(
                description=f"USTAAD Research Phase. Gather intelligence for:\n{user_prompt}\nWorkspace: {workspace}\n\n{optimized_rules}",
                expected_output="[RESEARCH]  [RECOMMENDATIONS]",
                agent=agent,
                context=[tasks[0]] if tasks else None,
            )

        elif role_name == "browser":
            task = Task(
                description=f"USTAAD Browsing & Web Intelligence Phase. Navigate target URLs, extract documentation, and gather information for:\n{user_prompt}",
                expected_output="[BROWSED URLS]  [EXTRACTED DETAILS]  [SYNTHESIZED SUMMARY]",
                agent=agent,
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

    send_progress_update(agent_phase_name, "Swarm agents executing roles...")
    event_bus.emit(EventType.PIPELINE_PHASE_START, data={"phase": agent_phase_name, "agents": route.agents_needed})
    
    crew = Crew(agents=agents, tasks=tasks, verbose=False)
    result = None
    
    with phase_spinner(agent_phase_name, "Agents analyzing and coding...") as timer:
        for attempt in range(2):  # 1 retry on timeout
            try:
                result = crew.kickoff()
                break
            except Exception as e:
                err_str = str(e)
                if attempt == 0 and ("timeout" in err_str.lower() or "connection" in err_str.lower()):
                    console.print(f"[yellow]   ⚠ LLM timeout — retrying (attempt 2/2)...[/yellow]")
                    audit.log_agent_action("orchestrator", "retry", f"LLM timeout on attempt 1: {err_str[:200]}")
                    continue
                console.print(f"\n[red]   ✗ Crew execution failed: {err_str[:200]}[/red]")
                result = f"[ERROR] Pipeline failed: {err_str[:500]}"
                event_bus.emit(EventType.TASK_FAILED, data={"error": err_str[:500]})
                audit.log_agent_action("orchestrator", "pipeline_failed", err_str[:200])
                break
        if result is None:
            result = "[ERROR] Pipeline failed after 2 attempts (LLM timeout)"
            console.print(f"\n[red]   ✗ {result}[/red]")
            
    pipeline.phases.append(timer)
    event_bus.emit(EventType.PIPELINE_PHASE_END, data={"phase": agent_phase_name, "duration": timer.end_time - timer.start_time})

    # --- FAILSAFE FILE EXTRACTION ---
    try:
        from ustaad.core.failsafe import extract_and_materialize_files
        written_files = extract_and_materialize_files(str(result), workspace)
        
        # v3.0: Scan extracted files for secrets
        for wf in (written_files or []):
            try:
                findings = secret_scanner.scan_file(wf)
                if findings:
                    console.print(f"[bold yellow]   ⚠ SECRET DETECTED in {wf}:[/bold yellow]")
                    console.print(f"[yellow]     {secret_scanner.format_findings(findings)}[/yellow]")
                    audit.log_security_event("secret_detected", "high", f"Secret found in {wf}")
                    event_bus.emit(EventType.FILE_CHANGED, data={"path": wf, "secrets_found": len(findings)})
                else:
                    event_bus.emit(EventType.POST_FILE_WRITE, data={"path": wf})
                    audit.log_file_operation("failsafe", "write", wf)
            except Exception:
                pass
    except Exception as fe:
        console.print(f"[dim yellow]   ⚠ Failsafe file extractor failed: {fe}[/dim yellow]")

    # --- TEST ---
    if not route.skip_tests:
        send_progress_update("TEST", "Running automated verification tests...")
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
                    fix_crew = Crew(agents=[coder], tasks=[fix_task], verbose=False)
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
    # Fetch latest git status to detect actual created/modified files
    try:
        latest_git_status = git_engine.status()
        files_created = latest_git_status.untracked
        files_modified = list(set(latest_git_status.staged + latest_git_status.modified))
        touched_files = list(set(files_created + files_modified))
    except Exception:
        files_created = []
        files_modified = []
        touched_files = []

    with phase_spinner("REFLECT", "Self-evaluating...") as timer:
        reflector = ReflectionEngine()
        report = reflector.reflect(
            task_description=user_prompt,
            files_modified=touched_files,
            test_passed=tests_passed,
            lint_passed=lints_passed,
        )
    pipeline.phases.append(timer)

    # Log telemetry for self-improving prompt optimizer
    try:
        optimizer.record_execution(
            task_type=route.task_type.value,
            score=report.score,
            duration=time.time() - pipeline.start_time,
            model=route.model_override or "cieloforge/qwen2.5-coder-7b-instruct-spec:latest",
            error_occurred=not tests_passed
        )
    except Exception as telemetry_error:
        console.print(f"[dim yellow]   ⚠ Telemetry recording skipped: {telemetry_error}[/dim yellow]")

    # --- COMPLETE ---
    completion_summary(
        pipeline=pipeline,
        files_created=files_created,
        files_modified=files_modified,
        test_passed=tests_passed,
        lint_passed=lints_passed,
        score=report.score,
    )

    # Save to memory
    memory.save(
        f"Task: {user_prompt}\nType: {route.task_type.value}\nComplexity: {route.complexity.value}\nResult: {str(result)[:1500]}",
        category="task",
    )

    # v3.0: Save to session history
    session.add_assistant_message(str(result)[:3000], metadata={
        "task_type": route.task_type.value,
        "complexity": route.complexity.value,
        "score": report.score,
        "files_created": files_created,
        "files_modified": files_modified,
    })

    output_path = os.path.join(workspace, "ustaad_output.md")
    write_file(output_path, str(result))
    console.print(f"[dim]   📄 Output saved: {output_path}[/dim]")

    # v3.0: Emit completion events and log audit
    event_bus.emit(EventType.TASK_COMPLETED, data={
        "prompt": user_prompt[:200],
        "score": report.score,
        "duration": time.time() - pipeline.start_time,
        "files_created": len(files_created),
        "files_modified": len(files_modified),
    })
    audit.log_agent_action("orchestrator", "task_completed", f"Score: {report.score:.2f}, Files: {len(touched_files)}")

    send_progress_update("COMPLETE", "Task finalized and outputs compiled.", "done")

    return str(result)
