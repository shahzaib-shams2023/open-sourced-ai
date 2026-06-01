"""
USTAAD Audit Logger — Full Operation History

Records every operation performed by agents for:
- Compliance and traceability
- Debugging agent behavior
- Rollback support
- Performance analysis
- Security auditing

Log format: JSONL (one JSON object per line)
Location: .ustaad/audit/audit.jsonl
"""

import os
import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
from pathlib import Path
from threading import Lock

from rich.console import Console

console = Console()


@dataclass
class AuditEntry:
    """A single audit log entry."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    timestamp: float = field(default_factory=time.time)
    event_type: str = ""        # tool_call, file_write, command_exec, agent_action
    agent_role: str = ""        # which agent performed the action
    tool_name: str = ""         # which tool was used
    operation: str = ""         # read, write, delete, execute
    target: str = ""            # file path, command, etc.
    args: Dict[str, Any] = field(default_factory=dict)
    result_status: str = ""     # success, failure, blocked
    result_summary: str = ""    # brief description of outcome
    duration: float = 0.0
    session_id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class AuditLogger:
    """
    Persistent audit logger for all agent operations.
    
    Usage:
        logger = AuditLogger(workspace)
        
        # Log a tool call
        logger.log_tool_call("coder", "write_file", {"path": "app.py"}, "success")
        
        # Log a command execution
        logger.log_command("shell", "npm test", 0, "Tests passed")
        
        # Query history
        entries = logger.query(agent_role="coder", limit=20)
    """

    def __init__(self, workspace: str, session_id: str = ""):
        self.workspace = os.path.abspath(workspace)
        self._audit_dir = os.path.join(self.workspace, ".ustaad", "audit")
        self._log_path = os.path.join(self._audit_dir, "audit.jsonl")
        self._session_id = session_id or str(uuid.uuid4())[:8]
        self._lock = Lock()
        os.makedirs(self._audit_dir, exist_ok=True)

    def log(self, entry: AuditEntry):
        """Write an audit entry to the log."""
        entry.session_id = self._session_id
        with self._lock:
            try:
                with open(self._log_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(asdict(entry), default=str) + "\n")
            except Exception:
                pass

    def log_tool_call(
        self,
        agent_role: str,
        tool_name: str,
        args: Dict[str, Any] = None,
        status: str = "success",
        result: str = "",
        duration: float = 0.0,
    ):
        """Log a tool invocation."""
        self.log(AuditEntry(
            event_type="tool_call",
            agent_role=agent_role,
            tool_name=tool_name,
            operation="execute",
            target=tool_name,
            args=args or {},
            result_status=status,
            result_summary=result[:500],
            duration=duration,
        ))

    def log_file_operation(
        self,
        agent_role: str,
        operation: str,
        file_path: str,
        status: str = "success",
        details: str = "",
    ):
        """Log a file operation (read, write, delete)."""
        self.log(AuditEntry(
            event_type="file_operation",
            agent_role=agent_role,
            tool_name=f"file_{operation}",
            operation=operation,
            target=file_path,
            result_status=status,
            result_summary=details[:500],
        ))

    def log_command(
        self,
        agent_role: str,
        command: str,
        exit_code: int,
        output_summary: str = "",
        duration: float = 0.0,
    ):
        """Log a shell command execution."""
        status = "success" if exit_code == 0 else "failure"
        self.log(AuditEntry(
            event_type="command_exec",
            agent_role=agent_role,
            tool_name="run_command",
            operation="execute",
            target=command[:200],
            result_status=status,
            result_summary=output_summary[:500],
            duration=duration,
            metadata={"exit_code": exit_code},
        ))

    def log_agent_action(
        self,
        agent_role: str,
        action: str,
        details: str = "",
    ):
        """Log a high-level agent action."""
        self.log(AuditEntry(
            event_type="agent_action",
            agent_role=agent_role,
            operation=action,
            result_summary=details[:500],
        ))

    def log_security_event(
        self,
        event: str,
        severity: str = "info",
        details: str = "",
    ):
        """Log a security-relevant event."""
        self.log(AuditEntry(
            event_type="security",
            operation=event,
            result_status=severity,
            result_summary=details[:500],
        ))

    def query(
        self,
        event_type: str = None,
        agent_role: str = None,
        tool_name: str = None,
        status: str = None,
        session_id: str = None,
        limit: int = 50,
    ) -> List[AuditEntry]:
        """Query the audit log with filters."""
        entries = []
        if not os.path.isfile(self._log_path):
            return entries

        try:
            with open(self._log_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        if event_type and data.get("event_type") != event_type:
                            continue
                        if agent_role and data.get("agent_role") != agent_role:
                            continue
                        if tool_name and data.get("tool_name") != tool_name:
                            continue
                        if status and data.get("result_status") != status:
                            continue
                        if session_id and data.get("session_id") != session_id:
                            continue
                        entries.append(AuditEntry(**data))
                    except (json.JSONDecodeError, TypeError):
                        pass
        except Exception:
            pass

        return entries[-limit:]

    def get_session_summary(self, session_id: str = None) -> Dict[str, Any]:
        """Get a summary of operations in a session."""
        sid = session_id or self._session_id
        entries = self.query(session_id=sid, limit=10000)

        tool_counts: Dict[str, int] = {}
        file_ops: Dict[str, int] = {}
        total_duration = 0.0

        for e in entries:
            if e.tool_name:
                tool_counts[e.tool_name] = tool_counts.get(e.tool_name, 0) + 1
            if e.event_type == "file_operation":
                file_ops[e.operation] = file_ops.get(e.operation, 0) + 1
            total_duration += e.duration

        return {
            "session_id": sid,
            "total_operations": len(entries),
            "tool_counts": tool_counts,
            "file_operations": file_ops,
            "total_duration": total_duration,
            "failures": len([e for e in entries if e.result_status == "failure"]),
            "security_events": len([e for e in entries if e.event_type == "security"]),
        }

    def rotate_log(self, max_lines: int = 50_000):
        """Rotate the log file if it exceeds max_lines."""
        if not os.path.isfile(self._log_path):
            return

        try:
            with open(self._log_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            if len(lines) > max_lines:
                keep = lines[-max_lines:]
                archive_path = self._log_path + f".{int(time.time())}.bak"
                os.rename(self._log_path, archive_path)
                with open(self._log_path, "w", encoding="utf-8") as f:
                    f.writelines(keep)
                console.print(f"[dim]   ✓ Audit log rotated: {len(lines) - max_lines} old entries archived[/dim]")
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------
_audit_logger: Optional[AuditLogger] = None


def get_audit_logger(workspace: str = None, session_id: str = "") -> AuditLogger:
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger(workspace or os.getcwd(), session_id)
    return _audit_logger
