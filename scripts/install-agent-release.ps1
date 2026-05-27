param(
    [string]$BackendUrl = "https://outpost-listener.vercel.app",
    [string]$OrgCode = "",
    [string]$ApiKey = "",
    [int]$PollInterval = 30,
    [string]$Repo = "YOUR_GITHUB_ORG/OUTPOST",
    [string]$Version = "latest",
    [string]$InstallDir = "$env:LOCALAPPDATA\OUTPOST\Agent",
    [switch]$StartAgent
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($OrgCode)) {
    $OrgCode = Read-Host "ORG CODE"
}

if ([string]::IsNullOrWhiteSpace($OrgCode)) {
    throw "ORG CODE is required."
}

if ([string]::IsNullOrWhiteSpace($ApiKey)) {
    $SecureApiKey = Read-Host "API KEY (leave blank if backend does not require one)" -AsSecureString
    $BSTR = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureApiKey)
    try {
        $ApiKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($BSTR)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($BSTR)
    }
}

if ($Version -eq "latest") {
    $releaseBaseUrl = "https://github.com/$Repo/releases/latest/download"
}
else {
    $releaseBaseUrl = "https://github.com/$Repo/releases/download/$Version"
}

New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null

$agentExe = Join-Path $InstallDir "outpost-agent.exe"
$installerExe = Join-Path $InstallDir "outpost-agent-install.exe"

Write-Host "Downloading OUTPOST agent release assets..."
Invoke-WebRequest -Uri "$releaseBaseUrl/outpost-agent.exe" -OutFile $agentExe
Invoke-WebRequest -Uri "$releaseBaseUrl/outpost-agent-install.exe" -OutFile $installerExe

$installArgs = @(
    "--backend", $BackendUrl,
    "--org-code", $OrgCode,
    "--poll-interval", "$PollInterval"
)

if (-not [string]::IsNullOrWhiteSpace($ApiKey)) {
    $env:OUTPOST_AGENT_API_KEY = $ApiKey
}

Write-Host "Writing OUTPOST agent configuration..."
& $installerExe @installArgs
$exitCode = $LASTEXITCODE
Remove-Item Env:\OUTPOST_AGENT_API_KEY -ErrorAction SilentlyContinue
if ($exitCode -ne 0) {
    throw "OUTPOST agent installer failed with exit code $exitCode."
}

Write-Host "OUTPOST agent installed to: $InstallDir"
if ($StartAgent) {
    Write-Host "Starting OUTPOST agent..."
    & $agentExe
}
else {
    Write-Host "Start it with: $agentExe"
}
