"""
USTAAD Project Memory

Persistent per-project memory stored in .ustaad/ directory.
Remembers architecture decisions, previous tasks, user preferences,
and engineering context across sessions.
"""

import os
import json
import uuid
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field, asdict

import chromadb


@dataclass
class MemoryEntry:
    id: str
    timestamp: str
    category: str  # task, decision, preference, error, architecture
    content: str
    tags: list[str] = field(default_factory=list)


class ProjectMemory:
    """
    Persistent project memory stored in .ustaad/memory/.
    Uses ChromaDB for semantic search and JSON for structured data.
    """

    def __init__(self, workspace: str):
        self.workspace = os.path.abspath(workspace)
        self._dir = os.path.join(self.workspace, ".ustaad", "memory")
        os.makedirs(self._dir, exist_ok=True)

        # ChromaDB for semantic memory
        self._client = chromadb.PersistentClient(path=self._dir)
        self._collection = self._client.get_or_create_collection(name="project_memory")

        # Structured memory file
        self._struct_path = os.path.join(self._dir, "structured.json")
        self._structured = self._load_structured()

    def save(self, content: str, category: str = "task", tags: list[str] = None):
        """Save a memory entry."""
        entry = MemoryEntry(
            id=str(uuid.uuid4()),
            timestamp=datetime.now().isoformat(),
            category=category,
            content=content[:3000],
            tags=tags or [],
        )
        # Save to ChromaDB
        try:
            self._collection.add(
                ids=[entry.id],
                documents=[entry.content],
                metadatas=[{"category": category, "timestamp": entry.timestamp}],
            )
        except Exception:
            pass

        # Save to structured file
        self._structured.append(asdict(entry))
        self._save_structured()

    def search(self, query: str, n_results: int = 5) -> list[dict]:
        """Search memory semantically."""
        try:
            results = self._collection.query(
                query_texts=[query], n_results=n_results,
            )
            if results and results["documents"] and results["documents"][0]:
                return [
                    {"content": doc, "metadata": meta}
                    for doc, meta in zip(results["documents"][0], results["metadatas"][0])
                ]
        except Exception:
            pass
        return []

    def get_recent(self, count: int = 5) -> list[dict]:
        """Get most recent memory entries."""
        return self._structured[-count:]

    def get_by_category(self, category: str) -> list[dict]:
        """Get entries by category."""
        return [e for e in self._structured if e.get("category") == category]

    def save_architecture(self, summary: str):
        """Save an architecture decision/summary."""
        self.save(summary, category="architecture", tags=["architecture"])

    def save_preference(self, pref: str):
        """Save a user preference."""
        self.save(pref, category="preference", tags=["preference"])

    def get_context_string(self, query: str = "") -> str:
        """Build a context string from relevant memories."""
        lines = ["[MEMORY]"]
        if query:
            results = self.search(query, n_results=3)
            if results:
                lines.append("  Relevant memories:")
                for r in results:
                    lines.append(f"    - [{r['metadata'].get('category', '?')}] {r['content'][:150]}")
        recent = self.get_recent(3)
        if recent:
            lines.append("  Recent activity:")
            for r in recent:
                lines.append(f"    - [{r.get('category', '?')}] {r.get('content', '')[:150]}")
        if len(lines) == 1:
            lines.append("  No memories stored yet.")
        return "\n".join(lines)

    def _load_structured(self) -> list:
        if os.path.exists(self._struct_path):
            try:
                return json.loads(Path(self._struct_path).read_text(encoding="utf-8"))
            except Exception:
                pass
        return []

    def _save_structured(self):
        try:
            Path(self._struct_path).write_text(
                json.dumps(self._structured[-500:], indent=2), encoding="utf-8"
            )
        except Exception:
            pass
