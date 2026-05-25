from browser_use import Agent
from langchain_ollama import ChatOllama

browser_agent = Agent(
    task="""
    Browse websites and extract information
    """,

    llm=ChatOllama(
        model="qwen3:32b"
    )
)
