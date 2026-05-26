"""
USTAAD Iterative Repair Loop

The core autonomous loop:
GENERATE → EXECUTE → OBSERVE FAILURES → DEBUG → PATCH → RETEST → VERIFY → COMPLETE

USTAAD must NEVER assume generated code works.
It must test, observe, fix, and retry automatically.
"""

import os
import time
from dataclasses import dataclass, field
from typing import Optional, Callable

from rich.console import Console

from ustaad.engine.testing import TestEngine, TestResult, LintResult

console = Console()

MAX_REPAIR_ATTEMPTS = 5


@dataclass
class RepairAttempt:
    """Record of a single repair attempt."""
    attempt: int
    failures_before: list[str]
    action_taken: str
    failures_after: list[str]
    resolved: bool


@dataclass
class RepairSession:
    """Full record of a repair session."""
    attempts: list[RepairAttempt] = field(default_factory=list)
    max_attempts: int = MAX_REPAIR_ATTEMPTS
    resolved: bool = False
    final_test_output: str = ""
    total_duration: float = 0.0

    def to_context_string(self) -> str:
        lines = [
            f"[REPAIR] Session: {'RESOLVED' if self.resolved else 'UNRESOLVED'}",
            f"  Attempts:  {len(self.attempts)} / {self.max_attempts}",
            f"  Duration:  {self.total_duration:.1f}s",
        ]
        for a in self.attempts:
            status = "OK" if a.resolved else "FAIL"
            lines.append(f"  #{a.attempt}: {status} — {a.action_taken[:80]}")
        return "\n".join(lines)


class RepairLoop:
    """
    Iterative test-fix-retest engine.

    Runs tests, detects failures, invokes a repair callback,
    then retests until success or max attempts reached.
    """

    def __init__(
        self,
        workspace: str,
        repair_fn: Callable[[list[str], str], str],
        max_attempts: int = MAX_REPAIR_ATTEMPTS,
    ):
        """
        Args:
            workspace: Path to the workspace
            repair_fn: Callable(failures, test_output) -> description of fix applied
                       This is typically the CrewAI agent pipeline that fixes code.
            max_attempts: Maximum repair iterations
        """
        self.workspace = os.path.abspath(workspace)
        self.repair_fn = repair_fn
        self.max_attempts = max_attempts
        self.test_engine = TestEngine(workspace)

    def run(self) -> RepairSession:
        """
        Execute the repair loop:
        1. Run tests
        2. If pass → done
        3. If fail → call repair_fn with failure details
        4. Retest
        5. Repeat until pass or max_attempts
        """
        session = RepairSession(max_attempts=self.max_attempts)
        start_time = time.time()

        for attempt_num in range(1, self.max_attempts + 1):
            console.print(
                f"\n[bold yellow][REPAIR][/bold yellow] Attempt {attempt_num}/{self.max_attempts}"
            )

            # Run tests
            test_results = self.test_engine.run_tests()
            failures = self._extract_failures(test_results)
            test_output = "\n".join(tr.to_context_string() for tr in test_results)

            if not failures:
                console.print("[bold green]  All tests passing![/bold green]")
                session.resolved = True
                session.final_test_output = test_output
                break

            console.print(f"  Found {len(failures)} failure(s)")
            for f in failures[:3]:
                console.print(f"    - {f[:100]}")

            # Invoke repair
            try:
                action = self.repair_fn(failures, test_output)
            except Exception as e:
                action = f"Repair failed: {e}"

            # Record attempt
            # Retest to see if repair worked
            retest_results = self.test_engine.run_tests()
            new_failures = self._extract_failures(retest_results)

            attempt = RepairAttempt(
                attempt=attempt_num,
                failures_before=[f[:100] for f in failures],
                action_taken=action[:200] if action else "No action",
                failures_after=[f[:100] for f in new_failures],
                resolved=len(new_failures) == 0,
            )
            session.attempts.append(attempt)

            if attempt.resolved:
                console.print("[bold green]  Repair successful![/bold green]")
                session.resolved = True
                session.final_test_output = "\n".join(
                    tr.to_context_string() for tr in retest_results
                )
                break
            else:
                delta = len(failures) - len(new_failures)
                if delta > 0:
                    console.print(f"  Progress: {delta} failures fixed, {len(new_failures)} remaining")
                else:
                    console.print(f"  No progress — {len(new_failures)} failures remain")

        session.total_duration = time.time() - start_time

        if not session.resolved:
            console.print(
                f"[bold red]  Repair loop exhausted after {self.max_attempts} attempts[/bold red]"
            )

        return session

    def _extract_failures(self, results: list[TestResult]) -> list[str]:
        """Extract failure descriptions from test results."""
        failures = []
        for r in results:
            if not r.passed:
                failures.extend(r.failure_details)
                if not r.failure_details:
                    # Use stderr/stdout as fallback
                    output = (r.stderr or r.stdout or "Unknown failure")[:500]
                    failures.append(f"{r.framework}: {output}")
        return failures

    def run_and_report(self) -> str:
        """Run the repair loop and return a formatted report."""
        session = self.run()
        return session.to_context_string()
