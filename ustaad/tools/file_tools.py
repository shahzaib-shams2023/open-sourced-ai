from pathlib import Path
from crewai.tools import tool

def read_file(path):
    try:
        return Path(path).read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        return f"Error: Could not read file at '{path}': {str(e)}"

def write_file(path, content):
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"Success: Written content to {path}"
    except Exception as e:
        return f"Error: Could not write to file at '{path}': {str(e)}"

def append_file(path, content):
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(content)
        return f"Success: Appended content to {path}"
    except Exception as e:
        return f"Error: Could not append to file at '{path}': {str(e)}"

@tool("read_file")
def read_file_tool(path: str) -> str:
    """Reads the contents of a file at the given path."""
    return read_file(path)

@tool("write_file")
def write_file_tool(path: str, content: str) -> str:
    """Writes the content to a file at the given path."""
    return write_file(path, content)

@tool("append_file")
def append_file_tool(path: str, content: str) -> str:
    """Appends the content to a file at the given path."""
    return append_file(path, content)
