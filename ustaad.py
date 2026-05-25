import typer

from rich.console import Console
from main import run_task

console = Console()

app = typer.Typer(
    help="USTAAD - Local Multi-Agent AI OS"
)

@app.command()
def ask(prompt: str):

    console.print(
        "\n[bold green]USTAAD AI OS[/bold green]\n"
    )

    result = run_task(prompt)

    console.print(
        "\n[bold cyan]RESULT[/bold cyan]\n"
    )

    console.print(result)

@app.command()
def chat():

    console.print(
        "\n[bold green]USTAAD Interactive Chat[/bold green]\n"
    )

    while True:

        user_input = input("ustaad> ")

        if user_input.lower() in [
            "exit",
            "quit"
        ]:
            break

        result = run_task(user_input)

        console.print(result)

if __name__ == "__main__":
    app()
