"""
USTAAD Secret Detection — Real-Time Secret Scanning

Scans file content for hardcoded secrets, API keys, tokens, and
credentials before they are written to disk.

Integrates with:
- PreFileWrite event hook (real-time scanning)
- Tool pipeline (blocks write_file if secrets detected)
- Audit logger (security events)

Detection patterns based on:
- GitHub secret scanning patterns
- OWASP guidelines
- Common cloud provider key formats
"""

import os
import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from pathlib import Path

from rich.console import Console

console = Console()


@dataclass
class SecretFinding:
    """A detected secret in file content."""
    pattern_name: str
    matched_text: str  # redacted
    line_number: int
    severity: str = "high"  # critical, high, medium, low
    file_path: str = ""


# ---------------------------------------------------------------------------
# Detection patterns
# ---------------------------------------------------------------------------

SECRET_PATTERNS: List[Tuple[str, str, re.Pattern, str]] = [
    # (name, severity, pattern, description)

    # API Keys
    ("AWS Access Key", "critical",
     re.compile(r"(?:AKIA|ASIA)[A-Z0-9]{16}"),
     "AWS access key ID"),

    ("AWS Secret Key", "critical",
     re.compile(r"(?:aws_secret_access_key|aws_secret)\s*[=:]\s*['\"]?([A-Za-z0-9/+=]{40})['\"]?"),
     "AWS secret access key"),

    ("GitHub Token", "critical",
     re.compile(r"(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{36,}"),
     "GitHub personal access token"),

    ("GitLab Token", "critical",
     re.compile(r"glpat-[A-Za-z0-9\-_]{20,}"),
     "GitLab personal access token"),

    ("Google API Key", "high",
     re.compile(r"AIza[A-Za-z0-9\-_]{35}"),
     "Google API key"),

    ("Slack Token", "high",
     re.compile(r"xox[baprs]-[A-Za-z0-9\-]+"),
     "Slack bot/user token"),

    ("Stripe Key", "critical",
     re.compile(r"(?:sk|pk)_(?:test|live)_[A-Za-z0-9]{20,}"),
     "Stripe API key"),

    ("OpenAI API Key", "critical",
     re.compile(r"sk-[A-Za-z0-9]{20,}"),
     "OpenAI API key"),

    ("Anthropic API Key", "critical",
     re.compile(r"sk-ant-[A-Za-z0-9\-]{20,}"),
     "Anthropic API key"),

    # Passwords and secrets
    ("Generic Password", "high",
     re.compile(r"(?:password|passwd|pwd)\s*[=:]\s*['\"]([^'\"]{8,})['\"]", re.I),
     "Hardcoded password"),

    ("Generic Secret", "high",
     re.compile(r"(?:secret|api_key|apikey|access_key)\s*[=:]\s*['\"]([^'\"]{8,})['\"]", re.I),
     "Hardcoded secret/API key"),

    ("Generic Token", "medium",
     re.compile(r"(?:token|auth_token|bearer)\s*[=:]\s*['\"]([^'\"]{8,})['\"]", re.I),
     "Hardcoded token"),

    # Connection strings
    ("Database URL", "high",
     re.compile(r"(?:postgres|mysql|mongodb|redis)://[^\s\"']+:[^\s\"'@]+@"),
     "Database connection string with credentials"),

    # Private keys
    ("Private Key", "critical",
     re.compile(r"-----BEGIN (?:RSA |EC |DSA )?PRIVATE KEY-----"),
     "Private key file content"),

    ("SSH Private Key", "critical",
     re.compile(r"-----BEGIN OPENSSH PRIVATE KEY-----"),
     "SSH private key"),

    # Cloud-specific
    ("Azure Connection String", "high",
     re.compile(r"DefaultEndpointsProtocol=https;AccountName=[^;]+;AccountKey=[^;]+"),
     "Azure storage connection string"),

    ("Firebase Config", "medium",
     re.compile(r"(?:firebase|firestore)[A-Za-z]*\s*[=:]\s*['\"][A-Za-z0-9\-_]{20,}['\"]"),
     "Firebase configuration key"),

    # JWT
    ("JWT Secret", "high",
     re.compile(r"(?:jwt_secret|JWT_SECRET)\s*[=:]\s*['\"]([^'\"]{8,})['\"]", re.I),
     "JWT signing secret"),
]

