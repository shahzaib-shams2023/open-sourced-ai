"""
USTAAD Security Agent — Vulnerability Detection & Hardening

The Security Agent scans code for credentials, vulnerabilities,
and security anti-patterns.
"""

from crewai import Agent
from ustaad.llm import load_model
from ustaad.tools.file_tools import read_file_tool, list_directory_tool, search_files_tool
from ustaad.tools.shell_tools import run_command_tool

SECURITY_BACKSTORY = """You are USTAAD's Security Agent — an application security engineer.

Scan for:
- Hardcoded secrets (API keys, passwords, tokens)
- Injection (SQL, command, XSS, SSRF)
- Auth/authz issues, insecure deserialization, path traversal
- Missing input validation, insecure dependencies
- Insecure defaults (DEBUG=True, CORS *, etc.)

Output:
[SECURITY SCAN] Files scanned.
[FINDINGS] Severity: CRITICAL/HIGH/MEDIUM/LOW — description, file, remediation.
[SECURITY VERDICT] SECURE or VULNERABLE.
"""

security_agent = Agent(
    role="Application Security Engineer",
    goal="Scan code for security vulnerabilities, secrets, injection vectors. Block insecure code.",
    backstory=SECURITY_BACKSTORY,
    verbose=True,
    allow_delegation=False,
    tools=[read_file_tool, list_directory_tool, search_files_tool, run_command_tool],
    llm=load_model("gemma3:12b"),
)
