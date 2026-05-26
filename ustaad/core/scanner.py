"""
USTAAD Workspace Scanner

Deep repository intelligence — detects languages, frameworks, package managers,
Docker, CI/CD, linters, test frameworks, and coding conventions.

This is the "repository awareness" layer that makes USTAAD understand
the project before touching any code.
"""

import os
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ScanResult:
    """Structured scan output for the workspace."""
    workspace: str = ""
    languages: list[str] = field(default_factory=list)
    frameworks: list[str] = field(default_factory=list)
    package_managers: list[str] = field(default_factory=list)
    runtime: list[str] = field(default_factory=list)
    docker: bool = False
    docker_compose: bool = False
    ci_cd: list[str] = field(default_factory=list)
    linters: list[str] = field(default_factory=list)
    formatters: list[str] = field(default_factory=list)
    test_frameworks: list[str] = field(default_factory=list)
    has_git: bool = False
    entry_points: list[str] = field(default_factory=list)
    config_files: list[str] = field(default_factory=list)
    file_count: int = 0
    directory_structure: list[str] = field(default_factory=list)

    def to_context_string(self) -> str:
        """Format scan result as a concise context block for agent prompts."""
        lines = [
            f"[SCAN] Workspace: {self.workspace}",
            f"  Languages:        {', '.join(self.languages) or 'Unknown'}",
            f"  Frameworks:       {', '.join(self.frameworks) or 'None detected'}",
            f"  Package Managers: {', '.join(self.package_managers) or 'None'}",
            f"  Runtime:          {', '.join(self.runtime) or 'Unknown'}",
            f"  Docker:           {'Yes' if self.docker else 'No'}",
            f"  Docker Compose:   {'Yes' if self.docker_compose else 'No'}",
            f"  CI/CD:            {', '.join(self.ci_cd) or 'None'}",
            f"  Linters:          {', '.join(self.linters) or 'None'}",
            f"  Formatters:       {', '.join(self.formatters) or 'None'}",
            f"  Test Frameworks:  {', '.join(self.test_frameworks) or 'None'}",
            f"  Git:              {'Yes' if self.has_git else 'No'}",
            f"  Entry Points:     {', '.join(self.entry_points) or 'None'}",
            f"  Total Files:      {self.file_count}",
        ]

        if self.directory_structure:
            lines.append(f"  Structure:")
            for d in self.directory_structure[:30]:
                lines.append(f"    {d}")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Detection mappings
# ---------------------------------------------------------------------------
LANGUAGE_EXTENSIONS = {
    ".py": "Python",
    ".js": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript (React)",
    ".jsx": "JavaScript (React)",
    ".go": "Go",
    ".rs": "Rust",
    ".java": "Java",
    ".kt": "Kotlin",
    ".rb": "Ruby",
    ".php": "PHP",
    ".cs": "C#",
    ".cpp": "C++",
    ".c": "C",
    ".swift": "Swift",
    ".dart": "Dart",
    ".lua": "Lua",
    ".r": "R",
    ".scala": "Scala",
    ".ex": "Elixir",
    ".hs": "Haskell",
}

FRAMEWORK_INDICATORS = {
    "requirements.txt": {"django": "Django", "flask": "Flask", "fastapi": "FastAPI",
                         "crewai": "CrewAI", "langchain": "LangChain", "celery": "Celery",
                         "scrapy": "Scrapy", "tornado": "Tornado", "sanic": "Sanic"},
    "package.json": {"react": "React", "next": "Next.js", "vue": "Vue.js",
                     "angular": "Angular", "express": "Express", "nestjs": "NestJS",
                     "svelte": "Svelte", "nuxt": "Nuxt.js", "gatsby": "Gatsby",
                     "electron": "Electron", "vite": "Vite"},
    "Cargo.toml": {"actix": "Actix", "rocket": "Rocket", "tokio": "Tokio",
                   "bevy": "Bevy"},
    "go.mod": {"gin": "Gin", "echo": "Echo", "fiber": "Fiber"},
    "Gemfile": {"rails": "Ruby on Rails", "sinatra": "Sinatra"},
}

CI_CD_FILES = {
    ".github/workflows": "GitHub Actions",
    ".gitlab-ci.yml": "GitLab CI",
    "Jenkinsfile": "Jenkins",
    ".circleci": "CircleCI",
    ".travis.yml": "Travis CI",
    "azure-pipelines.yml": "Azure Pipelines",
    "bitbucket-pipelines.yml": "Bitbucket Pipelines",
}

