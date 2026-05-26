"""
USTAAD Test Tools — CrewAI tool wrappers for Test Engine.
"""

from crewai.tools import tool


@tool("run_tests")
def run_tests_tool(dummy: str = "") -> str:
    """Auto-detect test framework and run all tests. Returns structured results."""
    import os
    from ustaad.engine.testing import TestEngine
    engine = TestEngine(os.getcwd())
    results = engine.run_tests()
    if not results:
        return "[TEST] No test frameworks detected."
    return "\n\n".join(r.to_context_string() for r in results)


@tool("run_linters")
def run_linters_tool(dummy: str = "") -> str:
    """Auto-detect linters and run them. Returns structured results."""
    import os
    from ustaad.engine.testing import TestEngine
    engine = TestEngine(os.getcwd())
    results = engine.run_linters()
    if not results:
        return "[LINT] No linters detected."
    return "\n\n".join(r.to_context_string() for r in results)


@tool("run_all_checks")
def run_all_checks_tool(dummy: str = "") -> str:
    """Run all tests AND linters. Returns combined results."""
    import os
    from ustaad.engine.testing import TestEngine
    engine = TestEngine(os.getcwd())
    return engine.run_all()
