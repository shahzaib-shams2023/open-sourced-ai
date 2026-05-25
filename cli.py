import typer

from rich.console import Console

from main import run_task

console = Console()

app = typer.Typer()

@app.command()
def ask(prompt: str):

    console.print(
        "\n[bold green]Running Multi-Agent Workflow[/bold green]\n"
    )

    result = run_task(prompt)

    console.print(
        "\n[bold cyan]RESULT[/bold cyan]\n"
    )

    console.print(result)

if __name__ == "__main__":
    app()
