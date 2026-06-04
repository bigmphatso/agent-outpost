param(
    [string]$BackendUrl = "https://backend-outpost.onrender.com",
    [string]$OrgCode = "",
    [string]$Passcode = "",
    [string]$ApiKey = "",
    [int]$PollInterval = 30,
    [string]$InstallDir = "",
    [switch]$StartAgent,
    [switch]$NoService,
    [switch]$NoStart
)

$ErrorActionPreference = "Stop"

function Test-IsAdministrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Read-PlaintextSecret {
    param([string]$Prompt)

    $secureValue = Read-Host $Prompt -AsSecureString
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureValue)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
}

$PackageRoot = Resolve-Path $PSScriptRoot
$AgentExeSource = Join-Path $PackageRoot "outpost-agent.exe"
$InstallerExeSource = Join-Path $PackageRoot "outpost-agent-install.exe"
$ServiceExeSource = Join-Path $PackageRoot "outpost-agent-service.exe"
$ServiceName = "OutpostAgent"

if (-not (Test-Path $AgentExeSource)) {
    throw "Missing package file: $AgentExeSource"
}

if (-not (Test-Path $InstallerExeSource)) {
    throw "Missing package file: $InstallerExeSource"
}

$ShouldInstallService = (Test-IsAdministrator) -and (-not $NoService)
if ($ShouldInstallService -and -not (Test-Path $ServiceExeSource)) {
    throw "Missing package file: $ServiceExeSource"
}

if ([string]::IsNullOrWhiteSpace($InstallDir)) {
    if (Test-IsAdministrator) {
        $InstallDir = Join-Path $env:ProgramFiles "OUTPOST\Agent"
    }
    else {
        $InstallDir = Join-Path $env:LOCALAPPDATA "OUTPOST\Agent"
    }
}

if ([string]::IsNullOrWhiteSpace($OrgCode)) {
    $OrgCode = Read-Host "ORGANISATIONAL CODE"
}

if ([string]::IsNullOrWhiteSpace($OrgCode)) {
    throw "ORGANISATIONAL CODE is required."
}

if ([string]::IsNullOrWhiteSpace($Passcode) -and -not [string]::IsNullOrWhiteSpace($ApiKey)) {
    $Passcode = $ApiKey
}

if ([string]::IsNullOrWhiteSpace($Passcode)) {
    $Passcode = Read-PlaintextSecret "PASSCODE (API)"
}

if ($ShouldInstallService) {
    $existingService = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
    if ($existingService -and $existingService.Status -ne "Stopped") {
        Write-Host "Stopping existing OUTPOST Agent service..."
        Stop-Service -Name $ServiceName -Force
        $existingService.WaitForStatus("Stopped", "00:00:30")
    }
}

New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null

$AgentExe = Join-Path $InstallDir "outpost-agent.exe"
$InstallerExe = Join-Path $InstallDir "outpost-agent-install.exe"
$ServiceExe = Join-Path $InstallDir "outpost-agent-service.exe"
$UninstallScript = Join-Path $InstallDir "uninstall-outpost-agent.ps1"

Copy-Item -Path $AgentExeSource -Destination $AgentExe -Force
Copy-Item -Path $InstallerExeSource -Destination $InstallerExe -Force
if (Test-Path $ServiceExeSource) {
    Copy-Item -Path $ServiceExeSource -Destination $ServiceExe -Force
}
Copy-Item -Path (Join-Path $PackageRoot "uninstall-outpost-agent.ps1") -Destination $UninstallScript -Force

$installArgs = @(
    "--backend", $BackendUrl,
    "--org-code", $OrgCode,
    "--poll-interval", "$PollInterval"
)

if (-not [string]::IsNullOrWhiteSpace($Passcode)) {
    $env:OUTPOST_AGENT_PASSCODE = $Passcode
}

try {
    Write-Host "Writing OUTPOST agent configuration..."
    & $InstallerExe @installArgs
    if ($LASTEXITCODE -ne 0) {
        throw "OUTPOST agent installer failed with exit code $LASTEXITCODE."
    }
}
finally {
    Remove-Item Env:\OUTPOST_AGENT_API_KEY -ErrorAction SilentlyContinue
    Remove-Item Env:\OUTPOST_AGENT_PASSCODE -ErrorAction SilentlyContinue
}

Write-Host "OUTPOST agent installed to: $InstallDir"
Write-Host "Configuration path: $env:PROGRAMDATA\OUTPOST\agent-config.json"

if ($ShouldInstallService) {
    Write-Host "Installing OUTPOST Agent Windows service..."
    $existingService = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
    if ($existingService) {
        & sc.exe config $ServiceName binPath= "`"$ServiceExe`"" start= auto | Out-Null
    }
    else {
        New-Service `
            -Name $ServiceName `
            -BinaryPathName "`"$ServiceExe`"" `
            -DisplayName "OUTPOST Agent" `
            -StartupType Automatic | Out-Null
    }
    & sc.exe description $ServiceName "Runs the OUTPOST endpoint monitoring and management agent." | Out-Null

    if (-not $NoStart) {
        Write-Host "Starting OUTPOST Agent service..."
        Start-Service -Name $ServiceName
    }
    Write-Host "Service installed: $ServiceName"
}
elseif ($StartAgent) {
    Write-Host "Starting OUTPOST agent in the current terminal..."
    & $AgentExe
}
else {
    Write-Host "Service was not installed because this PowerShell session is not elevated or -NoService was passed."
    Write-Host "Start it manually with: $AgentExe"
}
