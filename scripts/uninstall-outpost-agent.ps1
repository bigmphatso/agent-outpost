param(
    [string]$InstallDir = "",
    [switch]$RemoveConfig
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($InstallDir)) {
    $localInstall = Join-Path $env:LOCALAPPDATA "OUTPOST\Agent"
    $machineInstall = Join-Path $env:ProgramFiles "OUTPOST\Agent"
    if (Test-Path $machineInstall) {
        $InstallDir = $machineInstall
    }
    else {
        $InstallDir = $localInstall
    }
}

Get-Process outpost-agent -ErrorAction SilentlyContinue | Stop-Process -Force

if (Test-Path $InstallDir) {
    Remove-Item -LiteralPath $InstallDir -Recurse -Force
    Write-Host "Removed OUTPOST agent files from: $InstallDir"
}
else {
    Write-Host "OUTPOST agent install directory was not found: $InstallDir"
}

if ($RemoveConfig) {
    $configDir = Join-Path $env:PROGRAMDATA "OUTPOST"
    if (Test-Path $configDir) {
        Remove-Item -LiteralPath $configDir -Recurse -Force
        Write-Host "Removed OUTPOST agent configuration from: $configDir"
    }
}
else {
    Write-Host "Configuration was left in place. Re-run with -RemoveConfig to remove it."
}
