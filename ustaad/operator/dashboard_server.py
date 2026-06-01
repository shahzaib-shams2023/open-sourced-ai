import os
import threading
import webbrowser
import subprocess
from rich.console import Console

console = Console()

_DASHBOARD_PROCESS = None

def start_dashboard(workspace: str = None, port: int = 8000, open_browser: bool = True) -> bool:
    """
    Launches the FastAPI Dashboard server in a background process.
    Serves the Next.js static UI and WebSockets on port 8000.
    """
    global _DASHBOARD_PROCESS
    
    if _DASHBOARD_PROCESS is not None and _DASHBOARD_PROCESS.poll() is None:
        # Dashboard is already running, don't spam browser tabs on every task
        return False
        
    try:
        env = os.environ.copy()
        env["PYTHONPATH"] = os.getcwd()
        
        # We start the uvicorn server in a subprocess to prevent asyncio event loop clashes
        _DASHBOARD_PROCESS = subprocess.Popen(
            ["uvicorn", "ustaad.server.main:app", "--port", str(port)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env
        )
        
        console.print(f"[bold green]✓ Visualizer Dashboard running at http://localhost:{port}[/bold green]")
        
        if open_browser:
            # Short delay to allow uvicorn to bind
            threading.Timer(1.0, lambda: webbrowser.open(f"http://localhost:{port}")).start()
            
        return True
    except Exception as e:
        console.print(f"[bold red]✗ Failed to start visualizer server: {e}[/bold red]")
        return False

def stop_dashboard():
    """Shuts down the background dashboard server."""
    global _DASHBOARD_PROCESS
    if _DASHBOARD_PROCESS is not None:
        _DASHBOARD_PROCESS.terminate()
        _DASHBOARD_PROCESS.wait(timeout=3)
        _DASHBOARD_PROCESS = None
        console.print("[bold green]✓ Visualizer server stopped.[/bold green]")
        return True
    return False
