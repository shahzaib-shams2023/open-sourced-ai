import os
import json
from rich.console import Console

console = Console()

def save_session(workspace: str = None) -> bool:
    """
    Saves the active CLI session context (active files, active configurations)
    to .ustaad/session_context.json.
    """
    workspace = workspace or os.getcwd()
    ustaad_dir = os.path.join(workspace, ".ustaad")
    os.makedirs(ustaad_dir, exist_ok=True)
    
    session_file = os.path.join(ustaad_dir, "session_context.json")
    
    try:
        # Import context lists from cli.py
        from ustaad.cli import ACTIVE_CONTEXT_FILES, COMMAND_STATS
        from ustaad.core.execution_mode import get_mode
        
        mode = get_mode()
        payload = {
            "active_files": [os.path.relpath(f, workspace) if os.path.isabs(f) else f for f in ACTIVE_CONTEXT_FILES],
            "stats": COMMAND_STATS,
            "mode": {
                "safe": mode.safe,
                "autonomous": mode.autonomous,
                "confirm": mode.confirm_destructive
            },
            "saved_at": os.path.getmtime(ustaad_dir) if os.path.exists(ustaad_dir) else 0.0
        }
        
        with open(session_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
            
        console.print(f"[bold green]✓ Session context saved successfully to .ustaad/session_context.json ({len(payload['active_files'])} file(s) cached)[/bold green]")
        return True
    except Exception as e:
        console.print(f"[bold red]✗ Failed to save active session context:[/bold red] {e}")
        return False


def load_session(workspace: str = None) -> bool:
    """
    Restores the saved session context list into the active ustaad CLI instance.
    """
    workspace = workspace or os.getcwd()
    session_file = os.path.join(workspace, ".ustaad", "session_context.json")
    
    if not os.path.isfile(session_file):
        console.print("[yellow]No saved Ustaad session context found. Use /save to cache your current state.[/yellow]")
        return False
        
    try:
        with open(session_file, "r", encoding="utf-8") as f:
            payload = json.load(f)
            
        from ustaad.cli import ACTIVE_CONTEXT_FILES, COMMAND_STATS
        from ustaad.core.execution_mode import set_mode
        
        # Restore active files list
        ACTIVE_CONTEXT_FILES.clear()
        for f in payload.get("active_files", []):
            abs_path = os.path.abspath(os.path.join(workspace, f))
            if os.path.isfile(abs_path):
                ACTIVE_CONTEXT_FILES.append(abs_path)

        # Restore stats
        loaded_stats = payload.get("stats", {})
        for k, v in loaded_stats.items():
            if k in COMMAND_STATS:
                COMMAND_STATS[k] = v

        # Restore execution mode
        mode_data = payload.get("mode", {})
        if mode_data:
            set_mode(
                safe=mode_data.get("safe", True),
                autonomous=mode_data.get("autonomous", False),
                confirm_destructive=mode_data.get("confirm", True)
            )

        console.print(f"[bold green]✓ Session successfully restored. Loaded {len(ACTIVE_CONTEXT_FILES)} active file(s) into context.[/bold green]")
        return True
    except Exception as e:
        console.print(f"[bold red]✗ Failed to load active session context:[/bold red] {e}")
        return False
