"""
USTAAD Smart Task Router

Classifies tasks by complexity and routes them to the optimal pipeline:
- TRIVIAL  → Single-agent fast path (coder only, no review)
- STANDARD → Planner + Coder + Reviewer
- COMPLEX  → Full pipeline with all specialists

This is the #1 speed optimization: simple tasks should NOT spin up
5 agents when 1 will do.
"""

import re
from dataclasses import dataclass, field
from enum import Enum


class TaskComplexity(Enum):
    TRIVIAL = "trivial"      # ~1 agent, <30s target
    STANDARD = "standard"    # ~3 agents, <2min target
    COMPLEX = "complex"      # ~5 agents, full pipeline


class TaskType(Enum):
    CODE = "code"
    DEBUG = "debug"
    DEVOPS = "devops"
    RESEARCH = "research"
    REVIEW = "review"
    TEST = "test"
    REFACTOR = "refactor"


@dataclass
class TaskRoute:
    """Routing decision for a task."""
    task_type: TaskType
    complexity: TaskComplexity
    agents_needed: list[str]          # ordered list of agent roles
    skip_indexing: bool = False       # skip repo indexing for speed
    skip_search: bool = False         # skip semantic search
    skip_tests: bool = False          # skip post-task testing
    context_budget: int = 60_000      # chars of context to send
    model_override: str = ""          # use a different model for this task
    reason: str = ""                  # why this routing was chosen

    @property
    def agent_count(self) -> int:
        return len(self.agents_needed)


# ---------------------------------------------------------------------------
# Keyword banks for classification
# ---------------------------------------------------------------------------
_DEBUG_KW = frozenset([
    "fix", "bug", "error", "crash", "failing", "broken", "debug",
    "traceback", "exception", "not working", "issue", "problem",
    "undefined", "null", "segfault", "panic", "stacktrace",
])

_DEVOPS_KW = frozenset([
    "docker", "deploy", "ci/cd", "pipeline", "kubernetes", "k8s",
    "nginx", "infrastructure", "dockerfile", "compose", "github actions",
    "terraform", "ansible", "helm", "monitoring", "prometheus", "grafana",
])

_RESEARCH_KW = frozenset([
    "research", "investigate", "compare", "analyze", "what is",
    "how does", "explain", "difference between", "pros and cons",
    "best practice", "recommend",
])

_REVIEW_KW = frozenset([
    "review", "audit", "check", "inspect", "validate", "security scan",
])

_TEST_KW = frozenset([
    "test", "spec", "coverage", "unit test", "integration test",
    "e2e test",
])

_REFACTOR_KW = frozenset([
    "refactor", "restructure", "reorganize", "clean up", "simplify",
    "extract", "rename", "move", "split",
])

# Patterns that indicate a TRIVIAL task (fast path)
_TRIVIAL_PATTERNS = [
    re.compile(r"^(add|create|write)\s+(a\s+)?simple\s+", re.I),
    re.compile(r"^rename\s+", re.I),
    re.compile(r"^(add|update|change|modify)\s+(the\s+)?(import|comment|docstring|type\s*hint)", re.I),
    re.compile(r"^(add|remove|update)\s+(a\s+)?(dependency|package|requirement)", re.I),
    re.compile(r"^(fix|update)\s+(the\s+)?(typo|spelling|indent|format)", re.I),
    re.compile(r"^(add|create)\s+(a\s+)?\.?gitignore", re.I),
    re.compile(r"^(add|create)\s+(a\s+)?readme", re.I),
    re.compile(r"^(update|bump)\s+(the\s+)?version", re.I),
    re.compile(r"^(add|set)\s+(an?\s+)?env", re.I),
]

# Patterns that indicate a COMPLEX task
_COMPLEX_PATTERNS = [
    re.compile(r"(authentication|auth)\s+(system|flow|module)", re.I),
    re.compile(r"(database|db)\s+(migration|schema|model)", re.I),
    re.compile(r"(api|rest|graphql)\s+(endpoint|route|server)", re.I),
    re.compile(r"(microservice|distributed|multi.?tenant)", re.I),
    re.compile(r"(full.?stack|end.?to.?end|complete|entire)", re.I),
    re.compile(r"(architect|design|blueprint)", re.I),
    re.compile(r"(payment|billing|subscription|stripe)", re.I),
    re.compile(r"(deploy|production|scale)", re.I),
    re.compile(r"(ci/cd|pipeline|workflow)", re.I),
]


def _count_keyword_hits(prompt_lower: str, keyword_set: frozenset) -> int:
    return sum(1 for kw in keyword_set if kw in prompt_lower)


