# Bridges the running emulator's localhost to this machine's localhost.
#
# Why this is needed:
#   * The app talks to the Vite dev-server origin (http://localhost:5173/api/v1),
#     exactly like the web app does, and Vite proxies /api on to the API
#     (VITE_DEV_API_TARGET, currently http://127.0.0.1:8001).
#   * Google sign-in requires that indirection: the OAuth `state` lives in a CSRF
#     cookie, so the authorize request and Google's callback must be served by the
#     SAME host. Google only permits http:// redirect URIs for localhost, and the
#     registered URI is http://localhost:5173/api/v1/auth/google/callback.
#   * The emulator's `localhost` is the emulator, so it must be tunnelled.
#
# Re-run this after every emulator restart (or the tunnel silently disappears).
#
# Requirements on the host:
#   1. API:  uvicorn app.main:app --reload --app-dir chmabapos_api --port 8001
#   2. Web:  cd apps/web && npm run dev          (serves 5173, proxies /api)
#
# Usage:
#   .\adb-reverse.ps1            # default port 5173 (the Vite origin)
#   .\adb-reverse.ps1 -Port 8001 # if you want the API port bridged too

param([int]$Port = 5173)

$adb = Join-Path $env:LOCALAPPDATA "Android\Sdk\platform-tools\adb.exe"
if (-not (Test-Path $adb)) {
    Write-Error "adb not found at $adb"
    exit 1
}

& $adb reverse "tcp:$Port" "tcp:$Port"
Write-Host "Tunnel: emulator 127.0.0.1:$Port  ->  this machine 127.0.0.1:$Port"
Write-Host ""
Write-Host "Active reverse tunnels:"
& $adb reverse --list
Write-Host ""
Write-Host "Make sure the API is running on port $Port:"
Write-Host "  uvicorn app.main:app --reload --app-dir chmabapos_api --port $Port"
