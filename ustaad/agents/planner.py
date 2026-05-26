from crewai import Agent
from ustaad.llm import load_model
from ustaad.tools.file_tools import read_file_tool
from ustaad.tools.shell_tools import run_command_tool

planner = Agent(
    role="Project Planner",

    goal="""
    Break tasks into executable steps
    """,

    backstory="""
    Elite systems architect capable of
    designing scalable software systems.
    """,

    verbose=True,
    allow_delegation=False,
    tools=[read_file_tool, run_command_tool],

    llm=load_model(
        "gemma3:12b"
    )
)
