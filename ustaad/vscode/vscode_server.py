"""
USTAAD VS Code & IDE Workspace Server

This module implements a highly robust, bidirectional WebSocket server for
connecting Ustaad directly to IDE extensions (like VS Code or Cursor).
It allows external editors to trigger tasks, manage workspace context,
request AST scans, and listen to a real-time progress stream of the agent swarm.
"""

import os
import json
import asyncio
import threading
from typing import Set, Any, Optional
import websockets
from rich.console import Console

console = Console()

# Active connection clients
_CONNECTED_CLIENTS: Set[Any] = set()
_SERVER_THREAD: Optional[threading.Thread] = None
_EVENT_LOOP: Optional[asyncio.AbstractEventLoop] = None


async def broadcast_progress(phase: str, message: str, status: str = "running"):
    """
    Broadcasts swarm progress phase telemetry to all active IDE connections.
    """
    if not _CONNECTED_CLIENTS:
        return
        
    payload = {
        "event": "progress",
        "data": {
            "phase": phase,
            "message": message,
            "status": status
        }
    }
    message_str = json.dumps(payload)
    
    # Send message to all connected clients
    for client in list(_CONNECTED_CLIENTS):
        try:
            await client.send(message_str)
        except Exception:
            _CONNECTED_CLIENTS.remove(client)


async def handle_client(websocket):
    """
    Processes incoming messages from connected IDE clients.
    """
    _CONNECTED_CLIENTS.add(websocket)
    console.print(f"[bold green][CONNECTED] VS Code Extension connected to Ustaad IDE Server.[/bold green]")
    
    try:
        async for raw_message in websocket:
            try:
                message = json.loads(raw_message)
                action = message.get("action")
                payload = message.get("payload", {})
                message_id = message.get("id")
                
                if not action:
                    await websocket.send(json.dumps({"error": "Missing 'action' parameter", "id": message_id}))
                    continue

                response_payload = {}
                
                # --- API Routes ---
                if action == "execute_task":
                    # Run task via main orchestrator
                    prompt = payload.get("prompt")
                    if not prompt:
                        response_payload = {"error": "Missing prompt for task execution"}
                    else:
                        await broadcast_progress("ROUTE", f"Routing request: {prompt}")
                        from ustaad.main import run_task
                        
                        # Run the task synchronously in an executor to avoid locking the loop
                        loop = asyncio.get_running_loop()
                        result = await loop.run_in_executor(None, run_task, prompt, os.getcwd())
                        
                        await broadcast_progress("COMPLETE", "Task completed", "done")
                        response_payload = {"result": result}
                        
                elif action == "scan_workspace":
                    # Run workspace scanner
                    from ustaad.core.scanner import WorkspaceScanner
                    scanner = WorkspaceScanner(os.getcwd())
                    scan_info = scanner.scan()
                    response_payload = {
                        "file_count": scan_info.file_count,
                        "languages": list(scan_info.languages),
                        "frameworks": list(scan_info.frameworks)
                    }
                    
                elif action == "manage_context":
                    # Add/drop files from context
                    from ustaad.cli import ACTIVE_CONTEXT_FILES
                    sub_action = payload.get("sub_action") # "add" or "drop" or "list"
                    file_path = payload.get("file_path")
                    
                    if sub_action == "add" and file_path:
                        if file_path not in ACTIVE_CONTEXT_FILES:
                            ACTIVE_CONTEXT_FILES.append(file_path)
                        response_payload = {"status": "added", "context": ACTIVE_CONTEXT_FILES}
                    elif sub_action == "drop" and file_path:
                        if file_path in ACTIVE_CONTEXT_FILES:
                            ACTIVE_CONTEXT_FILES.remove(file_path)
                        response_payload = {"status": "dropped", "context": ACTIVE_CONTEXT_FILES}
                    else:
                        response_payload = {"context": ACTIVE_CONTEXT_FILES}

                elif action == "get_status":
                    # VSCode telemetry: system health status
                    import socket as _sock
                    ollama_up = False
                    try:
                        s = _sock.socket(_sock.AF_INET, _sock.SOCK_STREAM)
                        s.settimeout(1.0)
                        s.connect(("127.0.0.1", 11434))
                        s.close()
                        ollama_up = True
                    except Exception:
                        pass
                    kit_ok = os.path.isdir(os.path.join(os.getcwd(), ".ustaad-kit"))
                    try:
                        from ustaad.core.execution_mode import get_mode as _gm
                        _m = _gm()
                        mode_str = "AUTONOMOUS" if _m.autonomous else ("SAFE" if _m.safe else "SEMI-AUTO")
                    except Exception:
                        mode_str = "UNKNOWN"
                    response_payload = {
                        "ollama": ollama_up,
                        "websocket": True,
                        "kit_installed": kit_ok,
                        "has_docs": os.path.isdir(os.path.join(os.getcwd(), "docs")),
                        "has_git": os.path.isdir(os.path.join(os.getcwd(), ".git")),
                        "mode": mode_str,
                        "workspace": os.path.basename(os.getcwd()),
                    }

                elif action == "get_skills":
                    # VSCode telemetry: dynamic skills list
                    plugins_dir = os.path.join(os.getcwd(), ".ustaad", "plugins")
                    skills = []
                    if os.path.isdir(plugins_dir):
                        for f in os.listdir(plugins_dir):
                            if f.endswith(".py") and not f.startswith("__"):
                                skills.append({"name": f.replace(".py", ""), "file": f})
                    response_payload = {"skills": skills, "count": len(skills)}

                elif action == "security_scan":
                    # VSCode telemetry: run security audit
                    try:
                        from ustaad.operator.security_scanner import run_security_scan
                        response_payload = run_security_scan(os.getcwd())
                    except Exception as scan_err:
                        response_payload = {"score": -1, "findings": [], "error": str(scan_err)}

                else:
                    response_payload = {"error": f"Unknown action: {action}"}

                # Send success response
                await websocket.send(json.dumps({
                    "id": message_id,
                    "action": action,
                    "success": "error" not in response_payload,
                    "payload": response_payload
                }))
                
            except json.JSONDecodeError:
                await websocket.send(json.dumps({"error": "Invalid JSON format"}))
            except Exception as e:
                await websocket.send(json.dumps({"error": f"Internal execution error: {str(e)}", "id": message_id}))
                
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        _CONNECTED_CLIENTS.remove(websocket)
        console.print("[dim]VS Code Extension disconnected from Ustaad IDE Server.[/dim]")


