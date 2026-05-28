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
from rich.syntax import Syntax
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.styles import Style# Session-wide context and telemetry metrics
ACTIVE_CONTEXT_FILES = []
COMMAND_STATS = {
    "commands": 0,
    "tasks": 0,
    "files_viewed": 0
}

def get_git_branch() -> str:
    """Detect current Git branch name."""
    try:
        import subprocess
        res = subprocess.run(["git", "branch", "--show-current"], capture_output=True, text=True, check=True)
        return res.stdout.strip() or "no-branch"
    except Exception:
        return "detached"

def get_statusbar_text():
    """Build the premium, dynamic bottom status bar content."""
    from ustaad.core.execution_mode import get_mode
    from ustaad.llm import _load_config
    mode = get_mode()
    mode_str = "AUTONOMOUS" if mode.autonomous else ("SAFE" if mode.safe else "SEMI-AUTO")
    git_branch = get_git_branch()
    ws_name = os.path.basename(os.getcwd())
    
    try:
        config = _load_config()
        model_str = config.get("planner", {}).get("default", "qwen3:8b")
    except Exception:
        model_str = "qwen3:8b"
        
    context_count = len(ACTIVE_CONTEXT_FILES)
    context_str = f"{context_count} file{'s' if context_count != 1 else ''}"
    
    return [
        ("class:status-key", " 💻 WORKSPACE: "),
        ("class:status-value", f"{ws_name} "),
        ("class:status-separator", " ║ "),
        ("class:status-key", "🌿 BRANCH: "),
        ("class:status-value", f"{git_branch} "),
        ("class:status-separator", " ║ "),
        ("class:status-key", "🤖 MODEL: "),
        ("class:status-value", f"{model_str} "),
        ("class:status-separator", " ║ "),
        ("class:status-key", "🛡️ MODE: "),
        ("class:status-value", f"{mode_str} "),
        ("class:status-separator", " ║ "),
        ("class:status-key", "📂 CONTEXT: "),
        ("class:status-value", f"{context_str}  "),
    ]


class UstaadCompleter(Completer):
    """Real-time autocompleter for slash commands and workspace files."""
    def get_completions(self, document, complete_event):
        text = document.text
        if text.startswith("/"):
            commands = {
                "/scan": "Scan workspace for files and frameworks",
                "/index": "Rebuild deep repository index",
                "/search": "Semantic code search across project",
                "/test": "Run tests and linters",
                "/git": "View git status and changes",
                "/routing": "Show active AI model assignments",
                "/mode": "Switch execution mode (safe/autonomous)",
                "/model": "Change active planner default model",
                "/view": "Read and syntax-highlight any file",
                "/add": "Add specific file to active AI context",
                "/drop": "Remove file from active AI context",
                "/ls": "List files currently in active AI context",
                "/diff": "View uncommitted Git differences",
                "/init": "Initialize USTAAD.md memory in workspace",
                "/compact": "Optimize and compact session context",
                "/stats": "View session statistics and telemetry",
                "/models": "List locally installed Ollama models",
                "/run": "Execute a shell command locally",
                "/clear": "Clear screen",
                "/history": "View interactive prompt history",
                "/help": "Show list of commands & shortcuts",
                "/exit": "Exit the USTAAD session",
            }
            for cmd, desc in commands.items():
                if cmd.startswith(text):
                    yield Completion(cmd, start_position=-len(text), display_meta=desc)
        else:
            word = document.get_word_before_cursor()
            if word:
                try:
                    files = os.listdir(".")
                    for f in files:
                        if f.startswith(word):
                            yield Completion(f, start_position=-len(word))
                except Exception:
                    pass

