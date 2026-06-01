"""
USTAAD Extensible Command Framework

Plugin-based slash command system that replaces the hardcoded elif chain.
Commands can be registered by:
1. Built-in core commands
2. Plugins from .ustaad/plugins/
3. Skills that expose commands
4. User-defined commands

Each command is a callable with a standard interface:
    def my_command(args: list[str], context: CommandContext) -> None

Commands support:
- Auto-completion
- Help text
- Argument parsing
- Category grouping
- Plugin registration
"""

import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()


@dataclass
class CommandContext:
    """Context passed to every command handler."""
    workspace: str = ""
    args: List[str] = field(default_factory=list)
    raw_input: str = ""
    session: Any = None  # SessionManager
    event_bus: Any = None  # EventBus
    console: Console = field(default_factory=Console)


@dataclass
class CommandDefinition:
    """A registered slash command."""
    name: str  # e.g. "/review"
    handler: Callable  # function(args, context) -> None
    description: str = ""
    category: str = "General"
    usage: str = ""  # e.g. "/review <file_path>"
    aliases: List[str] = field(default_factory=list)
    hidden: bool = False  # Don't show in /help
    requires_args: bool = False
    min_args: int = 0
    source: str = "builtin"  # "builtin", "plugin", "skill", "user"


class CommandRegistry:
    """
    Central registry for all slash commands.
    
    Usage:
        registry = get_command_registry()
        
        # Register a command
        registry.register("/review", handler_fn, description="Review code changes")
        
        # Execute a command
        registry.execute("/review", ["main.py"], context)
        
        # Get completions
        completions = registry.get_completions("/re")
    """

    def __init__(self):
        self._commands: Dict[str, CommandDefinition] = {}
        self._alias_map: Dict[str, str] = {}  # alias -> canonical name

    def register(
        self,
        name: str,
        handler: Callable,
        description: str = "",
        category: str = "General",
        usage: str = "",
        aliases: List[str] = None,
        hidden: bool = False,
        requires_args: bool = False,
        min_args: int = 0,
        source: str = "builtin",
    ) -> CommandDefinition:
        """Register a slash command."""
        if not name.startswith("/"):
            name = f"/{name}"

        cmd = CommandDefinition(
            name=name,
            handler=handler,
            description=description,
            category=category,
            usage=usage or name,
            aliases=aliases or [],
            hidden=hidden,
            requires_args=requires_args,
            min_args=min_args,
            source=source,
        )
        self._commands[name] = cmd

        # Register aliases
        for alias in cmd.aliases:
            if not alias.startswith("/"):
                alias = f"/{alias}"
            self._alias_map[alias] = name

        return cmd

    def unregister(self, name: str):
        """Remove a command."""
        if not name.startswith("/"):
            name = f"/{name}"
        if name in self._commands:
            # Remove aliases
            for alias in self._commands[name].aliases:
                key = alias if alias.startswith("/") else f"/{alias}"
                self._alias_map.pop(key, None)
            del self._commands[name]

    def execute(self, name: str, args: List[str], context: CommandContext) -> bool:
        """
        Execute a slash command.
        Returns True if command was found and executed, False otherwise.
        """
        if not name.startswith("/"):
            name = f"/{name}"

        # Resolve alias
        canonical = self._alias_map.get(name, name)
        cmd = self._commands.get(canonical)

        if not cmd:
            return False

        # Check argument requirements
        if cmd.requires_args and not args:
            console.print(f"[yellow]Usage: {cmd.usage}[/yellow]")
            return True

        if len(args) < cmd.min_args:
            console.print(f"[yellow]Usage: {cmd.usage}[/yellow]")
            return True

        # Execute
        try:
            context.args = args
            cmd.handler(args, context)
        except Exception as e:
            console.print(f"[bold red]✗ Command {name} failed: {e}[/bold red]")

        return True

    def get_completions(self, prefix: str) -> List[Dict[str, str]]:
        """Get command completions for a prefix."""
        results = []
        for name, cmd in self._commands.items():
            if cmd.hidden:
                continue
            if name.startswith(prefix):
                results.append({"name": name, "description": cmd.description})
            for alias in cmd.aliases:
                a = alias if alias.startswith("/") else f"/{alias}"
                if a.startswith(prefix):
                    results.append({"name": a, "description": f"{cmd.description} (alias for {name})"})
        return results

    def get_all_commands(self, include_hidden: bool = False) -> Dict[str, CommandDefinition]:
        """Get all registered commands."""
        if include_hidden:
            return dict(self._commands)
        return {k: v for k, v in self._commands.items() if not v.hidden}

    def get_by_category(self) -> Dict[str, List[CommandDefinition]]:
        """Group commands by category."""
        categories: Dict[str, List[CommandDefinition]] = {}
        for cmd in self._commands.values():
            if cmd.hidden:
                continue
            if cmd.category not in categories:
                categories[cmd.category] = []
            categories[cmd.category].append(cmd)
        return categories

    def has_command(self, name: str) -> bool:
        """Check if a command is registered."""
        if not name.startswith("/"):
            name = f"/{name}"
        canonical = self._alias_map.get(name, name)
        return canonical in self._commands

    def print_help(self):
        """Print formatted help for all commands."""
        categories = self.get_by_category()

        table = Table(show_header=True, box=None, padding=(0, 2), header_style="bold cyan")
        table.add_column("Command", style="bold cyan", width=26)
        table.add_column("Category", style="magenta", width=18)
        table.add_column("Description", style="dim")

        for cat_name in sorted(categories.keys()):
            for cmd in sorted(categories[cat_name], key=lambda c: c.name):
                aliases_str = ""
                if cmd.aliases:
                    aliases_str = f" ({', '.join(cmd.aliases)})"
                table.add_row(
                    cmd.usage + aliases_str,
                    cat_name,
                    cmd.description,
                )

        console.print(Panel(
            table,
            title="[bold cyan]⚡ USTAAD Command Map[/bold cyan]",
            border_style="dim",
            padding=(0, 1),
        ))


