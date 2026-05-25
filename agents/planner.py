from crewai import Agent
from llm import load_model

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
    allow_delegation=True,

    llm=load_model(
        "deepseek-r1:32b"
    )
)