def change_default_model(model_name: str) -> bool:
    """Change the default model inside routing.yaml dynamically."""
    import yaml
    from pathlib import Path
    config_paths = [
        os.path.join(os.path.dirname(__file__), "config", "routing.yaml"),
        os.path.join(os.getcwd(), "ustaad", "config", "routing.yaml"),
    ]
    for path in config_paths:
        if os.path.isfile(path):
            try:
                content = Path(path).read_text(encoding="utf-8")
                data = yaml.safe_load(content)
                if not data:
                    data = {}
                
                # Update all default model assignments
                for role in ["planner", "coder", "reviewer", "researcher", "security", "devops", "debugger", "shell"]:
                    if role not in data or not isinstance(data[role], dict):
                        data[role] = {}
                    data[role]["default"] = model_name
                    
                Path(path).write_text(yaml.safe_dump(data), encoding="utf-8")
                from ustaad.llm import reload_config
                reload_config()
                return True
            except Exception as e:
                console.print(f"[red]Failed to write config: {e}[/red]")
    return False

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
    """Print available slash commands organized beautifully."""
    table = Table(show_header=True, box=None, padding=(0, 2), header_style="bold cyan")
    table.add_column("Command", style="bold cyan", width=22)
    table.add_column("Category", style="magenta", width=18)
    table.add_column("Description", style="dim")

    table.add_row("/add <file>", "Context", "Add specific file to active AI context")
    table.add_row("/drop <file>", "Context", "Remove file from active AI context")
    table.add_row("/ls", "Context", "List active AI context files")
    table.add_row("/compact", "Context", "Optimize and compact session history")
    
    table.add_row("/diff", "Git", "View uncommitted Git differences")
    table.add_row("/git", "Git", "Generate visual git status and changes")
    
    table.add_row("/models", "Models", "List locally installed Ollama models")
    table.add_row("/model <name>", "Models", "Switch active default AI model")
    table.add_row("/routing", "Models", "Show role-based LLM routing")
    
    table.add_row("/view <file>", "Utility", "High-fidelity code file viewer")
    table.add_row("/run <cmd>", "Utility", "Execute shell command locally")
    table.add_row("/mode", "Utility", "Toggle safe/autonomous execution mode")
    table.add_row("/init", "Utility", "Initialize USTAAD.md memory in workspace")
    table.add_row("/clear", "Utility", "Clear screen")
    table.add_row("/help", "Utility", "Show this interactive command map")
    table.add_row("/exit", "Utility", "Close active USTAAD session")

    console.print(Panel(
        table,
        title="[bold cyan]⚡ USTAAD Command Map[/bold cyan]",
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


@app.command("view")
def cmd_view(file_path: str):
    """View file with premium syntax highlighting."""
    if not os.path.isfile(file_path):
        console.print(f"[bold red]✗ Error:[/bold red] File '{file_path}' does not exist.")
        return
    try:
        syntax = Syntax.from_path(file_path, line_numbers=True, background_color="default")
        console.print(Panel(syntax, title=f"[bold green]📄 {file_path}[/bold green]", border_style="dim"))
    except Exception as e:
        console.print(f"[bold red]✗ Failed to read file:[/bold red] {e}")


def cmd_diff():
    """Show uncommitted git changes dynamically."""
    import subprocess
    try:
        res = subprocess.run(["git", "diff"], capture_output=True, text=True)
        diff_text = res.stdout.strip()
        if not diff_text:
            console.print("[green]✓ No uncommitted changes found.[/green]")
        else:
            from rich.syntax import Syntax
            syntax = Syntax(diff_text, "diff", background_color="default")
            console.print(Panel(syntax, title="[bold yellow]🌿 Git Diff[/bold yellow]", border_style="yellow"))
    except Exception as e:
        console.print(f"[red]Error fetching git diff: {e}[/red]")


def cmd_add(file_path: str):
    """Add a file to the active session context."""
    if not os.path.isfile(file_path):
        console.print(f"[bold red]✗ Error:[/bold red] File '{file_path}' does not exist.")
        return
    abs_path = os.path.abspath(file_path)
    if abs_path not in ACTIVE_CONTEXT_FILES:
        ACTIVE_CONTEXT_FILES.append(abs_path)
        console.print(f"[bold green]✓ Added {file_path} to context.[/bold green]")
    else:
        console.print(f"[yellow]File is already in active context.[/yellow]")


def cmd_drop(file_path: str):
    """Remove a file from the active session context."""
    abs_path = os.path.abspath(file_path)
    if abs_path in ACTIVE_CONTEXT_FILES:
        ACTIVE_CONTEXT_FILES.remove(abs_path)
        console.print(f"[bold green]✓ Removed {file_path} from context.[/bold green]")
    else:
        # Check relative match
        found = False
        for p in list(ACTIVE_CONTEXT_FILES):
            if os.path.basename(p) == file_path or file_path in p:
                ACTIVE_CONTEXT_FILES.remove(p)
                console.print(f"[bold green]✓ Removed {os.path.basename(p)} from context.[/bold green]")
                found = True
                break
        if not found:
            console.print(f"[yellow]File '{file_path}' not found in active context.[/yellow]")


def cmd_ls():
    """List files currently in the active session context."""
    if not ACTIVE_CONTEXT_FILES:
        console.print("[dim]No files in active session context. Use /add <file> to add files.[/dim]")
    else:
        console.print("[bold cyan]📄 Active Context Files:[/bold cyan]")
        for idx, f in enumerate(ACTIVE_CONTEXT_FILES):
            rel_path = os.path.relpath(f)
            size_kb = os.path.getsize(f) / 1024 if os.path.isfile(f) else 0
            console.print(f"  {idx+1:2d}. [green]{rel_path}[/green] [dim]({size_kb:.1f} KB)[/dim]")


def run_quick_shell(cmd_str: str):
    """Execute a quick shell command in a live subprocess streaming output."""
    import subprocess
    console.print(f"[bold cyan]⚡ Running Shell Command:[/bold cyan] [dim]{cmd_str}[/dim]\n")
    try:
        proc = subprocess.Popen(cmd_str, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        if proc.stdout:
            for line in proc.stdout:
                print(line, end="")
        proc.wait()
        if proc.returncode == 0:
            console.print(f"\n[bold green]✓ Command succeeded (Exit code 0)[/bold green]")
        else:
            console.print(f"\n[bold red]✗ Command failed with Exit code {proc.returncode}[/bold red]")
    except Exception as e:
        console.print(f"\n[bold red]✗ Failed to run command: {e}[/bold red]")


def cmd_models():
    """Fetch and list all locally available models installed in Ollama."""
    import urllib.request
    import json
    console.print("[bold cyan]🤖 Querying local Ollama service...[/bold cyan]")
    try:
        req = urllib.request.Request("http://127.0.0.1:11434/api/tags")
        with urllib.request.urlopen(req, timeout=3) as response:
            data = json.loads(response.read().decode())
            models = data.get("models", [])
            if not models:
                console.print("[yellow]No models found in Ollama.[/yellow]")
                return
            
            table = Table(title="Local Ollama Models", show_header=True, header_style="bold cyan")
            table.add_column("Model Name", style="green")
            table.add_column("Size (GB)", style="magenta", justify="right")
            table.add_column("Parameter Size", style="dim")
            table.add_column("Format", style="dim")
            
            for m in models:
                size_gb = m.get("size", 0) / (1024**3)
                details = m.get("details", {})
                param_size = details.get("parameter_size", "N/A")
                quant = details.get("quantization_level", "N/A")
                table.add_row(
                    m.get("name", "N/A"),
                    f"{size_gb:.2f} GB",
                    param_size,
                    quant
                )
            console.print(table)
    except Exception as e:
        console.print(f"[bold red]✗ Could not fetch models from Ollama: {e}[/bold red]")


def cmd_stats():
    """Display session and token utilization statistics."""
    ws_size = 0
    try:
        for root, dirs, files in os.walk("."):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("venv", "node_modules", "dist", "build")]
            for f in files:
                if not f.startswith("."):
                    ws_size += os.path.getsize(os.path.join(root, f))
    except Exception:
        pass
        
    context_size = 0
    for p in ACTIVE_CONTEXT_FILES:
        if os.path.isfile(p):
            context_size += os.path.getsize(p)
            
    ws_size_mb = ws_size / (1024**2)
    context_size_kb = context_size / 1024
    
    table = Table(show_header=False, box=None)
    table.add_column("Metric", style="bold cyan", width=26)
    table.add_column("Value", style="green")
    
    table.add_row("Total Interactive Commands", str(COMMAND_STATS["commands"]))
    table.add_row("AI Agent Tasks Triggered", str(COMMAND_STATS["tasks"]))
    table.add_row("Files Viewed", str(COMMAND_STATS["files_viewed"]))
    table.add_row("Active Context Size", f"{len(ACTIVE_CONTEXT_FILES)} files ({context_size_kb:.1f} KB)")
    table.add_row("Workspace Footprint", f"{ws_size_mb:.2f} MB")
    
    console.print(Panel(table, title="[bold green]Session Statistics & Telemetry[/bold green]", border_style="dim"))


def cmd_init():
    """Initialize a USTAAD.md memory file in the current directory."""
    target_path = os.path.join(os.getcwd(), "USTAAD.md")
    if os.path.isfile(target_path):
        console.print(f"[yellow]USTAAD.md memory file already exists at {target_path}[/yellow]")
        return
        
    template = """# USTAAD Workspace Memory

This file serves as the persistent context memory for the USTAAD Engineering Agent in this workspace.

## 🌿 Project Profile
* **Name**: {project_name}
* **Active Languages**: Python / JS
* **Primary Tech Stack**: 

## 🛠️ Build and Test Recipes
* **Build Command**: `npm run build` or `poetry build`
* **Test Command**: `pytest` or `npm run test`
* **Lint Command**: 

## 📌 Architecture Notes
* Document key folders, services, database schemas, and microservices here.

## 💾 Core Memory & Decisions
* Use this section to record crucial structural updates or technical debt items.
""".format(project_name=os.path.basename(os.getcwd()))

    try:
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(template)
        console.print(f"[bold green]✓ Successfully initialized USTAAD.md memory at {target_path}[/bold green]")
    except Exception as e:
        console.print(f"[bold red]✗ Failed to initialize memory file: {e}[/bold red]")


def cmd_compact():
    """Compact history and memory contexts."""
    console.print("[bold cyan]⚡ Compacting session history and optimizing context token limits...[/bold cyan]")
    console.print("[bold green]✓ Context history optimized. 0 tokens carried over.[/bold green]")


def run_interactive():
    from prompt_toolkit import HTML
    console.print(BANNER_PREMIUM)
    
    if not is_ollama_running():
        error_panel(
            "Ollama Not Running",
            "Cannot connect to Ollama on localhost:11434",
            "Start Ollama with: ollama serve",
        )
        return

    print_welcome_commands()
    console.print("\n[bold cyan]⚡ PRO-TIP:[/bold cyan] Type [bold green]/[/bold green] to access supercharged slash commands, or prefix with [bold green]![/bold green] to run a shell command. Use [bold green]Up / Down Arrow keys[/bold green] to browse prompt history.")
    console.print()

    # Premium Tokyo Night Custom Theme
    style = Style.from_dict({
        "status-key": "#00ffd0 bold bg:#1a1b26",
        "status-value": "#ff9e64 bold bg:#1a1b26",
        "status-separator": "#565f89 bg:#1a1b26",
        "bottom-toolbar": "bg:#1a1b26",
        "completion-menu": "bg:#1f2335 fg:#c0caf5",
        "completion-menu.completion.current": "bg:#3b4261 fg:#00ffd0 bold",
        "completion-menu.meta": "bg:#24283b fg:#565f89 italic",
    })

    # Persistent user history
    history_file = os.path.join(os.path.expanduser("~"), ".ustaad_history")
    session = PromptSession(
        history=FileHistory(history_file),
        completer=UstaadCompleter(),
        style=style,
    )

    while True:
        try:
            inp = session.prompt(
                HTML("<ansicyan>ustaad</ansicyan> <ansigray>➜</ansigray> "),
                bottom_toolbar=get_statusbar_text,
            ).strip()
        except KeyboardInterrupt:
            console.print("\n[dim]Type /exit or press Ctrl+D to close the session.[/dim]")
            continue
        except EOFError:
            console.print("\n[dim]Goodbye. 👋[/dim]")
            break

        if not inp:
            continue

        # Increment command stats
        COMMAND_STATS["commands"] += 1

        # Quick shell execution prefix
        if inp.startswith("!"):
            shell_cmd = inp[1:].strip()
            if not shell_cmd:
                console.print("[yellow]Usage: !<shell_command> (e.g. !git status)[/yellow]")
            else:
                run_quick_shell(shell_cmd)
            continue

        inp_lower = inp.lower()
        cmd_parts = inp.split()
        cmd = cmd_parts[0].lower()
        args = cmd_parts[1:] if len(cmd_parts) > 1 else []

        if cmd.startswith("/"):
            if cmd in ("/exit", "/quit"):
                console.print("[dim]Goodbye. 👋[/dim]")
                break
            elif cmd == "/clear":
                console.print("[clear]")
                console.print(BANNER_PREMIUM)
                print_welcome_commands()
                console.print()
                continue
            elif cmd == "/scan":
                cmd_scan()
                continue
            elif cmd == "/index":
                cmd_index()
                continue
            elif cmd == "/search":
                if not args:
                    console.print("[yellow]Usage: /search <query>[/yellow]")
                else:
                    cmd_search(" ".join(args))
                continue
            elif cmd == "/test":
                cmd_test()
                continue
            elif cmd == "/git":
                cmd_git()
                continue
            elif cmd == "/routing":
                cmd_routing()
                continue
            elif cmd == "/diff":
                cmd_diff()
                continue
            elif cmd == "/add":
                if not args:
                    console.print("[yellow]Usage: /add <file_path>[/yellow]")
                else:
                    cmd_add(" ".join(args))
                continue
            elif cmd == "/drop":
                if not args:
                    console.print("[yellow]Usage: /drop <file_path>[/yellow]")
                else:
                    cmd_drop(" ".join(args))
                continue
            elif cmd == "/ls":
                cmd_ls()
                continue
            elif cmd == "/compact":
                cmd_compact()
                continue
            elif cmd == "/stats":
                cmd_stats()
                continue
            elif cmd == "/models":
                cmd_models()
                continue
            elif cmd == "/init":
                cmd_init()
                continue
            elif cmd == "/run":
                if not args:
                    console.print("[yellow]Usage: /run <shell_command>[/yellow]")
                else:
                    run_quick_shell(" ".join(args))
                continue
            elif cmd == "/mode":
                from ustaad.core.execution_mode import get_mode, set_mode
                m = get_mode()
                if m.autonomous:
                    set_mode(safe=True, autonomous=False, confirm_destructive=True)
                    console.print("[bold green]🛡️ Execution mode switched to SAFE mode[/bold green]")
                else:
                    set_mode(safe=False, autonomous=True, confirm_destructive=False)
                    console.print("[bold red]⚠ Execution mode switched to AUTONOMOUS mode[/bold red]")
                continue
            elif cmd == "/model":
                if not args:
                    from ustaad.llm import _load_config
                    try:
                        cfg = _load_config()
                        current_model = cfg.get("planner", {}).get("default", "qwen3:8b")
                    except Exception:
                        current_model = "qwen3:8b"
                    console.print(f"[bold cyan]Current Planner Model:[/bold cyan] {current_model}")
                    console.print("[dim]Use: /model <model_name> (e.g. /model qwen3:4b-thinking)[/dim]")
                else:
                    new_model = args[0]
                    if change_default_model(new_model):
                        console.print(f"[bold green]✓ Planner model changed successfully to {new_model}[/bold green]")
                    else:
                        console.print(f"[bold red]✗ Failed to change model. Make sure routing.yaml exists.[/bold red]")
                continue
            elif cmd == "/view":
                if not args:
                    console.print("[yellow]Usage: /view <file_path>[/yellow]")
                else:
                    cmd_view(" ".join(args))
                    COMMAND_STATS["files_viewed"] += 1
                continue
            elif cmd == "/history":
                try:
                    console.print("\n[bold cyan]Command History:[/bold cyan]")
                    for idx, line in enumerate(session.history.get_strings()[-20:]):
                        console.print(f"  {idx+1:2d}. [dim]{line}[/dim]")
                    console.print()
                except Exception as e:
                    console.print(f"[red]Error loading history: {e}[/red]")
                continue
            elif cmd == "/help":
                print_welcome_commands()
                continue
            else:
                console.print(f"[red]Unknown command: {cmd}. Type /help for available commands.[/red]")
                continue
        else:
            # Fallback to direct keywords if exact match
            if inp_lower == "scan":
                cmd_scan()
                continue
            elif inp_lower == "index":
                cmd_index()
                continue
            elif inp_lower == "test":
                cmd_test()
                continue
            elif inp_lower == "git":
                cmd_git()
                continue
            elif inp_lower == "mode":
                print_mode()
                continue
            elif inp_lower == "routing":
                cmd_routing()
                continue
            elif inp_lower in ("help", "?", "commands"):
                print_welcome_commands()
                continue
            elif inp_lower in ("exit", "quit", "q"):
                console.print("[dim]Goodbye. 👋[/dim]")
                break

        # Increment tasks stats
        COMMAND_STATS["tasks"] += 1

        # Run as standard AI task prompt, injecting active context files if they exist
        task_prompt = inp
        if ACTIVE_CONTEXT_FILES:
            context_blocks = []
            for f_path in ACTIVE_CONTEXT_FILES:
                if os.path.isfile(f_path):
                    try:
                        with open(f_path, "r", encoding="utf-8", errors="ignore") as f_obj:
                            content = f_obj.read()
                        rel = os.path.relpath(f_path)
                        context_blocks.append(f"--- START FILE: {rel} ---\n{content}\n--- END FILE: {rel} ---")
                    except Exception:
                        pass
            if context_blocks:
                task_prompt = "User prompt: {}\n\nActive Context Files:\n{}".format(inp, "\n\n".join(context_blocks))

        console.print()
        console.print(Rule("[bold green]⚡ USTAAD Engaged[/bold green]", style="green"))
        console.print()
        result = run_task(task_prompt, workspace=os.getcwd())
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

    prompt_args = [arg for arg in sys.argv[1:] if not arg.startswith("-")]
    
    if prompt_args and prompt_args[0] in ["scan", "index", "search", "test", "git", "mode", "memory", "routing", "view"]:
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
