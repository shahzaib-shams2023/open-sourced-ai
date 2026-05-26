import os
import re
from pathlib import Path
from crewai.tools import tool

from ustaad.core.safety import get_safety_gate


def _sanitize_html_content(content: str, path: str) -> str:
    """Fix common LLM output corruptions in HTML/CSS/JS files.
    
    The gemma3 model via CrewAI's JSON tool pipeline sometimes injects
    trailing spaces inside quoted attribute values (e.g., id="board " → id="board").
    """
    ext = Path(path).suffix.lower()
    if ext not in ('.html', '.htm', '.css', '.js', '.jsx', '.ts', '.tsx', '.svg'):
        return content

    # Fix trailing whitespace inside HTML attribute values: attr="value " → attr="value"
    content = re.sub(r'(=\s*"[^"]*?)\s+"', r'\1"', content)
    content = re.sub(r"(=\s*'[^']*?)\s+'", r"\1'", content)
    return content


def read_file(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        return f"Error: Could not read file at '{path}': {str(e)}"


def write_file(path: str, content: str) -> str:
    try:
        p = Path(path)
        is_overwrite = p.exists()

        # Safety gate for overwrites of critical files
        if is_overwrite:
            gate = get_safety_gate()
            if not gate.confirm_file_write(str(p), is_overwrite=True):
                return f"[BLOCKED] User rejected overwrite of: {path}"

        # Sanitize LLM output corruptions
        content = _sanitize_html_content(content, path)

        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        action = "Overwritten" if is_overwrite else "Created"
        return f"Success: {action} {path}"
    except Exception as e:
        return f"Error: Could not write to file at '{path}': {str(e)}"


def append_file(path: str, content: str) -> str:
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(content)
        return f"Success: Appended content to {path}"
    except Exception as e:
        return f"Error: Could not append to file at '{path}': {str(e)}"


def delete_file(path: str) -> str:
    try:
        p = Path(path)
        if not p.exists():
            return f"Error: File does not exist: {path}"

        gate = get_safety_gate()
        if not gate.confirm_file_delete(str(p)):
            return f"[BLOCKED] User rejected deletion of: {path}"

        p.unlink()
        return f"Success: Deleted {path}"
    except Exception as e:
        return f"Error: Could not delete file at '{path}': {str(e)}"


# ---------------------------------------------------------------------------
# CrewAI tool wrappers
# ---------------------------------------------------------------------------

@tool("read_file")
def read_file_tool(path: str) -> str:
    """Reads the full contents of a file at the given path. Always safe."""
    return read_file(path)


@tool("write_file")
def write_file_tool(path: str, content: str) -> str:
    """
    Writes content to a file. Creates parent directories if needed.
    Overwrites to critical files (setup.py, .env, requirements.txt, etc.)
    will prompt the user for confirmation.
    """
    return write_file(path, content)


@tool("append_file")
def append_file_tool(path: str, content: str) -> str:
    """Appends content to the end of a file."""
    return append_file(path, content)


@tool("delete_file")
def delete_file_tool(path: str) -> str:
    """
    Deletes a file. Always requires user confirmation.
    Use with caution — this is a destructive operation.
    """
    return delete_file(path)


@tool("list_directory")
def list_directory_tool(path: str) -> str:
    """
    Lists all files and directories at the given path.
    Use this to understand project structure before making changes.
    """
    try:
        p = Path(path)
        if not p.exists():
            return f"Error: Path does not exist: {path}"
        if not p.is_dir():
            return f"Error: Not a directory: {path}"

        skip = {".git", ".ustaad", "node_modules", "venv", ".venv", "__pycache__", "memory", ".mypy_cache"}
        entries = []

        for item in sorted(p.iterdir()):
            if item.name in skip:
                continue
            icon = "[DIR]" if item.is_dir() else "[FILE]"
            size = ""
            if item.is_file():
                sz = item.stat().st_size
                if sz < 1024:
                    size = f" ({sz}B)"
                elif sz < 1024 * 1024:
                    size = f" ({sz // 1024}KB)"
                else:
                    size = f" ({sz // (1024*1024)}MB)"
            entries.append(f"{icon} {item.name}{size}")

        if not entries:
            return f"Directory is empty: {path}"

        return "\n".join(entries)
    except Exception as e:
        return f"Error listing directory: {str(e)}"


@tool("search_files")
def search_files_tool(path: str, pattern: str) -> str:
    """
    Search for files matching a glob pattern in the given directory.
    Example patterns: '*.py', '**/*.ts', 'test_*.py'
    Use this to find relevant files before reading or editing them.
    """
    try:
        p = Path(path)
        if not p.exists():
            return f"Error: Path does not exist: {path}"

        skip = {".git", "node_modules", "venv", ".venv", "__pycache__", "memory"}
        matches = []

        for match in p.glob(pattern):
            # Skip files in ignored directories
            parts = match.parts
            if any(s in parts for s in skip):
                continue
            rel = match.relative_to(p)
            matches.append(str(rel))

        if not matches:
            return f"No files matching '{pattern}' found in {path}"

        result = f"Found {len(matches)} file(s) matching '{pattern}':\n"
        for m in sorted(matches)[:50]:
            result += f"  {m}\n"

        if len(matches) > 50:
            result += f"  ... and {len(matches) - 50} more"

        return result
    except Exception as e:
        return f"Error searching files: {str(e)}"
