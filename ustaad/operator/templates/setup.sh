#!/bin/bash
# USTAAD Operator Kit Installer (POSIX)

echo "⚡ [USTAAD] Initializing Operator Kit..."

# Create project directories
mkdir -p .ustaad-kit/rules
mkdir -p .ustaad-kit/hooks
mkdir -p .ustaad-kit/skills

# Copy hooks
if [ -d ".git/hooks" ]; then
    cp .ustaad-kit/hooks/pre-commit .git/hooks/pre-commit 2>/dev/null || true
    chmod +x .git/hooks/pre-commit 2>/dev/null || true
    echo "🛡️ Git pre-commit hook registered."
fi

echo "✅ USTAAD Operator Kit setup complete!"
