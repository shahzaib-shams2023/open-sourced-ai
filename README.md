# USTAAD AI

USTAAD is an advanced, autonomous, multi-agent coding assistant designed to rival state-of-the-art systems like Claude Code and Cursor. It runs entirely on open-source, local language models and utilizes a modular architecture to plan, write, patch, and verify code dynamically.

## Features

- **Multi-Agent Orchestration**: Utilizes a dual-agent architecture (a Planner for high-level systems design and a Coder for implementation) powered by `CrewAI`.
- **Surgical File Patching**: Replaces naive full-file overwrites with an intelligent Unified Diff Patcher, capable of precise search-and-replace line edits to preserve structural integrity.
- **Persistent Knowledge Graph Memory**: Tracks architectural decisions, file changes, and bug histories across sessions. It augments ChromaDB's semantic vector search with explicit relational node-graph mappings for rich contextual understanding.
- **AST Code Mapping**: Analyzes massive files using AST (Python) and advanced heuristic mapping (JS/TS) to give the AI a skeleton view of large codebases, preserving LLM token context windows.
- **Dynamic Context Budgeting**: Intelligently tracks and truncates context injections using accurate `tiktoken` byte-pair encoding calculations rather than naive character limits.
- **Interactive Tool Execution**: The AI proactively runs terminal verification commands (like `pytest` or `npm test`) during code generation, correcting itself before finalizing output.

## Architecture Highlights

- `ustaad/agents/`: Definitions of Planner and Coder agents, featuring specific constraints, tool access arrays, and backstories.
- `ustaad/engine/`: Core functionality housing the `PatchEngine`, `ContextManager`, AST parser, and `SearchEngine`.
- `ustaad/memory/`: Hybrid memory cluster supporting both `chromadb` for semantic similarity and JSON-backed `KnowledgeGraph` representation.
- `ustaad/tools/`: Suite of functional toolsets explicitly exposed to the models, including git handlers, search agents, and surgical file editors.

## Getting Started

1. Set up a standard virtual environment and install the dependencies:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```
2. Start the USTAAD REPL or terminal interface to interact with your local agent swarm.

## Operator Kit
For advanced users, refer to the `.ustaad-kit/operator_guide.md` for information on initializing git hooks, rules, and telemetry persistence.
