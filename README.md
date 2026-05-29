# OUTPOST Agent

The agent is the lightweight endpoint component installed on every organizational device. It registers the device with the backend, reports inventory and health data, sends heartbeat updates, and polls for approved remote management tasks.

## Responsibilities

- Install with an Organisational Code and PASSCODE.
- Register the endpoint with the central backend.
- Collect hardware, operating system, disk, and basic software inventory.
- Send regular heartbeat updates so the dashboard can show online/offline state.
- Report health posture used for monitoring and alerting.
- Poll for remote management tasks and execute only allowlisted commands.
- Store outbound data locally in SQLite so offline devices can buffer updates and retry automatically.

## Folder Structure

- `outpost_agent/main.py` - runtime entrypoint for the installed agent.
- `outpost_agent/installer.py` - installation/configuration entrypoint that prompts for Organisational Code and PASSCODE.
- `outpost_agent/config.py` - local config storage and loading.
- `outpost_agent/client.py` - HTTP client for backend communication.
- `outpost_agent/local_store.py` - local SQLite outbox for offline buffering and retry.
- `outpost_agent/phase1_device_visibility/` - registration and inventory collectors.
- `outpost_agent/phase2_monitoring_alerts/` - endpoint health checks + reports.
- `outpost_agent/phase3_remote_management/` - remote task polling + allowlisted execution.
- `scripts/install-agent.ps1` - Windows-friendly setup script.
- `scripts/install-agent-from-github.ps1` - Windows bootstrap installer for devices that download the agent from GitHub.
- `scripts/install-agent-release.ps1` - Windows bootstrap installer for GitHub Release `.exe` assets.
<<<<<<< HEAD
<<<<<<< HEAD
- `scripts/install-agent-package.ps1` - installs the bundled Windows release package after download.
- `scripts/uninstall-outpost-agent.ps1` - removes installed Windows agent files.
- `installer-package/README.md` - instructions included inside the release installer package.
=======
- `scripts/install-agent.sh` - Linux setup script with optional systemd service installation.
- `scripts/install-agent-from-github.sh` - Linux bootstrap installer for devices that download the agent from GitHub.
>>>>>>> 087d43e537b9ff3fcf6a26325fab9eb127390c65
=======
- `scripts/install-agent.sh` - Linux setup script with optional systemd service installation.
- `scripts/install-agent-from-github.sh` - Linux bootstrap installer for devices that download the agent from GitHub.
>>>>>>> 0f2986f34979991fa2eb8d96581d6ed7d41d3d61
- `pyproject.toml` - installable package metadata and command registration.
- `requirements.txt` - direct runtime dependency list.

## Installation Flow

The setter installs the package and enters the organization code issued by the platform administrator.

```powershell
cd agent
.\scripts\install-agent.ps1
```

The script prompts:

```text
ORGANISATIONAL CODE:
PASSCODE (API):
```

After installation, the config is saved to:

```text
%PROGRAMDATA%\OUTPOST\agent-config.json
```

If the backend requires authentication, the installer prompts for the PASSCODE without echoing it. The saved config stores it as `api_key_protected`, not `api_key`. On Windows, `api_key_protected` is encrypted with DPAPI for the local machine/user context. `-ApiKey` remains available as a legacy alias for `-Passcode`.

The installer also hardens the config directory and file permissions. On Windows, the ACL is restricted to `SYSTEM`, `Administrators`, and the installing user. On Linux/macOS, the directory is set to `700` and the file to `600`.

To repair an existing config file:

```powershell
cd agent-op
python -m outpost_agent.installer --harden-config
```

This command also migrates a legacy plaintext `api_key` field into `api_key_protected`.

On non-Windows systems, the fallback path is:

```text
~/.outpost/agent-config.json
```

For Linux systemd installs, the installer creates a locked-down service account and moves the runtime config/state into:

```text
/var/lib/outpost/
```

## Manual Installation

```powershell
cd agent-op
python -m pip install -e .
outpost-agent-install --org-code DEMO-ORG
outpost-agent
```

## Linux Installation

Install the Python package and write the endpoint configuration:

```bash
cd agent-op
./scripts/install-agent.sh \
  --backend-url https://outpost-listener.vercel.app \
  --org-code DEMO-ORG
outpost-agent
```

Install and start the Linux systemd service:

```bash
cd agent-op
sudo ./scripts/install-agent.sh \
  --backend-url https://outpost-listener.vercel.app \
  --org-code DEMO-ORG \
  --install-service \
  --start-agent
```

The service runs as the `outpost` system user by default and stores config/state in `/var/lib/outpost`.

## GitHub Bootstrap Installation

After this repository is published to GitHub, Windows devices can install the agent from a raw GitHub script and repository ZIP archive:

```powershell
$Installer = "$env:TEMP\install-outpost-agent.ps1"
Invoke-WebRequest `
  -Uri "https://raw.githubusercontent.com/YOUR_GITHUB_ORG/OUTPOST/main/agent/scripts/install-agent-from-github.ps1" `
  -OutFile $Installer

powershell -ExecutionPolicy Bypass -File $Installer `
  -BackendUrl "https://outpost-listener.vercel.app" `
  -OrgCode "DEMO-ORG" `
  -Passcode "YOUR-PASSCODE" `
  -RepoZipUrl "https://github.com/YOUR_GITHUB_ORG/OUTPOST/archive/refs/heads/main.zip"
```

Linux devices can use the equivalent shell bootstrapper:

