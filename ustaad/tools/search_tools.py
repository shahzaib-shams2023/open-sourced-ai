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
    return f"[INDEX] Indexed {count} code chunks for semantic search."


@tool("query_knowledge_graph")
def query_knowledge_graph_tool(node_id_or_tag: str) -> str:
    """
    Query the persistent Knowledge Graph by an entity ID or tag to find related architecture decisions, bugs, or tasks.
    Returns the node attributes and all connected relationships.
    """
    import os
    from ustaad.memory import ProjectMemory
    memory = ProjectMemory(os.getcwd())
    
    node = memory.graph.nodes.get(node_id_or_tag)
    if not node:
        return f"Entity '{node_id_or_tag}' not found in Knowledge Graph."
        
    related = memory.graph.get_related(node_id_or_tag)
    
    lines = [f"[NODE] {node_id_or_tag} (Type: {node['type']})"]
    if node.get("attributes"):
        lines.append(f"Attributes: {node['attributes']}")
        
    if related:
        lines.append("Relationships:")
        for r in related:
            target = r['target']
            t_id = target['id'] if target else "Unknown"
            lines.append(f"  - [{r['relation']}] -> {t_id}")
    else:
        lines.append("No relationships found.")
        
    return "\n".join(lines)
