"""
USTAAD CLI — Terminal Interface

Supports:
- Interactive mode: `ustaad`
- Direct prompt: `ustaad "build auth system"`
- Execution modes: --safe, --autonomous, --yolo
- Workspace scan: `ustaad scan`
- Mode display: `ustaad mode`
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

# Reconfigure terminal encoding for UTF-8 on Windows to safely print emojis
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
[italic cyan]  Autonomous CLI Engineering Agent — Production Grade[/italic cyan]
[dim]  SCAN → UNDERSTAND → PLAN → EXECUTE → VERIFY → COMPLETE[/dim]
"""


def is_ollama_running() -> bool:
    """Check if the local Ollama server is up and listening."""
    try:
        socket.setdefaulttimeout(1.0)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(("127.0.0.1", 11434))
        sock.close()
        return True
    except Exception:
        return False


def print_mode():
    """Display current execution mode."""
    mode = get_mode()
    if mode.autonomous:
        label = "[bold red]AUTONOMOUS[/bold red] — all operations auto-execute"
    elif mode.safe:
        label = "[bold green]SAFE[/bold green] — read-only auto, writes confirm"
    else:
        label = "[bold yellow]SEMI-AUTONOMOUS[/bold yellow] — safe ops auto, dangerous confirm"

    confirm = "[green]ON[/green]" if mode.confirm_destructive else "[red]OFF[/red]"
    console.print(Panel(
        f"  Mode: {label}\n  Confirm Destructive: {confirm}",
        title="[bold cyan]🛡 Execution Mode[/bold cyan]",
        border_style="cyan",
    ))


app = typer.Typer(
    help="USTAAD — Autonomous CLI Engineering Agent",
    no_args_is_help=False,
)


@app.command("scan")
def scan_workspace():
    """Scan the current workspace and display detected technologies."""
    workspace = os.getcwd()
    console.print(f"\n[bold cyan][SCAN][/bold cyan] Analyzing: {workspace}\n")

    scanner = WorkspaceScanner(workspace)
    result = scanner.scan()
    console.print(result.to_context_string())
    console.print()


@app.command("mode")
def show_mode():
    """Display the current execution mode."""
    print_mode()


def run_ustaad_interactive():
    """Interactive REPL mode."""
    console.print(BANNER)
    print_mode()

    if not is_ollama_running():
        console.print("[bold red]❌ Ollama is not running on http://localhost:11434[/bold red]")
        console.print("[yellow]Start Ollama and try again.[/yellow]\n")
        return

    console.print("\n[dim]Type your task, or 'exit' to quit. 'scan' to scan workspace. 'mode' to check mode.[/dim]\n")

    while True:
        try:
            user_input = input("ustaad> ").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Goodbye.[/dim]")
            break

        if not user_input:
            continue

        if user_input.lower() in ("exit", "quit", "q"):
            console.print("[dim]Goodbye.[/dim]")
            break

        if user_input.lower() == "scan":
            scan_workspace()
            continue

        if user_input.lower() == "mode":
            print_mode()
            continue

        # Execute task
        console.print(f"\n[bold green]⚡ USTAAD Engaged[/bold green]\n")
        result = run_task(user_input, workspace=os.getcwd())
        console.print("\n[bold green]✨ Result:[/bold green]\n")
        console.print(Markdown(str(result)))


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    prompt: list[str] = typer.Argument(None, help="Task prompt (e.g., 'add JWT auth')"),
    safe: bool = typer.Option(False, "--safe", "-s", help="Safe mode: confirm all write operations"),
    autonomous: bool = typer.Option(False, "--autonomous", "--yolo", help="Autonomous mode: auto-execute everything"),
    no_confirm: bool = typer.Option(False, "--no-confirm", help="Disable destructive operation confirmation"),
):
    """
    USTAAD — Autonomous CLI Engineering Agent

    Run without arguments for interactive mode.
    Pass a prompt for direct execution.
    """
    # Apply execution mode from flags
    if autonomous:
        set_mode(safe=False, autonomous=True, confirm_destructive=False)
    elif safe:
        set_mode(safe=True, autonomous=False, confirm_destructive=True)
    elif no_confirm:
        set_mode(confirm_destructive=False)

    # If a subcommand was invoked, don't enter interactive
    if ctx.invoked_subcommand is not None:
        return

    # Interactive mode
    if not prompt:
        run_ustaad_interactive()
        return

    # Direct prompt mode
    if not is_ollama_running():
        console.print("[bold red]❌ Ollama is not running on http://localhost:11434[/bold red]")
        console.print("[yellow]Start Ollama and try again.[/yellow]")
        raise typer.Exit(code=1)

    user_prompt = " ".join(prompt)

    console.print(BANNER)
    print_mode()
    console.print(f"\n[bold green]⚡ USTAAD Engaged[/bold green]\n")

    result = run_task(user_prompt, workspace=os.getcwd())

    console.print("\n[bold green]✨ Result:[/bold green]\n")
    console.print(Markdown(str(result)))


if __name__ == "__main__":
    app()
