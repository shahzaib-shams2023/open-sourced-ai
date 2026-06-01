# 🧠 USTAAD AI: Comprehensive Operator & User Guide

Welcome to the official guide for **Ustaad AI**, your terminal-native, autonomous software engineering agent system. Ustaad is designed to operate as a full-fledged AI engineering team directly within your terminal, possessing the ability to plan, code, test, debug, and self-repair across entire codebases.

---

## 🌟 1. Core Capabilities & Features

Ustaad goes far beyond standard autocomplete assistants. It is a state-of-the-art AI orchestration engine with the following core features:

- **Multi-Agent Orchestration**: Utilizes the CrewAI framework to deploy specialized agents (Planner, Coder, Reviewer, Debugger, etc.) that collaborate to solve complex engineering tasks.
- **Surgical File Patching**: Rather than rewriting entire files, Ustaad uses a specialized `PatchEngine` with Unified Diff support to make precise, line-by-line surgical edits, preserving your existing code and layout.
- **Token-Aware Context Budgeting**: Powered by `tiktoken`, Ustaad dynamically counts tokens and truncates file context efficiently to prevent LLM context-window overflows, allowing it to handle massive codebases.
- **Persistent Knowledge Graph Memory**: Ustaad uses ChromaDB (vector storage) alongside a JSON-backed Knowledge Graph. It actively maps the relationships between your files, tasks, and architectural decisions, giving it "long-term memory" across sessions.
- **Self-Healing Test & Repair Loop**: After writing code, Ustaad automatically runs your test suites (e.g., `pytest`) and linters. If tests fail, it enters an autonomous **Repair Loop** to diagnose and fix the issue before presenting the final result.
- **AST-Based Code Understanding**: Ustaad generates lightweight "skeletons" (class and function signatures) of your files using Python's AST module, giving the AI deep architectural awareness without consuming massive context.
- **Local-First & Secure**: By default, Ustaad is optimized to run with local models via Ollama (e.g., `qwen3:8b`), ensuring your proprietary code never leaves your machine unless configured otherwise.

---

## 🤖 2. The Agent Swarm

When you assign a task to Ustaad, it dynamically routes the work to a subset of the following specialized agents:

| Agent | Role | Capabilities |
|-------|------|--------------|
| **Planner** | Architecture & Strategy | Analyzes workspace, reads directories, and outputs a concrete, step-by-step implementation plan. |
| **Coder** | Execution | Writes files, executes surgical patches, and implements the Planner's design. |
| **Reviewer** | Quality Assurance | Reads modified files and determines a PASS/FAIL verdict based on logic and standards. |
| **Debugger** | Diagnostics | Analyzes stack traces, finds root causes of errors, and applies fixes. |
| **Security** | Vulnerability Scanning | Audits code for leaked secrets, injections, and insecure configurations. |
| **DevOps** | Infrastructure | Handles infrastructure-as-code, Docker, and deployment configurations. |
| **Researcher** | Intelligence Gathering | Searches codebases and documentation for answers. |
| **Browser** | Web Intelligence | Navigates the web to extract external documentation and context. |

---

## 🔄 3. The Execution Pipeline

When you submit a prompt, Ustaad executes a rigorous, multi-phase pipeline:

1. **SCAN**: Rapidly walks the directory to detect languages, frameworks, and file counts.
2. **ROUTE**: Determines the complexity (Trivial, Standard, Complex) and selects the required agents.
3. **INDEX**: Builds an AST (Abstract Syntax Tree) index of your repository for structural awareness.
4. **SEARCH**: Vectorizes code blocks for semantic search (skipped for trivial tasks).
5. **PLAN**: The Planner agent drafts an execution strategy.
6. **EXECUTE**: The Coder (and other agents) execute the plan using tools (write, patch, search).
7. **TEST**: Runs local linters and tests.
8. **REPAIR**: (Conditional) If tests fail, the Debugger is invoked to self-correct the code.
9. **REFLECT**: The system evaluates its performance, scores the run, and saves it to the Knowledge Graph.
10. **COMPLETE**: Outputs a detailed summary and saves the result to `ustaad_output.md`.

---

## 💻 4. Interactive CLI & Commands

Ustaad operates via an interactive, terminal-based REPL (Read-Eval-Print Loop) built with Prompt Toolkit and Rich.

To launch Ustaad, simply run `ustaad` in your terminal.

### Workspace & Context Commands
- `/scan` - Scan the workspace for files, languages, and frameworks.
- `/index` - Rebuild the deep AST repository index.
- `/search <query>` - Perform a semantic code search across your project.
- `/add <file>` - Add a specific file to the active AI context.
- `/drop <file>` - Remove a file from the active AI context.
- `/ls` - List files currently injected into the AI's context.

### Execution & Agent Commands
- `/mode` - Toggle between execution modes:
  - **AUTONOMOUS**: AI executes all file writes and tests without asking.
  - **SAFE**: AI requires user confirmation before performing destructive actions.
  - **SEMI-AUTO**: Auto-writes safe files, asks for destructive overwrites.
- `/model <name>` - Change the active LLM model (e.g., `/model llama3`).
- `/routing` - Show which agents are active and their assigned LLMs.

### Git & Verification Commands
- `/git` - View git status and active modifications.
- `/diff` - View uncommitted Git differences.
- `/test` - Run workspace tests and linters manually.

### Utilities & Dashboards
- `/dashboard` - Launch the premium Ustaad Desktop Status Dashboard.
- `/kit init` - Initialize the Ustaad Operator Kit (bootstraps rules, hooks, and skills).
- `/kit check` - Run workspace security and readiness audits.
- `/stats` - View session statistics, telemetry, and execution times.
- `/view <file>` - View a file with high-fidelity syntax highlighting.

---

## 🚀 5. How to Use Ustaad (Workflow)

### Standard Task Workflow
1. **Launch**: Open your terminal in your project directory and type `ustaad`.
2. **Add Context (Optional)**: If you know which files need editing, explicitly add them to save the AI time: `/add src/main.py`.
3. **Prompt**: Type your natural language request. Example: *"Refactor the authentication logic in main.py to use JWT tokens."*
4. **Watch**: Ustaad will automatically scan, route the task, generate a plan, and execute surgical edits.
5. **Verify**: Ustaad will run tests. If they pass, the task is complete.

### Debugging Workflow
1. Run your code. If it crashes, copy the stack trace.
2. In Ustaad, paste the stack trace: *"I am getting this error: [paste trace]. Please fix it."*
3. Ustaad's `TaskRouter` will detect the debugging context, invoke the **Debugger Agent**, and surgically patch the failing code.

---

*Built for Engineers. Powered by Local AI.*
