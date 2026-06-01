"""
USTAAD Agent Teams
Pre-configured compositions of subagents for specific workflows.
"""
from typing import List, Dict
from ustaad.core.subagents import SubagentRole

class AgentTeams:
    """Pre-configured subagent teams."""
    
    @staticmethod
    def get_team(name: str) -> List[SubagentRole]:
        """Get a team by name."""
        teams = {
            "dev": [
                SubagentRole.ARCHITECTURE,
                SubagentRole.REFACTORING,
                SubagentRole.TESTING
            ],
            "security": [
                SubagentRole.SECURITY_AUDITOR,
                SubagentRole.CODE_REVIEW
            ],
            "docs": [
                SubagentRole.DOCUMENTATION,
                SubagentRole.ARCHITECTURE
            ],
            "audit": [
                SubagentRole.SECURITY_AUDITOR,
                SubagentRole.PERFORMANCE,
                SubagentRole.CODE_REVIEW
            ]
        }
        return teams.get(name.lower(), [])
        
    @staticmethod
    def list_teams() -> Dict[str, List[str]]:
        """List all available teams."""
        return {
            "dev": ["Architecture", "Refactoring", "Testing"],
            "security": ["Security Auditor", "Code Review"],
            "docs": ["Documentation", "Architecture"],
            "audit": ["Security Auditor", "Performance", "Code Review"]
        }
