# 🛡️ Agent Safety & Execution Constraints

To maintain safe operations and prevent data loss, the autonomous agents must abide by the following constraints:

## 1. File Writing Constraints
* **Creation**: Always use `write_file` rather than shell commands (`echo`, `cat`, etc.) to create files. This avoids shell escaping and platform compatibility issues.
* **Surgical Edits**: Use `patch_file` to modify files rather than writing them in full to minimize token waste and override collisions.

## 2. Command Execution Safety
* **Destructive Commands**: Never execute `rm -rf`, `git reset --hard`, or equivalent destructive commands without explicit developer confirmation.
* **Network Scans**: Avoid executing broad, external system scans or remote payload curls unless authorized.