LINTER_FILES = {
    ".eslintrc": "ESLint", ".eslintrc.js": "ESLint", ".eslintrc.json": "ESLint",
    "eslint.config.js": "ESLint", "eslint.config.mjs": "ESLint",
    ".pylintrc": "Pylint", "pyrightconfig.json": "Pyright",
    "mypy.ini": "mypy", ".mypy.ini": "mypy",
    "ruff.toml": "Ruff", ".flake8": "Flake8",
    ".rubocop.yml": "RuboCop",
    "biome.json": "Biome",
}

FORMATTER_FILES = {
    ".prettierrc": "Prettier", ".prettierrc.js": "Prettier",
    ".prettierrc.json": "Prettier",
    "pyproject.toml": "Black (check)",  # Need to verify [tool.black] inside
    ".editorconfig": "EditorConfig",
    "rustfmt.toml": "rustfmt",
}

TEST_FRAMEWORK_INDICATORS = {
    "pytest.ini": "pytest", "conftest.py": "pytest",
    "jest.config.js": "Jest", "jest.config.ts": "Jest",
    "vitest.config.ts": "Vitest", "vitest.config.js": "Vitest",
    "karma.conf.js": "Karma",
    ".mocharc.yml": "Mocha",
    "phpunit.xml": "PHPUnit",
    "spec/": "RSpec",
}

SKIP_DIRS = {
    ".git", "node_modules", "venv", ".venv", "env", "__pycache__",
    ".mypy_cache", ".pytest_cache", ".ruff_cache", ".next", ".nuxt",
    "dist", "build", "target", ".tox", "eggs", "*.egg-info",
    "memory", "artifacts", ".idea", ".vscode",
}


