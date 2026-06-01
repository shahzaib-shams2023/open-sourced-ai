"""
USTAAD Shell Tools — Safety-Gated Command Execution

All shell commands pass through the SafetyGate before execution.
Dangerous commands (rm -rf, git reset --hard, etc.) require user confirmation.
"""

import subprocess
from crewai.tools import tool

from ustaad.core.safety import get_safety_gate
from ustaad.core.execution_mode import get_mode


def run_command(command: str) -> dict:
    """
    Execute a shell command (internal use — no safety gate).
    Used by the scanner and other internal systems.
    """
    try:
        result = subprocess.run(
            command,
            shell=True,
            text=True,
            capture_output=True,
            timeout=120,
        )
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"error": f"Command timed out after 120s: {command}"}
    except Exception as e:
        return {"error": str(e)}


def run_command_safe(command: str) -> dict:
    """
    Execute a shell command with safety gate.
    Dangerous commands require user confirmation.
    """
    gate = get_safety_gate()
    mode = get_mode()

    classification = mode.classify_command(command)

    if not gate.confirm_command(command):
        return {
            "stdout": "",
            "stderr": f"[BLOCKED] Command rejected by safety gate: {command}",
            "returncode": -1,
            "blocked": True,
        }

    try:
        import os
        import subprocess
        result = subprocess.run(
            command,
            shell=True,
            text=True,
            capture_output=True,
            timeout=120,
            cwd=os.getcwd()
        )
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"error": f"Command timed out after 120s: {command}"}
    except Exception as e:
        return {"error": str(e)}


@tool("run_command")
def run_command_tool(command: str) -> str:
    """
    Runs a shell command and returns its output.
    Dangerous commands (rm -rf, git reset --hard, docker prune, etc.)
    will prompt the user for confirmation before executing.
    Safe commands (git status, ls, cat, pytest, etc.) auto-execute.

    WARNING: Do NOT use this tool to create or write files.
    Shell file creation (echo, type, cat, heredoc) is unreliable and
    WILL FAIL on Windows. Use the `write_file` tool instead.
    This tool is for running build commands, tests, git, etc.
    """
    mode = get_mode()
    classification = mode.classify_command(command)

    res = run_command_safe(command)

    if res.get("blocked"):
        return f"[BLOCKED] User rejected command: {command}"

    if "error" in res:
        return f"Error: {res['error']}"

    output = f"Stdout:\n{res['stdout']}\nStderr:\n{res['stderr']}\nExit Code: {res['returncode']}"

    # Prefix with classification for agent awareness
    prefix = {
        "safe": "[SAFE]",
        "normal": "[OK]",
        "dangerous": "[CONFIRMED]",
    }.get(classification, "[OK]")

    return f"{prefix} {output}"

@tool("ripgrep_search")
def ripgrep_search_tool(pattern: str, directory: str = ".") -> str:
    """
    Searches for a regex pattern across the codebase using ripgrep (rg) or git grep.
    Returns matched files and lines. Fast and language-agnostic.
    """
    try:
        import os
        import subprocess
        cmd = f"rg -n '{pattern}' {directory}"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=os.getcwd())
        if result.returncode != 0 and not result.stdout:
            # Fallback to git grep
            cmd = f"git grep -n '{pattern}'"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=os.getcwd())
            if result.returncode != 0 and not result.stdout:
                 return "No matches found."
        
        out = result.stdout
        if len(out) > 4000:
            out = out[:4000] + "\n...[TRUNCATED]"
        return out
    except Exception as e:
        return f"Search failed: {str(e)}"
