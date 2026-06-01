"""
USTAAD Subagent System — Isolated Execution Contexts

Implements isolated subagents with independent contexts, memory,
and result summarization. Supports:

- Spawning specialized subagents (security, refactor, test, docs, etc.)
- Independent context windows per subagent
- Supervisor orchestration pattern
- Result summarization and aggregation
- Parallel execution via threading
- Recursive delegation
"""

import os
import time
import uuid
import threading
from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, Future, as_completed

from rich.console import Console

console = Console()


class SubagentRole(str, Enum):
    """Built-in subagent roles."""
    SECURITY_AUDITOR = "security_auditor"
    REFACTORING = "refactoring"
    TESTING = "testing"
    DOCUMENTATION = "documentation"
    ARCHITECTURE = "architecture"
    DEVOPS = "devops"
    PERFORMANCE = "performance"
    CODE_REVIEW = "code_review"
    RESEARCH = "research"
    CUSTOM = "custom"


@dataclass
class SubagentResult:
    """Result from a subagent execution."""
    agent_id: str
    role: str
    status: str = "pending"  # pending, running, completed, failed
    result: str = ""
    error: str = ""
    duration: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_context_string(self) -> str:
        """Format result for injection into parent context."""
        status_icon = "✓" if self.status == "completed" else "✗"
        return f"[SUBAGENT:{self.role.upper()}] {status_icon} {self.result[:1000]}"


@dataclass 
class SubagentConfig:
    """Configuration for spawning a subagent."""
    role: SubagentRole
    task_description: str
    context: str = ""  # Additional context for the subagent
    workspace: str = ""
    max_context_chars: int = 30_000
    timeout: int = 300  # seconds
    model_override: str = ""
    tools_override: List[str] = field(default_factory=list)


