"""
USTAAD Testing & Validation Engine

Auto-detects test frameworks and runs them.
Captures failures, parses stack traces, and feeds them
to the repair loop for automatic fixing.

Supports: pytest, npm test, cargo test, go test, ruff, eslint, mypy, etc.
"""

import os
import re
from dataclasses import dataclass, field
from typing import Optional

from ustaad.tools.shell_tools import run_command
from ustaad.core.scanner import WorkspaceScanner, ScanResult


@dataclass
class TestResult:
    """Structured test execution result."""
    framework: str = ""
    command: str = ""
    passed: bool = False
    total: int = 0
    failures: int = 0
    errors: int = 0
    skipped: int = 0
    stdout: str = ""
    stderr: str = ""
    exit_code: int = -1
    failure_details: list[str] = field(default_factory=list)

    def to_context_string(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        lines = [
            f"[TEST] {self.framework} — {status}",
            f"  Command:  {self.command}",
            f"  Total:    {self.total}",
            f"  Passed:   {self.total - self.failures - self.errors}",
            f"  Failed:   {self.failures}",
            f"  Errors:   {self.errors}",
            f"  Skipped:  {self.skipped}",
        ]
        if self.failure_details:
            lines.append("  Failures:")
            for detail in self.failure_details[:10]:
                # Truncate long details
                short = detail[:200]
                lines.append(f"    - {short}")
        return "\n".join(lines)


@dataclass
class LintResult:
    """Structured lint/format check result."""
    tool: str = ""
    command: str = ""
    passed: bool = False
    issues: int = 0
    stdout: str = ""
    stderr: str = ""
    exit_code: int = -1

    def to_context_string(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        lines = [
            f"[LINT] {self.tool} — {status}",
            f"  Command: {self.command}",
            f"  Issues:  {self.issues}",
        ]
        if not self.passed and self.stdout:
            # Show first few lines of output
            for line in self.stdout.splitlines()[:8]:
                lines.append(f"    {line}")
        return "\n".join(lines)


class TestEngine:
    """
    Auto-detects and runs tests, linters, and formatters.
    Parses results into structured data for the repair loop.
    """

    def __init__(self, workspace: str, scan: ScanResult = None):
        self.workspace = os.path.abspath(workspace)
        self.scan = scan
        if not scan:
            scanner = WorkspaceScanner(workspace)
            self.scan = scanner.scan()

    def _run(self, cmd: str) -> dict:
        full_cmd = f"cd \"{self.workspace}\" && {cmd}"
        return run_command(full_cmd)

    # -------------------------------------------------------------------
    # Test execution
    # -------------------------------------------------------------------
    def run_tests(self) -> list[TestResult]:
        """Auto-detect and run all applicable test frameworks."""
        results = []

        for framework in self.scan.test_frameworks:
            result = self._run_framework(framework)
            if result:
                results.append(result)

        # If no test framework detected, try common defaults
        if not results:
            for framework, detector in self._default_detectors().items():
                if detector():
                    result = self._run_framework(framework)
                    if result:
                        results.append(result)
                        break

        return results

    def _run_framework(self, framework: str) -> Optional[TestResult]:
        """Run a specific test framework."""
        runners = {
            "pytest": self._run_pytest,
            "Jest": self._run_jest,
            "Vitest": self._run_vitest,
            "Mocha": self._run_npm_test,
            "Karma": self._run_npm_test,
        }
        runner = runners.get(framework)
        if runner:
            return runner()
        return None

    def _default_detectors(self) -> dict:
        """Fallback detectors for common test setups."""
        return {
            "pytest": lambda: os.path.exists(
                os.path.join(self.workspace, "pytest.ini")
            ) or any(
                f.startswith("test_") or f.endswith("_test.py")
                for f in (getattr(self.scan, '_all_files', []) if hasattr(self.scan, '_all_files') else [])
            ),
        }

    # -------------------------------------------------------------------
    # Framework-specific runners
    # -------------------------------------------------------------------
    def _run_pytest(self) -> TestResult:
        result = TestResult(framework="pytest", command="python -m pytest -v --tb=short")
        res = self._run("python -m pytest -v --tb=short 2>&1")
        result.stdout = res.get("stdout", "")
        result.stderr = res.get("stderr", "")
        result.exit_code = res.get("returncode", 1)
        result.passed = result.exit_code == 0

        # Parse pytest output
        output = result.stdout + result.stderr
        self._parse_pytest_output(output, result)
        return result

    def _run_jest(self) -> TestResult:
        result = TestResult(framework="Jest", command="npx jest --verbose")
        res = self._run("npx jest --verbose 2>&1")
        result.stdout = res.get("stdout", "")
        result.stderr = res.get("stderr", "")
        result.exit_code = res.get("returncode", 1)
        result.passed = result.exit_code == 0
        self._parse_jest_output(result.stdout + result.stderr, result)
        return result

    def _run_vitest(self) -> TestResult:
        result = TestResult(framework="Vitest", command="npx vitest run")
        res = self._run("npx vitest run 2>&1")
        result.stdout = res.get("stdout", "")
        result.stderr = res.get("stderr", "")
        result.exit_code = res.get("returncode", 1)
        result.passed = result.exit_code == 0
        return result

    def _run_npm_test(self) -> TestResult:
        result = TestResult(framework="npm test", command="npm test")
        res = self._run("npm test 2>&1")
        result.stdout = res.get("stdout", "")
        result.stderr = res.get("stderr", "")
        result.exit_code = res.get("returncode", 1)
        result.passed = result.exit_code == 0
        return result

    # -------------------------------------------------------------------
    # Output parsers
    # -------------------------------------------------------------------
    def _parse_pytest_output(self, output: str, result: TestResult):
        """Parse pytest verbose output for structured results."""
        # Match summary line: "X passed, Y failed, Z errors"
        summary = re.search(
            r"(\d+)\s+passed(?:.*?(\d+)\s+failed)?(?:.*?(\d+)\s+error)?(?:.*?(\d+)\s+skipped)?",
            output
        )
        if summary:
            passed_count = int(summary.group(1) or 0)
            result.failures = int(summary.group(2) or 0)
            result.errors = int(summary.group(3) or 0)
            result.skipped = int(summary.group(4) or 0)
            result.total = passed_count + result.failures + result.errors + result.skipped

        # Extract FAILED test names
        for match in re.finditer(r"FAILED\s+(.+?)(?:\s+-|$)", output):
            result.failure_details.append(match.group(1))

        # Extract short traceback sections
        tb_blocks = re.findall(
            r"_{3,}\s+(.*?)\s+_{3,}(.*?)(?=_{3,}|$)",
            output, re.DOTALL
        )
        for name, tb in tb_blocks[:5]:
            result.failure_details.append(f"{name.strip()}: {tb.strip()[:300]}")

    def _parse_jest_output(self, output: str, result: TestResult):
        """Parse Jest output."""
        summary = re.search(
            r"Tests:\s+(?:(\d+)\s+failed,\s+)?(?:(\d+)\s+skipped,\s+)?(\d+)\s+passed,\s+(\d+)\s+total",
            output
        )
        if summary:
            result.failures = int(summary.group(1) or 0)
            result.skipped = int(summary.group(2) or 0)
            result.total = int(summary.group(4) or 0)

    # -------------------------------------------------------------------
    # Lint / Format checking
    # -------------------------------------------------------------------
    def run_linters(self) -> list[LintResult]:
        """Auto-detect and run all applicable linters."""
        results = []

        linter_commands = {
            "Ruff": "python -m ruff check .",
            "Flake8": "python -m flake8 .",
            "Pylint": "python -m pylint --recursive=y .",
            "mypy": "python -m mypy .",
            "ESLint": "npx eslint .",
            "Biome": "npx biome check .",
        }

        for linter in self.scan.linters:
            cmd = linter_commands.get(linter)
            if cmd:
                results.append(self._run_lint(linter, cmd))

        return results

    def _run_lint(self, tool: str, command: str) -> LintResult:
        result = LintResult(tool=tool, command=command)
        res = self._run(f"{command} 2>&1")
        result.stdout = res.get("stdout", "")
        result.stderr = res.get("stderr", "")
        result.exit_code = res.get("returncode", 1)
        result.passed = result.exit_code == 0

        # Count issues from output lines
        output_lines = result.stdout.strip().splitlines()
        result.issues = len([
            l for l in output_lines
            if l.strip() and not l.startswith(("Found", "All", "Success", "-", "="))
        ])

        return result

    def run_all(self) -> str:
        """Run all tests and linters, return combined context string."""
        lines = []

        test_results = self.run_tests()
        for tr in test_results:
            lines.append(tr.to_context_string())

        lint_results = self.run_linters()
        for lr in lint_results:
            lines.append(lr.to_context_string())

        if not lines:
            return "[TEST] No test frameworks or linters detected."

        return "\n\n".join(lines)
