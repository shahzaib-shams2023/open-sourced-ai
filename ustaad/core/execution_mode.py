"""
USTAAD Execution Mode Controller

Controls how USTAAD operates:
- SAFE mode: read-only operations auto-approved, writes need confirmation
- SEMI-AUTONOMOUS (default): safe operations auto-run, dangerous ones confirm
- AUTONOMOUS: everything auto-runs (use with caution)
"""

from dataclasses import dataclass, field
from typing import Optional
import re


# ---------------------------------------------------------------------------
# Dangerous command patterns — anything matching these requires confirmation
# ---------------------------------------------------------------------------
DANGEROUS_PATTERNS: list[re.Pattern] = [
    # Destructive file operations
    re.compile(r"\brm\s+(-[rRf]+\s+|--force|--recursive)", re.I),
    re.compile(r"\brmdir\b", re.I),
    re.compile(r"\bdel\s+/[sS]", re.I),           # Windows del /S
    re.compile(r"\bRemove-Item\b.*-Recurse", re.I),

    # Git destructive operations
    re.compile(r"\bgit\s+(reset\s+--hard|push\s+--force|clean\s+-[fdx]+|checkout\s+--\s+\.)", re.I),
    re.compile(r"\bgit\s+branch\s+-[dD]", re.I),

    # Docker destructive
    re.compile(r"\bdocker\s+(system\s+prune|volume\s+prune|container\s+rm|rmi)", re.I),

    # Database destructive
    re.compile(r"\bDROP\s+(TABLE|DATABASE|SCHEMA)\b", re.I),
    re.compile(r"\bTRUNCATE\b", re.I),
    re.compile(r"\bDELETE\s+FROM\b", re.I),

    # Package removal
    re.compile(r"\b(pip|npm|yarn|pnpm)\s+(uninstall|remove)\b", re.I),

    # System-level
    re.compile(r"\bsudo\b", re.I),
    re.compile(r"\bchmod\s+777\b", re.I),
    re.compile(r"\bchown\b", re.I),

    # Credential / env manipulation
    re.compile(r"\bexport\s+\w*(?:KEY|SECRET|TOKEN|PASSWORD)\b", re.I),

    # Migration / data operations
    re.compile(r"\bmigrate\b.*--fake", re.I),
    re.compile(r"\bflush\b", re.I),
]

# Safe command patterns — always auto-approved
SAFE_PATTERNS: list[re.Pattern] = [
    re.compile(r"^\s*git\s+(status|log|diff|branch(?!\s+-[dD]))\b"),
    re.compile(r"^\s*ls\b"),
    re.compile(r"^\s*dir\b"),
    re.compile(r"^\s*cat\b"),
    re.compile(r"^\s*type\b"),
    re.compile(r"^\s*head\b"),
    re.compile(r"^\s*tail\b"),
    re.compile(r"^\s*find\b"),
    re.compile(r"^\s*grep\b"),
    re.compile(r"^\s*rg\b"),
    re.compile(r"^\s*wc\b"),
    re.compile(r"^\s*echo\b"),
    re.compile(r"^\s*pwd\b"),
    re.compile(r"^\s*tree\b"),
    re.compile(r"^\s*(python|node|pip|npm)\s+--version\b"),
    re.compile(r"^\s*(pip|npm|yarn)\s+(list|show|info)\b"),
    re.compile(r"^\s*pytest\b"),
    re.compile(r"^\s*python\s+-m\s+pytest\b"),
    re.compile(r"^\s*(pylint|flake8|mypy|ruff|eslint)\b"),
]


@dataclass
class ExecutionMode:
    """
    Controls USTAAD's execution behaviour.

    safe              – when True, only read operations auto-run
    autonomous        – when True, ALL operations auto-run (overrides safe)
    confirm_destructive – when True (default), dangerous operations prompt user
    """
    safe: bool = True
    autonomous: bool = False
    confirm_destructive: bool = True

    def classify_command(self, command: str) -> str:
        """
        Classify a shell command as 'safe', 'dangerous', or 'normal'.
        """
        cmd = command.strip()

        # Check dangerous first
        for pattern in DANGEROUS_PATTERNS:
            if pattern.search(cmd):
                return "dangerous"

        # Check safe
        for pattern in SAFE_PATTERNS:
            if pattern.search(cmd):
                return "safe"

        return "normal"

    def should_confirm(self, command: str) -> bool:
        """
        Returns True if the command requires user confirmation.
        """
        if self.autonomous:
            return False

        classification = self.classify_command(command)

        if classification == "dangerous":
            return self.confirm_destructive

        if classification == "safe":
            return False

        # Normal commands: confirm only in safe mode
        return self.safe

    def should_confirm_file_write(self, path: str) -> bool:
        """
        Returns True if writing to this file path requires confirmation.
        """
        if self.autonomous:
            return False

        # Always confirm overwriting critical files
        critical_patterns = [
            ".env", ".gitignore", "Dockerfile", "docker-compose",
            "requirements.txt", "package.json", "pyproject.toml",
            "setup.py", "setup.cfg", "Makefile", ".github",
            "Jenkinsfile", ".gitlab-ci", "tsconfig.json",
        ]
        for pattern in critical_patterns:
            if pattern in path:
                return True

        return self.safe


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------
_current_mode: Optional[ExecutionMode] = None


def get_mode() -> ExecutionMode:
    global _current_mode
    if _current_mode is None:
        _current_mode = ExecutionMode()
    return _current_mode


def set_mode(
    safe: Optional[bool] = None,
    autonomous: Optional[bool] = None,
    confirm_destructive: Optional[bool] = None,
) -> ExecutionMode:
    global _current_mode
    mode = get_mode()
    if safe is not None:
        mode.safe = safe
    if autonomous is not None:
        mode.autonomous = autonomous
    if confirm_destructive is not None:
        mode.confirm_destructive = confirm_destructive
    _current_mode = mode
    return mode