# ---------------------------------------------------------------------------
# Built-in smart commands (Phase 2 implementations)
# ---------------------------------------------------------------------------

def cmd_review(args: List[str], ctx: CommandContext):
    """Review code changes using the reviewer agent."""
    from ustaad.main import run_task

    target = " ".join(args) if args else "all recent changes"
    prompt = f"Review the following code for bugs, security issues, and best practice violations: {target}"
    result = run_task(prompt, workspace=ctx.workspace)

    from rich.markdown import Markdown
    console.print(Markdown(str(result)))


def cmd_fix(args: List[str], ctx: CommandContext):
    """Automatically fix issues in the codebase."""
    from ustaad.main import run_task

    target = " ".join(args) if args else "any failing tests or lint errors"
    prompt = f"[debug] Fix the following issue: {target}"
    result = run_task(prompt, workspace=ctx.workspace)

    from rich.markdown import Markdown
    console.print(Markdown(str(result)))


def cmd_refactor(args: List[str], ctx: CommandContext):
    """Refactor code for better quality."""
    from ustaad.main import run_task

    target = " ".join(args) if args else "the codebase"
    prompt = f"Refactor {target} for improved readability, maintainability, and performance. Preserve all existing functionality."
    result = run_task(prompt, workspace=ctx.workspace)

    from rich.markdown import Markdown
    console.print(Markdown(str(result)))


def cmd_test_generate(args: List[str], ctx: CommandContext):
    """Generate tests for the specified code."""
    from ustaad.main import run_task

    target = " ".join(args) if args else "the main modules"
    prompt = f"Generate comprehensive unit tests for {target}. Use pytest. Include edge cases, error cases, and happy paths."
    result = run_task(prompt, workspace=ctx.workspace)

    from rich.markdown import Markdown
    console.print(Markdown(str(result)))


def cmd_security_scan(args: List[str], ctx: CommandContext):
    """Run a security scan on the codebase."""
    from ustaad.main import run_task

    target = " ".join(args) if args else "the entire codebase"
    prompt = f"Perform a thorough security audit of {target}. Scan for: hardcoded secrets, injection vulnerabilities, auth issues, insecure configs, and dependency vulnerabilities."
    result = run_task(prompt, workspace=ctx.workspace)

    from rich.markdown import Markdown
    console.print(Markdown(str(result)))


