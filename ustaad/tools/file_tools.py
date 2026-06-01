import os
import re
from pathlib import Path
from crewai.tools import tool

from ustaad.core.safety import get_safety_gate
from ustaad.core.permissions import get_permission_manager, PermissionLevel
from ustaad.core.secrets import get_secret_scanner
from ustaad.core.events import get_event_bus, EventType


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
        perms = get_permission_manager(os.getcwd())
        if perms.check_file_access(path, "read") == PermissionLevel.DENY:
            return f"[BLOCKED] Permission denied to read: {path}"
        return Path(path).read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        return f"Error: Could not read file at '{path}': {str(e)}"


def write_file(path: str, content: str) -> str:
    try:
        p = Path(path)
        is_overwrite = p.exists()

        perms = get_permission_manager(os.getcwd())
        perm_level = perms.check_file_access(path, "write")
        if perm_level == PermissionLevel.DENY:
            return f"[BLOCKED] Permission denied to write: {path}"

        # Safety gate for overwrites of critical files
        if is_overwrite or perm_level == PermissionLevel.CONFIRM:
            gate = get_safety_gate()
            if not gate.confirm_file_write(str(p), is_overwrite=is_overwrite):
                return f"[BLOCKED] User rejected write of: {path}"

        # Real-time Secret Scanning
        scanner = get_secret_scanner()
        findings = scanner.scan_content(content, path)
        if findings:
            from rich.console import Console
            c = Console()
            c.print(f"[bold red]⚠ BLOCKED: Secrets detected in {path}[/bold red]")
            c.print(f"[yellow]{scanner.format_findings(findings)}[/yellow]")
            return f"[BLOCKED] Secret detected in content. Remove secrets before writing."

        # Sanitize LLM output corruptions
        content = _sanitize_html_content(content, path)

        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        
        get_event_bus().emit(EventType.POST_FILE_WRITE, data={"path": path})
        action = "Overwritten" if is_overwrite else "Created"
        return f"Success: {action} {path}"
    except Exception as e:
        return f"Error: Could not write to file at '{path}': {str(e)}"


def append_file(path: str, content: str) -> str:
    try:
        p = Path(path)
        
        perms = get_permission_manager(os.getcwd())
        perm_level = perms.check_file_access(path, "write")
        if perm_level == PermissionLevel.DENY:
            return f"[BLOCKED] Permission denied to append: {path}"
            
        if perm_level == PermissionLevel.CONFIRM:
            gate = get_safety_gate()
            if not gate.confirm_file_write(str(p), is_overwrite=True):
                return f"[BLOCKED] User rejected append to: {path}"
                
        # Real-time Secret Scanning
        scanner = get_secret_scanner()
        findings = scanner.scan_content(content, path)
        if findings:
            return f"[BLOCKED] Secret detected in content. Remove secrets before writing."

        p.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(content)
            
        get_event_bus().emit(EventType.FILE_CHANGED, data={"path": path, "action": "append"})
        return f"Success: Appended content to {path}"
    except Exception as e:
        return f"Error: Could not append to file at '{path}': {str(e)}"


def delete_file(path: str) -> str:
    try:
        p = Path(path)
        if not p.exists():
            return f"Error: File does not exist: {path}"

        perms = get_permission_manager(os.getcwd())
        if perms.check_file_access(path, "delete") == PermissionLevel.DENY:
            return f"[BLOCKED] Permission denied to delete: {path}"

        gate = get_safety_gate()
        if not gate.confirm_file_delete(str(p)):
            return f"[BLOCKED] User rejected deletion of: {path}"

        p.unlink()
        get_event_bus().emit(EventType.FILE_CHANGED, data={"path": path, "action": "delete"})
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


