# OUTPOST Linux Agent Setup

This guide is for a first-time user or client installing the OUTPOST agent on a clean Linux machine. It assumes the client has just visited the OUTPOST business/client site and needs clear setup steps from download to dashboard verification.

## What The Client Needs First

Before starting, the client should have:

- A Linux machine with internet access.
- A user account with `sudo` access for service installation.
- Python 3 installed.
- `curl` or `wget` installed for download-based setup.
- `unzip` installed if using the GitHub ZIP bootstrap installer.
- The OUTPOST backend URL, usually:

```text
https://outpost-listener.vercel.app
```

- The organization’s `ORGANISATIONAL CODE`.
- The organization’s `PASSCODE`.

The `PASSCODE` is sensitive. It should not be written in public tickets, screenshots, or shared chat messages.

## Recommended First-Time Flow

Use this flow when the user has downloaded the Linux installer from the OUTPOST business/client site.

### Step 1: Download The Linux Installer

From the OUTPOST business/client site:

1. Open the OUTPOST download page.
2. Click **Download Linux agent**.
3. Save the installer script.

The downloaded file is usually:

```text
install-outpost-agent.sh
```

### Step 2: Open A Terminal

Open a terminal and move to the download folder:

```bash
cd ~/Downloads
```

Confirm the file exists:

```bash
ls -l install-outpost-agent.sh
```

### Step 3: Make The Script Executable

Run:

```bash
chmod +x install-outpost-agent.sh
```

### Step 4: Install As A System Service

For a client device, the recommended install is a `systemd` service. This lets the agent start automatically after reboot.

Run:

```bash
sudo ./install-outpost-agent.sh \
  --backend-url "https://outpost-listener.vercel.app" \
  --org-code "DEMO-ORG" \
  --install-service \
  --start-agent
```

Replace:

- `DEMO-ORG` with the real organisational code.
- `https://outpost-listener.vercel.app` with the customer backend URL if different.

If the passcode is not provided on the command line, the installer prompts:

```text
PASSCODE (API):
```

Typing is hidden. This is normal.

If the backend does not require a passcode/API key, add:

```bash
--no-passcode
```

### Step 5: Silent Install Option

For IT staff or repeat installs, pass all values:

```bash
sudo ./install-outpost-agent.sh \
  --backend-url "https://outpost-listener.vercel.app" \
  --org-code "DEMO-ORG" \
  --passcode "OUTPOST_API_KEY@2000" \
  --poll-interval 30 \
  --install-service \
  --start-agent
```

Use this only in secure deployment tooling. Do not leave the passcode in shell history on shared machines.

### Step 6: Confirm The Service Is Running

Run:

```bash
systemctl status outpost-agent.service
```

If it is running, you should see:

```text
active (running)
```

View recent logs:

```bash
journalctl -u outpost-agent.service -n 50 --no-pager
```

### Step 7: Confirm The Install Location

For systemd installs, the agent stores configuration and local state in:

```text
/var/lib/outpost/
```

Expected files:

```text
/var/lib/outpost/agent-config.json
/var/lib/outpost/agent-state.sqlite3
```

The service runs as the dedicated Linux user:

```text
outpost
```

The service runtime is installed into a dedicated virtual environment:

```text
/opt/outpost-agent/venv
```

### Step 8: Verify In The OUTPOST Dashboard

Ask the dashboard administrator to check:

1. The Linux device appears in device inventory.
2. The hostname matches the Linux machine.
3. The operating system/distro is visible.
4. The device status changes to online.
5. Inventory and health fields start filling in.
6. Last-seen updates after the polling interval.

If the device appears, first-time setup is complete.

## Developer Or Foreground Install

Use this when testing locally or when the agent should run only while the terminal is open.

From the repository:

```bash
cd agent-op
./scripts/install-agent.sh \
  --backend-url "http://127.0.0.1:8000" \
  --org-code "DEMO-ORG"
```

Then start:

```bash
outpost-agent
```

Foreground config path:

```text
~/.outpost/agent-config.json
```

Foreground local queue path:

```text
~/.outpost/agent-state.sqlite3
```

## GitHub Bootstrap Flow

Use this if the client has not downloaded the installer and the repository is reachable.