# Files to skip scanning (test files, docs, configs)
SKIP_PATTERNS = [
    re.compile(r"\.test\.", re.I),
    re.compile(r"\.spec\.", re.I),
    re.compile(r"test_", re.I),
    re.compile(r"_test\.", re.I),
    re.compile(r"\.example$", re.I),
    re.compile(r"\.sample$", re.I),
    re.compile(r"\.md$", re.I),
    re.compile(r"\.txt$", re.I),
]


class SecretScanner:
    """
    Real-time secret scanner for file content.
    
    Usage:
        scanner = SecretScanner()
        
        # Scan content before writing
        findings = scanner.scan_content(content, "config.py")
        if findings:
            print(f"Found {len(findings)} secrets!")
            for f in findings:
                print(f"  {f.severity}: {f.pattern_name} on line {f.line_number}")
    """

    def __init__(self, skip_test_files: bool = True):
        self.skip_test_files = skip_test_files
        self._allowlist: List[str] = []  # Known false positives

    def scan_content(self, content: str, file_path: str = "") -> List[SecretFinding]:
        """Scan content for secrets. Returns list of findings."""

        # Skip certain file types
        if file_path and self.skip_test_files:
            for skip in SKIP_PATTERNS:
                if skip.search(file_path):
                    return []

        findings = []
        lines = content.split("\n")

        for line_num, line in enumerate(lines, 1):
            # Skip comments
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith("//") or stripped.startswith("<!--"):
                # But still scan for actual key-like patterns inside comments
                pass

            for name, severity, pattern, description in SECRET_PATTERNS:
                matches = pattern.finditer(line)
                for match in matches:
                    matched = match.group(0)

                    # Skip allowlisted patterns
                    if any(allow in matched for allow in self._allowlist):
                        continue

                    # Skip obvious placeholders
                    if any(placeholder in matched.lower() for placeholder in [
                        "example", "your_", "xxx", "placeholder", "changeme",
                        "todo", "fixme", "dummy", "test", "fake", "sample",
                    ]):
                        continue

                    # Redact the matched text for the finding
                    redacted = matched[:8] + "***" + matched[-4:] if len(matched) > 12 else "***"

                    findings.append(SecretFinding(
                        pattern_name=name,
                        matched_text=redacted,
                        line_number=line_num,
                        severity=severity,
                        file_path=file_path,
                    ))

        return findings

    def scan_file(self, file_path: str) -> List[SecretFinding]:
        """Scan a file on disk for secrets."""
        try:
            content = Path(file_path).read_text(encoding="utf-8", errors="ignore")
            return self.scan_content(content, file_path)
        except Exception:
            return []

    def scan_directory(self, directory: str, extensions: List[str] = None) -> List[SecretFinding]:
        """Scan all files in a directory for secrets."""
        if extensions is None:
            extensions = [".py", ".js", ".ts", ".yaml", ".yml", ".json", ".env", ".cfg", ".ini", ".toml"]

        skip_dirs = {".git", "node_modules", "venv", ".venv", "__pycache__", ".ustaad"}
        all_findings = []

        for root, dirs, files in os.walk(directory):
            dirs[:] = [d for d in dirs if d not in skip_dirs]
            for f in files:
                ext = Path(f).suffix.lower()
                if ext in extensions or f in [".env", ".env.local", ".env.production"]:
                    fp = os.path.join(root, f)
                    findings = self.scan_file(fp)
                    all_findings.extend(findings)

        return all_findings

    def add_allowlist(self, pattern: str):
        """Add a pattern to the allowlist (known false positives)."""
        if pattern not in self._allowlist:
            self._allowlist.append(pattern)

    def format_findings(self, findings: List[SecretFinding]) -> str:
        """Format findings as a human-readable report."""
        if not findings:
            return "No secrets detected."

        lines = [f"⚠ Found {len(findings)} potential secret(s):"]

        critical = [f for f in findings if f.severity == "critical"]
        high = [f for f in findings if f.severity == "high"]
        medium = [f for f in findings if f.severity == "medium"]

        for severity_name, group in [("CRITICAL", critical), ("HIGH", high), ("MEDIUM", medium)]:
            if group:
                lines.append(f"\n  [{severity_name}]:")
                for f in group:
                    file_ref = f"  {f.file_path}:" if f.file_path else ""
                    lines.append(f"    Line {f.line_number}{file_ref} {f.pattern_name} ({f.matched_text})")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------
_scanner: Optional[SecretScanner] = None


def get_secret_scanner() -> SecretScanner:
    global _scanner
    if _scanner is None:
        _scanner = SecretScanner()
    return _scanner
