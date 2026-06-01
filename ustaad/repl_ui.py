
import os
import socket
from rich.panel import Panel
from rich.table import Table
from rich.syntax import Syntax
from rich.markdown import Markdown
from rich.rule import Rule
from prompt_toolkit import PromptSession, HTML
from prompt_toolkit.history import FileHistory
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.styles import Style

from ustaad.core.execution_mode import get_mode, set_mode
from ustaad.core.progress import BANNER_PREMIUM, error_panel

# We will import console from cli.py for now
from ustaad.cli import console, COMMAND_STATS, ACTIVE_CONTEXT_FILES, is_ollama_running, change_default_model, run_quick_shell

def get_git_branch() -> str:
    try:
        import subprocess
        res = subprocess.run(["git", "branch", "--show-current"], capture_output=True, text=True, check=True)
        return res.stdout.strip() or "no-branch"
    except Exception:
        return "detached"

def get_statusbar_text():
    from ustaad.core.execution_mode import get_mode
    from ustaad.llm import _load_config
    mode = get_mode()
    mode_str = "AGENTIC" if mode.agentic else ("AUTONOMOUS" if mode.autonomous else ("SAFE" if mode.safe else "SEMI-AUTO"))
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
                "/plugins": "List loaded dynamic plugins & tools",
                "/plugin": "Install skills or plugins from GitHub",
                "/skills": "List loaded AI skills",
                "/skill": "Install AI skills from GitHub",
                "/reload": "Reload all dynamic plugins & tools",
                "/voice": "Transcribe .wav prompt & speak response",
                "/vscode": "Manage background VS Code WebSocket server",
                "/doc": "Query workspace documentation semantically via RAG",
                "/kit": "Operator Kit: init, check, learn",
                "/save": "Save active session context to disk",
                "/load": "Restore saved session context",

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

def print_mode():
    mode = get_mode()
    if mode.agentic:
        label = "[bold magenta]🚀 AGENTIC[/bold magenta] — single agent ReAct fluid loop"
    elif mode.autonomous:
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
    table = Table(show_header=True, box=None, padding=(0, 2), header_style="bold cyan")
    table.add_column("Command", style="bold cyan", width=22)
    table.add_column("Category", style="magenta", width=18)
    table.add_column("Description", style="dim")
    table.add_row("/add <file>", "Context", "Add specific file to active AI context")
    table.add_row("/drop <file>", "Context", "Remove file from active AI context")
    table.add_row("/ls", "Context", "List active AI context files")
    table.add_row("/doc <query>", "Context", "Query workspace documentation RAG")
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
    table.add_row("/plugins", "Plugins", "List loaded dynamic plugins & tools")
    table.add_row("/reload", "Plugins", "Reload all dynamic plugins & tools")
    table.add_row("/voice <path>", "Plugins", "Transcribe audio prompt & speak response")
    table.add_row("/vscode <action>", "Plugins", "Manage background VS Code WebSocket server")
    table.add_row("/kit init", "Operator Kit", "Bootstrap rules, hooks & skills in workspace")
    table.add_row("/kit check", "Operator Kit", "Run workspace security & readiness audit")
    table.add_row("/kit learn <n> \"<d>\"", "Operator Kit", "Synthesize a new reusable AI skill")
    table.add_row("/save", "Operator Kit", "Save active session context to disk")
    table.add_row("/load", "Operator Kit", "Restore saved session context")

    table.add_row("/clear", "Utility", "Clear screen")
    table.add_row("/help", "Utility", "Show this interactive command map")
    table.add_row("/exit", "Utility", "Close active USTAAD session")
    console.print(Panel(
        table,
        title="[bold cyan]⚡ USTAAD Command Map[/bold cyan]",
        border_style="dim",
        padding=(0, 1),
    ))
