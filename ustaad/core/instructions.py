"""
USTAAD Instruction Cascade System

Implements Claude Code-style hierarchical instruction loading:
- Global instructions (~/.ustaad/AGENTS.md)
- Project root instructions (AGENTS.md, AI.md, CLAUDE.md, USTAAD.md)
- Directory-level overrides (subdirectory AGENTS.md files)
- .ustaad/rules/*.md dynamic rule files
- Auto-discovery of project guidance files
- Context inheritance (child directories inherit parent rules)

Priority order (highest first):
1. Project root AGENTS.md / USTAAD.md
2. Directory-level AGENTS.md (for the active file's directory)
3. AI.md / CLAUDE.md conventions
4. .ustaad/rules/*.md
5. Global ~/.ustaad/AGENTS.md
"""

import os
from pathlib import Path
from typing import List, Dict, Optional

from rich.console import Console

console = Console()


class InstructionCascade:
    """
    Hierarchical instruction loading with directory-level cascading.
    
    Usage:
        cascade = InstructionCascade(workspace="/path/to/project")
        instructions = cascade.load_all()
        
        # Get instructions specific to a subdirectory
        instructions = cascade.load_for_directory("src/auth")
    """

    # Files to look for at each level
    INSTRUCTION_FILES = [
        "AGENTS.md",
        "USTAAD.md",
        "AI.md",
        "CLAUDE.md",
        ".cursorrules",
    ]

    def __init__(self, workspace: str):
        self.workspace = os.path.abspath(workspace)
        self._global_dir = os.path.join(os.path.expanduser("~"), ".ustaad")
        self._rules_dir = os.path.join(self.workspace, ".ustaad", "rules")

    def load_all(self) -> str:
        """Load all instructions in priority order."""
        sections = []

        # 1. Global instructions
        global_instructions = self._load_global()
        if global_instructions:
            sections.append(global_instructions)

        # 2. Project root instructions
        root_instructions = self._load_project_root()
        if root_instructions:
            sections.append(root_instructions)

        # 3. Rules directory
        rules = self._load_rules_directory()
        if rules:
            sections.append(rules)

        return "\n\n".join(sections) if sections else ""

    def load_for_directory(self, relative_path: str) -> str:
        """Load cascaded instructions for a specific subdirectory."""
        sections = []

        # Start with global instructions
        global_inst = self._load_global()
        if global_inst:
            sections.append(global_inst)

        # Walk from root to the target directory, collecting AGENTS.md files
        parts = Path(relative_path).parts
        current = self.workspace

        for part in parts:
            current = os.path.join(current, part)
            dir_inst = self._load_directory_instructions(current)
            if dir_inst:
                sections.append(dir_inst)

        # Rules directory
        rules = self._load_rules_directory()
        if rules:
            sections.append(rules)

        return "\n\n".join(sections) if sections else ""

    def _load_global(self) -> str:
        """Load global ~/.ustaad/AGENTS.md."""
        for filename in self.INSTRUCTION_FILES:
            path = os.path.join(self._global_dir, filename)
            if os.path.isfile(path):
                try:
                    content = Path(path).read_text(encoding="utf-8")
                    return f"[GLOBAL INSTRUCTIONS ({filename})]\n{content}\n"
                except Exception:
                    pass
        return ""

    def _load_project_root(self) -> str:
        """Load project root instruction files."""
        sections = []
        for filename in self.INSTRUCTION_FILES:
            path = os.path.join(self.workspace, filename)
            if os.path.isfile(path):
                try:
                    content = Path(path).read_text(encoding="utf-8")
                    sections.append(f"[PROJECT INSTRUCTIONS ({filename})]\n{content}\n")
                except Exception:
                    pass
        return "\n".join(sections) if sections else ""

    def _load_directory_instructions(self, directory: str) -> str:
        """Load AGENTS.md from a specific directory."""
        if directory == self.workspace:
            return ""  # Already handled by _load_project_root
            
        for filename in ["AGENTS.md", "USTAAD.md"]:
            path = os.path.join(directory, filename)
            if os.path.isfile(path):
                try:
                    rel = os.path.relpath(directory, self.workspace)
                    content = Path(path).read_text(encoding="utf-8")
                    return f"[DIRECTORY RULES ({rel}/{filename})]\n{content}\n"
                except Exception:
                    pass
        return ""

    def _load_rules_directory(self) -> str:
        """Load all .md files from .ustaad/rules/."""
        if not os.path.isdir(self._rules_dir):
            return ""

        rules = []
        for path in sorted(Path(self._rules_dir).glob("*.md")):
            try:
                content = path.read_text(encoding="utf-8")
                rules.append(f"[RULE: {path.stem}]\n{content}")
            except Exception:
                pass

        return "\n\n".join(rules) if rules else ""

    def get_all_instruction_files(self) -> List[Dict[str, str]]:
        """List all discovered instruction files."""
        files = []

        # Global
        for filename in self.INSTRUCTION_FILES:
            path = os.path.join(self._global_dir, filename)
            if os.path.isfile(path):
                files.append({"path": path, "scope": "global", "filename": filename})

        # Project root
        for filename in self.INSTRUCTION_FILES:
            path = os.path.join(self.workspace, filename)
            if os.path.isfile(path):
                files.append({"path": path, "scope": "project", "filename": filename})

        # Subdirectories
        for root, dirs, fnames in os.walk(self.workspace):
            dirs[:] = [d for d in dirs if d not in {".git", "node_modules", "venv", ".venv", "__pycache__", ".ustaad"}]
            if root == self.workspace:
                continue
            for filename in ["AGENTS.md", "USTAAD.md"]:
                if filename in fnames:
                    path = os.path.join(root, filename)
                    rel = os.path.relpath(root, self.workspace)
                    files.append({"path": path, "scope": f"directory:{rel}", "filename": filename})

        # Rules
        if os.path.isdir(self._rules_dir):
            for path in sorted(Path(self._rules_dir).glob("*.md")):
                files.append({"path": str(path), "scope": "rules", "filename": path.name})

        return files
