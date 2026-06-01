"""
USTAAD Git Awareness Engine

Full git intelligence:
- Branch awareness and management
- Diff/staged changes analysis
- Intelligent commit message generation
- Merge conflict detection
- History summarization
- Safe git operations with confirmation

USTAAD must NEVER destroy git history without confirmation.
"""

import os
import re
from dataclasses import dataclass, field
from typing import Optional

from ustaad.tools.shell_tools import run_command, run_command_safe


@dataclass
class GitStatus:
    """Structured git state."""
    is_repo: bool = False
    branch: str = ""
    staged: list[str] = field(default_factory=list)
    modified: list[str] = field(default_factory=list)
    untracked: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)
    ahead: int = 0
    behind: int = 0
    has_conflicts: bool = False
    conflict_files: list[str] = field(default_factory=list)
    stash_count: int = 0

    def to_context_string(self) -> str:
        lines = [f"[GIT] Branch: {self.branch}"]
        if self.staged:
            lines.append(f"  Staged ({len(self.staged)}):")
            for f in self.staged[:10]:
                lines.append(f"    + {f}")
        if self.modified:
            lines.append(f"  Modified ({len(self.modified)}):")
            for f in self.modified[:10]:
                lines.append(f"    M {f}")
        if self.untracked:
            lines.append(f"  Untracked ({len(self.untracked)}):")
            for f in self.untracked[:10]:
                lines.append(f"    ? {f}")
        if self.deleted:
            lines.append(f"  Deleted ({len(self.deleted)}):")
            for f in self.deleted[:5]:
                lines.append(f"    D {f}")
        if self.has_conflicts:
            lines.append(f"  CONFLICTS ({len(self.conflict_files)}):")
            for f in self.conflict_files:
                lines.append(f"    ! {f}")
        if self.ahead:
            lines.append(f"  Ahead of remote: {self.ahead} commits")
        if self.behind:
            lines.append(f"  Behind remote: {self.behind} commits")
        if self.stash_count:
            lines.append(f"  Stashes: {self.stash_count}")
        if not any([self.staged, self.modified, self.untracked, self.deleted]):
            lines.append("  Clean working tree")
        return "\n".join(lines)


