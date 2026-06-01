"""
USTAAD Skill & Context Assembly System
Implements AGENTS.md cascading, AI.md project memory, and Dynamic Skill Discovery.
"""

import os
import yaml
from pathlib import Path
from typing import List, Dict, Any

class ContextBuilder:
    """Handles the hierarchical loading of AGENTS.md and AI.md."""
    
    def __init__(self, workspace: str):
        self.workspace = os.path.abspath(workspace)

    def load_ai_md(self) -> str:
        """Loads AI.md or CLAUDE.md from the root of the project."""
        for filename in ["AI.md", "CLAUDE.md"]:
            path = os.path.join(self.workspace, filename)
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    return f"[PROJECT CONVENTIONS ({filename})]\n" + f.read() + "\n"
        return ""

    def load_agents_md(self) -> str:
        """
        Walks down from the root to the current directory (or just loads from root for now)
        to find AGENTS.md files and cascade their rules.
        """
        agents_content = []
        path = os.path.join(self.workspace, "AGENTS.md")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                agents_content.append(f"[AGENT RULES (Root)]\n{f.read()}")
        
        return "\n".join(agents_content) + "\n" if agents_content else ""


class SkillManager:
    """Handles parsing and retrieving .ustaad/skills/*/SKILL.md."""
    
    def __init__(self, workspace: str):
        self.workspace = workspace
        self.skills_dir = os.path.join(workspace, ".ustaad", "skills")
        self.global_skills_dir = os.path.expanduser("~/.ustaad/skills")
        self.core_skills_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "core_skills")
        self.registry: Dict[str, Dict[str, Any]] = {}

    def _parse_skill_md(self, path: str) -> Dict[str, Any]:
        """Parses YAML frontmatter and markdown body from SKILL.md."""
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
            
        metadata = {}
        body = content
        
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                try:
                    metadata = yaml.safe_load(parts[1]) or {}
                    body = parts[2].strip()
                except Exception:
                    pass
                    
        return {
            "metadata": metadata,
            "body": body,
            "path": path,
            "dir": os.path.dirname(path)
        }

    def index_skills(self):
        """Discovers and parses all SKILL.md files in local and global directories."""
        dirs_to_check = [self.core_skills_dir, self.global_skills_dir, self.skills_dir]
        
        for d in dirs_to_check:
            if not os.path.exists(d):
                continue
            for root, _, files in os.walk(d):
                if "SKILL.md" in files:
                    skill_path = os.path.join(root, "SKILL.md")
                    skill_id = os.path.basename(root)
                    data = self._parse_skill_md(skill_path)
                    
                    # Project skills override global skills with same ID
                    self.registry[skill_id] = {
                        "id": skill_id,
                        "name": data["metadata"].get("name", skill_id),
                        "description": data["metadata"].get("description", ""),
                        "tags": data["metadata"].get("tags", []),
                        "body": data["body"],
                        "dir": data["dir"]
                    }

    def retrieve_skills(self, user_prompt: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """
        Simple keyword/tag matching for now.
        In a full implementation, this uses Vector Search (cosine similarity).
        """
        prompt_lower = user_prompt.lower()
        scored_skills = []
        
        for skill_id, skill in self.registry.items():
            score = 0
            if skill_id.lower() in prompt_lower:
                score += 5
            for tag in skill["tags"]:
                if tag.lower() in prompt_lower:
                    score += 2
            if score > 0:
                scored_skills.append((score, skill))
                
        # Sort by score descending
        scored_skills.sort(key=lambda x: x[0], reverse=True)
        return [s[1] for s in scored_skills[:top_k]]
