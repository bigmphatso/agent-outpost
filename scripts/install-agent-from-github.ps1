param(
    [string]$BackendUrl = "https://backend-outpost.onrender.com",
    [string]$OrgCode = "",
    [string]$Passcode = "",
    [string]$ApiKey = "",
    [int]$PollInterval = 30,
    [string]$RepoZipUrl = "https://github.com/bigmphatso/agent-outpost/archive/refs/heads/master.zip",
    [switch]$StartAgent
)

$ErrorActionPreference = "Stop"

function Find-Python {
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
        return $python.Source
    }

    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) {
        return $py.Source
    }

    throw "Python 3.11+ is required before installing the OUTPOST agent."
}

function Invoke-Python {
    param(
        [string]$PythonCommand,
        [string[]]$Arguments
    )

    if ((Split-Path -Leaf $PythonCommand) -ieq "py.exe") {
        & $PythonCommand -3 @Arguments
    }
    else {
        & $PythonCommand @Arguments
    }

    if ($LASTEXITCODE -ne 0) {
        throw "Python command failed with exit code $LASTEXITCODE."
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
    $SecurePasscode = Read-Host "PASSCODE (API)" -AsSecureString
    $BSTR = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecurePasscode)
    try {
        $Passcode = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($BSTR)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($BSTR)
    }
}

$pythonCommand = Find-Python
$workRoot = Join-Path $env:TEMP ("outpost-agent-install-" + [guid]::NewGuid().ToString("N"))
$zipPath = Join-Path $workRoot "outpost.zip"
$extractPath = Join-Path $workRoot "source"

New-Item -ItemType Directory -Path $workRoot, $extractPath -Force | Out-Null

try {
    Write-Host "Downloading OUTPOST agent package..."
    try {
        Invoke-WebRequest -Uri $RepoZipUrl -OutFile $zipPath
    }
    catch {
        throw "Failed to download OUTPOST agent ZIP from $RepoZipUrl. If this is a private repository, download the installer package instead or provide an authenticated/internal ZIP URL."
    }

    Write-Host "Extracting package..."
    Expand-Archive -Path $zipPath -DestinationPath $extractPath -Force

    $agentProject = Get-ChildItem -Path $extractPath -Recurse -Filter pyproject.toml |
        Where-Object { Test-Path (Join-Path $_.DirectoryName "outpost_agent") } |
        Select-Object -First 1

    if (-not $agentProject) {
        throw "Could not find an OUTPOST agent Python package in the downloaded package."
    }

    $agentRoot = Split-Path -Parent $agentProject.FullName

    Write-Host "Installing OUTPOST agent..."
    Invoke-Python -PythonCommand $pythonCommand -Arguments @("-m", "pip", "install", $agentRoot)

    $installArgs = @(
        "-m", "outpost_agent.installer",
        "--backend", $BackendUrl,
        "--org-code", $OrgCode,
        "--poll-interval", "$PollInterval"
    )

    if (-not [string]::IsNullOrWhiteSpace($Passcode)) {
        $env:OUTPOST_AGENT_PASSCODE = $Passcode
    }

    Write-Host "Writing OUTPOST agent configuration..."
    Invoke-Python -PythonCommand $pythonCommand -Arguments $installArgs

    Write-Host "OUTPOST agent installed."
    if ($StartAgent) {
        Write-Host "Starting OUTPOST agent..."
        Invoke-Python -PythonCommand $pythonCommand -Arguments @("-m", "outpost_agent.main")
    }
    else {
        Write-Host "Start it with: python -m outpost_agent.main"
    }
}
finally {
    Remove-Item Env:\OUTPOST_AGENT_PASSCODE -ErrorAction SilentlyContinue
    Remove-Item Env:\OUTPOST_AGENT_API_KEY -ErrorAction SilentlyContinue
    if (Test-Path $workRoot) {
        Remove-Item -LiteralPath $workRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}
