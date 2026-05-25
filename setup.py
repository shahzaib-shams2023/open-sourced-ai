from setuptools import setup, find_packages

setup(
    name="ustaad",

    version="1.0.0",

    packages=find_packages(),

    install_requires=[
        "crewai",
        "langchain",
        "langchain-ollama",
        "rich",
        "typer",
        "chromadb",
    ],

    entry_points={
        "console_scripts": [
            "ustaad=ustaad.cli:app"
        ]
    }
)
