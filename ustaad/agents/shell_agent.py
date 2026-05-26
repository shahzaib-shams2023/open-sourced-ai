from crewai import Agent
from ustaad.llm import load_model
from ustaad.tools.shell_tools import run_command_tool

shell_agent = Agent(
    role="Shell Operator",

    goal="""
    Execute shell commands safely
    """,

    backstory="""
    Linux systems and DevOps specialist.
    """,

    verbose=True,
    allow_delegation=False,
    tools=[run_command_tool],

    llm=load_model(
        "gemma3:12b"
    )
)
