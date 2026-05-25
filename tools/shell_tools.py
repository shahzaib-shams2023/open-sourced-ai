import subprocess

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
