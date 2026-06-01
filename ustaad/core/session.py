"""
USTAAD Session Manager — Conversation History & Session State

Maintains conversation history within a REPL session, provides
cross-session memory, user preferences, and session persistence.

Features:
- Full conversation history within a session
- Session save/restore
- User memory (global preferences persisted across all projects)
- Automatic context summarization when history grows large
- Session-level context injection into agent prompts
"""

import os
import json
import uuid
import time
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
from pathlib import Path

from rich.console import Console

console = Console()


@dataclass
class Message:
    """A single message in the conversation history."""
    role: str  # "user", "assistant", "system", "tool"
    content: str
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SessionState:
    """Complete state of a session."""
    session_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    workspace: str = ""
    started_at: float = field(default_factory=time.time)
    messages: List[Message] = field(default_factory=list)
    active_files: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    task_count: int = 0
    command_count: int = 0


class SessionManager:
    """
    Manages conversation history and session state.
    
    Usage:
        session = SessionManager(workspace="/path/to/project")
        session.add_user_message("build an auth system")
        session.add_assistant_message("I'll create...")
        context = session.get_context_string()
    """

    def __init__(self, workspace: str):
        self.workspace = os.path.abspath(workspace)
        self._session_dir = os.path.join(self.workspace, ".ustaad", "sessions")
        self._user_memory_dir = os.path.join(os.path.expanduser("~"), ".ustaad", "user_memory")
        os.makedirs(self._session_dir, exist_ok=True)
        os.makedirs(self._user_memory_dir, exist_ok=True)

        self.state = SessionState(workspace=self.workspace)
        self._max_context_messages = 20  # Keep last N messages for context injection
        self._max_history_chars = 50_000  # Auto-summarize beyond this

    # -----------------------------------------------------------------------
    # Message management
    # -----------------------------------------------------------------------

    def add_user_message(self, content: str, metadata: Dict[str, Any] = None):
        """Record a user message."""
        msg = Message(role="user", content=content, metadata=metadata or {})
        self.state.messages.append(msg)
        self.state.task_count += 1
        self._auto_compact()

    def add_assistant_message(self, content: str, metadata: Dict[str, Any] = None):
        """Record an assistant response."""
        msg = Message(role="assistant", content=content[:5000], metadata=metadata or {})
        self.state.messages.append(msg)

    def add_system_message(self, content: str):
        """Record a system-level message."""
        msg = Message(role="system", content=content)
        self.state.messages.append(msg)

    def add_tool_message(self, tool_name: str, result: str, metadata: Dict[str, Any] = None):
        """Record a tool execution result."""
        msg = Message(
            role="tool",
            content=result[:2000],
            metadata={"tool": tool_name, **(metadata or {})},
        )
        self.state.messages.append(msg)

    # -----------------------------------------------------------------------
    # Context retrieval
    # -----------------------------------------------------------------------

    def get_context_string(self, max_messages: int = None) -> str:
        """Build a context string from recent conversation history."""
        n = max_messages or self._max_context_messages
        recent = self.state.messages[-n:]

        if not recent:
            return ""

        lines = ["[SESSION HISTORY]"]
        for msg in recent:
            role = msg.role.upper()
            content = msg.content[:500]  # Truncate for context budget
            lines.append(f"  [{role}] {content}")

        return "\n".join(lines)

    def get_recent_user_prompts(self, n: int = 5) -> List[str]:
        """Get the N most recent user prompts."""
        user_msgs = [m for m in self.state.messages if m.role == "user"]
        return [m.content for m in user_msgs[-n:]]

    def get_conversation_summary(self) -> str:
        """Get a summary of the current conversation."""
        user_msgs = [m for m in self.state.messages if m.role == "user"]
        asst_msgs = [m for m in self.state.messages if m.role == "assistant"]

        summary = f"Session {self.state.session_id}: "
        summary += f"{len(user_msgs)} prompts, {len(asst_msgs)} responses, "
        summary += f"{self.state.task_count} tasks"

        if user_msgs:
            summary += f"\nLast prompt: {user_msgs[-1].content[:100]}"

        return summary

    # -----------------------------------------------------------------------
    # Auto-compaction
    # -----------------------------------------------------------------------

    def _auto_compact(self):
        """Automatically compact history when it grows too large."""
        total_chars = sum(len(m.content) for m in self.state.messages)
        if total_chars > self._max_history_chars:
            self.compact()

    def compact(self):
        """Compact conversation history by summarizing older messages."""
        if len(self.state.messages) <= self._max_context_messages:
            return

        # Keep the most recent messages
        keep = self.state.messages[-self._max_context_messages:]
        old = self.state.messages[:-self._max_context_messages]

        # Create a summary of old messages
        user_prompts = [m.content[:100] for m in old if m.role == "user"]
        summary_parts = []
        if user_prompts:
            summary_parts.append(f"Previous prompts ({len(user_prompts)}): " + "; ".join(user_prompts[:10]))

        tool_uses = [m.metadata.get("tool", "unknown") for m in old if m.role == "tool"]
        if tool_uses:
            from collections import Counter
            tool_counts = Counter(tool_uses)
            summary_parts.append(f"Tools used: {dict(tool_counts)}")

        if summary_parts:
            summary = Message(
                role="system",
                content="[COMPACTED HISTORY]\n" + "\n".join(summary_parts),
                metadata={"compacted": True, "original_count": len(old)},
            )
            self.state.messages = [summary] + keep
        else:
            self.state.messages = keep

        console.print(f"[dim green]   ✓ Session history compacted: {len(old)} messages summarized[/dim green]")

    # -----------------------------------------------------------------------
    # Session persistence
    # -----------------------------------------------------------------------

    def save(self) -> str:
        """Save the current session to disk."""
        path = os.path.join(self._session_dir, f"session_{self.state.session_id}.json")
        data = {
            "session_id": self.state.session_id,
            "workspace": self.state.workspace,
            "started_at": self.state.started_at,
            "saved_at": time.time(),
            "task_count": self.state.task_count,
            "command_count": self.state.command_count,
            "active_files": self.state.active_files,
            "metadata": self.state.metadata,
            "messages": [m.to_dict() for m in self.state.messages],
        }
        Path(path).write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        console.print(f"[bold green]✓ Session saved: {self.state.session_id}[/bold green]")
        return path

    def load(self, session_id: str = None) -> bool:
        """Load a session from disk. If no ID given, load the most recent."""
        if session_id:
            path = os.path.join(self._session_dir, f"session_{session_id}.json")
        else:
            # Find most recent session
            sessions = sorted(Path(self._session_dir).glob("session_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
            if not sessions:
                console.print("[yellow]No saved sessions found.[/yellow]")
                return False
            path = str(sessions[0])

        if not os.path.isfile(path):
            console.print(f"[red]Session file not found: {path}[/red]")
            return False

        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            self.state.session_id = data.get("session_id", self.state.session_id)
            self.state.started_at = data.get("started_at", self.state.started_at)
            self.state.task_count = data.get("task_count", 0)
            self.state.command_count = data.get("command_count", 0)
            self.state.active_files = data.get("active_files", [])
            self.state.metadata = data.get("metadata", {})
            self.state.messages = [
                Message(**m) for m in data.get("messages", [])
            ]
            console.print(f"[bold green]✓ Session restored: {self.state.session_id} ({len(self.state.messages)} messages)[/bold green]")
            return True
        except Exception as e:
            console.print(f"[red]Failed to load session: {e}[/red]")
            return False

    def list_sessions(self) -> List[Dict[str, Any]]:
        """List all saved sessions."""
        sessions = []
        for path in sorted(Path(self._session_dir).glob("session_*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                sessions.append({
                    "id": data.get("session_id", "?"),
                    "saved_at": data.get("saved_at", 0),
                    "task_count": data.get("task_count", 0),
                    "message_count": len(data.get("messages", [])),
                })
            except Exception:
                pass
        return sessions[:20]

    # -----------------------------------------------------------------------
    # User memory (global, persists across projects)
    # -----------------------------------------------------------------------

    def save_user_preference(self, key: str, value: Any):
        """Save a global user preference."""
        prefs_path = os.path.join(self._user_memory_dir, "preferences.json")
        prefs = {}
        if os.path.isfile(prefs_path):
            try:
                prefs = json.loads(Path(prefs_path).read_text(encoding="utf-8"))
            except Exception:
                pass
        prefs[key] = value
        Path(prefs_path).write_text(json.dumps(prefs, indent=2), encoding="utf-8")

    def get_user_preference(self, key: str, default: Any = None) -> Any:
        """Get a global user preference."""
        prefs_path = os.path.join(self._user_memory_dir, "preferences.json")
        if not os.path.isfile(prefs_path):
            return default
        try:
            prefs = json.loads(Path(prefs_path).read_text(encoding="utf-8"))
            return prefs.get(key, default)
        except Exception:
            return default

    def get_all_user_preferences(self) -> Dict[str, Any]:
        """Get all user preferences."""
        prefs_path = os.path.join(self._user_memory_dir, "preferences.json")
        if not os.path.isfile(prefs_path):
            return {}
        try:
            return json.loads(Path(prefs_path).read_text(encoding="utf-8"))
        except Exception:
            return {}

    def save_user_memory(self, content: str, category: str = "general"):
        """Save a user-level memory entry (persists across all projects)."""
        memories_path = os.path.join(self._user_memory_dir, "memories.json")
        memories = []
        if os.path.isfile(memories_path):
            try:
                memories = json.loads(Path(memories_path).read_text(encoding="utf-8"))
            except Exception:
                pass

        entry = {
            "id": str(uuid.uuid4())[:8],
            "timestamp": time.time(),
            "category": category,
            "content": content[:2000],
            "workspace": os.path.basename(self.workspace),
        }
        memories.append(entry)

        # Keep only last 500 entries
        memories = memories[-500:]
        Path(memories_path).write_text(json.dumps(memories, indent=2), encoding="utf-8")

    def search_user_memory(self, query: str, limit: int = 5) -> List[Dict]:
        """Search user memories by keyword matching."""
        memories_path = os.path.join(self._user_memory_dir, "memories.json")
        if not os.path.isfile(memories_path):
            return []

        try:
            memories = json.loads(Path(memories_path).read_text(encoding="utf-8"))
        except Exception:
            return []

        query_lower = query.lower()
        query_words = [w for w in query_lower.split() if len(w) > 2]

        scored = []
        for entry in memories:
            content_lower = entry.get("content", "").lower()
            score = sum(1 for w in query_words if w in content_lower)
            if score > 0:
                scored.append((score, entry))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scored[:limit]]


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------
_session_manager: Optional[SessionManager] = None


def get_session_manager(workspace: str = None) -> SessionManager:
    """Get the global session manager singleton."""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager(workspace or os.getcwd())
    return _session_manager
