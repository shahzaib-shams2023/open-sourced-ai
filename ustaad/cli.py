"""
USTAAD CLI — Premium Terminal-Native Engineering Interface

Commands:
  ustaad                          Interactive REPL
  ustaad "build auth system"      Direct prompt
  ustaad scan                     Scan workspace
  ustaad index                    Index codebase
  ustaad search "auth handler"    Semantic search
  ustaad test                     Run tests
  ustaad git                      Git status
  ustaad mode                     Show execution mode
  ustaad memory "query"           Search project memory
  ustaad routing                  Show model routing

Flags:
  --safe / -s                     Confirm all writes
  --autonomous / --yolo           Auto-execute everything
  --debug / -d                    Force debug mode
  --no-confirm                    Skip destructive confirmations
"""

import os
import sys
import socket
from dotenv import load_dotenv
load_dotenv()
os.environ.setdefault("OPENAI_API_KEY", "na")

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text
from rich.rule import Rule
from rich.table import Table

from ustaad.main import run_task
from ustaad.core.execution_mode import get_mode, set_mode
from ustaad.core.scanner import WorkspaceScanner
from ustaad.core.progress import (
    BANNER_PREMIUM, phase_spinner, phase_header, error_panel,
)

if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

console = Console()


def is_ollama_running() -> bool:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1.0)
        s.connect(("127.0.0.1", 11434))
        s.close()
        return True
    except Exception:
        return False


def print_mode():
    mode = get_mode()
    if mode.autonomous:
        label = "[bold red]⚠ AUTONOMOUS[/bold red] — all ops auto-execute"
    elif mode.safe:
        label = "[bold green]🔒 SAFE[/bold green] — reads auto, writes confirm"
    else:
        label = "[bold yellow]⚙ SEMI-AUTO[/bold yellow] — safe auto, dangerous confirm"
    confirm = "[green]ON[/green]" if mode.confirm_destructive else "[red]OFF[/red]"
    console.print(Panel(
        f"  Mode: {label}\n  Confirm Destructive: {confirm}",
        title="[bold cyan]Execution Mode[/bold cyan]",
        border_style="cyan",
        padding=(0, 2),
    ))


def print_welcome_commands():
    """Print available commands in a nice table."""
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Command", style="bold cyan", width=24)
    table.add_column("Description", style="dim")

    table.add_row("scan", "Scan workspace for languages, frameworks, tools")
    table.add_row("index", "Build deep repository index")
    table.add_row("search <query>", "Semantic code search")
    table.add_row("test", "Auto-detect and run tests + linters")
    table.add_row("git", "Show comprehensive git status")
    table.add_row("mode", "Show current execution mode")
    table.add_row("memory [query]", "Search or view project memory")
    table.add_row("routing", "Show model routing configuration")
    table.add_row("exit", "Exit REPL")

    console.print(Panel(
        table,
        title="[bold cyan]Commands[/bold cyan]",
        border_style="dim",
        padding=(0, 1),
    ))


app = typer.Typer(help="USTAAD — Autonomous Terminal-Native Engineering Agent", no_args_is_help=False)


@app.command("scan")
def cmd_scan():
    """Scan workspace: detect languages, frameworks, CI/CD, linters, tests."""
    w = os.getcwd()
    with phase_spinner("SCAN", w):
        s = WorkspaceScanner(w)
        result = s.scan()
    console.print(result.to_context_string())


@app.command("index")
def cmd_index():
    """Build deep repository index: modules, classes, functions, imports."""
    from ustaad.engine.repo_index import RepoIndexer
    w = os.getcwd()
    with phase_spinner("INDEX", w):
        idx = RepoIndexer(w).load_or_rebuild()
    console.print(idx.to_context_string())


@app.command("search")
def cmd_search(query: str):
    """Semantic code search across the repository."""
    from ustaad.engine.search import SearchEngine
    with phase_spinner("SEARCH", query):
        e = SearchEngine(os.getcwd())
        e.index_workspace()
        results = e.search_formatted(query)
    console.print(results)


@app.command("test")
def cmd_test():
    """Auto-detect and run tests + linters."""
    from ustaad.engine.testing import TestEngine
    with phase_spinner("TEST", "Running..."):
        e = TestEngine(os.getcwd())
        output = e.run_all()
    console.print(output)


@app.command("git")
def cmd_git():
    """Show comprehensive git status."""
    from ustaad.engine.git import GitEngine
    with phase_spinner("GIT", "Checking..."):
        status = GitEngine(os.getcwd()).status()
    console.print(status.to_context_string())


