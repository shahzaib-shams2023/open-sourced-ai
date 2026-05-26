from crewai import Agent
from ustaad.llm import load_model
from ustaad.tools.file_tools import read_file_tool, write_file_tool, append_file_tool
from ustaad.tools.shell_tools import run_command_tool

coder = Agent(
    role="Senior Software Engineer",

    goal="""
    Write production-ready software
    """,

    backstory="""
    Expert backend and AI systems engineer.
    """,

    verbose=True,
    allow_delegation=False,
    tools=[read_file_tool, write_file_tool, append_file_tool, run_command_tool],

    llm=load_model(
        "gemma3:12b"
    )
)