```bash
curl -fsSL \
  https://raw.githubusercontent.com/YOUR_GITHUB_ORG/OUTPOST/main/agent-op/scripts/install-agent-from-github.sh \
  -o /tmp/install-outpost-agent.sh

sudo bash /tmp/install-outpost-agent.sh \
  --backend-url https://outpost-listener.vercel.app \
  --org-code DEMO-ORG \
  --repo-zip-url https://github.com/YOUR_GITHUB_ORG/OUTPOST/archive/refs/heads/main.zip \
  --install-service \
  --start-agent
```

## GitHub Release EXE Installation

Tagged releases build downloadable Windows executables through GitHub Actions:

- `outpost-agent.exe` - runs the endpoint agent.
- `outpost-agent-install.exe` - writes the local agent configuration.
- `outpost-agent-windows-x64.zip` - bundle containing both executables and `SHA256SUMS.txt`.
- `outpost-agent-installer-windows-x64.zip` - user-facing installer package with executables, install/uninstall scripts, checksums, README, and release manifest.

To publish a release, push a version tag:

```powershell
git tag v.1
git push origin v.1
```

The workflow at `.github/workflows/windows-release.yml` builds the executables and attaches them to the GitHub Release for that tag.

Windows devices can install from the latest GitHub Release:

```powershell
$Installer = "$env:TEMP\install-outpost-agent-release.ps1"
Invoke-WebRequest `
  -Uri "https://raw.githubusercontent.com/YOUR_GITHUB_ORG/OUTPOST/main/agent/scripts/install-agent-release.ps1" `
  -OutFile $Installer

powershell -ExecutionPolicy Bypass -File $Installer `
  -Repo "YOUR_GITHUB_ORG/OUTPOST" `
  -BackendUrl "https://outpost-listener.vercel.app" `
  -OrgCode "DEMO-ORG" `
  -Passcode "YOUR-PASSCODE"
```

For a specific release, pass `-Version "v.1"`.

You can also download `outpost-agent-installer-windows-x64.zip` from the release page, extract it, and run:

```powershell
powershell -ExecutionPolicy Bypass -File .\install-agent-package.ps1 `
  -BackendUrl "https://outpost-listener.vercel.app" `
  -OrgCode "DEMO-ORG" `
  -Passcode "YOUR-PASSCODE"
```

To remove the installed files:

```powershell
powershell -ExecutionPolicy Bypass -File .\uninstall-outpost-agent.ps1
```

## Runtime Configuration

The installed config stores:

- `backend_url` - backend API base URL.
- `org_code` - organization code used during device registration.
- `agent_version` - local agent version.
- `poll_interval_seconds` - heartbeat, health report, and task polling interval.
- `api_key_protected` - encrypted PASSCODE/API value for backend `X-API-Key` authentication when configured.

The runtime can override installed config values:

```powershell
outpost-agent --backend http://server.example:8000 --poll-interval 60
```

If the deployed backend has `OUTPOST_API_KEY` configured, the installed agent must have the same key:

```powershell
outpost-agent-install `
  --backend https://outpost-listener.vercel.app `
  --org-code DEMO-ORG `
  --passcode YOUR-PASSCODE
```

Linux equivalent:

```bash
outpost-agent-install \
  --backend https://outpost-listener.vercel.app \
  --org-code DEMO-ORG \
  --passcode YOUR-PASSCODE
```

Your current config can be checked at:

```text
%PROGRAMDATA%\OUTPOST\agent-config.json
```

If `device_id` is `null`, the agent has not successfully registered yet.

By default, new installs communicate with the deployed BACKEND-OUTPOST listener:

```text
https://outpost-listener.vercel.app
```

## Local SQLite Outbox

The agent does not rely only on memory. Runtime telemetry is written to a local SQLite database before sync attempts.

Default path on Windows:

```text
%PROGRAMDATA%\OUTPOST\agent-state.sqlite3
```

Default path on non-Windows systems:

```text
~/.outpost/agent-state.sqlite3
```

The SQLite outbox stores:

- inventory reports
- heartbeat updates
- health reports
- registry telemetry events
- registry snapshots

On Linux, inventory includes distro/kernel details, SMBIOS serial data when exposed by the host, hashed hardware fingerprint components, memory/disk totals, and a capped package inventory. Health includes pending update counts, ClamAV presence/status when available, signature age, disk free percentage, and a small suspicious-process heuristic for executables running from temporary directories.

When the internet or backend is unavailable, the agent keeps the records locally. On later ticks, it retries the oldest queued records first and deletes each record only after the backend accepts it.

## Backend Communication

The agent currently calls:

- `POST /api/v1/devices/register`
- `POST /api/v1/devices/{device_id}/inventory`
- `POST /api/v1/devices/{device_id}/heartbeat`
- `POST /api/v1/devices/{device_id}/health`
- `GET /api/v1/remote/devices/{device_id}/tasks`
- `POST /api/v1/remote/devices/{device_id}/tasks/{task_id}/result`

## Remote Task Safety

Remote execution is intentionally restricted in `phase3_remote_management/executor.py`.

Only commands matching the local allowlist can run. Anything else is rejected and reported back to the backend. This keeps remote administration useful while avoiding unrestricted remote shell behavior.

## Current Limitations

- Windows service registration is not implemented yet.
- Windows antivirus and update checks are placeholder values.
- Device identity is created fresh on each registration; persistent device identity should be added before production use.

## Next Steps

- Add persistent `device_id` storage after first registration.
- Add Windows service installation.
- Expand Linux systemd hardening and package-manager coverage.
- Replace remaining Windows placeholder health checks with OS-specific collectors.
- Add signed agent update support.

# Commit for the release executables
- `
git status
git add .github/workflows/windows-release.yml README.md installer-package/README.md scripts/install-agent-package.ps1 scripts/uninstall-outpost-agent.ps1
git commit -m "Update agent installer release package"
git push origin master
git tag v.1.4
git push origin v.1.4`
