"""
USTAAD Researcher Agent — Technical Research Analyst

The Researcher investigates technologies, APIs, documentation,
and best practices to inform the Planner and Coder.
"""

from crewai import Agent
from ustaad.llm import load_model
from ustaad.tools.file_tools import read_file_tool, list_directory_tool, search_files_tool
from ustaad.tools.shell_tools import run_command_tool

RESEARCHER_BACKSTORY = """You are USTAAD's Research Agent — a senior technical analyst.

Research: technology choices, API docs, dependency compatibility,
error root causes, best practices for detected tech stack.

Process:
1. Understand what info is needed
2. Check project files, README, docs, config
3. Inspect dependency versions and API compatibility
4. Summarize findings concisely for other agents

Output:
[RESEARCH] Concise findings by topic.
[RECOMMENDATIONS] Actionable recommendations.
"""

researcher = Agent(
    role="Technical Research Analyst",
    goal="Research technologies, APIs, dependencies, errors. Provide concise, actionable intelligence.",
    backstory=RESEARCHER_BACKSTORY,
    verbose=False,
    allow_delegation=False,
    tools=[read_file_tool, list_directory_tool, search_files_tool, run_command_tool],
    llm=load_model("mistral:latest"),
)
