"""
USTAAD Repository Indexer

Builds deep repository maps: dependency graphs, module relationships,
class hierarchies, function signatures, import chains.
Stored in .ustaad/ for persistence across sessions.
"""

import os
import re
import json
from pathlib import Path
from dataclasses import dataclass, field, asdict

SKIP_DIRS = {
    ".git", "node_modules", "venv", ".venv", "__pycache__",
    ".mypy_cache", "dist", "build", "target", "memory", ".ustaad",
}


@dataclass
class ModuleInfo:
    path: str
    language: str = ""
    imports: list[str] = field(default_factory=list)
    exports: list[str] = field(default_factory=list)
    classes: list[str] = field(default_factory=list)
    functions: list[str] = field(default_factory=list)
    lines: int = 0


@dataclass
class RepoIndex:
    workspace: str = ""
    modules: dict[str, ModuleInfo] = field(default_factory=dict)
    dependency_graph: dict[str, list[str]] = field(default_factory=dict)

    def to_context_string(self) -> str:
        lines = [f"[INDEX] {len(self.modules)} modules indexed"]
        for path, mod in sorted(self.modules.items())[:30]:
            parts = []
            if mod.classes:
                parts.append(f"classes={len(mod.classes)}")
            if mod.functions:
                parts.append(f"funcs={len(mod.functions)}")
            if mod.imports:
                parts.append(f"imports={len(mod.imports)}")
            info = ", ".join(parts) if parts else f"{mod.lines}L"
            lines.append(f"  {path} ({info})")
        if len(self.modules) > 30:
            lines.append(f"  ... and {len(self.modules) - 30} more")
        return "\n".join(lines)

    def get_dependents(self, module_path: str) -> list[str]:
        """Find all modules that import the given module."""
        dependents = []
        for path, deps in self.dependency_graph.items():
            if module_path in deps:
                dependents.append(path)
        return dependents


class RepoIndexer:
    def __init__(self, workspace: str):
        self.workspace = os.path.abspath(workspace)
        self._index_path = os.path.join(self.workspace, ".ustaad", "repo_index.json")

    def build_index(self) -> RepoIndex:
        idx = RepoIndex(workspace=self.workspace)
        for root, dirs, files in os.walk(self.workspace):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for f in files:
                fp = os.path.join(root, f)
                rel = os.path.relpath(fp, self.workspace)
                ext = Path(f).suffix.lower()
                if ext == ".py":
                    mod = self._index_python(rel, fp)
                    if mod:
                        idx.modules[rel] = mod
                elif ext in (".js", ".ts", ".tsx", ".jsx"):
                    mod = self._index_js(rel, fp)
                    if mod:
                        idx.modules[rel] = mod

        # Build dependency graph
        for path, mod in idx.modules.items():
            deps = []
            for imp in mod.imports:
                for other_path in idx.modules:
                    module_name = Path(other_path).stem
                    if module_name in imp:
                        deps.append(other_path)
            idx.dependency_graph[path] = deps

        self._save(idx)
        return idx

    def load_index(self) -> RepoIndex:
        if os.path.exists(self._index_path):
            try:
                data = json.loads(Path(self._index_path).read_text(encoding="utf-8"))
                idx = RepoIndex(workspace=data.get("workspace", ""))
                for p, m in data.get("modules", {}).items():
                    idx.modules[p] = ModuleInfo(**m)
                idx.dependency_graph = data.get("dependency_graph", {})
                return idx
            except Exception:
                pass
        return self.build_index()

    def _save(self, idx: RepoIndex):
        os.makedirs(os.path.dirname(self._index_path), exist_ok=True)
        data = {
            "workspace": idx.workspace,
            "modules": {p: asdict(m) for p, m in idx.modules.items()},
            "dependency_graph": idx.dependency_graph,
        }
        Path(self._index_path).write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _index_python(self, rel: str, abspath: str) -> ModuleInfo:
        try:
            content = Path(abspath).read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return None
        mod = ModuleInfo(path=rel, language="Python", lines=len(content.splitlines()))
        for m in re.finditer(r"^(?:from\s+(\S+)\s+)?import\s+(.+)", content, re.M):
            mod.imports.append(m.group(0).strip())
        for m in re.finditer(r"^class\s+(\w+)", content, re.M):
            mod.classes.append(m.group(1))
        for m in re.finditer(r"^(?:async\s+)?def\s+(\w+)", content, re.M):
            mod.functions.append(m.group(1))
        return mod

    def _index_js(self, rel: str, abspath: str) -> ModuleInfo:
        try:
            content = Path(abspath).read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return None
        ext = Path(rel).suffix
        lang = "TypeScript" if ext in (".ts", ".tsx") else "JavaScript"
        mod = ModuleInfo(path=rel, language=lang, lines=len(content.splitlines()))
        for m in re.finditer(r"(?:import|require)\s*\(?['\"]([^'\"]+)['\"]", content):
            mod.imports.append(m.group(1))
        for m in re.finditer(r"(?:class|interface)\s+(\w+)", content):
            mod.classes.append(m.group(1))
        for m in re.finditer(r"(?:function|const|let|var)\s+(\w+)\s*(?:=\s*(?:async\s*)?\(|[\(])", content):
            mod.functions.append(m.group(1))
        for m in re.finditer(r"export\s+(?:default\s+)?(?:function|class|const|let|var)\s+(\w+)", content):
            mod.exports.append(m.group(1))
        return mod
