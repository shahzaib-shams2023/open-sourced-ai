# USTAAD Operator Kit Installer (PowerShell)
Write-Host "⚡ [USTAAD] Initializing Operator Kit..." -ForegroundColor Cyan

# Create project directories
New-Item -ItemType Directory -Force -Path ".ustaad-kit\rules" | Out-Null
New-Item -ItemType Directory -Force -Path ".ustaad-kit\hooks" | Out-Null
New-Item -ItemType Directory -Force -Path ".ustaad-kit\skills" | Out-Null

# Copy git pre-commit hook
if (Test-Path ".git\hooks") {
    Copy-Item -Path ".ustaad-kit\hooks\pre-commit" -Destination ".git\hooks\pre-commit" -Force -ErrorAction SilentlyContinue
    Write-Host "🛡️ Git pre-commit hook registered." -ForegroundColor Green
}

Write-Host "✅ USTAAD Operator Kit setup complete!" -ForegroundColor Green
