"""
USTAAD Context Management Engine

Intelligently manages the context window to avoid token overflow.
Selects only relevant repository sections, compresses old context,
and prioritizes recent/relevant information.
"""

import os
from pathlib import Path
from dataclasses import dataclass, field


MAX_CONTEXT_TOKENS = 15_000  # 15K tokens


@dataclass
class ContextBlock:
    """A prioritized block of context."""
    label: str
    content: str
    priority: int  # lower = higher priority
    token_count: int = 0

    def __post_init__(self):
        try:
            import tiktoken
            enc = tiktoken.get_encoding("cl100k_base")
            self.token_count = len(enc.encode(self.content))
        except ImportError:
            self.token_count = len(self.content) // 4


class ContextManager:
    """
    Assembles context for agent prompts without exceeding token limits.
    Higher priority blocks are included first.
    """

    def __init__(self, max_tokens: int = None, max_chars: int = None):
        if max_tokens is None:
            if max_chars is not None:
                self.max_tokens = max_chars // 4
            else:
                self.max_tokens = MAX_CONTEXT_TOKENS
        else:
            self.max_tokens = max_tokens
        self._blocks: list[ContextBlock] = []

    def add(self, label: str, content: str, priority: int = 50):
        if content and content.strip():
            self._blocks.append(ContextBlock(label=label, content=content.strip(), priority=priority))

    def build(self) -> str:
        """Build final context string within budget."""
        sorted_blocks = sorted(self._blocks, key=lambda b: b.priority)
        result_parts = []
        remaining = self.max_tokens

        for block in sorted_blocks:
            if remaining <= 0:
                break
            tokens = block.token_count
            content = block.content
            if tokens > remaining:
                ratio = remaining / tokens if tokens > 0 else 0
                char_limit = int(len(content) * ratio)
                content = content[:char_limit] + "\n... (truncated)"
                tokens = remaining
            result_parts.append(f"=== {block.label} ===\n{content}")
            remaining -= tokens

        return "\n\n".join(result_parts)

    def get_budget_remaining(self) -> int:
        used = sum(b.token_count for b in self._blocks)
        return max(0, self.max_tokens - used)

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
