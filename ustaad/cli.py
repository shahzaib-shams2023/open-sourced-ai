import os
import sys
import socket
from dotenv import load_dotenv
load_dotenv()
os.environ.setdefault("OPENAI_API_KEY", "na")
import typer

from rich.console import Console
from rich.markdown import Markdown

from ustaad.main import run_task

# Reconfigure terminal encoding for UTF-8 on Windows to safely print emojis
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

console = Console()

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

app = typer.Typer(
    help="USTAAD - Local AI Operating System"
)

def run_ustaad_interactive():
    console.print("""
[bold green]
██╗   ██╗███████╗████████╗ █████╗  █████╗ ██████╗
██║   ██║██╔════╝╚══██╔══╝██╔══██╗██╔══██╗██╔══██╗
██║   ██║███████╗   ██║   ███████║███████║██║  ██║
██║   ██║╚════██║   ██║   ██╔══██║██╔══██║██║  ██║
╚██████╔╝███████║   ██║   ██║  ██║██║  ██║██████╔╝
 ╚═════╝ ╚══════╝   ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝
[/bold green]
[italic blue]   ★ Local AI OS & Pair Programmer — Production Grade ★[/italic blue]
    """)

    if not is_ollama_running():
        console.print("[bold red]❌ Error: Ollama does not seem to be running on http://localhost:11434.[/bold red]")
        console.print("[yellow]Please start Ollama (e.g. open the Ollama Desktop App or run 'ollama serve') and try again.[/yellow]\n")
        return

    while True:
        try:
            user_input = input("\nustaad> ").strip()
        except (KeyboardInterrupt, EOFError):
            break

        if not user_input:
            continue

        if user_input.lower() in ["exit", "quit"]:
            break

        console.print("\n[bold green]⚡ Orchestrating your local AI agents...[/bold green]\n")
        result = run_task(
            user_input,
            workspace=os.getcwd()
        )

        console.print("\n[bold green]✨ Final Result Summary:[/bold green]\n")
        console.print(Markdown(str(result)))

@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    prompt: list[str] = typer.Argument(None)
):
    # Interactive mode
    if not prompt:
        run_ustaad_interactive()
    # Direct prompt mode
    else:
        if not is_ollama_running():
            console.print("[bold red]❌ Error: Ollama is not running on http://localhost:11434.[/bold red]")
            console.print("[yellow]Please start Ollama and try again.[/yellow]")
            raise typer.Exit(code=1)

        user_prompt = " ".join(prompt)
        console.print("\n[bold green]⚡ Orchestrating your local AI agents...[/bold green]\n")
        result = run_task(
            user_prompt,
            workspace=os.getcwd()
        )

        console.print("\n[bold green]✨ Final Result Summary:[/bold green]\n")
        console.print(Markdown(str(result)))

if __name__ == "__main__":
    app()