def cmd_docs_generate(args: List[str], ctx: CommandContext):
    """Generate documentation for the codebase."""
    from ustaad.main import run_task

    target = " ".join(args) if args else "the project"
    prompt = f"Generate comprehensive documentation for {target}. Include: API docs, architecture overview, setup instructions, and usage examples."
    result = run_task(prompt, workspace=ctx.workspace)

    from rich.markdown import Markdown
    console.print(Markdown(str(result)))


def cmd_commit(args: List[str], ctx: CommandContext):
    """Auto-generate a commit message and commit changes."""
    import subprocess

    # Get staged diff
    try:
        diff_result = subprocess.run(
            ["git", "diff", "--cached", "--stat"],
            capture_output=True, text=True, cwd=ctx.workspace,
        )
        if not diff_result.stdout.strip():
            # Auto-stage all changes
            subprocess.run(["git", "add", "-A"], cwd=ctx.workspace, capture_output=True)
            diff_result = subprocess.run(
                ["git", "diff", "--cached", "--stat"],
                capture_output=True, text=True, cwd=ctx.workspace,
            )

        if not diff_result.stdout.strip():
            console.print("[yellow]No changes to commit.[/yellow]")
            return

        # Get detailed diff for message generation
        detailed_diff = subprocess.run(
            ["git", "diff", "--cached"],
            capture_output=True, text=True, cwd=ctx.workspace,
        )

        if args:
            commit_msg = " ".join(args)
        else:
            # Auto-generate commit message
            from ustaad.main import run_task
            prompt = f"Generate a concise, conventional commit message (1 line, max 72 chars) for these changes. Output ONLY the message, nothing else:\n\n{detailed_diff.stdout[:3000]}"
            commit_msg = str(run_task(prompt, workspace=ctx.workspace)).strip()
            # Clean up the message
            commit_msg = commit_msg.strip('"\'').split("\n")[0][:72]

        console.print(f"[bold cyan]Commit message:[/bold cyan] {commit_msg}")

        result = subprocess.run(
            ["git", "commit", "-m", commit_msg],
            capture_output=True, text=True, cwd=ctx.workspace,
        )

        if result.returncode == 0:
            console.print(f"[bold green]✓ Committed successfully[/bold green]")
        else:
            console.print(f"[bold red]✗ Commit failed: {result.stderr}[/bold red]")

    except Exception as e:
        console.print(f"[bold red]✗ Commit error: {e}[/bold red]")


def cmd_explain(args: List[str], ctx: CommandContext):
    """Explain code or a concept."""
    from ustaad.main import run_task

    target = " ".join(args) if args else "the current codebase architecture"
    prompt = f"Explain {target} in detail. Be thorough but concise. Include code references where applicable."
    result = run_task(prompt, workspace=ctx.workspace)

    from rich.markdown import Markdown
    console.print(Markdown(str(result)))


def cmd_analyze(args: List[str], ctx: CommandContext):
    """Analyze the codebase for issues and improvements."""
    from ustaad.main import run_task

    target = " ".join(args) if args else "the entire codebase"
    prompt = f"Analyze {target} and provide: 1) Architecture assessment 2) Code quality metrics 3) Performance bottlenecks 4) Security concerns 5) Suggested improvements"
    result = run_task(prompt, workspace=ctx.workspace)

    from rich.markdown import Markdown
    console.print(Markdown(str(result)))


def cmd_simplify(args: List[str], ctx: CommandContext):
    """Simplify complex code."""
    from ustaad.main import run_task

    target = " ".join(args) if args else "the most complex modules"
    prompt = f"Simplify {target}. Reduce complexity, remove dead code, extract common patterns, and improve readability. Preserve all functionality."
    result = run_task(prompt, workspace=ctx.workspace)

    from rich.markdown import Markdown
    console.print(Markdown(str(result)))


def cmd_deploy(args: List[str], ctx: CommandContext):
    """Deploy or prepare for deployment."""
    from ustaad.main import run_task

    target = " ".join(args) if args else "the project"
    prompt = f"Prepare {target} for deployment. Create or update: Dockerfile, docker-compose.yaml, CI/CD configuration, and deployment documentation."
    result = run_task(prompt, workspace=ctx.workspace)

    from rich.markdown import Markdown
    console.print(Markdown(str(result)))


