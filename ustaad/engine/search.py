"""
USTAAD Semantic Code Search Engine

Vector-based code search using ChromaDB.
Indexes code into chunks and retrieves relevant sections
for natural language queries.
"""

import os
import hashlib
from pathlib import Path
from dataclasses import dataclass, field
import chromadb

CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java",
    ".kt", ".rb", ".php", ".cs", ".cpp", ".c", ".swift", ".dart",
    ".sql", ".yaml", ".yml", ".toml", ".json", ".html", ".css", ".md",
}
SKIP_DIRS = {
    ".git", "node_modules", "venv", ".venv", "__pycache__",
    ".mypy_cache", ".pytest_cache", "dist", "build", "target",
    "memory", ".ustaad", ".next",
}
MAX_FILE_SIZE = 100_000
CHUNK_SIZE = 60
CHUNK_OVERLAP = 10


@dataclass
class SearchResult:
    path: str
    chunk: str
    score: float
    line_start: int = 0
    line_end: int = 0

    def to_context_string(self) -> str:
        return f"--- {self.path} (L{self.line_start}-L{self.line_end}, score={self.score:.3f}) ---\n{self.chunk}"


class SearchEngine:
    def __init__(self, workspace: str):
        self.workspace = os.path.abspath(workspace)
        idx_dir = os.path.join(self.workspace, ".ustaad", "search_index")
        os.makedirs(idx_dir, exist_ok=True)
        self._client = chromadb.PersistentClient(path=idx_dir)
        self._collection = self._client.get_or_create_collection(
            name="code_index", metadata={"hnsw:space": "cosine"},
        )
        self._hashes: set[str] = set()

    def index_workspace(self, force: bool = False) -> int:
        count = 0
        for root, dirs, files in os.walk(self.workspace):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for f in files:
                if Path(f).suffix.lower() not in CODE_EXTENSIONS:
                    continue
                fp = os.path.join(root, f)
                if os.path.getsize(fp) > MAX_FILE_SIZE:
                    continue
                count += self._index_file(os.path.relpath(fp, self.workspace), fp, force)
        return count

    def _index_file(self, rel: str, abspath: str, force: bool) -> int:
        try:
            content = Path(abspath).read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return 0
        fh = hashlib.md5(content.encode()).hexdigest()
        hid = f"{rel}::{fh}"
        if not force and hid in self._hashes:
            return 0
        try:
            ex = self._collection.get(where={"path": rel})
            if ex and ex["ids"]:
                self._collection.delete(ids=ex["ids"])
        except Exception:
            pass
        lines = content.splitlines()
        chunks = []
        for i in range(0, len(lines), CHUNK_SIZE - CHUNK_OVERLAP):
            cl = lines[i:i + CHUNK_SIZE]
            if not cl:
                continue
            ct = "\n".join(cl)
            if len(ct.strip()) < 20:
                continue
            chunks.append({"text": ct, "ls": i + 1, "le": min(i + CHUNK_SIZE, len(lines))})
        if not chunks:
            return 0
        ids = [f"{rel}::chunk_{j}" for j in range(len(chunks))]
        docs = [c["text"] for c in chunks]
        metas = [{"path": rel, "line_start": c["ls"], "line_end": c["le"], "file_hash": fh} for c in chunks]
        try:
            self._collection.add(ids=ids, documents=docs, metadatas=metas)
            self._hashes.add(hid)
            return len(chunks)
        except Exception:
            return 0

    def search(self, query: str, n_results: int = 5) -> list[SearchResult]:
        try:
            res = self._collection.query(query_texts=[query], n_results=n_results)
        except Exception:
            return []
        out = []
        if res and res["documents"] and res["documents"][0]:
            docs = res["documents"][0]
            metas = res["metadatas"][0] if res["metadatas"] else [{}] * len(docs)
            dists = res["distances"][0] if res["distances"] else [0.0] * len(docs)
            for d, m, dist in zip(docs, metas, dists):
                out.append(SearchResult(
                    path=m.get("path", "?"), chunk=d, score=1.0 - dist,
                    line_start=m.get("line_start", 0), line_end=m.get("line_end", 0),
                ))
        return out

    def search_formatted(self, query: str, n_results: int = 5) -> str:
        results = self.search(query, n_results)
        if not results:
            return f"No results for: {query}"
        lines = [f"[SEARCH] Query: {query}", f"  {len(results)} result(s):\n"]
        for r in results:
            lines.append(r.to_context_string())
            lines.append("")
        return "\n".join(lines)