@app.command("mode")
def cmd_mode():
    """Display current execution mode."""
    print_mode()


@app.command("memory")
def cmd_memory(query: str = ""):
    """Search or view project memory."""
    from ustaad.memory import ProjectMemory
    m = ProjectMemory(os.getcwd())
    phase_header("MEMORY")
    if query:
        results = m.search(query)
        if results:
            for r in results:
                console.print(f"  [{r['metadata'].get('category', '?')}] {r['content'][:200]}")
        else:
            console.print("[dim]   No memories found.[/dim]")
    else:
        recent = m.get_recent(10)
        if recent:
            for r in recent:
                console.print(f"  [{r.get('category', '?')}] {r.get('content', '')[:200]}")
        else:
            console.print("[dim]   Memory is empty.[/dim]")


@app.command("routing")
def cmd_routing():
    """Show model routing configuration."""
    from ustaad.llm import get_routing_summary
    console.print(f"\n{get_routing_summary()}\n")


def run_interactive():
    console.print(BANNER_PREMIUM)
    print_mode()

    if not is_ollama_running():
        error_panel(
            "Ollama Not Running",
            "Cannot connect to Ollama on localhost:11434",
            "Start Ollama with: ollama serve",
        )
        return

    print_welcome_commands()
    console.print()

    while True:
        try:
            console.print("[bold cyan]ustaad[/bold cyan] [dim]>[/dim] ", end="")
            inp = input("").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Goodbye. 👋[/dim]")
            break

        if not inp:
            continue
        if inp.lower() in ("exit", "quit", "q"):
            console.print("[dim]Goodbye. 👋[/dim]")
            break
        if inp.lower() == "scan":
            cmd_scan()
            continue
        if inp.lower() == "index":
            cmd_index()
            continue
        if inp.lower().startswith("search "):
            cmd_search(inp[7:].strip())
            continue
        if inp.lower() == "test":
            cmd_test()
            continue
        if inp.lower() == "git":
            cmd_git()
            continue
        if inp.lower() == "mode":
            print_mode()
            continue
        if inp.lower().startswith("memory"):
            q = inp[6:].strip()
            cmd_memory(q)
            continue
        if inp.lower() == "routing":
            cmd_routing()
            continue
        if inp.lower() in ("help", "?", "commands"):
            print_welcome_commands()
            continue

        # Run as task prompt
        console.print()
        console.print(Rule("[bold green]⚡ USTAAD Engaged[/bold green]", style="green"))
        console.print()
        result = run_task(inp, workspace=os.getcwd())
        console.print()
        console.print(Rule("[bold green]Result[/bold green]", style="green"))
        console.print(Markdown(str(result)))
        console.print()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    safe: bool = typer.Option(False, "--safe", "-s", help="Safe mode"),
    autonomous: bool = typer.Option(False, "--autonomous", "--yolo", help="Autonomous mode"),
    debug_mode: bool = typer.Option(False, "--debug", "-d", help="Force debug classification"),
    no_confirm: bool = typer.Option(False, "--no-confirm", help="Skip destructive confirmations"),
):
    """USTAAD — Autonomous Terminal-Native Engineering Agent"""
    if autonomous:
        set_mode(safe=False, autonomous=True, confirm_destructive=False)
    elif safe:
        set_mode(safe=True, autonomous=False, confirm_destructive=True)
    if no_confirm:
        set_mode(confirm_destructive=False)
    
    if ctx.invoked_subcommand is not None:
        return

    # Extract prompt manually from sys.argv filtering out flags
    prompt_args = [arg for arg in sys.argv[1:] if not arg.startswith("-")]
    
    # If the first positional arg is a known subcommand, do not treat as a prompt
    if prompt_args and prompt_args[0] in ["scan", "index", "search", "test", "git", "mode", "memory", "routing"]:
        return

    if not prompt_args:
        run_interactive()
        return

    if not is_ollama_running():
        error_panel(
            "Ollama Not Running",
            "Cannot connect to Ollama on localhost:11434",
            "Start Ollama with: ollama serve",
        )
        raise typer.Exit(code=1)

    user_prompt = " ".join(prompt_args)
    if debug_mode:
        user_prompt = f"[debug] {user_prompt}"
    console.print(BANNER_PREMIUM)
    print_mode()
    console.print()
    console.print(Rule("[bold green]⚡ USTAAD Engaged[/bold green]", style="green"))
    console.print()
    result = run_task(user_prompt, workspace=os.getcwd())
    console.print()
    console.print(Rule("[bold green]Result[/bold green]", style="green"))
    console.print(Markdown(str(result)))


if __name__ == "__main__":
    app()
