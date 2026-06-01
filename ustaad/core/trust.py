"""
USTAAD Repository Trust Model
Determines whether a repository is trusted or untrusted, which restricts tool access.
"""
import os
import json

class TrustModel:
    def __init__(self, global_config_dir: str = "~/.ustaad"):
        self.config_dir = os.path.expanduser(global_config_dir)
        os.makedirs(self.config_dir, exist_ok=True)
        self.trust_file = os.path.join(self.config_dir, "trusted_repos.json")
        self._load_trust()
        
    def _load_trust(self):
        if os.path.exists(self.trust_file):
            with open(self.trust_file, "r") as f:
                self.trusted_paths = json.load(f)
        else:
            self.trusted_paths = []
            
    def _save_trust(self):
        with open(self.trust_file, "w") as f:
            json.dump(self.trusted_paths, f)
            
    def is_trusted(self, workspace: str) -> bool:
        """Check if a workspace is explicitly trusted."""
        workspace = os.path.abspath(workspace)
        return workspace in self.trusted_paths
        
    def trust_repo(self, workspace: str):
        """Mark a repository as trusted."""
        workspace = os.path.abspath(workspace)
        if workspace not in self.trusted_paths:
            self.trusted_paths.append(workspace)
            self._save_trust()
            
    def revoke_trust(self, workspace: str):
        """Revoke trust from a repository."""
        workspace = os.path.abspath(workspace)
        if workspace in self.trusted_paths:
            self.trusted_paths.remove(workspace)
            self._save_trust()
