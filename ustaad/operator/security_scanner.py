import os
import re
import glob
from typing import Dict, List, Any
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()

# Regular expressions for detecting secrets and high-risk API keys
SECRET_PATTERNS = {
    "OpenAI API Key": re.compile(r"sk-[a-zA-Z0-9]{48}"),
    "Generic Secret / Token / Key": re.compile(r"(?:secret|token|password|auth|api_key|private_key|passwd)\s*[:=]\s*['\"][a-zA-Z0-9_\-]{16,}['\"]", re.IGNORECASE),
    "Slack Webhook / Bot Token": re.compile(r"xoxb-[0-9]{11,13}-[a-zA-Z0-9]{24}"),
    "AWS Key ID": re.compile(r"(?:AKIA|ASIA)[0-9A-Z]{16}"),
    "GitHub Personal Access Token": re.compile(r"gh[oprs]_[a-zA-Z0-9]{36,255}"),
    "Private Key Block": re.compile(r"-----BEGIN [A-Z ]+ PRIVATE KEY-----")
}

RISKY_COMMAND_PATTERNS = {
    "Destructive Script Execution": re.compile(r"(?:rm\s+-rf\s|git\s+reset\s+--hard|docker\s+prune|mkfs|dd\s+if=)"),
    "Piped Remote Payload Execution": re.compile(r"(?:curl|wget)\s+.*\|\s*(?:sh|bash|zsh|python|perl)"),
    "Arbitrary Command Eval": re.compile(r"(?:eval|exec)\s*\(.*?(?:sys\.argv|input|request|os\.environ)"),
}

def run_security_scan(workspace: str = None, git_staged_only: bool = False) -> Dict[str, Any]:
    """
    Scans the workspace files (or staged files) for hardcoded secrets, database URIs,
    or dangerous script commands.
    """
    workspace = workspace or os.getcwd()
    findings: List[Dict[str, Any]] = []
    
    # 1. Gather files to scan
    files_to_scan = []
    
    if git_staged_only:
        # Get staged files via Git
        import subprocess
        try:
            res = subprocess.run(["git", "diff", "--cached", "--name-only"], capture_output=True, text=True, check=True)
            files_to_scan = [os.path.join(workspace, f.strip()) for f in res.stdout.splitlines() if f.strip() and os.path.isfile(os.path.join(workspace, f.strip()))]
        except Exception:
            files_to_scan = []
    else:
        # Scan general text files in the project
        extensions = ["*.py", "*.js", "*.ts", "*.json", "*.yml", "*.yaml", "*.md", "*.env", "*.sh", "*.bat", "*.ps1"]
        skip_folders = {".git", ".ustaad", "node_modules", "venv", ".venv", "env", "__pycache__", "dist", "build"}
        
        for root, dirs, files in os.walk(workspace):
            dirs[:] = [d for d in dirs if d not in skip_folders]
            for f in files:
                ext = "*" + os.path.splitext(f)[1]
                if ext in [os.path.splitext(e)[1] for e in extensions] or f == ".env" or f == "Dockerfile":
                    files_to_scan.append(os.path.join(root, f))

    # 2. Check Gitignore leaks
    gitignore_check = True
    gitignore_path = os.path.join(workspace, ".gitignore")
    if os.path.isfile(gitignore_path):
        try:
            with open(gitignore_path, "r", encoding="utf-8", errors="ignore") as f:
                gitignore_content = f.read()
            # Verify if .env is ignored
            if ".env" not in gitignore_content:
                gitignore_check = False
                findings.append({
                    "file": ".gitignore",
                    "line": 0,
                    "type": "Config Security Breach",
                    "severity": "dangerous",
                    "content": ".env file is not added to .gitignore. This could leak credentials!"
                })
        except Exception:
            pass

    # 3. Perform file regex matching
    for filepath in files_to_scan[:200]: # Cap file scans to prevent system lockups
        if os.path.isdir(filepath):
            continue
        try:
            filename = os.path.relpath(filepath, workspace)
            
            # Avoid scanning huge binary files
            if os.path.getsize(filepath) > 1 * 1024 * 1024:
                continue
                
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                for line_idx, line in enumerate(f):
                    line_str = line.strip()
                    
                    # A. Check secrets patterns
                    for name, pat in SECRET_PATTERNS.items():
                        if pat.search(line_str):
                            findings.append({
                                "file": filename,
                                "line": line_idx + 1,
                                "type": f"Hardcoded Secret ({name})",
                                "severity": "dangerous",
                                "content": re.sub(r"['\"][a-zA-Z0-9_\-]{8,}['\"]", "'******'", line_str)[:120] # mask the key
                            })

                    # B. Check risky commands patterns
                    for name, pat in RISKY_COMMAND_PATTERNS.items():
                        if pat.search(line_str):
                            findings.append({
                                "file": filename,
                                "line": line_idx + 1,
                                "type": f"Risky Script Instruction ({name})",
                                "severity": "normal",
                                "content": line_str[:120]
                            })
        except Exception:
            pass

    # 4. Render Rich Dashboard elements if executed interactively
    score = max(0, 100 - len([f for f in findings if f["severity"] == "dangerous"]) * 20 - len([f for f in findings if f["severity"] == "normal"]) * 5)
    
    return {
        "score": score,
        "findings": findings,
        "gitignore_passed": gitignore_check
    }


def print_security_report(scan_results: Dict[str, Any]):
    """Renders a gorgeous security report table in the Rich terminal console."""
    findings = scan_results.get("findings", [])
    score = scan_results.get("score", 100)
    
    console.print()
    score_style = "bold green" if score >= 90 else ("bold yellow" if score >= 70 else "bold red")
    console.print(Panel(
        f"  Security Health Score: [{score_style}]{score} / 100[/{score_style}]\n"
        f"  Total Security Alerts: [bold yellow]{len(findings)}[/bold yellow] findings",
        title="[bold cyan]🛡️ USTAAD Workspace Security Audit[/bold cyan]",
        border_style="cyan",
        padding=(0, 2)
    ))
    
    if not findings:
        console.print("[bold green]✓ Security Scan Passed. No hardcoded credentials or risky commands found![/bold green]")
        return

    table = Table(title="Security Findings Registry", show_header=True, header_style="bold cyan")
    table.add_column("Location", style="green")
    table.add_column("Severity", style="bold red")
    table.add_column("Vulnerability Classification", style="magenta")
    table.add_column("Snippet Evidence", style="dim")
    
    for f in findings:
        severity_label = "[red]HIGH[/red]" if f["severity"] == "dangerous" else "[yellow]MEDIUM[/yellow]"
        table.add_row(
            f"{f['file']}:{f['line']}" if f['line'] > 0 else f['file'],
            severity_label,
            f["type"],
            f["content"]
        )
    console.print(table)


def run_git_pre_commit() -> int:
    """
    Runs during the Git pre-commit lifecycle.
    Returns 1 if HIGH severity secrets are detected, blocking the commit.
    Returns 0 if safe.
    """
    res = run_security_scan(git_staged_only=True)
    findings = res.get("findings", [])
    dangerous_findings = [f for f in findings if f["severity"] == "dangerous"]
    
    if dangerous_findings:
        console.print("\n[bold red]❌ [USTAAD SECURITY AUDIT] staged commit BLOCKED! Hardcoded secrets detected:[/bold red]")
        for df in dangerous_findings:
            console.print(f"   - [red]{df['file']}:{df['line']}[/red] | [dim]{df['content']}[/dim]")
        console.print("\n[yellow]Please remove the credentials or commit with 'git commit --no-verify'.[/yellow]")
        return 1
        
    return 0
