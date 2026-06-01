"""
USTAAD Operator Dashboard Server

Zero-dependency background HTTP server that serves the premium glassmorphic
desktop dashboard on localhost:8000. Uses Python's built-in http.server module
to avoid adding any new requirements.
"""

import os
import json
import threading
import webbrowser
from http.server import HTTPServer, SimpleHTTPRequestHandler
from functools import partial
from rich.console import Console

console = Console()

_DASHBOARD_THREAD = None
_DASHBOARD_SERVER = None


class DashboardHandler(SimpleHTTPRequestHandler):
    """Custom handler that serves dashboard files and provides JSON API endpoints."""

    def __init__(self, *args, workspace: str = None, **kwargs):
        self.workspace = workspace or os.getcwd()
        super().__init__(*args, **kwargs)

    def do_GET(self):
        # JSON API endpoints
        if self.path == "/api/status":
            self._send_json(self._get_status())
            return
        elif self.path == "/api/skills":
            self._send_json(self._get_skills())
            return
        elif self.path == "/api/security":
            self._send_json(self._get_security())
            return
        elif self.path == "/api/session":
            self._send_json(self._get_session())
            return
        elif self.path == "/api/scan":
            self._send_json(self._get_scan())
            return

        # Static file serving
        super().do_GET()

    def log_message(self, format, *args):
        """Suppress default HTTP log messages to keep the REPL clean."""
        pass

    def _send_json(self, data: dict):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def _get_status(self) -> dict:
        """Return system health status."""
        import socket
        ollama_online = False
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1.0)
            s.connect(("127.0.0.1", 11434))
            s.close()
            ollama_online = True
        except Exception:
            pass

        ws_online = False
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1.0)
            s.connect(("127.0.0.1", 8765))
            s.close()
            ws_online = True
        except Exception:
            pass

        kit_installed = os.path.isdir(os.path.join(self.workspace, ".ustaad-kit"))
        has_docs = os.path.isdir(os.path.join(self.workspace, "docs"))
        has_git = os.path.isdir(os.path.join(self.workspace, ".git"))

        try:
            from ustaad.core.execution_mode import get_mode
            mode = get_mode()
            mode_str = "AUTONOMOUS" if mode.autonomous else ("SAFE" if mode.safe else "SEMI-AUTO")
        except Exception:
            mode_str = "UNKNOWN"

        return {
            "ollama": ollama_online,
            "websocket": ws_online,
            "kit_installed": kit_installed,
            "has_docs": has_docs,
            "has_git": has_git,
            "mode": mode_str,
            "workspace": os.path.basename(self.workspace),
        }

    def _get_skills(self) -> dict:
        """Return list of dynamically loaded skills/plugins."""
        plugins_dir = os.path.join(self.workspace, ".ustaad", "plugins")
        skills = []
        if os.path.isdir(plugins_dir):
            for f in os.listdir(plugins_dir):
                if f.endswith(".py") and not f.startswith("__"):
                    filepath = os.path.join(plugins_dir, f)
                    size_kb = os.path.getsize(filepath) / 1024
                    skills.append({
                        "name": f.replace(".py", ""),
                        "file": f,
                        "size_kb": round(size_kb, 1)
                    })
        return {"skills": skills, "count": len(skills)}

    def _get_security(self) -> dict:
        """Return latest security scan results."""
        try:
            from ustaad.operator.security_scanner import run_security_scan
            return run_security_scan(self.workspace)
        except Exception as e:
            return {"score": -1, "findings": [], "error": str(e)}

    def _get_session(self) -> dict:
        """Return saved session context."""
        session_file = os.path.join(self.workspace, ".ustaad", "session_context.json")
        if os.path.isfile(session_file):
            try:
                with open(session_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"active_files": [], "stats": {}}

    def _get_scan(self) -> dict:
        """Return workspace scan data."""
        try:
            from ustaad.core.scanner import WorkspaceScanner
            scanner = WorkspaceScanner(self.workspace)
            result = scanner.scan()
            return {
                "languages": result.languages,
                "frameworks": result.frameworks,
                "file_count": result.file_count,
                "has_git": result.has_git,
                "docker": result.docker,
                "test_frameworks": result.test_frameworks,
                "linters": result.linters,
            }
        except Exception as e:
            return {"error": str(e)}


def start_dashboard(workspace: str = None, port: int = 8000, open_browser: bool = True) -> bool:
    """
    Launches the Operator Kit dashboard HTTP server on a background thread.
    Serves static files from the dashboard/ directory alongside JSON API endpoints.
    """
    global _DASHBOARD_THREAD, _DASHBOARD_SERVER
    workspace = workspace or os.getcwd()

    if _DASHBOARD_THREAD is not None and _DASHBOARD_THREAD.is_alive():
        console.print("[yellow]⚠ Dashboard server is already running.[/yellow]")
        if open_browser:
            webbrowser.open(f"http://localhost:{port}")
        return False

    dashboard_dir = os.path.join(os.path.dirname(__file__), "dashboard")
    if not os.path.isdir(dashboard_dir):
        console.print("[bold red]✗ Dashboard UI files directory not found.[/bold red]")
        return False

    handler_class = partial(DashboardHandler, directory=dashboard_dir, workspace=workspace)

    try:
        _DASHBOARD_SERVER = HTTPServer(("127.0.0.1", port), handler_class)
    except OSError as e:
        console.print(f"[bold red]✗ Dashboard server port {port} is already in use: {e}[/bold red]")
        return False

    _DASHBOARD_THREAD = threading.Thread(target=_DASHBOARD_SERVER.serve_forever, daemon=True)
    _DASHBOARD_THREAD.start()

    console.print(f"[bold green]✓ Dashboard server launched at http://localhost:{port}[/bold green]")

    if open_browser:
        webbrowser.open(f"http://localhost:{port}")

    return True


def stop_dashboard():
    """Shuts down the background dashboard server."""
    global _DASHBOARD_SERVER, _DASHBOARD_THREAD
    if _DASHBOARD_SERVER:
        _DASHBOARD_SERVER.shutdown()
        _DASHBOARD_SERVER = None
        _DASHBOARD_THREAD = None
        console.print("[bold green]✓ Dashboard server stopped.[/bold green]")
        return True
    return False
