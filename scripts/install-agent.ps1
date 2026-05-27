param(
    [string]$BackendUrl = "https://outpost-listener.vercel.app",
    [string]$OrgCode = "",
    [string]$ApiKey = "",
    [int]$PollInterval = 30
)

$ErrorActionPreference = "Stop"
$AgentRoot = Resolve-Path (Join-Path $PSScriptRoot "..")

Push-Location $AgentRoot
try {
    python -m pip install -e .

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

    if (-not [string]::IsNullOrWhiteSpace($ApiKey)) {
        $env:OUTPOST_AGENT_API_KEY = $ApiKey
    }

    outpost-agent-install --backend $BackendUrl --org-code $OrgCode --poll-interval $PollInterval
    Write-Host "OUTPOST agent installed. Start it with: outpost-agent"
}
finally {
    Remove-Item Env:\OUTPOST_AGENT_API_KEY -ErrorAction SilentlyContinue
    Pop-Location
}
