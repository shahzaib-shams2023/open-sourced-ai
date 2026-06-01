"""
USTAAD Workflow Automation Engine
Executes multi-step YAML workflows for CI/CD and repetitive tasks.
"""
import yaml
import os
from typing import List, Dict, Any
from ustaad.main import run_task

class WorkflowEngine:
    def __init__(self, workspace: str):
        self.workspace = workspace
        self.workflow_dir = os.path.join(workspace, ".ustaad", "workflows")

    def list_workflows(self) -> List[str]:
        """List available workflows in .ustaad/workflows/"""
        if not os.path.exists(self.workflow_dir):
            return []
        return [f for f in os.listdir(self.workflow_dir) if f.endswith((".yml", ".yaml"))]

    def run_workflow(self, name: str) -> str:
        """Executes a workflow sequence."""
        if not name.endswith(".yml") and not name.endswith(".yaml"):
            name += ".yml"
        
        path = os.path.join(self.workflow_dir, name)
        if not os.path.exists(path):
            return f"Workflow '{name}' not found in {self.workflow_dir}"
            
        with open(path, "r", encoding="utf-8") as f:
            try:
                workflow = yaml.safe_load(f)
            except Exception as e:
                return f"Failed to parse workflow YAML: {e}"
            
        steps = workflow.get("steps", [])
        if not steps:
            return "Workflow has no steps."
            
        results = []
        for i, step in enumerate(steps, 1):
            step_name = step.get("name", f"Step {i}")
            action = step.get("action", "prompt")
            payload = step.get("payload", "")
            
            if action == "prompt":
                res = run_task(payload, workspace=self.workspace)
                results.append(f"[{step_name}] ✓ {str(res)[:100]}")
            elif action == "shell":
                from ustaad.tools.shell_tools import run_command_safe
                res = run_command_safe(f"cd \"{self.workspace}\" && {payload}")
                if res.get("blocked"):
                    results.append(f"[{step_name}] ✗ Blocked by Safety Gate")
                else:
                    results.append(f"[{step_name}] ✓ Shell completed")
                
        return "\n".join(results)
