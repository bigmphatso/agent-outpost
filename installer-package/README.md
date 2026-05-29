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
  -OrgCode "DEMO-ORG" `
  -Passcode "YOUR-PASSCODE"
```

The installer prompts for the Organisational Code and PASSCODE if either value is omitted. `-ApiKey` is still accepted as a legacy alias for `-Passcode`.

The PASSCODE is the same backend API key value. It is masked as PASSCODE in the installer UX and stored through the existing protected API key path.

Interactive install:

```powershell
powershell -ExecutionPolicy Bypass -File .\install-agent-package.ps1
```

Prompts:

```text
ORGANISATIONAL CODE:
PASSCODE (API):
```

```powershell
powershell -ExecutionPolicy Bypass -File .\install-agent-package.ps1 `
  -BackendUrl "https://outpost-listener.vercel.app" `
  -OrgCode "DEMO-ORG" `
  -Passcode "YOUR-PASSCODE"
```

## Silent Install

```powershell
powershell -ExecutionPolicy Bypass -File .\install-agent-package.ps1 `
  -BackendUrl "https://outpost-listener.vercel.app" `
  -OrgCode "DEMO-ORG" `
  -Passcode "YOUR-PASSCODE" `
  -PollInterval 30
```


The installer writes config to:

```text
C:\ProgramData\OUTPOST\agent-config.json
```

After installation, start the agent:

```powershell
.\outpost-agent.exe
```

If the agent cannot register, verify the Organisational Code, PASSCODE/API key, backend URL, and network connection.

## Uninstall

```powershell
powershell -ExecutionPolicy Bypass -File .\uninstall-outpost-agent.ps1
```

Remove installed files and local config:

```powershell
powershell -ExecutionPolicy Bypass -File .\uninstall-outpost-agent.ps1 -RemoveConfig
```