def cmd_batch(args: List[str], ctx: CommandContext):
    """Run multiple commands in sequence from a file."""
    if not args:
        console.print("[yellow]Usage: /batch <file_path>[/yellow]")
        console.print("[dim]File should contain one command per line.[/dim]")
        return

    batch_file = args[0]
    if not os.path.isfile(batch_file):
        console.print(f"[red]Batch file not found: {batch_file}[/red]")
        return

    try:
        with open(batch_file, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip() and not line.startswith("#")]

        console.print(f"[bold cyan]Running {len(lines)} batch commands...[/bold cyan]")

        for i, line in enumerate(lines, 1):
            console.print(f"\n[bold yellow]--- Batch [{i}/{len(lines)}]: {line} ---[/bold yellow]")
            from ustaad.main import run_task
            result = run_task(line, workspace=ctx.workspace)
            console.print(f"[dim]Completed {i}/{len(lines)}[/dim]")

        console.print(f"\n[bold green]✓ Batch complete: {len(lines)} commands executed[/bold green]")

    except Exception as e:
        console.print(f"[bold red]✗ Batch execution failed: {e}[/bold red]")


def cmd_undo(args: List[str], ctx: CommandContext):
    """Undo the last agent action by reverting git changes."""
    from ustaad.engine.git import GitEngine
    
    git = GitEngine(ctx.workspace)
    console.print("[yellow]Attempting to undo last USTAAD action...[/yellow]")
    res = git.undo()
    if "✓" in res:
        console.print(f"[bold green]{res}[/bold green]")
    else:
        console.print(f"[yellow]{res}[/yellow]")


def cmd_bg(args: List[str], ctx: CommandContext):
    """Run a prompt as a background task."""
    if not args:
        console.print("[yellow]Usage: /bg <prompt>[/yellow]")
        return
        
    prompt = " ".join(args)
    from ustaad.core.background import get_background_manager
    from ustaad.main import run_task
    
    bg = get_background_manager()
    
    def _run_bg():
        return run_task(prompt, workspace=ctx.workspace)
        
    task_id = bg.submit(f"Prompt: {prompt[:30]}...", _run_bg)
    console.print(f"[bold green]✓ Started background task '{task_id}'[/bold green]")
    console.print(f"[dim]Use /jobs to check status[/dim]")


def cmd_jobs(args: List[str], ctx: CommandContext):
    """List all background tasks."""
    from ustaad.core.background import get_background_manager
    from rich.table import Table
    import time
    
    bg = get_background_manager()
    tasks = bg.list_tasks()
    
    if not tasks:
        console.print("[dim]No background tasks running.[/dim]")
        return
        
    table = Table(title="Background Tasks", show_header=True)
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="white")
    table.add_column("Status", style="bold")
    table.add_column("Duration (s)", justify="right")
    
    for t in tasks:
        dur = (t.end_time or time.time()) - t.start_time
        status_color = "yellow" if t.status == "running" else "green" if t.status == "completed" else "red"
        table.add_row(t.id, t.name, f"[{status_color}]{t.status}[/{status_color}]", f"{dur:.1f}")
        
    console.print(table)


def cmd_team(args: List[str], ctx: CommandContext):
    """Run a pre-configured subagent team."""
    from ustaad.core.teams import AgentTeams
    from ustaad.core.subagents import SubagentManager
    from rich.table import Table
    
    if not args:
        console.print("[yellow]Usage: /team <team_name> <task>[/yellow]")
        console.print("Available teams:")
        teams = AgentTeams.list_teams()
        for t, roles in teams.items():
            console.print(f"  - [cyan]{t}[/cyan] ({', '.join(roles)})")
        return
        
    team_name = args[0]
    task = " ".join(args[1:])
    roles = AgentTeams.get_team(team_name)
    
    if not roles:
        console.print(f"[red]Unknown team: {team_name}[/red]")
        return
        
    if not task:
        console.print("[yellow]Please provide a task description for the team.[/yellow]")
        return
        
    console.print(f"[bold cyan]🚀 Starting team '{team_name}'...[/bold cyan]")
    manager = SubagentManager(ctx.workspace)
    summary = manager.spawn_supervisor(task, roles)
    
    from rich.markdown import Markdown
    console.print(Markdown(summary))

