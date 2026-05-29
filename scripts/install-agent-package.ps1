param(
    [string]$BackendUrl = "https://outpost-listener.vercel.app",
    [string]$OrgCode = "",
    [string]$ApiKey = "",
    [int]$PollInterval = 30,
    [string]$InstallDir = "",
    [switch]$StartAgent
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

if (-not (Test-Path $AgentExeSource)) {
    throw "Missing package file: $AgentExeSource"
}

if (-not (Test-Path $InstallerExeSource)) {
    throw "Missing package file: $InstallerExeSource"
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
    $OrgCode = Read-Host "ORG CODE"
}

if ([string]::IsNullOrWhiteSpace($OrgCode)) {
    throw "ORG CODE is required."
}

if ([string]::IsNullOrWhiteSpace($ApiKey)) {
    $ApiKey = Read-PlaintextSecret "API KEY (leave blank if backend does not require one)"
}

New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null

$AgentExe = Join-Path $InstallDir "outpost-agent.exe"
$InstallerExe = Join-Path $InstallDir "outpost-agent-install.exe"
$UninstallScript = Join-Path $InstallDir "uninstall-outpost-agent.ps1"

Copy-Item -Path $AgentExeSource -Destination $AgentExe -Force
Copy-Item -Path $InstallerExeSource -Destination $InstallerExe -Force
Copy-Item -Path (Join-Path $PackageRoot "uninstall-outpost-agent.ps1") -Destination $UninstallScript -Force

$installArgs = @(
    "--backend", $BackendUrl,
    "--org-code", $OrgCode,
    "--poll-interval", "$PollInterval"
)

if (-not [string]::IsNullOrWhiteSpace($ApiKey)) {
    $env:OUTPOST_AGENT_API_KEY = $ApiKey
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
}

Write-Host "OUTPOST agent installed to: $InstallDir"
Write-Host "Configuration path: $env:PROGRAMDATA\OUTPOST\agent-config.json"

if ($StartAgent) {
    Write-Host "Starting OUTPOST agent..."
    & $AgentExe
}
else {
    Write-Host "Start it with: $AgentExe"
}