async def start_server_async(host: str, port: int):
    async with websockets.serve(handle_client, host, port):
        console.print(f"[bold green][ONLINE] Bidirectional IDE integration server online on ws://{host}:{port}[/bold green]")
        await asyncio.Future()  # run forever


def start_server_in_loop(host: str, port: int):
    """Initializes and runs the asyncio websocket loop."""
    global _EVENT_LOOP
    _EVENT_LOOP = asyncio.new_event_loop()
    asyncio.set_event_loop(_EVENT_LOOP)
    try:
        _EVENT_LOOP.run_until_complete(start_server_async(host, port))
    except Exception as e:
        console.print(f"[bold red][ERROR] VS Code integration server error: {e}[/bold red]")


def start_vscode_server(host: str = "127.0.0.1", port: int = 8765):
    """
    Launches the VS Code workspace server in a background thread to prevent blocking.
    """
    global _SERVER_THREAD
    if _SERVER_THREAD is not None and _SERVER_THREAD.is_alive():
        console.print("[yellow]⚠ VS Code Server is already running.[/yellow]")
        return False
        
    _SERVER_THREAD = threading.Thread(
        target=start_server_in_loop,
        args=(host, port),
        daemon=True
    )
    _SERVER_THREAD.start()
    return True


def stop_vscode_server():
    """Stops the active background server loop."""
    global _EVENT_LOOP, _SERVER_THREAD
    if _EVENT_LOOP:
        _EVENT_LOOP.call_soon_threadsafe(_EVENT_LOOP.stop)
        console.print("[yellow]VS Code integration server stopped.[/yellow]")
        _EVENT_LOOP = None
        _SERVER_THREAD = None
        return True
    return False


def send_progress_update(phase: str, message: str, status: str = "running"):
    """
    Safely sends a progress update from synchronous code to the active websocket server.
    """
    global _EVENT_LOOP
    if not _CONNECTED_CLIENTS or not _EVENT_LOOP:
        return
        
    try:
        if _EVENT_LOOP.is_running():
            asyncio.run_coroutine_threadsafe(
                broadcast_progress(phase, message, status),
                _EVENT_LOOP
            )
    except Exception:
        pass
