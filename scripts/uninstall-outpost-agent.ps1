param(
    [string]$InstallDir = "",
    [switch]$RemoveConfig
)

$ErrorActionPreference = "Stop"
$ServiceName = "OutpostAgent"

function Test-IsAdministrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

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

$existingService = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if ($existingService) {
    if (-not (Test-IsAdministrator)) {
        throw "OUTPOST Agent service is installed. Re-run this uninstall script from an elevated PowerShell session."
    }
    if ($existingService.Status -ne "Stopped") {
        Stop-Service -Name $ServiceName -Force
        $existingService.WaitForStatus("Stopped", "00:00:30")
    }
    & sc.exe delete $ServiceName | Out-Null
    Write-Host "Removed OUTPOST Agent service: $ServiceName"
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
