param(
    [string]$BackendUrl = "https://outpost-listener.vercel.app",
    [string]$OrgCode = "",
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

    outpost-agent-install --backend $BackendUrl --org-code $OrgCode --poll-interval $PollInterval
    Write-Host "OUTPOST agent installed. Start it with: outpost-agent"
}
finally {
    Pop-Location
}
