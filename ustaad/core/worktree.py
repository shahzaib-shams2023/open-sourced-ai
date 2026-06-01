"""
USTAAD Worktree & Multi-Repository Management
Handles isolated git worktrees and multi-repo orchestration.
"""
import os
import subprocess
from typing import List, Dict

class WorkspaceManager:
    def __init__(self, primary_workspace: str):
        self.primary_workspace = os.path.abspath(primary_workspace)
        self.active_workspace = self.primary_workspace
        self.repos: Dict[str, str] = {"primary": self.primary_workspace}
        
    def add_repo(self, name: str, path: str) -> bool:
        """Register another repository for multi-repo operations."""
        full_path = os.path.abspath(path)
        if os.path.exists(full_path) and os.path.isdir(os.path.join(full_path, ".git")):
            self.repos[name] = full_path
            return True
        return False
        
    def switch_workspace(self, name: str) -> str:
        """Switch active context to a different repo or worktree."""
        if name in self.repos:
            self.active_workspace = self.repos[name]
            return f"Switched to workspace: {name} ({self.active_workspace})"
        return f"Workspace '{name}' not found."

    def create_worktree(self, branch_name: str, path: str = None) -> str:
        """Creates a git worktree for isolated execution."""
        if not path:
            path = os.path.join(os.path.dirname(self.primary_workspace), f"{os.path.basename(self.primary_workspace)}_{branch_name}")
            
        try:
            subprocess.run(
                ["git", "worktree", "add", "-b", branch_name, path, "main"], 
                cwd=self.primary_workspace, check=True, capture_output=True, text=True
            )
            self.repos[f"worktree_{branch_name}"] = path
            return f"Created and registered worktree at {path}"
        except subprocess.CalledProcessError as e:
            return f"Failed to create worktree: {e.stderr}"
            
    def list_workspaces(self) -> List[str]:
        return [f"{name}: {path}" for name, path in self.repos.items()]
