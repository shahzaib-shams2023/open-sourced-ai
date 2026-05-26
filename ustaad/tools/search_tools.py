"""
USTAAD Search Tools — CrewAI tool wrappers for Semantic Search Engine.
"""

from crewai.tools import tool


@tool("semantic_search")
def semantic_search_tool(query: str) -> str:
    """
    Search the codebase semantically. Ask questions like:
    - 'where is authentication handled'
    - 'find database models'
    - 'locate API routes'
    Returns the most relevant code chunks.
    """
    import os
    from ustaad.engine.search import SearchEngine
    engine = SearchEngine(os.getcwd())
    return engine.search_formatted(query, n_results=5)


@tool("index_codebase")
def index_codebase_tool(dummy: str = "") -> str:
    """Index the entire codebase for semantic search. Run this before searching."""
    import os
    from ustaad.engine.search import SearchEngine
    engine = SearchEngine(os.getcwd())
    count = engine.index_workspace()
    stats = engine.get_index_stats()
    return f"[INDEX] Indexed {count} new chunks. Total: {stats['total_chunks']} chunks."