def get_file_skeleton(path: str) -> str:
    """Generates a skeleton map of classes and functions for a file."""
    try:
        p = Path(path)
        if not p.exists():
            return f"Error: File does not exist: {path}"
            
        content = p.read_text(encoding="utf-8", errors="ignore")
        ext = p.suffix.lower()
        skeleton = []
        
        if ext == ".py":
            import ast
            try:
                tree = ast.parse(content)
                class SkeletonVisitor(ast.NodeVisitor):
                    def visit_ClassDef(self, node):
                        skeleton.append(f"{node.lineno}: class {node.name}:")
                        self.generic_visit(node)
                    def visit_FunctionDef(self, node):
                        skeleton.append(f"{node.lineno}: {'    ' if getattr(node, 'is_method', False) else ''}def {node.name}(...):")
                    def visit_AsyncFunctionDef(self, node):
                        skeleton.append(f"{node.lineno}: {'    ' if getattr(node, 'is_method', False) else ''}async def {node.name}(...):")
                
                # Tag methods to indent them
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        for child in node.body:
                            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                                child.is_method = True
                
                SkeletonVisitor().visit(tree)
            except Exception:
                pass
        
        # Fallback / JS / TS regex approach
        if not skeleton:
            lines = content.splitlines()
            for i, line in enumerate(lines):
                if re.match(r"^\s*(?:export\s+)?(?:default\s+)?(?:class|interface|function|def|async\s+def)\s+\w+", line):
                    if len(line) - len(line.lstrip()) <= 4:
                        skeleton.append(f"{i+1}: {line.rstrip()}")
                        
        if not skeleton:
            return "No classes or functions found."
            
        return "\n".join(skeleton)
    except Exception as e:
        return f"Error extracting skeleton: {str(e)}"


@tool("get_file_skeleton")
def get_file_skeleton_tool(path: str) -> str:
    """
    Returns a highly condensed AST skeleton of a file, showing only 
    class and function definitions with their line numbers.
    Use this to understand a file's structure quickly and save context tokens
    before reading the entire file.
    """
    return get_file_skeleton(path)


@tool("find_symbol")
def find_symbol_tool(symbol_name: str, path: str = ".") -> str:
    """
    Finds all definitions and references of a specific symbol (class, function, variable)
    in the workspace. Serves as 'Go To Definition' and 'Find References'.
    """
    try:
        import os
        import subprocess
        # Search for exact word boundary matches to avoid partial matches
        cmd = f"rg -n -w '{symbol_name}' {path}"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=os.getcwd())
        if result.returncode != 0 and not result.stdout:
            # Fallback to git grep
            cmd = f"git grep -n -w '{symbol_name}'"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=os.getcwd())
            if result.returncode != 0 and not result.stdout:
                return f"Symbol '{symbol_name}' not found."
                
        out = result.stdout
        if len(out) > 4000:
            out = out[:4000] + "\n...[TRUNCATED]"
        return f"Symbol navigation results for '{symbol_name}':\n{out}"
    except Exception as e:
        return f"Search failed: {str(e)}"


@tool("ast_refactor")
def ast_refactor_tool(path: str, old_name: str, new_name: str) -> str:
    """
    Safely renames a class, function, or variable across a single file using 
    AST-aware replacement (or strict word-boundary regex for non-Python).
    """
    try:
        p = Path(path)
        if not p.exists():
            return f"Error: File does not exist: {path}"
            
        content = p.read_text(encoding="utf-8", errors="ignore")
        
        # Simple but safe word-boundary replacement
        import re
        # Avoid replacing inside strings by matching identifier boundaries
        pattern = r'\b' + re.escape(old_name) + r'\b'
        new_content = re.sub(pattern, new_name, content)
        
        if new_content == content:
            return f"Symbol '{old_name}' not found in {path}"
            
        return write_file(path, new_content)
    except Exception as e:
        return f"AST Refactor failed: {str(e)}"

@tool("analyze_dependencies")
def analyze_dependencies_tool(path: str = ".") -> str:
    """
    Analyzes project dependencies (requirements.txt, package.json, pyproject.toml)
    and returns a summary of the dependency graph and any detected outdated/insecure packages.
    """
    try:
        import os
        results = []
        if os.path.exists(os.path.join(path, "requirements.txt")):
            results.append("Found requirements.txt. Managing Python dependencies.")
            reqs = Path(os.path.join(path, "requirements.txt")).read_text()
            results.append(f"Dependencies: {len(reqs.splitlines())} packages.")
        if os.path.exists(os.path.join(path, "package.json")):
            results.append("Found package.json. Managing Node.js dependencies.")
            import json
            try:
                pkg = json.loads(Path(os.path.join(path, "package.json")).read_text())
                deps = len(pkg.get("dependencies", {})) + len(pkg.get("devDependencies", {}))
                results.append(f"Dependencies: {deps} packages.")
            except:
                pass
                
        if not results:
            return "No recognized dependency files found (requirements.txt, package.json)."
            
        return "\n".join(results)
    except Exception as e:
        return f"Dependency analysis failed: {str(e)}"

