param(
    [string]$BackendUrl = "https://backend-outpost.onrender.com",
    [string]$OrgCode = "",
    [string]$Passcode = "",
    [string]$ApiKey = "",
    [int]$PollInterval = 30
)

$ErrorActionPreference = "Stop"
$AgentRoot = Resolve-Path (Join-Path $PSScriptRoot "..")

Push-Location $AgentRoot
try {
    python -m pip install -e .

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

    if (-not [string]::IsNullOrWhiteSpace($Passcode)) {
        $env:OUTPOST_AGENT_PASSCODE = $Passcode
    }

    outpost-agent-install --backend $BackendUrl --org-code $OrgCode --poll-interval $PollInterval
    Write-Host "OUTPOST agent installed. Start it with: outpost-agent"
}
finally {
    Remove-Item Env:\OUTPOST_AGENT_PASSCODE -ErrorAction SilentlyContinue
    Remove-Item Env:\OUTPOST_AGENT_API_KEY -ErrorAction SilentlyContinue
    Pop-Location
}
