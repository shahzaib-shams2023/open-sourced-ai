# 🌿 Workspace Coding Standards

This guide is utilized by autonomous engineering agents to maintain consistency and high structural standards in this repository.

## 1. Code Style Conventions
* **Readability**: Code must be descriptive, self-documenting, and follow PEP-8 (for Python) or ESLint/Airbnb guidelines (for JavaScript).
* **Typing**: Use standard type annotations (e.g. Python `typing` or TypeScript `types`) for all public interface methods.
* **Preservation**: Keep all existing documentation, comments, and unrelated code intact.

## 2. Refactoring Standards
* **DRY (Don't Repeat Yourself)**: Reuse existing utilities, models, and classes rather than re-creating them.
* **Single Responsibility**: Keep functions small and specialized.
* **Error Handling**: Always handle exceptional cases, resource cleanups (`try/finally` or `with` blocks), and log errors cleanly.
