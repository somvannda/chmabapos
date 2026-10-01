# start-pos.ps1
# Launches the Chmaba POS in a browser window with silent (kiosk) printing enabled.
#
# Browsers cannot print without a dialog from a normal tab. The only built-in way
# to make window.print() bypass the dialog is the --kiosk-printing flag, which
# sends the page straight to the default Windows printer (or the last printer
# chosen in a print dialog). The POS receipt/Z-report print styles already print
# only the receipt area, so no extra app configuration is needed.
#
# It can also open the customer-facing display on a second monitor, so the
# customer sees the running order and the KHQR code while the cashier works on
# the main screen. Both windows share the same browser profile, which is what
# lets the display receive the order over BroadcastChannel.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File .\start-pos.ps1 -Url https://chmaba.com/somvannda/pos
#   powershell -ExecutionPolicy Bypass -File .\start-pos.ps1 -Url http://localhost:5173
#   powershell -ExecutionPolicy Bypass -File .\start-pos.ps1 -Url http://localhost:5173 -FullScreen
#   powershell -ExecutionPolicy Bypass -File .\start-pos.ps1 -Url http://localhost:5173 -WithDisplay
#   powershell -ExecutionPolicy Bypass -File .\start-pos.ps1 -Url https://chmaba.com/store/pos -WithDisplay -DisplayFullScreen
#
# Notes:
#   * Set the receipt printer as the Windows default printer, or pick it once
#     from a normal browser print dialog first. Kiosk printing reuses it silently.
#   * A dedicated browser profile is used so kiosk printing does not change the
#     normal browsing session.
#   * The customer display must share that profile to receive the order, so it is
#     opened as a second window of the same browser instance. Chromium can ignore
#     the requested window position when it reuses a running instance; if the
#     display does not land on the second monitor, drag it there once and it will
#     be remembered for that browser session.

param(
    [Parameter(Mandatory = $true)]
    [string]$Url,

    [string]$Browser = "",

    [switch]$FullScreen,

    # Also open the customer display (a second window showing the order + KHQR).
    [switch]$WithDisplay,

    # Customer display URL. Defaults to <origin>/display when -WithDisplay is set.
    [string]$DisplayUrl = "",

    # 1-based monitor for the customer display (1 = primary, 2 = second monitor).
    [int]$DisplayScreen = 2,

    # Open the customer display in full-screen.
    [switch]$DisplayFullScreen,

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

# Bounds of the requested monitor, or $null when it cannot be detected. Used to
# place the customer display window on the second screen.
function Get-ScreenBounds {
    param([int]$ScreenNumber)
    try {
        Add-Type -AssemblyName System.Windows.Forms -ErrorAction Stop
        $screens = [System.Windows.Forms.Screen]::AllScreens
        if (-not $screens -or $screens.Count -le 1) { return $null }
        if ($ScreenNumber -ge 2) {
            $target = $screens | Where-Object { -not $_.Primary } | Select-Object -First 1
        } else {
            $target = $screens | Where-Object { $_.Primary } | Select-Object -First 1
        }
        if (-not $target) { return $null }
        return [pscustomobject]@{
            X      = $target.Bounds.X
            Y      = $target.Bounds.Y
            Width  = $target.Bounds.Width
            Height = $target.Bounds.Height
        }
    } catch {
        return $null
    }
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

if ($WithDisplay -and -not $DisplayUrl) {
    try {
        $uri = [uri]$Url
        $DisplayUrl = "$($uri.Scheme)://$($uri.Authority)/display"
    } catch {
        Write-Warning "Could not derive a customer display URL from '$Url'. Pass -DisplayUrl explicitly."
    }
}

if ($DisplayUrl) {
    # Same profile as the POS: the display receives the order over BroadcastChannel.
    $displayArguments = @("--user-data-dir=`"$UserDataDir`"")
    if ($DisplayFullScreen) { $displayArguments += "--start-fullscreen" }
    $bounds = Get-ScreenBounds -ScreenNumber $DisplayScreen
    if ($bounds) {
        $displayArguments += "--window-position=$($bounds.X),$($bounds.Y)"
        $displayArguments += "--window-size=$($bounds.Width),$($bounds.Height)"
    }
    $displayArguments += "--app=$DisplayUrl"

    Write-Host ""
    Write-Host "Launching customer display"
    Write-Host "  URL     : $DisplayUrl"
    if ($bounds) {
        Write-Host "  Screen  : monitor $DisplayScreen ($($bounds.Width)x$($bounds.Height) at $($bounds.X),$($bounds.Y))"
    } else {
        Write-Host "  Screen  : monitor $DisplayScreen (no second monitor detected; drag the window once if needed)"
    }

    Start-Process -FilePath $browserPath -ArgumentList $displayArguments
}
