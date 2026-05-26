"""
USTAAD CLI — Terminal-Native Engineering Interface

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

from ustaad.main import run_task
from ustaad.core.execution_mode import get_mode, set_mode
from ustaad.core.scanner import WorkspaceScanner

if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

console = Console()

BANNER = """[bold green]
██╗   ██╗███████╗████████╗ █████╗  █████╗ ██████╗
██║   ██║██╔════╝╚══██╔══╝██╔══██╗██╔══██╗██╔══██╗
██║   ██║███████╗   ██║   ███████║███████║██║  ██║
██║   ██║╚════██║   ██║   ██╔══██║██╔══██║██║  ██║
╚██████╔╝███████║   ██║   ██║  ██║██║  ██║██████╔╝
 ╚═════╝ ╚══════╝   ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝
[/bold green]
[italic cyan]  Autonomous Terminal-Native Engineering Agent[/italic cyan]
[dim]  SCAN > INDEX > PLAN > EXECUTE > TEST > REPAIR > REFLECT > COMPLETE[/dim]
"""


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
        label = "[bold red]AUTONOMOUS[/bold red] -- all ops auto-execute"
    elif mode.safe:
        label = "[bold green]SAFE[/bold green] -- reads auto, writes confirm"
    else:
        label = "[bold yellow]SEMI-AUTONOMOUS[/bold yellow] -- safe auto, dangerous confirm"
    confirm = "[green]ON[/green]" if mode.confirm_destructive else "[red]OFF[/red]"
    console.print(Panel(
        f"  Mode: {label}\n  Confirm Destructive: {confirm}",
        title="[bold cyan]Execution Mode[/bold cyan]",
        border_style="cyan",
    ))


app = typer.Typer(help="USTAAD -- Autonomous Terminal-Native Engineering Agent", no_args_is_help=False)


@app.command("scan")
def cmd_scan():
    """Scan workspace: detect languages, frameworks, CI/CD, linters, tests."""
    w = os.getcwd()
    console.print(f"\n[bold cyan][SCAN][/bold cyan] {w}\n")
    s = WorkspaceScanner(w)
    console.print(s.scan().to_context_string())


@app.command("index")
def cmd_index():
    """Build deep repository index: modules, classes, functions, imports."""
    from ustaad.engine.repo_index import RepoIndexer
    w = os.getcwd()
    console.print(f"\n[bold cyan][INDEX][/bold cyan] {w}\n")
    idx = RepoIndexer(w).build_index()
    console.print(idx.to_context_string())


@app.command("search")
def cmd_search(query: str):
    """Semantic code search across the repository."""
    from ustaad.engine.search import SearchEngine
    console.print(f"\n[bold blue][SEARCH][/bold blue] {query}\n")
    e = SearchEngine(os.getcwd())
    e.index_workspace()
    console.print(e.search_formatted(query))


@app.command("test")
def cmd_test():
    """Auto-detect and run tests + linters."""
    from ustaad.engine.testing import TestEngine
    console.print("\n[bold yellow][TEST][/bold yellow]\n")
    e = TestEngine(os.getcwd())
    console.print(e.run_all())


@app.command("git")
def cmd_git():
    """Show comprehensive git status."""
    from ustaad.engine.git import GitEngine
    console.print("\n[bold magenta][GIT][/bold magenta]\n")
    console.print(GitEngine(os.getcwd()).status().to_context_string())


@app.command("mode")
def cmd_mode():
    """Display current execution mode."""
    print_mode()


@app.command("memory")
def cmd_memory(query: str = ""):
    """Search or view project memory."""
    from ustaad.memory import ProjectMemory
    m = ProjectMemory(os.getcwd())
    console.print(f"\n[dim][MEMORY][/dim]\n")
    if query:
        results = m.search(query)
        if results:
            for r in results:
                console.print(f"  [{r['metadata'].get('category', '?')}] {r['content'][:200]}")
        else:
            console.print("  No memories found.")
    else:
        recent = m.get_recent(10)
        if recent:
            for r in recent:
                console.print(f"  [{r.get('category', '?')}] {r.get('content', '')[:200]}")
        else:
            console.print("  Memory is empty.")


@app.command("routing")
def cmd_routing():
    """Show model routing configuration."""
    from ustaad.llm import get_routing_summary
    console.print(f"\n{get_routing_summary()}\n")


def run_interactive():
    console.print(BANNER)
    print_mode()
    if not is_ollama_running():
        console.print("[bold red]Ollama is not running on localhost:11434[/bold red]")
        console.print("[yellow]Start Ollama and try again.[/yellow]\n")
        return
    console.print("\n[dim]Commands: scan, index, search <q>, test, git, mode, memory, exit[/dim]\n")
    while True:
        try:
            inp = input("ustaad> ").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Goodbye.[/dim]")
            break
        if not inp:
            continue
        if inp.lower() in ("exit", "quit", "q"):
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
        console.print("\n[bold green]USTAAD Engaged[/bold green]\n")
        result = run_task(inp, workspace=os.getcwd())
        console.print("\n[bold green]Result:[/bold green]\n")
        console.print(Markdown(str(result)))


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    prompt: list[str] = typer.Argument(None, help="Task prompt"),
    safe: bool = typer.Option(False, "--safe", "-s", help="Safe mode"),
    autonomous: bool = typer.Option(False, "--autonomous", "--yolo", help="Autonomous mode"),
    debug_mode: bool = typer.Option(False, "--debug", "-d", help="Force debug classification"),
    no_confirm: bool = typer.Option(False, "--no-confirm", help="Skip destructive confirmations"),
):
    """USTAAD -- Autonomous Terminal-Native Engineering Agent"""
    if autonomous:
        set_mode(safe=False, autonomous=True, confirm_destructive=False)
    elif safe:
        set_mode(safe=True, autonomous=False, confirm_destructive=True)
    if no_confirm:
        set_mode(confirm_destructive=False)
    if ctx.invoked_subcommand is not None:
        return
    if not prompt:
        run_interactive()
        return
    if not is_ollama_running():
        console.print("[bold red]Ollama not running on localhost:11434[/bold red]")
        raise typer.Exit(code=1)
    user_prompt = " ".join(prompt)
    if debug_mode:
        user_prompt = f"[debug] {user_prompt}"
    console.print(BANNER)
    print_mode()
    console.print("\n[bold green]USTAAD Engaged[/bold green]\n")
    result = run_task(user_prompt, workspace=os.getcwd())
    console.print("\n[bold green]Result:[/bold green]\n")
    console.print(Markdown(str(result)))


if __name__ == "__main__":
    app()
