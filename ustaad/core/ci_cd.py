"""
USTAAD CI/CD Integration
Detects and interacts with CI/CD pipelines (GitHub Actions, GitLab CI).
"""
import os

class CIIntegration:
    def __init__(self, workspace: str):
        self.workspace = workspace
        
    def detect_provider(self) -> str:
        if os.path.exists(os.path.join(self.workspace, ".github", "workflows")):
            return "github"
        if os.path.exists(os.path.join(self.workspace, ".gitlab-ci.yml")):
            return "gitlab"
        return "none"
        
    def get_status(self) -> str:
        """Get the latest pipeline status using official CLIs."""
        provider = self.detect_provider()
        if provider == "github":
            from ustaad.tools.shell_tools import run_command
            res = run_command(f"cd \"{self.workspace}\" && gh run list --limit 5")
            if res.get("returncode") == 0 and res.get("stdout"):
                return res.get("stdout")
            return "GitHub CLI (gh) not available, not authenticated, or no runs found."
        elif provider == "gitlab":
            return "GitLab pipeline status requires the 'glab' CLI."
        return "No supported CI/CD provider detected (.github/workflows or .gitlab-ci.yml)."
        
    def trigger_workflow(self, workflow_name: str) -> str:
        """Trigger a CI/CD pipeline."""
        provider = self.detect_provider()
        if provider == "github":
            from ustaad.tools.shell_tools import run_command
            res = run_command(f"cd \"{self.workspace}\" && gh workflow run {workflow_name}")
            if res.get("returncode") == 0:
                return f"Successfully triggered GitHub workflow: {workflow_name}"
            return f"Failed to trigger workflow: {res.get('stderr')}"
        return f"Workflow triggering not supported for provider: {provider}"