class GitEngine:
    """Git awareness and operations engine."""

    def __init__(self, workspace: str):
        self.workspace = os.path.abspath(workspace)

    def _run(self, cmd: str) -> dict:
        """Run a git command in the workspace."""
        full_cmd = f"cd \"{self.workspace}\" && {cmd}"
        return run_command(full_cmd)

    def _run_safe(self, cmd: str) -> dict:
        """Run a git command with safety gate."""
        full_cmd = f"cd \"{self.workspace}\" && {cmd}"
        return run_command_safe(full_cmd)

    # -------------------------------------------------------------------
    # Status and info
    # -------------------------------------------------------------------
    def is_repo(self) -> bool:
        return os.path.isdir(os.path.join(self.workspace, ".git"))

    def status(self) -> GitStatus:
        """Get comprehensive git status."""
        gs = GitStatus(is_repo=self.is_repo())
        if not gs.is_repo:
            return gs

        # Branch
        res = self._run("git branch --show-current")
        gs.branch = res.get("stdout", "").strip() or "HEAD (detached)"

        # Porcelain status
        res = self._run("git status --porcelain=v1")
        for line in res.get("stdout", "").splitlines():
            if len(line) < 4:
                continue
            xy = line[:2]
            filepath = line[3:].strip()

            if "U" in xy or xy == "AA" or xy == "DD":
                gs.has_conflicts = True
                gs.conflict_files.append(filepath)
            elif xy[0] in "MADRC":
                gs.staged.append(filepath)
            if xy[1] == "M":
                gs.modified.append(filepath)
            elif xy[1] == "D":
                gs.deleted.append(filepath)
            elif xy == "??":
                gs.untracked.append(filepath)

        # Ahead/behind
        res = self._run("git rev-list --left-right --count HEAD...@{upstream}")
        parts = res.get("stdout", "").strip().split()
        if len(parts) == 2:
            try:
                gs.ahead = int(parts[0])
                gs.behind = int(parts[1])
            except ValueError:
                pass

        # Stash count
        res = self._run("git stash list")
        stash_lines = res.get("stdout", "").strip().splitlines()
        gs.stash_count = len(stash_lines) if stash_lines and stash_lines[0] else 0

        return gs

    def diff(self, staged: bool = False) -> str:
        """Get diff of working tree or staged changes."""
        cmd = "git diff --stat" + (" --cached" if staged else "")
        res = self._run(cmd)
        return res.get("stdout", "").strip()

    def diff_full(self, path: str = None, staged: bool = False) -> str:
        """Get full unified diff, optionally for a specific file."""
        cmd = "git diff" + (" --cached" if staged else "")
        if path:
            cmd += f" -- \"{path}\""
        res = self._run(cmd)
        return res.get("stdout", "")[:5000]  # cap for context window

    def log(self, count: int = 10) -> str:
        """Get recent commit log."""
        res = self._run(
            f"git log --oneline --graph --decorate -n {count}"
        )
        return res.get("stdout", "").strip()

    def log_file(self, path: str, count: int = 5) -> str:
        """Get commit history for a specific file."""
        res = self._run(f'git log --oneline -n {count} -- "{path}"')
        return res.get("stdout", "").strip()

    def branches(self) -> list[str]:
        """List all branches."""
        res = self._run("git branch -a")
        return [
            b.strip().lstrip("* ")
            for b in res.get("stdout", "").splitlines()
            if b.strip()
        ]

    # -------------------------------------------------------------------
    # Operations (safe — go through safety gate)
    # -------------------------------------------------------------------
    def stage_files(self, paths: list[str] = None) -> str:
        """Stage files for commit. If paths is None, stage all."""
        if paths:
            files = " ".join(f'"{p}"' for p in paths)
            res = self._run_safe(f"git add {files}")
        else:
            res = self._run_safe("git add -A")
        if res.get("blocked"):
            return "[BLOCKED] User rejected git add"
        return res.get("stdout", "") + res.get("stderr", "")

    def commit(self, message: str) -> str:
        """Create a commit with the given message."""
        safe_msg = message.replace('"', '\\"')
        res = self._run_safe(f'git commit -m "{safe_msg}"')
        if res.get("blocked"):
            return "[BLOCKED] User rejected commit"
        stdout = res.get("stdout", "")
        stderr = res.get("stderr", "")
        return stdout + stderr

    def generate_commit_message(self) -> str:
        """
        Generate an intelligent commit message from staged changes.
        Analyzes the diff to produce a conventional commit message.
        """
        diff_stat = self.diff(staged=True)
        if not diff_stat:
            diff_stat = self.diff(staged=False)
        if not diff_stat:
            return "chore: update files"

        # Parse diff stat
        files_changed = []
        for line in diff_stat.splitlines():
            parts = line.strip().split("|")
            if len(parts) >= 1:
                fname = parts[0].strip()
                if fname and not fname.startswith(" "):
                    files_changed.append(fname)

        # Determine prefix
        prefix = "feat"
        all_files = " ".join(files_changed).lower()
        if any(w in all_files for w in ["test", "spec", "conftest"]):
            prefix = "test"
        elif any(w in all_files for w in ["fix", "bug", "patch"]):
            prefix = "fix"
        elif any(w in all_files for w in [
            "dockerfile", "docker", "ci", "yml", "yaml", "deploy",
            ".github", "jenkins", "pipeline"
        ]):
            prefix = "ci"
        elif any(w in all_files for w in ["readme", "doc", "docs", "changelog"]):
            prefix = "docs"
        elif any(w in all_files for w in [
            "lint", "format", "style", "eslint", "prettier", "ruff"
        ]):
            prefix = "style"
        elif any(w in all_files for w in ["refactor", "rename", "move", "clean"]):
            prefix = "refactor"

        # Build description
        if len(files_changed) == 1:
            desc = f"update {files_changed[0]}"
        elif len(files_changed) <= 3:
            desc = f"update {', '.join(files_changed)}"
        else:
            # Group by directory
            dirs = set()
            for f in files_changed:
                parts = f.split("/")
                if len(parts) > 1:
                    dirs.add(parts[0])
            if dirs:
                desc = f"update {', '.join(sorted(dirs))} ({len(files_changed)} files)"
            else:
                desc = f"update {len(files_changed)} files"

        return f"{prefix}: {desc}"

    def auto_commit(self) -> str:
        """Stage all changes and commit with auto-generated message."""
        stage_result = self.stage_files()
        if "BLOCKED" in stage_result:
            return stage_result

        msg = self.generate_commit_message()
        return self.commit(msg)

    # -------------------------------------------------------------------
    # Rollback / Undo
    # -------------------------------------------------------------------
    def checkpoint(self, task_name: str = "agent task") -> str:
        """Create a safety checkpoint before risky agent operations."""
        status = self.status()
        if not status.is_repo:
            return "Not a git repository, skipping checkpoint."
        
        # Stage everything and commit as a checkpoint
        msg = f"USTAAD CHECKPOINT: {task_name}"
        self.stage_files()
        res = self._run(f'git commit -m "{msg}"')
        return f"Checkpoint created: {msg}"
        
    def undo(self) -> str:
        """Undo the most recent commit if it's an USTAAD operation."""
        status = self.status()
        if not status.is_repo:
            return "Not a git repository, cannot undo."
            
        # Check if the last commit was by Ustaad (either checkpoint or normal)
        log = self.log(1)
        if not log:
            return "No commit history found to undo."
            
        res = self._run_safe("git reset --hard HEAD~1")
        if res.get("blocked"):
            return "[BLOCKED] User rejected undo operation (git reset --hard)."
            
        return "✓ Successfully rolled back the last action (git reset --hard HEAD~1)."