class SubagentManager:
    """
    Manages subagent spawning, execution, and result collection.
    
    Usage:
        manager = SubagentManager(workspace)
        
        # Spawn a single subagent
        result = manager.spawn(SubagentConfig(
            role=SubagentRole.SECURITY_AUDITOR,
            task_description="Scan for vulnerabilities",
        ))
        
        # Spawn multiple subagents in parallel
        results = manager.spawn_parallel([config1, config2, config3])
        
        # Get aggregated summary
        summary = manager.summarize_results(results)
    """

    def __init__(self, workspace: str):
        self.workspace = os.path.abspath(workspace)
        self._active_agents: Dict[str, SubagentResult] = {}
        self._executor = ThreadPoolExecutor(max_workers=3)

    def spawn(self, config: SubagentConfig) -> SubagentResult:
        """Spawn a single subagent and wait for completion."""
        agent_id = str(uuid.uuid4())[:8]
        result = SubagentResult(agent_id=agent_id, role=config.role.value)
        self._active_agents[agent_id] = result

        try:
            result.status = "running"
            start = time.time()

            # Build the subagent prompt with isolated context
            prompt = self._build_subagent_prompt(config)

            # Execute via CrewAI single-agent crew
            output = self._execute_subagent(config, prompt)

            result.result = str(output)[:5000]
            result.status = "completed"
            result.duration = time.time() - start

        except Exception as e:
            result.status = "failed"
            result.error = str(e)[:500]

        return result

    def spawn_parallel(self, configs: List[SubagentConfig]) -> List[SubagentResult]:
        """Spawn multiple subagents in parallel."""
        futures: Dict[Future, SubagentConfig] = {}
        results: List[SubagentResult] = []

        for config in configs:
            future = self._executor.submit(self.spawn, config)
            futures[future] = config

        for future in as_completed(futures, timeout=max(c.timeout for c in configs)):
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                config = futures[future]
                results.append(SubagentResult(
                    agent_id="error",
                    role=config.role.value,
                    status="failed",
                    error=str(e),
                ))

        return results

    def spawn_supervisor(
        self,
        task: str,
        roles: List[SubagentRole],
    ) -> str:
        """
        Supervisor orchestration pattern.
        Spawns multiple subagents, collects results, and synthesizes.
        """
        configs = []
        for role in roles:
            configs.append(SubagentConfig(
                role=role,
                task_description=task,
                workspace=self.workspace,
            ))

        # Execute all subagents
        console.print(f"[bold cyan]🔄 Spawning {len(configs)} subagents...[/bold cyan]")
        results = self.spawn_parallel(configs)

        # Summarize
        return self.summarize_results(results)

    def _build_subagent_prompt(self, config: SubagentConfig) -> str:
        """Build an isolated prompt for a subagent."""
        role_instructions = {
            SubagentRole.SECURITY_AUDITOR: (
                "You are a security auditor. Scan for: hardcoded secrets, injection vulnerabilities, "
                "auth issues, insecure configs, and OWASP Top 10 issues. Report severity levels."
            ),
            SubagentRole.REFACTORING: (
                "You are a refactoring specialist. Identify code smells, suggest improvements, "
                "and apply clean code principles. Preserve all existing functionality."
            ),
            SubagentRole.TESTING: (
                "You are a test engineer. Generate comprehensive tests including unit, "
                "integration, and edge case tests. Use the project's existing test framework."
            ),
            SubagentRole.DOCUMENTATION: (
                "You are a documentation specialist. Generate clear, comprehensive documentation "
                "including API docs, architecture notes, and usage guides."
            ),
            SubagentRole.ARCHITECTURE: (
                "You are a software architect. Analyze the codebase architecture, identify "
                "patterns and anti-patterns, and suggest structural improvements."
            ),
            SubagentRole.DEVOPS: (
                "You are a DevOps engineer. Handle infrastructure, CI/CD, Docker, "
                "deployment configurations, and monitoring setup."
            ),
            SubagentRole.PERFORMANCE: (
                "You are a performance engineer. Profile the codebase, identify bottlenecks, "
                "and suggest optimizations for speed and resource usage."
            ),
            SubagentRole.CODE_REVIEW: (
                "You are a senior code reviewer. Review all changes for correctness, "
                "security, performance, and adherence to project conventions."
            ),
            SubagentRole.RESEARCH: (
                "You are a technical researcher. Investigate technologies, APIs, "
                "best practices, and provide actionable recommendations."
            ),
        }

        role_prompt = role_instructions.get(config.role, "You are a specialized agent.")

        prompt = f"{role_prompt}\n\nTask: {config.task_description}"
        if config.context:
            prompt += f"\n\nAdditional Context:\n{config.context}"
        prompt += f"\n\nWorkspace: {config.workspace or self.workspace}"

        return prompt

    def _execute_subagent(self, config: SubagentConfig, prompt: str) -> str:
        """Execute a subagent using CrewAI."""
        try:
            from crewai import Agent, Task, Crew
            from ustaad.llm import load_model_for_role_and_complexity
            from ustaad.tools.file_tools import read_file_tool, list_directory_tool, search_files_tool
            from ustaad.tools.shell_tools import run_command_tool, ripgrep_search_tool
            from ustaad.tools.search_tools import semantic_search_tool

            # Map role to LLM role name
            role_map = {
                SubagentRole.SECURITY_AUDITOR: "security",
                SubagentRole.REFACTORING: "coder",
                SubagentRole.TESTING: "coder",
                SubagentRole.DOCUMENTATION: "researcher",
                SubagentRole.ARCHITECTURE: "planner",
                SubagentRole.DEVOPS: "devops",
                SubagentRole.PERFORMANCE: "reviewer",
                SubagentRole.CODE_REVIEW: "reviewer",
                SubagentRole.RESEARCH: "researcher",
            }

            llm_role = role_map.get(config.role, "coder")
            llm = load_model_for_role_and_complexity(llm_role, "standard")

            if config.model_override:
                from ustaad.llm import load_model
                llm = load_model(config.model_override)

            agent = Agent(
                role=f"Subagent: {config.role.value}",
                goal=config.task_description[:200],
                backstory=prompt[:2000],
                verbose=False,
                allow_delegation=False,
                tools=[read_file_tool, list_directory_tool, search_files_tool,
                       run_command_tool, ripgrep_search_tool, semantic_search_tool],
                llm=llm,
            )

            task = Task(
                description=prompt,
                expected_output=f"[{config.role.value.upper()}] Detailed analysis and findings",
                agent=agent,
            )

            crew = Crew(agents=[agent], tasks=[task], verbose=False)
            result = crew.kickoff()
            return str(result)

        except Exception as e:
            return f"Subagent execution error: {e}"

    def summarize_results(self, results: List[SubagentResult]) -> str:
        """Aggregate and summarize results from multiple subagents."""
        lines = [f"[SUPERVISOR] Aggregated results from {len(results)} subagent(s):"]

        completed = [r for r in results if r.status == "completed"]
        failed = [r for r in results if r.status == "failed"]

        if completed:
            lines.append(f"\n  ✓ {len(completed)} succeeded:")
            for r in completed:
                lines.append(f"    [{r.role.upper()}] ({r.duration:.1f}s)")
                lines.append(f"    {r.result[:300]}")

        if failed:
            lines.append(f"\n  ✗ {len(failed)} failed:")
            for r in failed:
                lines.append(f"    [{r.role.upper()}] Error: {r.error[:200]}")

        return "\n".join(lines)

    def get_active_agents(self) -> Dict[str, SubagentResult]:
        """Get all currently active subagents."""
        return {k: v for k, v in self._active_agents.items() if v.status == "running"}

    def shutdown(self):
        """Shutdown the executor."""
        self._executor.shutdown(wait=False)