def classify_type(prompt: str) -> TaskType:
    """Classify the task type based on keywords."""
    p = prompt.lower()

    scores = {
        TaskType.DEBUG: _count_keyword_hits(p, _DEBUG_KW),
        TaskType.DEVOPS: _count_keyword_hits(p, _DEVOPS_KW),
        TaskType.RESEARCH: _count_keyword_hits(p, _RESEARCH_KW),
        TaskType.REVIEW: _count_keyword_hits(p, _REVIEW_KW),
        TaskType.TEST: _count_keyword_hits(p, _TEST_KW),
        TaskType.REFACTOR: _count_keyword_hits(p, _REFACTOR_KW),
    }

    best_type = max(scores, key=scores.get)
    if scores[best_type] > 0:
        return best_type
    return TaskType.CODE


def classify_complexity(prompt: str, file_count: int = 0) -> TaskComplexity:
    """Classify task complexity based on prompt patterns and workspace size."""
    p = prompt.strip()

    # Check for complex patterns first (takes priority)
    complex_hits = sum(1 for pat in _COMPLEX_PATTERNS if pat.search(p))
    if complex_hits >= 2:
        return TaskComplexity.COMPLEX
    if complex_hits >= 1:
        return TaskComplexity.STANDARD

    # Multi-file indicators
    if any(kw in p.lower() for kw in ["multiple files", "several files", "across", "all files"]):
        return TaskComplexity.COMPLEX

    # Creation keywords that imply multi-file work
    creation_kw = ["create", "build", "implement", "set up", "setup", "scaffold", "generate"]
    has_creation = any(kw in p.lower() for kw in creation_kw)
    if has_creation and len(p) > 40:
        return TaskComplexity.STANDARD

    # Check for trivial patterns
    for pattern in _TRIVIAL_PATTERNS:
        if pattern.search(p):
            return TaskComplexity.TRIVIAL

    # Short prompts (<40 chars) with no complex keywords = trivial
    if len(p) < 40:
        return TaskComplexity.TRIVIAL

    # Large workspace + long task = complex
    if file_count > 200 and len(p) > 100:
        return TaskComplexity.COMPLEX

    return TaskComplexity.STANDARD


def route_task(prompt: str, file_count: int = 0, is_empty_workspace: bool = False) -> TaskRoute:
    """
    The main routing function. Analyzes the prompt and returns
    optimal pipeline configuration.
    """
    task_type = classify_type(prompt)
    complexity = classify_complexity(prompt, file_count)

    from ustaad.core.execution_mode import get_mode
    mode = get_mode()

    # --- FLUID LOOP (Claude Code style) ---
    if mode.agentic:
        return TaskRoute(
            task_type=task_type,
            complexity=complexity,
            agents_needed=["coder"],
            skip_indexing=True,
            skip_search=True,
            skip_tests=True,
            context_budget=100_000,
            reason="Fluid agentic loop — Lead agent handles all phases autonomously via tools"
        )

    # Empty workspace overrides: always use planner + coder for greenfield
    if is_empty_workspace:
        return TaskRoute(
            task_type=task_type,
            complexity=TaskComplexity.STANDARD,
            agents_needed=["planner", "coder"],
            skip_indexing=True,
            skip_search=True,
            skip_tests=True,
            context_budget=20_000,
            reason="Empty workspace — greenfield project, skip scanning/indexing",
        )

    # --- TRIVIAL fast path ---
    if complexity == TaskComplexity.TRIVIAL:
        return TaskRoute(
            task_type=task_type,
            complexity=complexity,
            agents_needed=["coder"],
            skip_indexing=True,
            skip_search=False,
            skip_tests=False,
            context_budget=30_000,
            reason="Simple task — single-agent fast path",
        )

    # --- STANDARD pipeline ---
    if complexity == TaskComplexity.STANDARD:
        agents = ["planner", "coder", "reviewer"]

        if task_type == TaskType.DEBUG:
            # Debugger traces root cause + Coder applies fix — skip planner/reviewer
            agents = ["debugger", "coder"]
        elif task_type == TaskType.RESEARCH:
            agents = ["researcher", "planner", "coder", "reviewer"]

        return TaskRoute(
            task_type=task_type,
            complexity=complexity,
            agents_needed=agents,
            context_budget=50_000,
            reason="Standard pipeline",
        )

    # --- COMPLEX full pipeline ---
    agents = ["planner", "coder", "reviewer"]

    if task_type == TaskType.DEBUG:
        agents = ["researcher", "planner", "debugger", "coder", "reviewer", "security"]
    elif task_type == TaskType.DEVOPS:
        agents = ["planner", "devops", "coder", "reviewer", "security"]
    elif task_type == TaskType.CODE:
        agents = ["planner", "coder", "reviewer", "security"]
    elif task_type == TaskType.RESEARCH:
        agents = ["researcher", "planner", "coder", "reviewer"]
    elif task_type == TaskType.REFACTOR:
        agents = ["planner", "coder", "reviewer"]

    return TaskRoute(
        task_type=task_type,
        complexity=complexity,
        agents_needed=agents,
        context_budget=60_000,
        reason="Complex task — full pipeline with specialists",
    )
