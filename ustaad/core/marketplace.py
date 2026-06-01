"""
USTAAD Skill Marketplace
Provides discovery, installation, and semantic version resolution for skills.
"""
import os
import requests
from typing import Dict, Any, List
from ustaad.core.skills import SkillManager

class Marketplace:
    def __init__(self, workspace: str):
        self.workspace = workspace
        self.registry_url = "https://raw.githubusercontent.com/shahzaib-shams2023/ustaad-registry/main/registry.json"
        
    def fetch_registry(self) -> Dict[str, Any]:
        """Fetch the central skill registry."""
        try:
            res = requests.get(self.registry_url, timeout=5)
            if res.status_code == 200:
                return res.json()
        except:
            pass
            
        # Hardcoded default fallback registry
        return {
            "skills": [
                {
                    "id": "aws-deploy",
                    "name": "AWS Deploy Skill",
                    "description": "Deploys to AWS via CDK.",
                    "version": "1.0.0",
                    "repo": "https://github.com/ustaad/aws-deploy.git",
                    "dependencies": []
                },
                {
                    "id": "django-pro",
                    "name": "Django Pro",
                    "description": "Django advanced best practices.",
                    "version": "2.1.0",
                    "repo": "https://github.com/ustaad/django-pro.git",
                    "dependencies": []
                }
            ]
        }

    def list_skills(self) -> List[Dict[str, Any]]:
        reg = self.fetch_registry()
        return reg.get("skills", [])
        
    def _parse_semver(self, v: str) -> tuple:
        parts = v.strip('v').split('.')
        return tuple(int(p) if p.isdigit() else p for p in parts)
        
    def _check_version(self, available: str, constraint: str) -> bool:
        """Evaluate semver constraint like '>=1.0.0'"""
        if '@' in constraint:
            constraint = constraint.split('@')[1]
            
        if constraint.startswith('>='):
            req = constraint[2:]
            return self._parse_semver(available) >= self._parse_semver(req)
        elif constraint.startswith('>'):
            req = constraint[1:]
            return self._parse_semver(available) > self._parse_semver(req)
        elif constraint.startswith('=='):
            req = constraint[2:]
            return self._parse_semver(available) == self._parse_semver(req)
        return available == constraint or not constraint
        
    def install_skill(self, skill_id: str, version_constraint: str = "") -> str:
        """Install a skill from the marketplace, resolving dependencies."""
        skills = {s["id"]: s for s in self.list_skills()}
        
        if skill_id not in skills:
            return f"Skill '{skill_id}' not found in marketplace registry."
            
        skill = skills[skill_id]
        
        if version_constraint and not self._check_version(skill["version"], version_constraint):
            return f"Version conflict: {skill_id} requires {version_constraint}, but v{skill['version']} is available."
            
        manager = SkillManager(self.workspace)
        results = []
        
        # Dependency resolution (recursive)
        for dep in skill.get("dependencies", []):
            d_id = dep
            d_ver = ""
            if "@" in dep:
                d_id, d_ver = dep.split("@", 1)
            results.append(self.install_skill(d_id, d_ver))
            
        try:
            repo_name = manager.install_from_git(skill["repo"])
            results.append(f"✓ Installed {skill['name']} (v{skill['version']}) -> {repo_name}")
        except Exception as e:
            results.append(f"✗ Failed to install {skill_id}: {e}")
            
        return "\n".join(results)
