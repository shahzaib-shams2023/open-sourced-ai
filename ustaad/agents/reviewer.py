from crewai import Agent
from llm import load_model

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

    llm=load_model(
        "deepseek-r1:32b"
    )
)
