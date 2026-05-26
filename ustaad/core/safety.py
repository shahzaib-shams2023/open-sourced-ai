"""
USTAAD Safety Gate

Intercepts dangerous operations and prompts the user for confirmation.
This is the layer that transforms USTAAD from blind-execution to
controlled-execution — matching Claude Code's confirmation behaviour.
"""

import os
from typing import Optional
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from ustaad.core.execution_mode import get_mode

console = Console()


class SafetyGate:
    """
    Central safety checkpoint for all USTAAD operations.

    Usage:
        gate = SafetyGate()
        if gate.confirm_command("rm -rf build/"):
            # proceed
        else:
            # aborted
    """

    def __init__(self):
        self._suppressed: set[str] = set()  # commands user said "always allow"

    def confirm_command(self, command: str) -> bool:
        """
        Check whether a shell command should proceed.
        Returns True if approved, False if rejected.
        """
        mode = get_mode()

        if not mode.should_confirm(command):
            return True

        if command in self._suppressed:
            return True

        classification = mode.classify_command(command)
        return self._prompt_user(
            action_type="SHELL COMMAND",
            description=command,
            risk_level=classification,
        )

    def confirm_file_write(self, path: str, is_overwrite: bool = False) -> bool:
        """
        Check whether writing to a file should proceed.
        """
        mode = get_mode()

        if not mode.should_confirm_file_write(path):
            return True

        if not is_overwrite:
            return True  # New files are generally safe

        return self._prompt_user(
            action_type="FILE OVERWRITE",
            description=f"Overwrite: {path}",
            risk_level="dangerous" if self._is_critical_file(path) else "normal",
        )

    def confirm_file_delete(self, path: str) -> bool:
        """
        File deletion always requires confirmation unless autonomous.
        """
        mode = get_mode()
        if mode.autonomous:
            return True

        return self._prompt_user(
            action_type="FILE DELETION",
            description=f"Delete: {path}",
            risk_level="dangerous",
        )

    def confirm_action(self, action: str, description: str, risk: str = "normal") -> bool:
        """
        Generic confirmation for any action.
        """
        mode = get_mode()
        if mode.autonomous:
            return True
        if risk == "safe" and not mode.safe:
            return True

        return self._prompt_user(
            action_type=action,
            description=description,
            risk_level=risk,
        )

    def _is_critical_file(self, path: str) -> bool:
        critical = [
            ".env", ".gitignore", "Dockerfile", "docker-compose",
            "requirements.txt", "package.json", "pyproject.toml",
            "setup.py", "Makefile", "Jenkinsfile",
        ]
        basename = os.path.basename(path)
        return any(c in basename for c in critical)

    def _prompt_user(
        self,
        action_type: str,
        description: str,
        risk_level: str = "normal",
    ) -> bool:
        """
        Display a rich confirmation prompt and wait for user input.
        """
        colour = {
            "dangerous": "bold red",
            "normal": "bold yellow",
            "safe": "bold green",
        }.get(risk_level, "bold yellow")

        risk_label = {
            "dangerous": "⚠ HIGH RISK",
            "normal": "⚡ NEEDS APPROVAL",
            "safe": "✓ SAFE",
        }.get(risk_level, "⚡ NEEDS APPROVAL")

        panel_content = Text.assemble(
            ("USTAAD wants to perform:\n\n", "bold white"),
            (f"  {description}\n\n", colour),
            (f"Risk: {risk_label}\n", colour),
        )

        console.print()
        console.print(Panel(
            panel_content,
            title=f"[bold cyan]🛡 {action_type}[/bold cyan]",
            border_style="cyan",
            padding=(1, 2),
        ))

        try:
            response = input("  Proceed? [y/N/always] ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            console.print("[red]Aborted.[/red]")
            return False

        if response in ("always", "a"):
            self._suppressed.add(description)
            return True

        return response in ("y", "yes")


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------
_gate: Optional[SafetyGate] = None


def get_safety_gate() -> SafetyGate:
    global _gate
    if _gate is None:
        _gate = SafetyGate()
    return _gate
