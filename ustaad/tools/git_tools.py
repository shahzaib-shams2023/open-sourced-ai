"""
USTAAD Git Tools — CrewAI tool wrappers for Git Engine.
"""

from crewai.tools import tool


@tool("git_status")
def git_status_tool(dummy: str = "") -> str:
    """Get comprehensive git status: branch, staged, modified, untracked, conflicts."""
    import os
    from ustaad.engine.git import GitEngine
    engine = GitEngine(os.getcwd())
    return engine.status().to_context_string()


@tool("git_diff")
def git_diff_tool(path: str = "") -> str:
    """Show git diff for working tree changes. Optionally specify a file path."""
    import os
    from ustaad.engine.git import GitEngine
    engine = GitEngine(os.getcwd())
    return engine.diff_full(path=path if path else None)[:4000]


@tool("git_log")
def git_log_tool(count: str = "10") -> str:
    """Show recent git commit history."""
    import os
    from ustaad.engine.git import GitEngine
    engine = GitEngine(os.getcwd())
    return engine.log(count=int(count))


@tool("git_commit")
def git_commit_tool(message: str) -> str:
    """Stage all changes and commit with the given message."""
    import os
    from ustaad.engine.git import GitEngine
    engine = GitEngine(os.getcwd())
    engine.stage_files()
    return engine.commit(message)


@tool("git_auto_commit")
def git_auto_commit_tool(dummy: str = "") -> str:
    """Auto-generate a commit message from changes and commit."""
    import os
    from ustaad.engine.git import GitEngine
    engine = GitEngine(os.getcwd())
    return engine.auto_commit()