def cmd_workflow(args: List[str], ctx: CommandContext):
    """Run a pre-configured multi-step YAML workflow."""
    from ustaad.core.workflows import WorkflowEngine
    engine = WorkflowEngine(ctx.workspace)
    
    if not args:
        workflows = engine.list_workflows()
        if not workflows:
            console.print("[yellow]No workflows found in .ustaad/workflows/[/yellow]")
            return
        console.print("[cyan]Available Workflows:[/cyan]")
        for w in workflows:
            console.print(f"  - {w}")
        return
        
    name = args[0]
    console.print(f"[bold cyan]🚀 Running Workflow: {name}...[/bold cyan]")
    result = engine.run_workflow(name)
    console.print(result)


def cmd_ci(args: List[str], ctx: CommandContext):
    """Interact with CI/CD pipelines (GitHub Actions, GitLab)."""
    from ustaad.core.ci_cd import CIIntegration
    ci = CIIntegration(ctx.workspace)
    
    if not args or args[0] == "status":
        console.print(f"[cyan]CI/CD Provider:[/cyan] {ci.detect_provider()}")
        console.print("[cyan]Latest Pipeline Runs:[/cyan]")
        console.print(ci.get_status())
    elif args[0] == "run" and len(args) > 1:
        console.print(f"[cyan]Triggering workflow '{args[1]}'[/cyan]")
        console.print(ci.trigger_workflow(args[1]))
    else:
        console.print("[yellow]Usage: /ci status | /ci run <workflow_name>[/yellow]")

def cmd_market(args: List[str], ctx: CommandContext):
    """Discover and install skills from the USTAAD marketplace."""
    from ustaad.core.marketplace import Marketplace
    market = Marketplace(ctx.workspace)
    
    if not args or args[0] == "list":
        console.print("[cyan]USTAAD Skill Marketplace[/cyan]")
        skills = market.list_skills()
        from rich.table import Table
        table = Table(show_header=True)
        table.add_column("ID", style="bold cyan")
        table.add_column("Name")
        table.add_column("Version", style="dim")
        table.add_column("Description")
        
        for s in skills:
            table.add_row(s["id"], s["name"], f"v{s['version']}", s["description"])
        console.print(table)
        console.print("[dim]Use /market install <id> to install a skill.[/dim]")
    elif args[0] == "install" and len(args) > 1:
        skill_id = args[1]
        console.print(f"[bold cyan]📥 Installing {skill_id}...[/bold cyan]")
        console.print(market.install_skill(skill_id))
    else:
        console.print("[yellow]Usage: /market list | /market install <skill_id>[/yellow]")

def cmd_worktree(args: List[str], ctx: CommandContext):
    """Manage isolated worktrees and multiple repositories."""
    from ustaad.core.worktree import WorkspaceManager
    manager = WorkspaceManager(ctx.workspace)
    
    if not args:
        console.print("[cyan]Active Workspaces:[/cyan]")
        for w in manager.list_workspaces():
            console.print(f"  - {w}")
    elif args[0] == "create" and len(args) > 1:
        console.print(f"[bold cyan]🌿 Creating worktree for branch {args[1]}[/bold cyan]")
        console.print(manager.create_worktree(args[1]))
    elif args[0] == "switch" and len(args) > 1:
        console.print(manager.switch_workspace(args[1]))
    else:
        console.print("[yellow]Usage: /worktree [create <branch> | switch <name>][/yellow]")

def cmd_trust(args: List[str], ctx: CommandContext):
    """Manage repository trust model."""
    from ustaad.core.trust import TrustModel
    tm = TrustModel()
    
    if not args:
        trusted = tm.is_trusted(ctx.workspace)
        status = "[green]TRUSTED[/green]" if trusted else "[red]UNTRUSTED[/red]"
        console.print(f"Current workspace is {status}")
    elif args[0] == "grant":
        tm.trust_repo(ctx.workspace)
        console.print(f"[green]✓ Trust granted for {ctx.workspace}[/green]")
    elif args[0] == "revoke":
        tm.revoke_trust(ctx.workspace)
        console.print(f"[yellow]✗ Trust revoked for {ctx.workspace}[/yellow]")
    else:
        console.print("[yellow]Usage: /trust [grant | revoke][/yellow]")
        
