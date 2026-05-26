"""
USTAAD Context Management Engine

Intelligently manages the context window to avoid token overflow.
Selects only relevant repository sections, compresses old context,
and prioritizes recent/relevant information.
"""

import os
from pathlib import Path
from dataclasses import dataclass, field


MAX_CONTEXT_CHARS = 60_000  # ~15K tokens


@dataclass
class ContextBlock:
    """A prioritized block of context."""
    label: str
    content: str
    priority: int  # lower = higher priority
    char_count: int = 0

    def __post_init__(self):
        self.char_count = len(self.content)


class ContextManager:
    """
    Assembles context for agent prompts without exceeding token limits.
    Higher priority blocks are included first.
    """

    def __init__(self, max_chars: int = MAX_CONTEXT_CHARS):
        self.max_chars = max_chars
        self._blocks: list[ContextBlock] = []

    def add(self, label: str, content: str, priority: int = 50):
        if content and content.strip():
            self._blocks.append(ContextBlock(label=label, content=content.strip(), priority=priority))

    def build(self) -> str:
        """Build final context string within budget."""
        sorted_blocks = sorted(self._blocks, key=lambda b: b.priority)
        result_parts = []
        remaining = self.max_chars

        for block in sorted_blocks:
            if remaining <= 0:
                break
            content = block.content
            if len(content) > remaining:
                content = content[:remaining] + "\n... (truncated)"
            result_parts.append(f"=== {block.label} ===\n{content}")
            remaining -= len(content) + len(block.label) + 10

        return "\n\n".join(result_parts)

    def get_budget_remaining(self) -> int:
        used = sum(b.char_count for b in self._blocks)
        return max(0, self.max_chars - used)

    def summarize_file(self, path: str, max_lines: int = 50) -> str:
        """Read a file but only return first N lines as summary."""
        try:
            content = Path(path).read_text(encoding="utf-8", errors="ignore")
            lines = content.splitlines()
            if len(lines) <= max_lines:
                return content
            return "\n".join(lines[:max_lines]) + f"\n... ({len(lines) - max_lines} more lines)"
        except Exception as e:
            return f"Error reading {path}: {e}"

    def clear(self):
        self._blocks.clear()
