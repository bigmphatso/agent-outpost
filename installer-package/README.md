# OUTPOST Agent Installer Package

This folder is included in the Windows release package.

## Files

- `outpost-agent.exe` - runs the endpoint agent.
- `outpost-agent-install.exe` - writes and hardens local configuration.
- `install-agent-package.ps1` - installs the bundled executables on this machine.
- `uninstall-outpost-agent.ps1` - removes installed agent files.
- `SHA256SUMS.txt` - checksums for release verification.
- `release-manifest.json` - release metadata.

## Install

Open PowerShell in the extracted package folder:

```powershell
powershell -ExecutionPolicy Bypass -File .\install-agent-package.ps1 `
  -BackendUrl "https://outpost-listener.vercel.app" `
  -OrgCode "DEMO-ORG"
```

If your backend still requires the legacy API key, pass it with `-ApiKey` or enter it when prompted.

```powershell
powershell -ExecutionPolicy Bypass -File .\install-agent-package.ps1 `
  -BackendUrl "https://outpost-listener.vercel.app" `
  -OrgCode "DEMO-ORG" `
  -ApiKey "YOUR-BACKEND-API-KEY"
```

## Silent Install

```powershell
powershell -ExecutionPolicy Bypass -File .\install-agent-package.ps1 `
  -BackendUrl "https://outpost-listener.vercel.app" `
  -OrgCode "DEMO-ORG" `
  -PollInterval 30
```


The installer writes config to:

```text
C:\ProgramData\OUTPOST\agent-config.json
```

## Uninstall

```powershell
powershell -ExecutionPolicy Bypass -File .\uninstall-outpost-agent.ps1
```

Remove installed files and local config:

```powershell
powershell -ExecutionPolicy Bypass -File .\uninstall-outpost-agent.ps1 -RemoveConfig
```
