"""
USTAAD Model Router

Loads model assignments from config/routing.yaml and routes
each agent role to its optimal Ollama model.
"""

import os
import yaml
from crewai import LLM
from pathlib import Path


_config_cache = None
_llm_cache: dict[str, LLM] = {}


def _load_config() -> dict:
    global _config_cache
    if _config_cache is not None:
        return _config_cache

    # Search for routing.yaml relative to this file
    config_paths = [
        os.path.join(os.path.dirname(__file__), "config", "routing.yaml"),
        os.path.join(os.getcwd(), "ustaad", "config", "routing.yaml"),
    ]
    for path in config_paths:
        if os.path.isfile(path):
            try:
                _config_cache = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
                return _config_cache
            except Exception:
                pass

    _config_cache = {}
    return _config_cache


def load_model(model_name: str) -> LLM:
    """Load an Ollama model, with caching."""
    if model_name in _llm_cache:
        return _llm_cache[model_name]

    if not model_name.startswith("ollama/"):
        model_name_full = f"ollama/{model_name}"
    else:
        model_name_full = model_name

    llm = LLM(
        model=model_name_full,
        temperature=0.2,
        base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"),
    )
    _llm_cache[model_name] = llm
    return llm


def load_model_for_role(role: str) -> LLM:
    """
    Load the model assigned to a specific agent role from routing.yaml.
    Falls back to gemma3:12b if not configured.
    """
    config = _load_config()
    role_config = config.get(role, {})

    if isinstance(role_config, dict):
        model_name = role_config.get("model", "gemma3:12b")
    else:
        model_name = "gemma3:12b"

    return load_model(model_name)


def get_routing_summary() -> str:
    """Return a formatted summary of model routing."""
    config = _load_config()
    lines = ["[ROUTING] Agent -> Model"]
    for role, cfg in config.items():
        if role == "execution":
            continue
        if isinstance(cfg, dict):
            model = cfg.get("model", "default")
        else:
            model = str(cfg)
        lines.append(f"  {role:12s} -> {model}")
    return "\n".join(lines)
