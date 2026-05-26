from crewai import Agent
from ustaad.llm import load_model
from ustaad.tools.file_tools import read_file_tool

reviewer = Agent(
    role="Code Reviewer",

    goal="""
    Review generated code for bugs,
    security and scalability
    """,

    backstory="""
    Expert security engineer and reviewer.
    """,

    verbose=True,
    allow_delegation=False,
    tools=[read_file_tool],

    llm=load_model(
        "gemma3:12b"
    )
)
