"""
USTAAD Patch Tools — CrewAI tool wrappers for the Patch Engine.
Provides surgical file editing, diff preview, and rollback to agents.
"""

from crewai.tools import tool


@tool("patch_file")
def patch_file_tool(path: str, search: str, replace: str) -> str:
    """
    Surgically edit a file by finding exact text and replacing it.
    This is MUCH better than rewriting the entire file.
    Only the matched text is changed; everything else is preserved.
    Use this instead of write_file when modifying existing files.
    """
    import os
    from ustaad.engine.patch import PatchEngine, PatchHunk
    workspace = os.getcwd()
    engine = PatchEngine(workspace)
    hunk = PatchHunk(search=search, replace=replace)
    result = engine.apply_patch(path, [hunk])
    if result.success:
        return f"[PATCHED] {path} — {result.hunks_applied} hunk(s) applied\n{result.diff[:2000]}"
    return f"[PATCH FAILED] {path} — {result.error}"


@tool("preview_diff")
def preview_diff_tool(path: str, search: str, replace: str) -> str:
    """
    Preview what a patch would look like WITHOUT applying it.
    Use this to verify changes before committing them.
    """
    import os
    from ustaad.engine.patch import PatchEngine, PatchHunk
    workspace = os.getcwd()
    engine = PatchEngine(workspace)
    hunk = PatchHunk(search=search, replace=replace)
    return engine.preview_diff(path, [hunk])[:3000]


@tool("rollback_file")
def rollback_file_tool(path: str) -> str:
    """Rollback a file to its state before the last patch was applied."""
    import os
    from ustaad.engine.patch import PatchEngine
    workspace = os.getcwd()
    engine = PatchEngine(workspace)
    return engine.rollback(path)
