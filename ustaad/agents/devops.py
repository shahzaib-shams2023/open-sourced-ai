"""
USTAAD DevOps Agent — Infrastructure & Deployment

The DevOps Agent handles Docker, CI/CD, deployment configs,
and infrastructure-related tasks.
"""

from crewai import Agent
from ustaad.llm import load_model
from ustaad.tools.file_tools import (
    read_file_tool, write_file_tool, list_directory_tool, search_files_tool,
)
from ustaad.tools.shell_tools import run_command_tool

DEVOPS_BACKSTORY = """You are USTAAD's DevOps Agent — a senior platform engineer.

Responsibilities: Docker, CI/CD, environment, dependencies, deployment, monitoring.

Rules:
- NEVER commit secrets to VCS
- Use multi-stage Docker builds
- Pin dependency versions in production
- Include health check endpoints
- Prefer env vars over config files for secrets

Output: [INFRASTRUCTURE] [CHANGES] [VERIFICATION]
"""

devops_agent = Agent(
    role="Senior DevOps & Platform Engineer",
    goal="Handle infrastructure, Docker, CI/CD, deployment. Build reliable, automated infrastructure.",
    backstory=DEVOPS_BACKSTORY,
    verbose=False,
    allow_delegation=False,
    tools=[
        read_file_tool, write_file_tool, list_directory_tool,
        search_files_tool, run_command_tool,
    ],
    llm=load_model("gemma3:12b"),
)
