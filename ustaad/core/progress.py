"""
USTAAD Premium Progress Display

Rich, animated progress panels that make USTAAD feel like a
frontier-class AI system. Replaces the bland print_phase() calls
with live spinners, timing breakdowns, and status indicators.

Windows-compatible: uses ASCII fallbacks when Unicode isn't supported.
"""

import os
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Optional

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    Progress, SpinnerColumn, TextColumn, BarColumn,
    TimeElapsedColumn, MofNCompleteColumn,
)
from rich.table import Table
from rich.text import Text
from rich.columns import Columns
from rich.rule import Rule


# ---------------------------------------------------------------------------
# Windows Unicode fix — force UTF-8 console output
# ---------------------------------------------------------------------------
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except (AttributeError, OSError):
        pass
    # Also set console codepage
    try:
        os.system("chcp 65001 > nul 2>&1")
    except Exception:
        pass

console = Console(force_terminal=True)


# ---------------------------------------------------------------------------
# Detect Unicode support
# ---------------------------------------------------------------------------
def _supports_unicode() -> bool:
    """Check if the terminal can render Unicode/emoji."""
    try:
        encoding = getattr(sys.stdout, 'encoding', 'ascii') or 'ascii'
        return encoding.lower() in ('utf-8', 'utf8', 'utf-8-sig')
    except Exception:
        return False


_UNICODE = _supports_unicode()


# ---------------------------------------------------------------------------
# Phase timing tracker
# ---------------------------------------------------------------------------
@dataclass
class PhaseTimer:
    """Tracks timing for each pipeline phase."""
    name: str
    start_time: float = 0.0
    end_time: float = 0.0
    status: str = "pending"  # pending, running, done, skipped

    @property
    def duration(self) -> float:
        if self.end_time > 0:
            return self.end_time - self.start_time
        if self.start_time > 0:
            return time.time() - self.start_time
        return 0.0

    @property
    def duration_str(self) -> str:
        d = self.duration
        if d < 1:
            return f"{d*1000:.0f}ms"
        if d < 60:
            return f"{d:.1f}s"
        return f"{d/60:.1f}m"


@dataclass
class PipelineProgress:
    """Tracks the entire pipeline execution."""
    phases: list[PhaseTimer] = field(default_factory=list)
    start_time: float = 0.0
    task_description: str = ""
    task_type: str = ""
    complexity: str = ""
    agent_count: int = 0

    def add_phase(self, name: str) -> PhaseTimer:
        phase = PhaseTimer(name=name)
        self.phases.append(phase)
        return phase

    @property
    def total_duration(self) -> float:
        if self.start_time > 0:
            return time.time() - self.start_time
        return 0.0

    @property
    def total_duration_str(self) -> str:
        d = self.total_duration
        if d < 60:
            return f"{d:.1f}s"
        return f"{d/60:.1f}m"


# ---------------------------------------------------------------------------
# Phase icons and colors — ASCII fallbacks for Windows
# ---------------------------------------------------------------------------
if _UNICODE:
    PHASE_STYLE = {
        "SCAN":       {"icon": "\U0001f50d", "color": "cyan",    "verb": "Scanning workspace"},
        "INDEX":      {"icon": "\U0001f4d1", "color": "cyan",    "verb": "Indexing repository"},
        "SEARCH":     {"icon": "\U0001f50e", "color": "blue",    "verb": "Building search index"},
        "UNDERSTAND": {"icon": "\U0001f9e0", "color": "blue",    "verb": "Understanding context"},
        "ROUTE":      {"icon": "\U0001f6a6", "color": "yellow",  "verb": "Routing task"},
        "PLAN":       {"icon": "\U0001f4cb", "color": "magenta", "verb": "Creating plan"},
        "EXECUTE":    {"icon": "\u26a1",     "color": "green",   "verb": "Executing code"},
        "DEBUG":      {"icon": "\U0001f41b", "color": "red",     "verb": "Debugging"},
        "REVIEW":     {"icon": "[*]",        "color": "yellow",  "verb": "Reviewing code"},
        "SECURITY":   {"icon": "[!]",        "color": "red",     "verb": "Security scanning"},
        "TEST":       {"icon": "\U0001f9ea", "color": "yellow",  "verb": "Running tests"},
        "REPAIR":     {"icon": "\U0001f527", "color": "red",     "verb": "Repairing issues"},
        "REFLECT":    {"icon": "\U0001f4ad", "color": "white",   "verb": "Self-reflecting"},
        "COMPLETE":   {"icon": "[OK]",       "color": "green",   "verb": "Complete"},
        "RESEARCH":   {"icon": "\U0001f4da", "color": "blue",    "verb": "Researching"},
        "DEVOPS":     {"icon": "[>>]",       "color": "magenta", "verb": "Infrastructure"},
        "GIT":        {"icon": "\U0001f4e6", "color": "magenta", "verb": "Git status"},
        "MEMORY":     {"icon": "\U0001f4be", "color": "dim",     "verb": "Loading memory"},
    }
