import subprocess
from crewai.tools import tool

def run_command(command: str):

    try:

        result = subprocess.run(
            command,
            shell=True,
            text=True,
            capture_output=True
        )

        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode
        }

    except Exception as e:

        return {
            "error": str(e)
        }

@tool("run_command")
def run_command_tool(command: str) -> str:
    """Runs a shell command and returns its output (stdout and stderr)."""
    res = run_command(command)
    if "error" in res:
        return f"Error: {res['error']}"
    return f"Stdout:\n{res['stdout']}\nStderr:\n{res['stderr']}\nExit Code: {res['returncode']}"
