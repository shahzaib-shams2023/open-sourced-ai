from crewai import Agent
from ustaad.llm import load_model

shell_agent = Agent(
    role="Shell Operator",

    goal="""
    Execute shell commands safely
    """,

    backstory="""
    Linux systems and DevOps specialist.
    """,

    verbose=True,

    llm=load_model(
        "gemma3:12b"
    )
)
