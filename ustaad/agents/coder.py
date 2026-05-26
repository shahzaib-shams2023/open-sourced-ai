from crewai import Agent
from ustaad.llm import load_model

coder = Agent(
    role="Senior Software Engineer",

    goal="""
    Write production-ready software
    """,

    backstory="""
    Expert backend and AI systems engineer.
    """,

    verbose=True,

    llm=load_model(
        "qwen3:32b"
    )
)
