"""
USTAAD Patch Engine — Surgical File Editing

Implements Claude Code / Aider-style surgical patching:
- Line-level edits instead of full-file rewrites
- Unified diff generation and preview
- Rollback capability via backup snapshots
- Safe editing with confirmation gates

This is what separates a real coding agent from a naive file overwriter.
"""

import os
import re
import shutil
import difflib
import hashlib
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional

from ustaad.core.safety import get_safety_gate


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------
@dataclass
class PatchHunk:
    """A single edit operation within a file."""
    search: str          # exact text to find
    replace: str         # replacement text
    description: str = ""

@dataclass
class PatchResult:
    """Result of applying a patch."""
    path: str
    success: bool = False
    hunks_applied: int = 0
    hunks_failed: int = 0
    diff: str = ""
    error: str = ""
    backup_path: str = ""

@dataclass
class FileSnapshot:
    """Backup of a file before modification."""
    path: str
    content: str
    timestamp: str
    checksum: str


class PatchEngine:
    """
    Surgical file editing engine.

    Instead of rewriting entire files, PatchEngine applies targeted
    search-and-replace hunks, generates diffs, and maintains rollback
    capability.
    """

    def __init__(self, workspace: str):
        self.workspace = os.path.abspath(workspace)
        self._backups: dict[str, list[FileSnapshot]] = {}
        self._ustaad_dir = os.path.join(self.workspace, ".ustaad")
        self._backup_dir = os.path.join(self._ustaad_dir, "backups")

    # -------------------------------------------------------------------
    # Surgical patching
    # -------------------------------------------------------------------
    def apply_patch(self, path: str, hunks: list[PatchHunk]) -> PatchResult:
        """
        Apply surgical edits to a file.

        Each hunk is a search→replace operation. The engine finds the exact
        text and replaces it, preserving everything else.
        """
        abs_path = self._resolve(path)
        result = PatchResult(path=path)

        if not os.path.isfile(abs_path):
            result.error = f"File does not exist: {path}"
            return result

        # Read original
        try:
            original = Path(abs_path).read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            result.error = f"Cannot read file: {e}"
            return result

        # Create backup
        snapshot = self._create_snapshot(abs_path, original)
        result.backup_path = snapshot.path if snapshot else ""

        # Apply hunks sequentially
        modified = original
        for hunk in hunks:
            if hunk.search in modified:
                modified = modified.replace(hunk.search, hunk.replace, 1)
                result.hunks_applied += 1
            else:
                result.hunks_failed += 1

        if result.hunks_applied == 0:
            result.error = "No hunks matched. File unchanged."
            return result

        # Generate diff
        result.diff = self.generate_diff(original, modified, path)

        # Safety gate for critical files
        gate = get_safety_gate()
        if not gate.confirm_file_write(abs_path, is_overwrite=True):
            result.success = False
            result.error = "[BLOCKED] User rejected patch"
            return result

        # Write modified file
        try:
            Path(abs_path).write_text(modified, encoding="utf-8")
            result.success = True
        except Exception as e:
            result.error = f"Write failed: {e}"
            result.success = False

        return result

    def apply_insert(self, path: str, after_line: str, content: str) -> PatchResult:
        """Insert content after a specific line."""
        hunk = PatchHunk(
            search=after_line,
            replace=after_line + "\n" + content,
            description=f"Insert after: {after_line[:50]}",
        )
        return self.apply_patch(path, [hunk])

    def apply_delete_lines(self, path: str, lines_to_delete: str) -> PatchResult:
        """Delete specific lines from a file."""
        hunk = PatchHunk(
            search=lines_to_delete,
            replace="",
            description=f"Delete: {lines_to_delete[:50]}",
        )
        return self.apply_patch(path, [hunk])

    def apply_unified_diff(self, path: str, diff_text: str) -> PatchResult:
        """Parse a unified diff and apply it via search/replace hunks."""
        hunks = []
        lines = diff_text.splitlines()
        
        current_search = []
        current_replace = []
        in_hunk = False
        
        for line in lines:
            if line.startswith("@@"):
                if in_hunk and (current_search or current_replace):
                    hunks.append(PatchHunk(
                        search="\n".join(current_search),
                        replace="\n".join(current_replace)
                    ))
                current_search = []
                current_replace = []
                in_hunk = True
            elif in_hunk:
                if line.startswith("-"):
                    current_search.append(line[1:])
                elif line.startswith("+"):
                    current_replace.append(line[1:])
                elif line.startswith(" "):
                    current_search.append(line[1:])
                    current_replace.append(line[1:])
                else:
                    if line.strip() != "\\ No newline at end of file":
                        current_search.append(line)
                        current_replace.append(line)
        
        if in_hunk and (current_search or current_replace):
            hunks.append(PatchHunk(
                search="\n".join(current_search),
                replace="\n".join(current_replace)
            ))
            
        return self.apply_patch(path, hunks)

    # -------------------------------------------------------------------
    # Diff generation
    # -------------------------------------------------------------------
    def generate_diff(self, original: str, modified: str, path: str = "file") -> str:
        """Generate a unified diff between two strings."""
        orig_lines = original.splitlines(keepends=True)
        mod_lines = modified.splitlines(keepends=True)
        diff = difflib.unified_diff(
            orig_lines, mod_lines,
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
            lineterm="",
        )
        return "".join(diff)

    def preview_diff(self, path: str, hunks: list[PatchHunk]) -> str:
        """Preview what a patch would look like without applying it."""
        abs_path = self._resolve(path)
        if not os.path.isfile(abs_path):
            return f"File does not exist: {path}"

        original = Path(abs_path).read_text(encoding="utf-8", errors="ignore")
        modified = original
        for hunk in hunks:
            if hunk.search in modified:
                modified = modified.replace(hunk.search, hunk.replace, 1)

        if original == modified:
            return "No changes — hunks did not match."

        return self.generate_diff(original, modified, path)

    def diff_file_against_backup(self, path: str) -> str:
        """Show diff between current file and its most recent backup."""
        abs_path = self._resolve(path)
        if abs_path not in self._backups or not self._backups[abs_path]:
            return "No backup found for this file."

        snapshot = self._backups[abs_path][-1]
        current = Path(abs_path).read_text(encoding="utf-8", errors="ignore")
        return self.generate_diff(snapshot.content, current, path)

    # -------------------------------------------------------------------
    # Rollback
    # -------------------------------------------------------------------
    def rollback(self, path: str) -> str:
        """Restore a file to its most recent backup."""
        abs_path = self._resolve(path)
        if abs_path not in self._backups or not self._backups[abs_path]:
            return f"No backup available for: {path}"

        snapshot = self._backups[abs_path].pop()
        try:
            Path(abs_path).write_text(snapshot.content, encoding="utf-8")
            return f"Rolled back {path} to snapshot from {snapshot.timestamp}"
        except Exception as e:
            return f"Rollback failed: {e}"

    def rollback_all(self) -> list[str]:
        """Rollback all modified files to their backups."""
        results = []
        for abs_path in list(self._backups.keys()):
            rel = os.path.relpath(abs_path, self.workspace)
            results.append(self.rollback(rel))
        return results

    # -------------------------------------------------------------------
    # Backup management
    # -------------------------------------------------------------------
    def _create_snapshot(self, abs_path: str, content: str) -> Optional[FileSnapshot]:
        """Create an in-memory snapshot of a file."""
        snapshot = FileSnapshot(
            path=abs_path,
            content=content,
            timestamp=datetime.now().isoformat(),
            checksum=hashlib.md5(content.encode()).hexdigest(),
        )
        if abs_path not in self._backups:
            self._backups[abs_path] = []
        self._backups[abs_path].append(snapshot)

        # Also save to disk for persistence
        try:
            os.makedirs(self._backup_dir, exist_ok=True)
            rel = os.path.relpath(abs_path, self.workspace).replace(os.sep, "_")
            backup_file = os.path.join(
                self._backup_dir, f"{rel}.{snapshot.checksum[:8]}.bak"
            )
            Path(backup_file).write_text(content, encoding="utf-8")
        except Exception:
            pass

        return snapshot

    def get_modified_files(self) -> list[str]:
        """Return list of files that have been modified (have backups)."""
        return [
            os.path.relpath(p, self.workspace)
            for p in self._backups.keys()
        ]

    # -------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------
    def _resolve(self, path: str) -> str:
        """Resolve a path relative to workspace."""
        if os.path.isabs(path):
            return path
        return os.path.join(self.workspace, path)
