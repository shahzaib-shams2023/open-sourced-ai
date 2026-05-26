from crewai import Agent
from ustaad.llm import load_model
from ustaad.tools.file_tools import read_file_tool
from ustaad.tools.shell_tools import run_command_tool

researcher = Agent(
    role="Research Analyst",

    goal="""
    Research and summarize technologies
    """,

    backstory="""
    Technical researcher and analyst.
    """,

    verbose=True,
    allow_delegation=False,
    tools=[read_file_tool, run_command_tool],

    llm=load_model(
        "mistral:latest"
    )
)
