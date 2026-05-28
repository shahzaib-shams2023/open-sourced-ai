"""
USTAAD Dynamic Auto-Optimizing Prompt Library

This module implements a self-improving prompt template framework that dynamically
customizes agent instructions, logs execution metrics (success rate, token efficiency,
and run times), and auto-optimizes guidelines for subsequent agent tasks.
"""

import os
import json
import time
from typing import Dict, Any, List
from rich.console import Console

console = Console()

TELEMETRY_PATH = os.path.abspath(os.path.join(os.getcwd(), "memory", "prompt_telemetry.json"))

DEFAULT_TEMPLATES = {
    "CODE": {
        "system": (
            "You are Ustaad's Elite Coder Agent.\n"
            "Your objective is to write robust, maintainable, and clean code.\n"
            "Ensure code strictly adheres to modern styling standards, implements strict "
            "error handling, and avoids deprecated library paradigms."
        ),
        "guidelines": [
            "Write modular, dry functions.",
            "Include comprehensive docstrings.",
            "Safeguard all array bounds and memory interfaces.",
            "You MUST use the write_file tool to write and create all specified files on disk. Do NOT simply print the code blocks in your final response without actually executing the write_file/patch_file tool.",
            "You MUST use the patch_file tool for surgical edits to existing files."
        ]
    },
    "DEBUG": {
        "system": (
            "You are Ustaad's Expert Debugging Agent.\n"
            "Your objective is to analyze log tracebacks, identify core structural failures, "
            "and suggest high-reliability minimal-impact repairs."
        ),
        "guidelines": [
            "Reproduce the trace logic mentally first.",
            "Explain exactly why the exception occurred.",
            "Verify dependencies and state changes."
        ]
    },
    "TEST": {
        "system": (
            "You are Ustaad's Quality Assurance & Test Agent.\n"
            "Your objective is to design, generate, and run automated unit and integration tests "
            "to guarantee codebase correctness."
        ),
        "guidelines": [
            "Design broad boundary test cases.",
            "Use standard mocking libraries for isolation.",
            "Validate both success and failure execution branches."
        ]
    },
    "RESEARCH": {
        "system": (
            "You are Ustaad's High-Intelligence Research Agent.\n"
            "Your objective is to explore directories, investigate files, analyze "
            "architectural relationships, and synthesize complete analysis briefs."
        ),
        "guidelines": [
            "Examine file imports and layout paradigms.",
            "Highlight performance risks or circular dependencies.",
            "Propose scalable architectural blueprints."
        ]
    }
}


class PromptOptimizer:
    """
    Manages and auto-optimizes prompt templates based on historical task reflection telemetry.
    """

    def __init__(self, telemetry_path: str = TELEMETRY_PATH):
        self.telemetry_path = telemetry_path
        self._load_telemetry()

    def _load_telemetry(self):
        """Loads prompt performance logs and overrides."""
        os.makedirs(os.path.dirname(self.telemetry_path), exist_ok=True)
        if os.path.exists(self.telemetry_path):
            try:
                with open(self.telemetry_path, "r") as f:
                    data = json.load(f)
                    self.templates = data.get("templates", DEFAULT_TEMPLATES)
                    self.history = data.get("history", [])
            except Exception:
                self.templates = DEFAULT_TEMPLATES
                self.history = []
        else:
            self.templates = DEFAULT_TEMPLATES
            self.history = []

    def _save_telemetry(self):
        """Persists the optimized templates and histories to disk."""
        try:
            with open(self.telemetry_path, "w") as f:
                json.dump({
                    "templates": self.templates,
                    "history": self.history
                }, f, indent=2)
        except Exception as e:
            console.print(f"[yellow]   ⚠ Telemetry persistence failure: {e}[/yellow]")

    def get_template(self, task_type: str) -> Dict[str, Any]:
        """
        Retrieves the optimized instructions and system rules for a specific task role.
        """
        t_type = task_type.upper()
        if t_type not in self.templates:
            # Fallback to general code template if undefined
            t_type = "CODE"
        return self.templates[t_type]

    def compile_instructions(self, task_type: str, user_context: str = "") -> str:
        """
        Compiles optimized instructions and guidelines into a single high-impact prompt.
        """
        template = self.get_template(task_type)
        system_base = template.get("system", "")
        guidelines = template.get("guidelines", [])
        
        compiled = f"{system_base}\n\n[CORE RULES & REQUIREMENTS]:\n"
        for i, rule in enumerate(guidelines, 1):
            compiled += f" {i}. {rule}\n"
            
        if user_context:
            compiled += f"\n[ADDITIONAL TASK CONTEXT]:\n{user_context}\n"
            
        return compiled

    def record_execution(self, task_type: str, score: float, duration: float, model: str, error_occurred: bool = False):
        """
        Records reflection scores and triggers dynamic optimizations for underperforming templates.
        """
        t_type = task_type.upper()
        if t_type not in self.templates:
            t_type = "CODE"

        entry = {
            "timestamp": time.time(),
            "task_type": t_type,
            "score": score,
            "duration": duration,
            "model": model,
            "error": error_occurred
        }
        self.history.append(entry)

        # Triggers self-repair/optimization logic for templates showing low reflection scores (< 0.70)
        if score < 0.70 or error_occurred:
            self._optimize_template(t_type, error_occurred)

        self._save_telemetry()

    def _optimize_template(self, task_type: str, error_occurred: bool):
        """
        Applies heuristic self-reinforcement to instructions when low metrics are recorded.
        """
        template = self.templates[task_type]
        guidelines = template.get("guidelines", [])

        # Prevent duplicates
        failsafe_rules = {
            "CODE": "Verify all variable scopes and avoid uninitialized reference assignments.",
            "DEBUG": "Analyze the stack depth thoroughly and do not mask syntax errors.",
            "TEST": "Integrate comprehensive mocks to avoid hanging asynchronous loop connections.",
            "RESEARCH": "Scan file layout patterns recursively to guarantee import trace precision."
        }

        target_rule = failsafe_rules.get(task_type, "Implement comprehensive error-catching gates.")
        
        if target_rule not in guidelines:
            guidelines.append(target_rule)
            template["guidelines"] = guidelines
            console.print(f"[bold green][OPTIMIZATION] Auto-reinforced guidelines for {task_type} with failures mitigations.[/bold green]")