class WorkspaceScanner:
    """Scans a workspace directory and produces a ScanResult."""

    def __init__(self, workspace: str):
        self.workspace = os.path.abspath(workspace)
        self.result = ScanResult(workspace=self.workspace)

    def scan(self) -> ScanResult:
        """Run all detection passes and return structured results."""
        if not os.path.isdir(self.workspace):
            return self.result

        self._scan_files()
        self._detect_git()
        self._detect_package_managers()
        self._detect_languages()
        self._detect_frameworks()
        self._detect_ci_cd()
        self._detect_linters()
        self._detect_formatters()
        self._detect_test_frameworks()
        self._detect_docker()
        self._detect_entry_points()
        self._detect_runtime()
        self._build_directory_structure()

        return self.result

    def _should_skip(self, dirname: str) -> bool:
        return dirname in SKIP_DIRS or dirname.endswith(".egg-info")

    def _scan_files(self):
        """Walk the workspace and collect all file paths."""
        self._all_files: list[str] = []
        self._all_dirs: list[str] = []

        for root, dirs, files in os.walk(self.workspace):
            dirs[:] = [d for d in dirs if not self._should_skip(d)]
            for f in files:
                full_path = os.path.join(root, f)
                rel_path = os.path.relpath(full_path, self.workspace)
                self._all_files.append(rel_path)

            for d in dirs:
                rel_dir = os.path.relpath(os.path.join(root, d), self.workspace)
                self._all_dirs.append(rel_dir)

        self.result.file_count = len(self._all_files)

    def _detect_git(self):
        self.result.has_git = os.path.isdir(os.path.join(self.workspace, ".git"))

    def _detect_package_managers(self):
        pm_files = {
            "requirements.txt": "pip",
            "Pipfile": "pipenv",
            "pyproject.toml": "pip/poetry",
            "setup.py": "pip (setup.py)",
            "package.json": "npm",
            "yarn.lock": "yarn",
            "pnpm-lock.yaml": "pnpm",
            "Cargo.toml": "cargo",
            "go.mod": "go modules",
            "Gemfile": "bundler",
            "composer.json": "composer",
        }
        for f, pm in pm_files.items():
            if self._file_exists(f):
                self.result.package_managers.append(pm)
                self.result.config_files.append(f)

    def _detect_languages(self):
        lang_counts: dict[str, int] = {}
        for f in self._all_files:
            ext = Path(f).suffix.lower()
            if ext in LANGUAGE_EXTENSIONS:
                lang = LANGUAGE_EXTENSIONS[ext]
                lang_counts[lang] = lang_counts.get(lang, 0) + 1

        # Sort by frequency and take top languages
        self.result.languages = [
            lang for lang, _ in sorted(lang_counts.items(), key=lambda x: -x[1])
        ]

    def _detect_frameworks(self):
        for config_file, indicators in FRAMEWORK_INDICATORS.items():
            path = os.path.join(self.workspace, config_file)
            if os.path.isfile(path):
                try:
                    content = Path(path).read_text(encoding="utf-8", errors="ignore").lower()
                    for keyword, framework in indicators.items():
                        if keyword in content:
                            if framework not in self.result.frameworks:
                                self.result.frameworks.append(framework)
                except Exception:
                    pass

    def _detect_ci_cd(self):
        for indicator, ci in CI_CD_FILES.items():
            full_path = os.path.join(self.workspace, indicator)
            if os.path.exists(full_path):
                self.result.ci_cd.append(ci)

    def _detect_linters(self):
        for indicator, linter in LINTER_FILES.items():
            if self._file_exists(indicator):
                if linter not in self.result.linters:
                    self.result.linters.append(linter)

        # Check pyproject.toml for ruff/black/mypy sections
        pyproject = os.path.join(self.workspace, "pyproject.toml")
        if os.path.isfile(pyproject):
            try:
                content = Path(pyproject).read_text(encoding="utf-8", errors="ignore")
                if "[tool.ruff]" in content and "Ruff" not in self.result.linters:
                    self.result.linters.append("Ruff")
                if "[tool.mypy]" in content and "mypy" not in self.result.linters:
                    self.result.linters.append("mypy")
            except Exception:
                pass

    def _detect_formatters(self):
        for indicator, fmt in FORMATTER_FILES.items():
            if self._file_exists(indicator):
                if "check" in fmt:
                    # Verify it actually has the config
                    if indicator == "pyproject.toml":
                        try:
                            content = Path(os.path.join(self.workspace, indicator)).read_text(
                                encoding="utf-8", errors="ignore"
                            )
                            if "[tool.black]" in content:
                                self.result.formatters.append("Black")
                        except Exception:
                            pass
                else:
                    if fmt not in self.result.formatters:
                        self.result.formatters.append(fmt)

    def _detect_test_frameworks(self):
        for indicator, framework in TEST_FRAMEWORK_INDICATORS.items():
            if indicator.endswith("/"):
                if os.path.isdir(os.path.join(self.workspace, indicator.rstrip("/"))):
                    if framework not in self.result.test_frameworks:
                        self.result.test_frameworks.append(framework)
            else:
                # Check both root and subdirectories
                if self._file_exists(indicator) or self._file_exists_anywhere(indicator):
                    if framework not in self.result.test_frameworks:
                        self.result.test_frameworks.append(framework)

    def _detect_docker(self):
        self.result.docker = self._file_exists("Dockerfile")
        self.result.docker_compose = (
            self._file_exists("docker-compose.yml") or
            self._file_exists("docker-compose.yaml") or
            self._file_exists("compose.yml") or
            self._file_exists("compose.yaml")
        )

    def _detect_entry_points(self):
        entry_candidates = [
            "main.py", "app.py", "manage.py", "server.py", "cli.py",
            "index.js", "index.ts", "app.js", "app.ts", "server.js",
            "main.go", "main.rs", "Program.cs",
        ]
        for candidate in entry_candidates:
            if self._file_exists(candidate) or self._file_exists_anywhere(candidate):
                self.result.entry_points.append(candidate)

    def _detect_runtime(self):
        if self._file_exists(".python-version"):
            try:
                ver = Path(os.path.join(self.workspace, ".python-version")).read_text().strip()
                self.result.runtime.append(f"Python {ver}")
            except Exception:
                self.result.runtime.append("Python (version file found)")
        elif "Python" in self.result.languages:
            self.result.runtime.append("Python")

        if self._file_exists(".nvmrc") or self._file_exists(".node-version"):
            self.result.runtime.append("Node.js")
        elif "JavaScript" in self.result.languages or "TypeScript" in self.result.languages:
            self.result.runtime.append("Node.js")

        if "Go" in self.result.languages:
            self.result.runtime.append("Go")
        if "Rust" in self.result.languages:
            self.result.runtime.append("Rust")
        if "Ruby" in self.result.languages:
            self.result.runtime.append("Ruby")

    def _build_directory_structure(self):
        """Build a top-level directory tree for context."""
        top_level = []
        for d in sorted(self._all_dirs):
            depth = d.count(os.sep)
            if depth <= 1:
                top_level.append(f"[DIR]  {d}/")

        for f in sorted(self._all_files):
            if os.sep not in f:
                top_level.append(f"[FILE] {f}")

        self.result.directory_structure = top_level[:50]

    def _file_exists(self, filename: str) -> bool:
        return os.path.exists(os.path.join(self.workspace, filename))

    def _file_exists_anywhere(self, filename: str) -> bool:
        return any(f.endswith(filename) for f in self._all_files)
