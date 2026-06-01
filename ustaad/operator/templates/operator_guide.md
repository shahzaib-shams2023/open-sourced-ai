# 🚀 USTAAD Operator Guide

Welcome to your AI Assistant Operator Kit! This toolkit provides drop-in rules, persistence configs, and safety guardrails to bootstrap an extremely safe and consistent engineering environment.

## ⚡ Quick Start Checklist
1. **Initialize the Kit**:
   Run `/kit init` inside the REPL to generate project rules and git hooks.
2. **Verify Security**:
   Run `/kit check` or `ustaad kit check` to audit code for leaked secrets or risky configurations.
3. **Context Persistence**:
   Add files with `/add` and save your workspace state with `/save` (or reload with `/load`).

## 📁 Directory Structure
* `.ustaad-kit/rules/`: Custom code styling and security policies.
* `.ustaad-kit/hooks/`: Git pre-commit hooks.
* `.ustaad-kit/skills/`: Dynamically synthesized local coding tools.
* `.ustaad/session_context.json`: Saved context, telemetries, and state files.