def cmd_dashboard(args: List[str], ctx: CommandContext):
    """Start the agent telemetry dashboard."""
    from ustaad.core.dashboard import TelemetryDashboard
    
    # Simple singleton to avoid port binding errors in REPL
    if not hasattr(cmd_dashboard, "server"):
        cmd_dashboard.server = TelemetryDashboard(port=8080)
        
    if args and args[0] == "stop":
        cmd_dashboard.server.stop()
        console.print("[yellow]Dashboard stopped.[/yellow]")
    else:
        cmd_dashboard.server.start()
        console.print("[bold green]✓ Dashboard running at http://localhost:8080[/bold green]")
        console.print("[dim]Use /dashboard stop to terminate.[/dim]")

# ---------------------------------------------------------------------------
# Register all built-in commands
# ---------------------------------------------------------------------------

def register_builtin_commands(registry: CommandRegistry):
    """Register all built-in slash commands."""

    # Smart AI commands
    registry.register("/review", cmd_review, "Review code for bugs, security, and quality", "AI Tasks", "/review [file]")
    registry.register("/fix", cmd_fix, "Auto-fix issues (tests, lint, errors)", "AI Tasks", "/fix [issue]")
    registry.register("/refactor", cmd_refactor, "Refactor code for quality", "AI Tasks", "/refactor [target]")
    registry.register("/test", cmd_test_generate, "Generate tests for code", "AI Tasks", "/test [target]", aliases=["test-gen"])
    registry.register("/security", cmd_security_scan, "Security audit scan", "AI Tasks", "/security [target]")
    registry.register("/docs", cmd_docs_generate, "Generate documentation", "AI Tasks", "/docs [target]")
    registry.register("/commit", cmd_commit, "Auto-commit with smart message", "AI Tasks", "/commit [message]")
    registry.register("/explain", cmd_explain, "Explain code or concepts", "AI Tasks", "/explain <topic>")
    registry.register("/analyze", cmd_analyze, "Analyze codebase quality", "AI Tasks", "/analyze [target]")
    registry.register("/simplify", cmd_simplify, "Simplify complex code", "AI Tasks", "/simplify [target]")
    registry.register("/deploy", cmd_deploy, "Prepare for deployment", "AI Tasks", "/deploy [target]")
    registry.register("/batch", cmd_batch, "Run commands from file", "AI Tasks", "/batch <file>", requires_args=True)
    registry.register("/undo", cmd_undo, "Undo last agent action", "AI Tasks", "/undo")
    registry.register("/bg", cmd_bg, "Run a prompt in the background", "Background", "/bg <prompt>", requires_args=True)
    registry.register("/jobs", cmd_jobs, "List all background tasks", "Background", "/jobs")
    registry.register("/team", cmd_team, "Run a subagent team", "Orchestration", "/team <name> <task>", requires_args=True)
    registry.register("/workflow", cmd_workflow, "Run YAML workflow", "Ecosystem", "/workflow [name]")
    registry.register("/ci", cmd_ci, "Check CI/CD status", "Ecosystem", "/ci [status|run]")
    registry.register("/market", cmd_market, "Skill Marketplace", "Ecosystem", "/market [list|install]")
    registry.register("/worktree", cmd_worktree, "Manage git worktrees", "Advanced", "/worktree [create|switch]")
    registry.register("/trust", cmd_trust, "Manage repo trust", "Security", "/trust [grant|revoke]")
    registry.register("/dashboard", cmd_dashboard, "Start telemetry UI", "Ecosystem", "/dashboard")


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------
_registry: Optional[CommandRegistry] = None


def get_command_registry() -> CommandRegistry:
    """Get the global command registry singleton."""
    global _registry
    if _registry is None:
        _registry = CommandRegistry()
        register_builtin_commands(_registry)
    return _registry
