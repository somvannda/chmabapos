# start-pos.ps1
# Launches the Chmaba POS in a browser window with silent (kiosk) printing enabled.
#
# Browsers cannot print without a dialog from a normal tab. The only built-in way
# to make window.print() bypass the dialog is the --kiosk-printing flag, which
# sends the page straight to the default Windows printer (or the last printer
# chosen in a print dialog). The POS receipt/Z-report print styles already print
# only the receipt area, so no extra app configuration is needed.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File .\start-pos.ps1 -Url https://chmaba.com/somvannda/pos
#   powershell -ExecutionPolicy Bypass -File .\start-pos.ps1 -Url http://localhost:5173
#   powershell -ExecutionPolicy Bypass -File .\start-pos.ps1 -Url http://localhost:5173 -FullScreen
#
# Notes:
#   * Set the receipt printer as the Windows default printer, or pick it once
#     from a normal browser print dialog first. Kiosk printing reuses it silently.
#   * A dedicated browser profile is used so kiosk printing does not change the
#     normal browsing session.

param(
    [Parameter(Mandatory = $true)]
    [string]$Url,

    [string]$Browser = "",

    [switch]$FullScreen,

    [string]$UserDataDir = "$env:LOCALAPPDATA\ChmabaPOS\browser"
)

$ErrorActionPreference = "Stop"

function Find-Browser {
    param([string]$Explicit)
    if ($Explicit) {
        if (Test-Path -LiteralPath $Explicit) { return (Resolve-Path -LiteralPath $Explicit).Path }
        throw "Browser not found at '$Explicit'."
    }
    $candidates = @(
        "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
        "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
        "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe",
        "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe",
        "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe"
    )
    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path -LiteralPath $candidate)) { return $candidate }
    }
    throw "Could not find Chrome or Edge. Pass -Browser with the full path to the browser executable."
}

$browserPath = Find-Browser -Explicit $Browser
New-Item -ItemType Directory -Force -Path $UserDataDir | Out-Null

$arguments = @(
    "--kiosk-printing",
    "--user-data-dir=`"$UserDataDir`""
)
if ($FullScreen) {
    $arguments += "--kiosk"
    $arguments += $Url
} else {
    $arguments += "--app=$Url"
}

Write-Host "Launching Chmaba POS with silent printing"
Write-Host "  Browser : $browserPath"
Write-Host "  URL     : $Url"
Write-Host "  Mode    : $(if ($FullScreen) { 'full-screen kiosk' } else { 'app window' })"
Write-Host "  Profile : $UserDataDir"
Write-Host ""
Write-Host "Receipts and Z reports now print without a dialog to the default Windows printer."

Start-Process -FilePath $browserPath -ArgumentList $arguments
