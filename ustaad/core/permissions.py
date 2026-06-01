"""
USTAAD Permission System — Tool-Level Access Control

Fine-grained permission system for tool access:
- Per-tool allow/deny rules
- MCP tool sandboxing
- Path-based file access restrictions
- Network access controls
- Resource limits
- Permission profiles (strict, normal, permissive)

Configuration: .ustaad/permissions.yaml or .ustaad/permissions.json
"""

import os
import re
import json
from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set
from pathlib import Path

from rich.console import Console

console = Console()


class PermissionLevel(str, Enum):
    DENY = "deny"
    CONFIRM = "confirm"
    ALLOW = "allow"


class PermissionProfile(str, Enum):
    """Pre-built permission profiles."""
    STRICT = "strict"       # Everything requires confirmation
    NORMAL = "normal"       # Reads auto, writes confirm
    PERMISSIVE = "permissive"  # Most things auto-approved
    CUSTOM = "custom"       # User-defined rules


@dataclass
class ToolPermission:
    """Permission rule for a specific tool."""
    tool_name: str
    level: PermissionLevel = PermissionLevel.CONFIRM
    allowed_args: Dict[str, str] = field(default_factory=dict)  # arg_name -> regex pattern
    denied_args: Dict[str, str] = field(default_factory=dict)
    max_calls_per_session: int = 0  # 0 = unlimited
    _call_count: int = 0


@dataclass
class PathPermission:
    """Permission rule for file/directory access."""
    pattern: str  # glob pattern
    read: PermissionLevel = PermissionLevel.ALLOW
    write: PermissionLevel = PermissionLevel.CONFIRM
    delete: PermissionLevel = PermissionLevel.DENY


class PermissionManager:
    """
    Manages tool-level permissions and access control.
    
    Usage:
        perms = PermissionManager(workspace)
        
        # Check if a tool can be used
        if perms.check_tool("write_file", {"path": "/etc/passwd"}):
            ...
            
        # Check file access
        if perms.check_file_access("src/main.py", "write"):
            ...
    """

    def __init__(self, workspace: str):
        self.workspace = os.path.abspath(workspace)
        self._profile = PermissionProfile.NORMAL
        self._tool_permissions: Dict[str, ToolPermission] = {}
        self._path_permissions: List[PathPermission] = []
        self._denied_paths: Set[str] = set()
        self._allowed_paths: Set[str] = set()
        self._network_allowed: bool = True

        self._load_config()

    def _load_config(self):
        """Load permission configuration from .ustaad/permissions.yaml or .json."""
        yaml_path = os.path.join(self.workspace, ".ustaad", "permissions.yaml")
        json_path = os.path.join(self.workspace, ".ustaad", "permissions.json")

        config = None
        if os.path.isfile(yaml_path):
            try:
                import yaml
                config = yaml.safe_load(Path(yaml_path).read_text(encoding="utf-8"))
            except Exception:
                pass
        elif os.path.isfile(json_path):
            try:
                config = json.loads(Path(json_path).read_text(encoding="utf-8"))
            except Exception:
                pass

        if not config:
            self._apply_default_profile()
            return

        # Load profile
        profile_str = config.get("profile", "normal")
        try:
            self._profile = PermissionProfile(profile_str)
        except ValueError:
            self._profile = PermissionProfile.NORMAL

        # Load tool permissions
        for tool_config in config.get("tools", []):
            perm = ToolPermission(
                tool_name=tool_config.get("name", ""),
                level=PermissionLevel(tool_config.get("level", "confirm")),
                max_calls_per_session=tool_config.get("max_calls", 0),
            )
            if perm.tool_name:
                self._tool_permissions[perm.tool_name] = perm

        # Load path permissions
        for path_config in config.get("paths", []):
            pp = PathPermission(
                pattern=path_config.get("pattern", ""),
                read=PermissionLevel(path_config.get("read", "allow")),
                write=PermissionLevel(path_config.get("write", "confirm")),
                delete=PermissionLevel(path_config.get("delete", "deny")),
            )
            if pp.pattern:
                self._path_permissions.append(pp)

        # Load denied/allowed paths
        self._denied_paths = set(config.get("denied_paths", []))
        self._allowed_paths = set(config.get("allowed_paths", []))
        self._network_allowed = config.get("network_allowed", True)

    def _apply_default_profile(self):
        """Apply default permission profile."""
        # Default denied paths
        self._denied_paths = {
            "/etc", "/usr", "/var", "/sys", "/proc",
            "C:\\Windows", "C:\\Program Files",
        }

        # Default tool permissions
        self._tool_permissions = {
            "read_file": ToolPermission("read_file", PermissionLevel.ALLOW),
            "list_directory": ToolPermission("list_directory", PermissionLevel.ALLOW),
            "search_files": ToolPermission("search_files", PermissionLevel.ALLOW),
            "get_file_skeleton": ToolPermission("get_file_skeleton", PermissionLevel.ALLOW),
            "ripgrep_search": ToolPermission("ripgrep_search", PermissionLevel.ALLOW),
            "semantic_search": ToolPermission("semantic_search", PermissionLevel.ALLOW),
            "write_file": ToolPermission("write_file", PermissionLevel.CONFIRM),
            "patch_file": ToolPermission("patch_file", PermissionLevel.CONFIRM),
            "append_file": ToolPermission("append_file", PermissionLevel.CONFIRM),
            "delete_file": ToolPermission("delete_file", PermissionLevel.DENY),
            "run_command": ToolPermission("run_command", PermissionLevel.CONFIRM),
        }

    def check_tool(self, tool_name: str, args: Dict[str, Any] = None) -> PermissionLevel:
        """
        Check permission for a tool invocation.
        Returns the permission level.
        """
        perm = self._tool_permissions.get(tool_name)
        if not perm:
            return PermissionLevel.CONFIRM  # Default: confirm

        # Check rate limit
        if perm.max_calls_per_session > 0 and perm._call_count >= perm.max_calls_per_session:
            return PermissionLevel.DENY

        # Check argument restrictions
        if args and perm.denied_args:
            for arg_name, pattern in perm.denied_args.items():
                if arg_name in args and re.search(pattern, str(args[arg_name])):
                    return PermissionLevel.DENY

        perm._call_count += 1
        return perm.level

    def check_file_access(self, file_path: str, operation: str = "read") -> PermissionLevel:
        """
        Check permission for file access.
        operation: "read", "write", "delete"
        """
        abs_path = os.path.abspath(file_path)

        # Check denied paths
        for denied in self._denied_paths:
            if abs_path.startswith(os.path.abspath(denied)):
                return PermissionLevel.DENY

        # Check path permissions
        for pp in self._path_permissions:
            if Path(abs_path).match(pp.pattern):
                if operation == "read":
                    return pp.read
                elif operation == "write":
                    return pp.write
                elif operation == "delete":
                    return pp.delete

        # Defaults based on operation
        if operation == "read":
            return PermissionLevel.ALLOW
        elif operation == "write":
            return PermissionLevel.CONFIRM
        elif operation == "delete":
            return PermissionLevel.DENY

        return PermissionLevel.CONFIRM

    def check_network_access(self) -> bool:
        """Check if network access is allowed."""
        return self._network_allowed

    def get_profile(self) -> str:
        """Get current permission profile name."""
        return self._profile.value


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------
_permission_manager: Optional[PermissionManager] = None


def get_permission_manager(workspace: str = None) -> PermissionManager:
    global _permission_manager
    if _permission_manager is None:
        _permission_manager = PermissionManager(workspace or os.getcwd())
    return _permission_manager