```bash
curl -fsSL \
  "https://raw.githubusercontent.com/bigmphatso/agent-outpost/master/scripts/install-agent-from-github.sh" \
  -o /tmp/install-outpost-agent.sh

sudo bash /tmp/install-outpost-agent.sh \
  --backend-url "https://outpost-listener.vercel.app" \
  --org-code "DEMO-ORG" \
  --passcode "YOUR-PASSCODE" \
  --install-service \
  --start-agent
```

Replace `DEMO-ORG` and `YOUR-PASSCODE` before sending this to a client. The script defaults to the public `bigmphatso/agent-outpost` ZIP. Use `--repo-zip-url` only when installing from a different repository or an internal mirror.

## Install Prerequisites By Distribution

Debian/Ubuntu/Kali:

```bash
sudo apt update
sudo apt install -y python3 python3-pip curl unzip
```

Fedora:

```bash
sudo dnf install -y python3 python3-pip curl unzip
```

RHEL/CentOS:

```bash
sudo yum install -y python3 python3-pip curl unzip
```

Arch:

```bash
sudo pacman -Sy python python-pip curl unzip
```

Alpine:

```bash
sudo apk add python3 py3-pip curl unzip
```

## What Data The Linux Agent Collects

The Linux agent reports:

- hostname
- Linux distribution and kernel
- SMBIOS serial values when available
- hashed machine and hardware fingerprint components
- CPU, disk, and memory summary
- capped package/software inventory
- pending package update count for common package managers
- ClamAV presence/status when available
- suspicious process count for executables running from temporary directories
- removable storage and startup/systemd/cron snapshots
- approved remote task results

The agent does not run unrestricted shell commands. Remote tasks must match the local allowlist.

## Troubleshooting

### Script Says `python3 is required`

Install Python 3 using the command for your distribution, then rerun the installer.

### Script Says `--install-service requires root`

Use `sudo`:

```bash
sudo ./install-outpost-agent.sh --install-service --start-agent
```

### Service Is Not Running

Check status:

```bash
systemctl status outpost-agent.service
```

Restart:

```bash
sudo systemctl restart outpost-agent.service
```

Read logs:

```bash
journalctl -u outpost-agent.service -n 100 --no-pager
```

### `ModuleNotFoundError: No module named 'outpost_agent'`

This usually means an older GitHub bootstrap install used editable mode from a temporary folder, then deleted that folder after installation.

Repair from the local repository:

```bash
cd /home/hunter/Documents/reign/OUTPOST-SRC/agent-op
python3 -m pip uninstall -y outpost-agent
./scripts/install-agent.sh \
  --backend-url "https://outpost-listener.vercel.app" \
  --org-code "DEMO-ORG" \
  --package-install
```

For a boot-time service, run the repair with `sudo` and service flags:

```bash
cd /home/hunter/Documents/reign/OUTPOST-SRC/agent-op
sudo python3 -m pip uninstall -y outpost-agent
sudo ./scripts/install-agent.sh \
  --backend-url "https://outpost-listener.vercel.app" \
  --org-code "DEMO-ORG" \
  --package-install \
  --no-passcode \
  --install-service \
  --start-agent
```

### Device Does Not Appear In Dashboard

Check:

- The backend URL is correct.
- The `ORGANISATIONAL CODE` is correct.
- The `PASSCODE` matches the backend `OUTPOST_API_KEY`.
- The Linux device has internet access.
- The backend is online at `/healthz`.
- The service can read `/var/lib/outpost/agent-config.json`.

### Check Backend Connectivity

Run:

```bash
curl -fsSL https://outpost-listener.vercel.app/healthz
```

Expected response:

```json
{"status":"ok"}
```

### Check Config Permissions

Run:

```bash
sudo ls -la /var/lib/outpost
```

The config should be owned by the `outpost` service user and should not be world-readable.

## Stop Or Remove The Linux Service

Stop:

```bash
sudo systemctl stop outpost-agent.service
```

Disable startup:

```bash
sudo systemctl disable outpost-agent.service
```

Remove the service file:

```bash
sudo rm -f /etc/systemd/system/outpost-agent.service
sudo systemctl daemon-reload
```

Remove local state only if the client wants a clean reinstall:

```bash
sudo rm -rf /var/lib/outpost
```

## Client Handoff Checklist

Before leaving the client site, confirm:

- `outpost-agent.service` is active.
- The device appears in the dashboard.
- Last seen updates within the expected polling interval.
- Inventory and health data are visible.
- The passcode was not saved in visible shell history, screenshots, or notes.
- The client knows who to contact if the device goes offline.
