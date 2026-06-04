# OUTPOST Windows Agent Setup

This guide is for a first-time user or client installing the OUTPOST agent on a clean Windows computer. It assumes the client has just visited the OUTPOST business/client site and is ready to connect their device to the OUTPOST dashboard.

## What The Client Needs First

Before starting, the client should have:

- A Windows 10 or Windows 11 computer.
- Internet access.
- Permission to run PowerShell scripts on the device.
- The OUTPOST backend URL, usually:

```text
https://backend-outpost.onrender.com
```

- The organization’s `ORGANISATIONAL CODE`.
- The organization’s `PASSCODE`.

The `PASSCODE` is sensitive. It should be shared only with trusted installers or deployment tooling.

## Recommended First-Time Flow

Use this flow when the user has downloaded the Windows installer package from the OUTPOST site or GitHub release page.

### Step 1: Download The Windows Installer

From the OUTPOST business/client site:

1. Open the OUTPOST download page.
2. Click **Download Windows agent**.
3. Save the file to the computer.

The downloaded package is usually named:

```text
outpost-agent-installer-windows-x64.zip
```

### Step 2: Extract The Installer Package

1. Right-click the downloaded `.zip` file.
2. Select **Extract All**.
3. Choose a simple folder such as:

```text
C:\Users\<your-user>\Downloads\outpost-agent-installer-windows-x64
```

4. Open the extracted folder.

You should see files like:

```text
outpost-agent.exe
outpost-agent-install.exe
outpost-agent-service.exe
install-agent-package.ps1
uninstall-outpost-agent.ps1
SHA256SUMS.txt
release-manifest.json
```

### Step 3: Open PowerShell In The Folder

In the extracted folder:

1. Hold `Shift`.
2. Right-click inside the folder.
3. Select **Open PowerShell window here** or **Open in Terminal**.

If Windows opens Command Prompt instead, search for **PowerShell** in the Start Menu, open it, then change into the extracted folder:

```powershell
cd "$env:USERPROFILE\Downloads\outpost-agent-installer-windows-x64"
```

### Step 4: Run The Interactive Installer

Run:

```powershell
powershell -ExecutionPolicy Bypass -File .\install-agent-package.ps1
```

The installer asks for:

```text
ORGANISATIONAL CODE:
PASSCODE (API):
```

Enter the values exactly as provided by the OUTPOST administrator.

The passcode is hidden while typing. This is normal.

### Step 5: Silent Install Option

For IT staff or repeat installs, run:

```powershell
powershell -ExecutionPolicy Bypass -File .\install-agent-package.ps1 `
  -BackendUrl "https://backend-outpost.onrender.com" `
  -OrgCode "DEMO-ORG" `
  -Passcode "YOUR-PASSCODE" `
  -PollInterval 30
```

Replace:

- `DEMO-ORG` with the real organisational code.
- `YOUR-PASSCODE` with the real passcode.
- `https://backend-outpost.onrender.com` with the customer backend URL if different.

### Step 6: Confirm The Install Location

The installer writes the local configuration to:

```text
C:\ProgramData\OUTPOST\agent-config.json
```

The passcode is stored as:

```text
api_key_protected
```

It should not be stored as plaintext `api_key`.

### Step 7: Confirm The Service Is Running

Run the installer from an elevated PowerShell session to install the persistent Windows service. The installer starts the service automatically.

Check it with:

```powershell
Get-Service OutpostAgent
```

The service should show `Running`. The agent should keep running after the terminal closes and restart automatically after reboot.

If PowerShell was not elevated, the installer writes configuration and installed files only. In that case, start the agent manually for testing:

```powershell
.\outpost-agent.exe
```

### Step 8: Verify In The OUTPOST Dashboard

Ask the dashboard administrator to check:

1. The device appears in the device inventory.
2. The hostname matches the Windows computer.
3. The device status changes to online.
4. Inventory and health fields start filling in.
5. The last-seen timestamp updates.

If the device appears, first-time setup is complete.

## Alternate Flow: Install From GitHub Script

Use this only if the client has not downloaded the release package and the repository is publicly reachable.

Open PowerShell and run:

```powershell
$Installer = "$env:TEMP\install-outpost-agent-release.ps1"
Invoke-WebRequest `
  -Uri "https://raw.githubusercontent.com/YOUR_GITHUB_ORG/OUTPOST/main/agent-op/scripts/install-agent-release.ps1" `
  -OutFile $Installer

powershell -ExecutionPolicy Bypass -File $Installer `
  -Repo "YOUR_GITHUB_ORG/OUTPOST" `
  -BackendUrl "https://backend-outpost.onrender.com" `
  -OrgCode "DEMO-ORG" `
  -Passcode "YOUR-PASSCODE"
```

Replace `YOUR_GITHUB_ORG/OUTPOST`, `DEMO-ORG`, and `YOUR-PASSCODE` before sending this to a client.

## What Data The Windows Agent Collects

The Windows agent reports:

- hostname
- operating system name
- hardware fingerprint components
- serial number when available
- CPU, disk, and memory summary
- Python/runtime version
- heartbeat status
- health posture
- registry intelligence snapshots
- approved remote task results

The agent does not run unrestricted shell commands. Remote tasks must match the local allowlist.

## Troubleshooting

### The Service Was Not Installed

Open PowerShell as Administrator and re-run:

```powershell
powershell -ExecutionPolicy Bypass -File .\install-agent-package.ps1
```

To intentionally install without a service, pass `-NoService`.

### Check The Service

```powershell
Get-Service OutpostAgent
```

Restart the service:

```powershell
Restart-Service OutpostAgent
```

### PowerShell Blocks The Script

Run the script with:

```powershell
powershell -ExecutionPolicy Bypass -File .\install-agent-package.ps1
```

### The Agent Says Config Is Missing

Run the installer first:

```powershell
powershell -ExecutionPolicy Bypass -File .\install-agent-package.ps1
```

Then start:

```powershell
Start-Service OutpostAgent
```

### Device Does Not Appear In Dashboard

Check:

- The backend URL is correct.
- The `ORGANISATIONAL CODE` is correct.
- The `PASSCODE` matches the backend `OUTPOST_API_KEY`.
- The Windows device has internet access.
- The backend is online at `/healthz`.

### Registration Keeps Failing

Try a clean reinstall:

```powershell
powershell -ExecutionPolicy Bypass -File .\uninstall-outpost-agent.ps1 -RemoveConfig
powershell -ExecutionPolicy Bypass -File .\install-agent-package.ps1
```

## Uninstall

Remove installed files:

```powershell
powershell -ExecutionPolicy Bypass -File .\uninstall-outpost-agent.ps1
```

Remove installed files and local configuration:

```powershell
powershell -ExecutionPolicy Bypass -File .\uninstall-outpost-agent.ps1 -RemoveConfig
```

## Client Handoff Checklist

Before leaving the client site, confirm:

- The agent starts successfully.
- `OutpostAgent` is installed and running when setup was run as Administrator.
- The device appears in the dashboard.
- Last seen updates within the expected polling interval.
- Inventory and health data are visible.
- The passcode was not saved in notes, screenshots, or chat messages.
- The installer package is stored or removed according to the client’s policy.
