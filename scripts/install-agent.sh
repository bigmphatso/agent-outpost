#!/usr/bin/env bash
set -euo pipefail

BACKEND_URL="https://backend-outpost.onrender.com"
ORG_CODE=""
PASSCODE=""
API_KEY=""
POLL_INTERVAL="30"
CONFIG_PATH=""
INSTALL_SERVICE="0"
START_AGENT="0"
SERVICE_USER="outpost"
PACKAGE_INSTALL="0"
NO_PASSCODE="0"
VENV_PATH=""

usage() {
  cat <<'EOF'
Usage: install-agent.sh [options]

Options:
  --backend-url URL       Backend API URL. Default: https://backend-outpost.onrender.com
  --org-code CODE         Organisational code issued from OUTPOST.
  --passcode PASSCODE     PASSCODE used for authenticated backend calls.
  --api-key KEY           Legacy alias for --passcode.
  --poll-interval SECONDS Agent polling interval. Default: 30
  --config PATH           Optional config path.
  --install-service       Install a systemd service.
  --start-agent           Start the systemd service after installation.
  --service-user USER     User for the service. Default: outpost
  --package-install       Install a normal package instead of editable source.
  --no-passcode           Do not prompt for PASSCODE when backend auth is disabled.
  --venv PATH             Virtualenv path for systemd installs. Default: /opt/outpost-agent/venv
  -h, --help              Show this help.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --backend-url) BACKEND_URL="${2:?}"; shift 2 ;;
    --org-code) ORG_CODE="${2:?}"; shift 2 ;;
    --passcode) PASSCODE="${2:?}"; shift 2 ;;
    --api-key) API_KEY="${2:?}"; shift 2 ;;
    --poll-interval) POLL_INTERVAL="${2:?}"; shift 2 ;;
    --config) CONFIG_PATH="${2:?}"; shift 2 ;;
    --install-service) INSTALL_SERVICE="1"; shift ;;
    --start-agent) START_AGENT="1"; INSTALL_SERVICE="1"; shift ;;
    --service-user) SERVICE_USER="${2:?}"; shift 2 ;;
    --package-install) PACKAGE_INSTALL="1"; shift ;;
    --no-passcode) NO_PASSCODE="1"; shift ;;
    --venv) VENV_PATH="${2:?}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 2 ;;
  esac
done

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required." >&2
  exit 1
fi

if [[ "$INSTALL_SERVICE" == "1" && "$(id -u)" -ne 0 ]]; then
  echo "--install-service requires root. Re-run with sudo." >&2
  exit 1
fi

AGENT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$AGENT_ROOT"

PYTHON_BIN="python3"
if [[ "$INSTALL_SERVICE" == "1" ]]; then
  VENV_PATH="${VENV_PATH:-/opt/outpost-agent/venv}"
  python3 -m venv "$VENV_PATH"
  PYTHON_BIN="$VENV_PATH/bin/python"
  "$PYTHON_BIN" -m pip install --upgrade pip
  PACKAGE_INSTALL="1"
fi

if [[ "$PACKAGE_INSTALL" == "1" ]]; then
  "$PYTHON_BIN" -m pip install .
else
  "$PYTHON_BIN" -m pip install -e .
fi

if [[ -z "$ORG_CODE" ]]; then
  read -r -p "ORGANISATIONAL CODE: " ORG_CODE
fi

if [[ -z "$ORG_CODE" ]]; then
  echo "ORGANISATIONAL CODE is required." >&2
  exit 1
fi

if [[ -z "$PASSCODE" && -n "$API_KEY" ]]; then
  PASSCODE="$API_KEY"
fi

if [[ -z "$PASSCODE" && "$NO_PASSCODE" != "1" ]]; then
  read -r -s -p "PASSCODE (API): " PASSCODE
  echo
fi

INSTALL_ARGS=(--backend "$BACKEND_URL" --org-code "$ORG_CODE" --poll-interval "$POLL_INTERVAL")
if [[ -n "$PASSCODE" ]]; then
  INSTALL_ARGS+=(--passcode "$PASSCODE")
fi
if [[ -n "$CONFIG_PATH" ]]; then
  INSTALL_ARGS+=(--config "$CONFIG_PATH")
fi

"$PYTHON_BIN" -m outpost_agent.installer "${INSTALL_ARGS[@]}"
EFFECTIVE_CONFIG_PATH="${CONFIG_PATH:-$HOME/.outpost/agent-config.json}"

if [[ "$INSTALL_SERVICE" == "1" ]]; then
  if ! id "$SERVICE_USER" >/dev/null 2>&1; then
    useradd --system --home-dir /var/lib/outpost --create-home --shell /usr/sbin/nologin "$SERVICE_USER"
  fi

  install -d -m 700 -o "$SERVICE_USER" -g "$SERVICE_USER" /var/lib/outpost
  if [[ -f "$EFFECTIVE_CONFIG_PATH" ]]; then
    install -m 600 -o "$SERVICE_USER" -g "$SERVICE_USER" "$EFFECTIVE_CONFIG_PATH" /var/lib/outpost/agent-config.json
  fi

  OUTPOST_AGENT_BIN="$VENV_PATH/bin/outpost-agent"
  cat >/etc/systemd/system/outpost-agent.service <<EOF
[Unit]
Description=OUTPOST Endpoint Agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$SERVICE_USER
Group=$SERVICE_USER
Environment=HOME=/var/lib/outpost
ExecStart=$OUTPOST_AGENT_BIN --config /var/lib/outpost/agent-config.json
Restart=always
RestartSec=15
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ProtectHome=true
ReadWritePaths=/var/lib/outpost

[Install]
WantedBy=multi-user.target
EOF

  systemctl daemon-reload
  systemctl enable outpost-agent.service
  if [[ "$START_AGENT" == "1" ]]; then
    systemctl restart outpost-agent.service
  fi
  echo "OUTPOST systemd service installed: outpost-agent.service"
else
  echo "OUTPOST agent installed. Start it with: outpost-agent"
fi