else:
    PHASE_STYLE = {
        "SCAN":       {"icon": "[>>]", "color": "cyan",    "verb": "Scanning workspace"},
        "INDEX":      {"icon": "[>>]", "color": "cyan",    "verb": "Indexing repository"},
        "SEARCH":     {"icon": "[>>]", "color": "blue",    "verb": "Building search index"},
        "UNDERSTAND": {"icon": "[>>]", "color": "blue",    "verb": "Understanding context"},
        "ROUTE":      {"icon": "[>>]", "color": "yellow",  "verb": "Routing task"},
        "PLAN":       {"icon": "[>>]", "color": "magenta", "verb": "Creating plan"},
        "EXECUTE":    {"icon": "[>>]", "color": "green",   "verb": "Executing code"},
        "DEBUG":      {"icon": "[!!]", "color": "red",     "verb": "Debugging"},
        "REVIEW":     {"icon": "[**]", "color": "yellow",  "verb": "Reviewing code"},
        "SECURITY":   {"icon": "[!!]", "color": "red",     "verb": "Security scanning"},
        "TEST":       {"icon": "[>>]", "color": "yellow",  "verb": "Running tests"},
        "REPAIR":     {"icon": "[>>]", "color": "red",     "verb": "Repairing issues"},
        "REFLECT":    {"icon": "[..]", "color": "white",   "verb": "Self-reflecting"},
        "COMPLETE":   {"icon": "[OK]", "color": "green",   "verb": "Complete"},
        "RESEARCH":   {"icon": "[>>]", "color": "blue",    "verb": "Researching"},
        "DEVOPS":     {"icon": "[>>]", "color": "magenta", "verb": "Infrastructure"},
        "GIT":        {"icon": "[>>]", "color": "magenta", "verb": "Git status"},
        "MEMORY":     {"icon": "[>>]", "color": "dim",     "verb": "Loading memory"},
    }


def phase_header(phase: str, detail: str = "", timer: PhaseTimer = None):
    """Print a premium phase header with icon and optional detail."""
    style = PHASE_STYLE.get(phase, {"icon": ">>", "color": "white", "verb": phase})
    icon = style["icon"]
    color = style["color"]
    verb = style["verb"]

    timing = ""
    if timer and timer.duration > 0:
        timing = f" [{timer.duration_str}]"

    header_text = f"{icon}  {verb}"
    console.print(f"\n[bold {color}]{header_text}[/bold {color}]", end="")
    if timing:
        console.print(f"[dim]{timing}[/dim]", end="")
    console.print()

    if detail:
        for line in detail.strip().split("\n"):
            console.print(f"[dim]   {line}[/dim]")


@contextmanager
def phase_spinner(phase: str, detail: str = ""):
    """Context manager that shows a live spinner during a phase."""
    style = PHASE_STYLE.get(phase, {"icon": ">>", "color": "white", "verb": phase})
    icon = style["icon"]
    color = style["color"]
    verb = style["verb"]

    timer = PhaseTimer(name=phase)
    timer.start_time = time.time()
    timer.status = "running"

    spinner = Progress(
        SpinnerColumn("dots", style=f"bold {color}"),
        TextColumn(f"[bold {color}]{icon}  {verb}[/bold {color}]"),
        TextColumn("[dim]{task.description}[/dim]"),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    )

    with spinner:
        task = spinner.add_task(detail, total=None)
        try:
            yield timer
        finally:
            timer.end_time = time.time()
            timer.status = "done"

    # Print completed header
    console.print(
        f"[bold {color}]{icon}  {verb}[/bold {color}] "
        f"[dim]({timer.duration_str})[/dim]"
    )


