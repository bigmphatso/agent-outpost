#!/usr/bin/env bash
set -euo pipefail

REPO_ZIP_URL=""
BACKEND_URL="https://outpost-listener.vercel.app"
ORG_CODE=""
PASSCODE=""
API_KEY=""
POLL_INTERVAL="30"
INSTALL_SERVICE="0"
START_AGENT="0"
SERVICE_USER="outpost"

usage() {
  cat <<'EOF'
Usage: install-agent-from-github.sh --repo-zip-url URL [options]

Options:
  --repo-zip-url URL      GitHub repository ZIP URL.
  --backend-url URL       Backend API URL.
  --org-code CODE         Organisational code issued from OUTPOST.
  --passcode PASSCODE     PASSCODE used for authenticated backend calls.
  --api-key KEY           Legacy alias for --passcode.
  --poll-interval SECONDS Agent polling interval. Default: 30
  --install-service       Install a systemd service.
  --start-agent           Start the systemd service after installation.
  --service-user USER     User for the service. Default: outpost
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
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 2 ;;
  esac
done

if [[ -z "$REPO_ZIP_URL" ]]; then
  echo "--repo-zip-url is required." >&2
  usage
  exit 2
fi

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
  curl -fsSL "$REPO_ZIP_URL" -o "$ZIP_PATH"
elif command -v wget >/dev/null 2>&1; then
  wget -q "$REPO_ZIP_URL" -O "$ZIP_PATH"
else
  echo "curl or wget is required." >&2
  exit 1
fi

unzip -q "$ZIP_PATH" -d "$WORK_DIR"
AGENT_DIR="$(find "$WORK_DIR" -type d \( -name agent-op -o -name agent \) | head -n 1)"
if [[ -z "$AGENT_DIR" ]]; then
  echo "Could not find agent-op/ or agent/ in repository ZIP." >&2
  exit 1
fi

ARGS=(--backend-url "$BACKEND_URL" --poll-interval "$POLL_INTERVAL")
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

bash "$AGENT_DIR/scripts/install-agent.sh" "${ARGS[@]}"
