#!/usr/bin/env bash
set -euo pipefail

DEFAULT_REPO_ZIP_URL="https://github.com/bigmphatso/agent-outpost/archive/refs/heads/master.zip"
REPO_ZIP_URL="$DEFAULT_REPO_ZIP_URL"
BACKEND_URL="https://backend-outpost.onrender.com"
ORG_CODE=""
PASSCODE=""
API_KEY=""
POLL_INTERVAL="30"
INSTALL_SERVICE="0"
START_AGENT="0"
SERVICE_USER="outpost"
NO_PASSCODE="0"
VENV_PATH=""

usage() {
  cat <<'EOF'
Usage: install-agent-from-github.sh [options]

Options:
  --repo-zip-url URL      GitHub repository ZIP URL. Default: bigmphatso/agent-outpost master ZIP.
  --backend-url URL       Backend API URL.
  --org-code CODE         Organisational code issued from OUTPOST.
  --passcode PASSCODE     PASSCODE used for authenticated backend calls.
  --api-key KEY           Legacy alias for --passcode.
  --poll-interval SECONDS Agent polling interval. Default: 30
  --install-service       Install a systemd service.
  --start-agent           Start the systemd service after installation.
  --service-user USER     User for the service. Default: outpost
  --no-passcode           Do not prompt for PASSCODE when backend auth is disabled.
  --venv PATH             Virtualenv path for systemd installs. Default: /opt/outpost-agent/venv
  -h, --help              Show this help.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo-zip-url) REPO_ZIP_URL="${2:?}"; shift 2 ;;
    --backend-url) BACKEND_URL="${2:?}"; shift 2 ;;
    --org-code) ORG_CODE="${2:?}"; shift 2 ;;
    --passcode) PASSCODE="${2:?}"; shift 2 ;;
    --api-key) API_KEY="${2:?}"; shift 2 ;;
    --poll-interval) POLL_INTERVAL="${2:?}"; shift 2 ;;
    --install-service) INSTALL_SERVICE="1"; shift ;;
    --start-agent) START_AGENT="1"; INSTALL_SERVICE="1"; shift ;;
    --service-user) SERVICE_USER="${2:?}"; shift 2 ;;
    --no-passcode) NO_PASSCODE="1"; shift ;;
    --venv) VENV_PATH="${2:?}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 2 ;;
  esac
done

if ! command -v unzip >/dev/null 2>&1; then
  echo "unzip is required." >&2
  exit 1
fi

WORK_DIR="$(mktemp -d)"
cleanup() {
  rm -rf "$WORK_DIR"
}
trap cleanup EXIT

ZIP_PATH="$WORK_DIR/outpost.zip"
if command -v curl >/dev/null 2>&1; then
  if ! curl -fsSL "$REPO_ZIP_URL" -o "$ZIP_PATH"; then
    echo "Failed to download OUTPOST agent ZIP: $REPO_ZIP_URL" >&2
    echo "If this is a private repository, download the installer package instead or provide an authenticated/internal ZIP URL." >&2
    echo "Default public agent ZIP: $DEFAULT_REPO_ZIP_URL" >&2
    exit 1
  fi
elif command -v wget >/dev/null 2>&1; then
  if ! wget -q "$REPO_ZIP_URL" -O "$ZIP_PATH"; then
    echo "Failed to download OUTPOST agent ZIP: $REPO_ZIP_URL" >&2
    echo "If this is a private repository, download the installer package instead or provide an authenticated/internal ZIP URL." >&2
    echo "Default public agent ZIP: $DEFAULT_REPO_ZIP_URL" >&2
    exit 1
  fi
else
  echo "curl or wget is required." >&2
  exit 1
fi

unzip -q "$ZIP_PATH" -d "$WORK_DIR"
AGENT_DIR="$(
  find "$WORK_DIR" -type f -name pyproject.toml -print | while read -r project_file; do
    project_dir="$(dirname "$project_file")"
    if [[ -d "$project_dir/outpost_agent" ]]; then
      printf '%s\n' "$project_dir"
      break
    fi
  done
)"
if [[ -z "$AGENT_DIR" ]]; then
  echo "Could not find an OUTPOST agent Python package in the repository ZIP." >&2
  exit 1
fi

ARGS=(--backend-url "$BACKEND_URL" --poll-interval "$POLL_INTERVAL" --package-install)
if [[ -n "$ORG_CODE" ]]; then
  ARGS+=(--org-code "$ORG_CODE")
fi
if [[ -z "$PASSCODE" && -n "$API_KEY" ]]; then
  PASSCODE="$API_KEY"
fi
if [[ -n "$PASSCODE" ]]; then
  ARGS+=(--passcode "$PASSCODE")
fi
if [[ "$INSTALL_SERVICE" == "1" ]]; then
  ARGS+=(--install-service --service-user "$SERVICE_USER")
fi
if [[ "$START_AGENT" == "1" ]]; then
  ARGS+=(--start-agent)
fi
if [[ "$NO_PASSCODE" == "1" ]]; then
  ARGS+=(--no-passcode)
fi
if [[ -n "$VENV_PATH" ]]; then
  ARGS+=(--venv "$VENV_PATH")
fi

bash "$AGENT_DIR/scripts/install-agent.sh" "${ARGS[@]}"
