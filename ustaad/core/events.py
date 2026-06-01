"""
USTAAD Event System — Lifecycle Hooks & Event Bus

Central event bus for the entire agent system. Allows plugins, hooks,
and internal components to subscribe to lifecycle events.

Supports:
- Synchronous and async event handlers
- Priority-ordered execution
- Shell hooks (run external commands)
- HTTP/webhook hooks
- Agent hooks (trigger agent actions)
- Event filtering by pattern
- Event history for debugging

Events:
    SessionStart, SessionEnd, UserPromptSubmit,
    PreToolUse, PostToolUse, ToolFailure,
    TaskCreated, TaskCompleted, TaskFailed,
    ContextCompaction, FileChanged, ConfigChanged,
    AgentSpawned, AgentCompleted, MemoryCreated,
    PreFileWrite, PostFileWrite, PreCommand, PostCommand
"""

import os
import time
import json
import threading
import subprocess
from enum import Enum
from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Dict, List, Optional
from pathlib import Path

from rich.console import Console

console = Console()


class EventType(str, Enum):
    """All lifecycle events in the Ustaad system."""
    # Session lifecycle
    SESSION_START = "session_start"
    SESSION_END = "session_end"

    # User interaction
    USER_PROMPT_SUBMIT = "user_prompt_submit"

    # Tool lifecycle
    PRE_TOOL_USE = "pre_tool_use"
    POST_TOOL_USE = "post_tool_use"
    TOOL_FAILURE = "tool_failure"

    # Task lifecycle
    TASK_CREATED = "task_created"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"

    # Context management
    CONTEXT_COMPACTION = "context_compaction"

    # File operations
    FILE_CHANGED = "file_changed"
    PRE_FILE_WRITE = "pre_file_write"
    POST_FILE_WRITE = "post_file_write"

    # Config
    CONFIG_CHANGED = "config_changed"

    # Agent lifecycle
    AGENT_SPAWNED = "agent_spawned"
    AGENT_COMPLETED = "agent_completed"

    # Memory
    MEMORY_CREATED = "memory_created"
    MEMORY_PRUNED = "memory_pruned"

    # Command lifecycle
    PRE_COMMAND = "pre_command"
    POST_COMMAND = "post_command"

    # Pipeline
    PIPELINE_PHASE_START = "pipeline_phase_start"
    PIPELINE_PHASE_END = "pipeline_phase_end"


@dataclass
class Event:
    """A single event in the system."""
    type: EventType
    timestamp: float = field(default_factory=time.time)
    data: Dict[str, Any] = field(default_factory=dict)
    source: str = ""
    cancelled: bool = False

    def cancel(self):
        """Cancel this event (prevents further handlers from running)."""
        self.cancelled = True

    def to_dict(self) -> dict:
        return {
            "type": self.type.value,
            "timestamp": self.timestamp,
            "data": self.data,
            "source": self.source,
            "cancelled": self.cancelled,
        }


@dataclass
class EventHandler:
    """A registered event handler."""
    callback: Callable
    event_type: EventType
    priority: int = 50  # lower = runs first
    name: str = ""
    once: bool = False  # if True, unsubscribe after first call
    _called: bool = False


class HookType(str, Enum):
    """Types of external hooks."""
    SHELL = "shell"
    HTTP = "http"
    AGENT = "agent"


@dataclass
class HookConfig:
    """Configuration for an external hook."""
    hook_type: HookType
    event_type: EventType
    command: str = ""  # for shell hooks
    url: str = ""  # for HTTP hooks
    agent_role: str = ""  # for agent hooks
    timeout: int = 30
    enabled: bool = True


