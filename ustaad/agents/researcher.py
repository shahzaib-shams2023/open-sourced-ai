from crewai import Agent
from ustaad.llm import load_model

researcher = Agent(
    role="Research Analyst",

    goal="""
    Research and summarize technologies
    """,

    backstory="""
    Technical researcher and analyst.
    """,

    verbose=True,

    llm=load_model(
        "mistral:latest"
    )
)
