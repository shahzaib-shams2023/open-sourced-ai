from crewai import LLM
import os

def load_model(model_name: str):
    if not model_name.startswith("ollama/"):
        model_name = f"ollama/{model_name}"

    return LLM(
        model=model_name,
        temperature=0.2,
        base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    )
