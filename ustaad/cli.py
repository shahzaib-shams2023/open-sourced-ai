import os
from dotenv import load_dotenv
load_dotenv()
os.environ.setdefault("OPENAI_API_KEY", "na")
import typer

from rich.console import Console

from ustaad.main import run_task

console = Console()

app = typer.Typer(
    help="USTAAD - Local AI Operating System"
)

@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    prompt: list[str] = typer.Argument(None)
):

    # Interactive mode
    if not prompt:

        console.print("""
[bold green]
██╗   ██╗███████╗████████╗ █████╗  █████╗ ██████╗
██║   ██║██╔════╝╚══██╔══╝██╔══██╗██╔══██╗██╔══██╗
██║   ██║███████╗   ██║   ███████║███████║██║  ██║
██║   ██║╚════██║   ██║   ██╔══██║██╔══██║██║  ██║
╚██████╔╝███████║   ██║   ██║  ██║██║  ██║██████╔╝
 ╚═════╝ ╚══════╝   ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝
[/bold green]
        """)

        while True:

            user_input = input("\nustaad> ")

            if user_input.lower() in [
                "exit",
                "quit"
            ]:
                break

            result = run_task(
                user_input,
                workspace=os.getcwd()
            )

            console.print(result)

    # Direct prompt mode
    else:

        user_prompt = " ".join(prompt)

        result = run_task(
            user_prompt,
            workspace=os.getcwd()
        )

        console.print(result)


if __name__ == "__main__":
    app()