class EventBus:
    """
    Central event bus for Ustaad.
    
    Usage:
        bus = get_event_bus()
        
        # Subscribe to events
        bus.on(EventType.PRE_TOOL_USE, my_handler, priority=10)
        
        # Emit events
        bus.emit(EventType.PRE_TOOL_USE, data={"tool": "write_file", "args": {...}})
        
        # Load hooks from config
        bus.load_hooks_from_config(workspace)
    """

    def __init__(self):
        self._handlers: Dict[EventType, List[EventHandler]] = {}
        self._history: List[Event] = []
        self._max_history = 1000
        self._hooks: List[HookConfig] = []
        self._lock = threading.Lock()

    def on(
        self,
        event_type: EventType,
        callback: Callable,
        priority: int = 50,
        name: str = "",
        once: bool = False,
    ) -> EventHandler:
        """Subscribe to an event type."""
        handler = EventHandler(
            callback=callback,
            event_type=event_type,
            priority=priority,
            name=name or getattr(callback, "__name__", "anonymous"),
            once=once,
        )
        with self._lock:
            if event_type not in self._handlers:
                self._handlers[event_type] = []
            self._handlers[event_type].append(handler)
            self._handlers[event_type].sort(key=lambda h: h.priority)
        return handler

    def once(self, event_type: EventType, callback: Callable, priority: int = 50) -> EventHandler:
        """Subscribe to an event type, auto-unsubscribe after first call."""
        return self.on(event_type, callback, priority=priority, once=True)

    def off(self, handler: EventHandler):
        """Unsubscribe a handler."""
        with self._lock:
            handlers = self._handlers.get(handler.event_type, [])
            if handler in handlers:
                handlers.remove(handler)

    def off_all(self, event_type: EventType = None):
        """Remove all handlers, optionally for a specific event type."""
        with self._lock:
            if event_type:
                self._handlers[event_type] = []
            else:
                self._handlers.clear()

    def emit(self, event_type: EventType, data: Dict[str, Any] = None, source: str = "") -> Event:
        """
        Emit an event, executing all handlers in priority order.
        
        Returns the Event object (check .cancelled for cancellation).
        """
        event = Event(type=event_type, data=data or {}, source=source)

        # Record in history
        with self._lock:
            self._history.append(event)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]

        # Execute handlers
        handlers = self._handlers.get(event_type, [])
        handlers_to_remove = []

        for handler in handlers:
            if event.cancelled:
                break
            try:
                handler.callback(event)
                if handler.once:
                    handlers_to_remove.append(handler)
            except Exception as e:
                console.print(f"[dim yellow]   ⚠ Event handler '{handler.name}' failed: {e}[/dim yellow]")

        # Clean up one-shot handlers
        for h in handlers_to_remove:
            self.off(h)

        # Execute external hooks
        self._execute_hooks(event)

        return event

    def _execute_hooks(self, event: Event):
        """Execute external hooks (shell, HTTP, agent) for an event."""
        for hook in self._hooks:
            if not hook.enabled or hook.event_type != event.type:
                continue

            try:
                if hook.hook_type == HookType.SHELL:
                    self._execute_shell_hook(hook, event)
                elif hook.hook_type == HookType.HTTP:
                    self._execute_http_hook(hook, event)
            except Exception as e:
                console.print(f"[dim yellow]   ⚠ Hook execution failed: {e}[/dim yellow]")

    def _execute_shell_hook(self, hook: HookConfig, event: Event):
        """Execute a shell command hook."""
        env = os.environ.copy()
        env["USTAAD_EVENT_TYPE"] = event.type.value
        env["USTAAD_EVENT_DATA"] = json.dumps(event.data, default=str)
        env["USTAAD_EVENT_SOURCE"] = event.source

        try:
            result = subprocess.run(
                hook.command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=hook.timeout,
                env=env,
            )
            if result.returncode != 0:
                console.print(f"[dim yellow]   ⚠ Shell hook failed: {result.stderr[:200]}[/dim yellow]")
        except subprocess.TimeoutExpired:
            console.print(f"[dim yellow]   ⚠ Shell hook timed out after {hook.timeout}s[/dim yellow]")

    def _execute_http_hook(self, hook: HookConfig, event: Event):
        """Execute an HTTP webhook."""
        try:
            import urllib.request
            payload = json.dumps(event.to_dict(), default=str).encode("utf-8")
            req = urllib.request.Request(
                hook.url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=hook.timeout)
        except Exception as e:
            console.print(f"[dim yellow]   ⚠ HTTP hook failed: {e}[/dim yellow]")

    def load_hooks_from_config(self, workspace: str):
        """Load hook configurations from .ustaad/hooks.yaml or .ustaad/hooks.json."""
        hooks_yaml = os.path.join(workspace, ".ustaad", "hooks.yaml")
        hooks_json = os.path.join(workspace, ".ustaad", "hooks.json")

        config_data = None
        if os.path.isfile(hooks_yaml):
            try:
                import yaml
                config_data = yaml.safe_load(Path(hooks_yaml).read_text(encoding="utf-8"))
            except Exception:
                pass
        elif os.path.isfile(hooks_json):
            try:
                config_data = json.loads(Path(hooks_json).read_text(encoding="utf-8"))
            except Exception:
                pass

        if not config_data or not isinstance(config_data, dict):
            return

        hooks_list = config_data.get("hooks", [])
        for hook_def in hooks_list:
            try:
                hook = HookConfig(
                    hook_type=HookType(hook_def.get("type", "shell")),
                    event_type=EventType(hook_def.get("event", "")),
                    command=hook_def.get("command", ""),
                    url=hook_def.get("url", ""),
                    agent_role=hook_def.get("agent_role", ""),
                    timeout=hook_def.get("timeout", 30),
                    enabled=hook_def.get("enabled", True),
                )
                self._hooks.append(hook)
            except (ValueError, KeyError):
                pass

    def get_history(self, event_type: EventType = None, limit: int = 50) -> List[Event]:
        """Get event history, optionally filtered by type."""
        with self._lock:
            if event_type:
                filtered = [e for e in self._history if e.type == event_type]
            else:
                filtered = list(self._history)
            return filtered[-limit:]

    def get_handler_count(self) -> Dict[str, int]:
        """Return handler count per event type."""
        return {et.value: len(handlers) for et, handlers in self._handlers.items() if handlers}


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------
_event_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """Get the global event bus singleton."""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus
