"""
USTAAD Self-Reflection Engine

After code modifications, the reflection engine critiques the work:
- Did it solve the problem?
- Is architecture still clean?
- Were conventions respected?
- Are tests passing?
- Did new bugs appear?
"""

from dataclasses import dataclass, field


@dataclass
class ReflectionReport:
    """Structured self-critique output."""
    task_completed: bool = False
    architecture_clean: bool = True
    conventions_respected: bool = True
    tests_passing: bool = True
    new_issues: list[str] = field(default_factory=list)
    improvements: list[str] = field(default_factory=list)
    score: float = 0.0  # 0.0 to 1.0

    def to_context_string(self) -> str:
        lines = [
            f"[REFLECT] Score: {self.score:.0%}",
            f"  Task completed:      {'Yes' if self.task_completed else 'No'}",
            f"  Architecture clean:  {'Yes' if self.architecture_clean else 'No'}",
            f"  Conventions OK:      {'Yes' if self.conventions_respected else 'No'}",
            f"  Tests passing:       {'Yes' if self.tests_passing else 'No'}",
        ]
        if self.new_issues:
            lines.append("  New issues:")
            for issue in self.new_issues[:5]:
                lines.append(f"    - {issue}")
        if self.improvements:
            lines.append("  Suggested improvements:")
            for imp in self.improvements[:5]:
                lines.append(f"    - {imp}")
        return "\n".join(lines)


class ReflectionEngine:
    """
    Self-reflection: evaluates the quality of USTAAD's own work.
    Uses test results, lint results, and diff analysis.
    """

    def reflect(
        self,
        task_description: str,
        files_modified: list[str],
        test_passed: bool,
        lint_passed: bool,
        errors: list[str] = None,
    ) -> ReflectionReport:
        report = ReflectionReport()

        # Score components
        score = 0.0
        if test_passed:
            report.tests_passing = True
            score += 0.4
        else:
            report.tests_passing = False
            report.new_issues.append("Tests are failing")

        if lint_passed:
            score += 0.2
        else:
            report.new_issues.append("Lint issues detected")

        if files_modified:
            score += 0.2
            report.task_completed = True
        else:
            report.task_completed = False
            report.new_issues.append("No files were modified")

        # Check for suspicious patterns
        if errors:
            for err in errors[:5]:
                report.new_issues.append(err)
        else:
            score += 0.2

        report.score = min(score, 1.0)
        report.architecture_clean = score >= 0.6
        report.conventions_respected = lint_passed

        # Suggest improvements
        if not test_passed:
            report.improvements.append("Fix failing tests before finalizing")
        if not lint_passed:
            report.improvements.append("Run linter and fix issues")
        if len(files_modified) > 10:
            report.improvements.append("Large changeset — consider splitting into smaller commits")

        return report
