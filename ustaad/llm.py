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
        timeout=900,           # 900s per request (prevents timeouts during large generations)
        max_retries=2,         # retry on timeout/connection errors
    )
    _llm_cache[model_name] = llm
    return llm


def load_model_for_role_and_complexity(role: str, complexity: str = None) -> LLM:
    """
    Load the model assigned to a specific agent role and task complexity from routing.yaml.
    Falls back to role-level default, then to cieloforge/qwen2.5-coder-7b-instruct-spec:latest.
    """
    config = _load_config()
    role_config = config.get(role, {})

    if isinstance(role_config, dict):
        if complexity and complexity in role_config:
            model_name = role_config[complexity]
        elif "model" in role_config:
            model_name = role_config["model"]
        else:
            model_name = role_config.get("default", "cieloforge/qwen2.5-coder-7b-instruct-spec:latest")
    else:
        model_name = role_config or "cieloforge/qwen2.5-coder-7b-instruct-spec:latest"

    return load_model(model_name)


def load_model_for_role(role: str) -> LLM:
    """
    Load the model assigned to a specific agent role from routing.yaml.
    Falls back to cieloforge/qwen2.5-coder-7b-instruct-spec:latest if not configured.
    """
    return load_model_for_role_and_complexity(role, None)


def get_routing_summary() -> str:
    """Return a formatted summary of model routing."""
    config = _load_config()
    lines = ["[ROUTING] Agent -> Model Mapping"]
    for role, cfg in config.items():
        if role in ("execution", "repair", "context"):
            continue
        if isinstance(cfg, dict):
            details = []
            for comp in ("trivial", "standard", "complex"):
                if comp in cfg:
                    details.append(f"{comp}:{cfg[comp]}")
            if details:
                model = f"{cfg.get('default', 'default')} ({', '.join(details)})"
            else:
                model = cfg.get("model", "default")
        else:
            model = str(cfg)
        lines.append(f"  {role:12s} -> {model}")
    return "\n".join(lines)


def reload_config():
    """Clear the cached routing config to force a reload."""
    global _config_cache
    _config_cache = None

