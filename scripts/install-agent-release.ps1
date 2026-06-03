param(
    [string]$BackendUrl = "https://outpost-listener.vercel.app",
    [string]$OrgCode = "",
    [string]$Passcode = "",
    [string]$ApiKey = "",
    [int]$PollInterval = 30,
    [string]$Repo = "YOUR_GITHUB_ORG/OUTPOST",
    [string]$Version = "latest",
    [string]$InstallDir = "",
    [switch]$StartAgent,
    [switch]$NoService,
    [switch]$NoStart
)

$ErrorActionPreference = "Stop"
$ServiceName = "OutpostAgent"

function Test-IsAdministrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
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
    $SecurePasscode = Read-Host "PASSCODE (API)" -AsSecureString
    $BSTR = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecurePasscode)
    try {
        $Passcode = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($BSTR)
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

if ([string]::IsNullOrWhiteSpace($InstallDir)) {
    if (Test-IsAdministrator) {
        $InstallDir = Join-Path $env:ProgramFiles "OUTPOST\Agent"
    }
    else {
        $InstallDir = Join-Path $env:LOCALAPPDATA "OUTPOST\Agent"
    }
}

$ShouldInstallService = (Test-IsAdministrator) -and (-not $NoService)
if ($ShouldInstallService) {
    $existingService = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
    if ($existingService -and $existingService.Status -ne "Stopped") {
        Write-Host "Stopping existing OUTPOST Agent service..."
        Stop-Service -Name $ServiceName -Force
        $existingService.WaitForStatus("Stopped", "00:00:30")
    }
}

New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null

$agentExe = Join-Path $InstallDir "outpost-agent.exe"
$installerExe = Join-Path $InstallDir "outpost-agent-install.exe"
$serviceExe = Join-Path $InstallDir "outpost-agent-service.exe"

Write-Host "Downloading OUTPOST agent release assets..."
Invoke-WebRequest -Uri "$releaseBaseUrl/outpost-agent.exe" -OutFile $agentExe
Invoke-WebRequest -Uri "$releaseBaseUrl/outpost-agent-install.exe" -OutFile $installerExe
if ($ShouldInstallService) {
    Invoke-WebRequest -Uri "$releaseBaseUrl/outpost-agent-service.exe" -OutFile $serviceExe
}

$installArgs = @(
    "--backend", $BackendUrl,
    "--org-code", $OrgCode,
    "--poll-interval", "$PollInterval"
)

if (-not [string]::IsNullOrWhiteSpace($Passcode)) {
    $env:OUTPOST_AGENT_PASSCODE = $Passcode
}

Write-Host "Writing OUTPOST agent configuration..."
& $installerExe @installArgs
$exitCode = $LASTEXITCODE
Remove-Item Env:\OUTPOST_AGENT_API_KEY -ErrorAction SilentlyContinue
Remove-Item Env:\OUTPOST_AGENT_PASSCODE -ErrorAction SilentlyContinue
if ($exitCode -ne 0) {
    throw "OUTPOST agent installer failed with exit code $exitCode."
}

Write-Host "OUTPOST agent installed to: $InstallDir"
if ($ShouldInstallService) {
    Write-Host "Installing OUTPOST Agent Windows service..."
    $existingService = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
    if ($existingService) {
        & sc.exe config $ServiceName binPath= "`"$serviceExe`"" start= auto | Out-Null
    }
    else {
        New-Service `
            -Name $ServiceName `
            -BinaryPathName "`"$serviceExe`"" `
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
    & $agentExe
}
else {
    Write-Host "Service was not installed because this PowerShell session is not elevated or -NoService was passed."
    Write-Host "Start it manually with: $agentExe"
}
