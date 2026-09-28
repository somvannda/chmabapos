# start-dev.ps1
# Starts all Chmaba dev servers, each in its own PowerShell window:
#   MailHog  -> SMTP 1025 / UI http://localhost:8025
#   FastAPI  -> http://localhost:8000/docs (or the port in apps/web/.env.local)
#   Web      -> http://localhost:5173
#   Admin    -> http://localhost:5174/admin
#
# Usage:  powershell -ExecutionPolicy Bypass -File .\start-dev.ps1

$ErrorActionPreference = "Stop"

$RepoRoot   = Split-Path -Parent $MyInvocation.MyCommand.Path
$MailHogExe = "C:\Users\Kong Somvannda\Documents\trae_projects\Chmaba\Chmaba\mailhog.exe"

function Start-DevWindow {
    param(
        [string]$Title,
        [string]$Script
    )
    $inner = "`$Host.UI.RawUI.WindowTitle = '$Title'; Set-Location -LiteralPath '$RepoRoot'; $Script"
    $encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($inner))
    Start-Process powershell -ArgumentList "-NoLogo", "-NoExit", "-EncodedCommand", $encoded
}

Write-Host "Starting Chmaba dev servers from $RepoRoot"

# 1. MailHog (development email catcher)
if (Test-Path -LiteralPath $MailHogExe) {
    Start-DevWindow -Title "MailHog" -Script "& '$MailHogExe'"
    Write-Host "[1/4] MailHog   -> http://localhost:8025 (SMTP 1025)"
} else {
    Write-Warning "MailHog not found at '$MailHogExe' - skipping. Registration emails will not send."
}

# 2. FastAPI backend (loads chmabapos_api/.env from repo root).
# Use the same port the Vite dev proxy targets (apps/web/.env.local) so the
# backend and frontend can never drift; falls back to 8000 without an override.
$ApiPort = 8000
$WebEnvLocal = Join-Path $RepoRoot "apps\web\.env.local"
if (Test-Path -LiteralPath $WebEnvLocal) {
    $match = Select-String -LiteralPath $WebEnvLocal -Pattern 'VITE_DEV_API_TARGET\s*=\s*(\S+)' | Select-Object -First 1
    if ($match) {
        try {
            $candidate = ([uri]$match.Matches[0].Groups[1].Value.Trim()).Port
            if ($candidate -gt 0) { $ApiPort = $candidate }
        } catch { }
    }
}
Start-DevWindow -Title "Chmaba API" -Script "python -m uvicorn app.main:app --reload --app-dir chmabapos_api --port $ApiPort"
Write-Host "[2/4] API       -> http://localhost:$ApiPort/docs"

# 3. Vite frontend (apps/web)
Start-DevWindow -Title "Chmaba Frontend" -Script "Set-Location -LiteralPath '$RepoRoot\apps\web'; npm run dev"
Write-Host "[3/4] Frontend  -> http://localhost:5173"

# 4. Vite admin panel (apps/admin) - separate app, base path /admin/, fixed port 5174
Start-DevWindow -Title "Chmaba Admin" -Script "Set-Location -LiteralPath '$RepoRoot\apps\admin'; npm run dev -- --port 5174 --strictPort"
Write-Host "[4/4] Admin     -> http://localhost:5174/admin"