def route_banner(task_type: str, complexity: str, agent_count: int, reason: str):
    """Display routing decision as a premium panel."""
    complexity_colors = {
        "trivial": "green",
        "standard": "yellow",
        "complex": "red",
    }
    c_color = complexity_colors.get(complexity, "white")

    content = Text()
    content.append("  Task Type:   ", style="dim")
    content.append(f"{task_type.upper()}\n", style="bold white")
    content.append("  Complexity:  ", style="dim")
    content.append(f"{complexity.upper()}\n", style=f"bold {c_color}")
    content.append("  Agents:      ", style="dim")
    content.append(f"{agent_count}\n", style="bold white")
    content.append("  Strategy:    ", style="dim")
    content.append(reason, style="italic dim")

    console.print(Panel(
        content,
        title="[bold cyan]Task Routing[/bold cyan]",
        border_style="cyan",
        padding=(0, 2),
    ))


def completion_summary(
    pipeline: PipelineProgress,
    files_created: list[str] = None,
    files_modified: list[str] = None,
    test_passed: bool = True,
    lint_passed: bool = True,
    score: float = 0.0,
):
    """Display a premium completion summary panel."""
    # Summary section
    summary = Text()
    summary.append("\n")

    if files_created:
        summary.append(f"  Created:  {len(files_created)} file(s)\n", style="green")
        for f in files_created[:5]:
            summary.append(f"     + {f}\n", style="dim green")

    if files_modified:
        summary.append(f"  Modified: {len(files_modified)} file(s)\n", style="yellow")
        for f in files_modified[:5]:
            summary.append(f"     ~ {f}\n", style="dim yellow")

    # Verdicts
    t_mark = "[PASS]" if test_passed else "[FAIL]"
    l_mark = "[PASS]" if lint_passed else "[FAIL]"
    summary.append(f"\n  {t_mark} Tests    ", style="bold")
    summary.append("passed\n" if test_passed else "FAILING\n",
                    style="green" if test_passed else "bold red")
    summary.append(f"  {l_mark} Linting  ", style="bold")
    summary.append("clean\n" if lint_passed else "issues found\n",
                    style="green" if lint_passed else "bold yellow")

    # Score bar
    filled = int(score * 20)
    score_bar = "#" * filled + "-" * (20 - filled)
    score_color = "green" if score >= 0.8 else ("yellow" if score >= 0.5 else "red")
    summary.append("\n  Quality: ", style="dim")
    summary.append(f"[{score_bar}]", style=score_color)
    summary.append(f" {score:.0%}\n", style=f"bold {score_color}")

    # Timing breakdown
    summary.append("\n  Timing:\n", style="bold")
    for phase in pipeline.phases:
        if phase.status == "skipped":
            summary.append(f"    {phase.name:<14s}  --  ", style="dim")
            summary.append("skipped\n", style="dim")
        elif phase.status == "done":
            summary.append(f"    {phase.name:<14s}  {phase.duration_str:>8s}  ", style="dim")
            summary.append("OK\n", style="green")
        else:
            summary.append(f"    {phase.name:<14s}  {phase.duration_str:>8s}  ", style="dim")
            summary.append("?\n", style="yellow")

    # Total time
    summary.append(f"\n  Total: {pipeline.total_duration_str}", style="bold white")

    console.print(Panel(
        summary,
        title="[bold green]USTAAD Complete[/bold green]",
        subtitle=f"[dim]{pipeline.agent_count} agent(s) | {pipeline.total_duration_str}[/dim]",
        border_style="green",
        padding=(0, 2),
    ))


def error_panel(title: str, message: str, suggestion: str = ""):
    """Display a premium error panel."""
    content = Text()
    content.append(f"  {message}\n", style="bold red")
    if suggestion:
        content.append(f"\n  Hint: {suggestion}\n", style="dim yellow")

    console.print(Panel(
        content,
        title=f"[bold red]{title}[/bold red]",
        border_style="red",
        padding=(0, 2),
    ))


BANNER_PREMIUM = """[bold green]
 ██╗   ██╗███████╗████████╗ █████╗  █████╗ ██████╗
 ██║   ██║██╔════╝╚══██╔══╝██╔══██╗██╔══██╗██╔══██╗
 ██║   ██║███████╗   ██║   ███████║███████║██║  ██║
 ██║   ██║╚════██║   ██║   ██╔══██║██╔══██║██║  ██║
 ╚██████╔╝███████║   ██║   ██║  ██║██║  ██║██████╔╝
  ╚═════╝ ╚══════╝   ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝[/bold green]
[bold cyan]  Autonomous Engineering Agent[/bold cyan]
[dim]  scan > index > route > plan > execute > test > repair > reflect[/dim]
"""
