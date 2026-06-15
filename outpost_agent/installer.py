from __future__ import annotations

import argparse
import getpass
import os
from pathlib import Path

from outpost_agent.config import (
    AgentConfig,
    config_security_summary,
    default_config_path,
    harden_path_permissions,
    load_config,
    normalize_backend_url,
    save_config,
)

DEFAULT_BACKEND_URL = "https://backend-outpost.onrender.com"


def prompt_if_missing(value: str | None, label: str) -> str:
    if value:
        return value.strip()
    entered = input(f"{label}: ").strip()
    if not entered:
        raise SystemExit(f"{label} is required.")
    return entered


def prompt_secret_if_missing(value: str | None, label: str) -> str:
    if value:
        return value.strip()
    entered = getpass.getpass(f"{label}: ").strip()
    if not entered:
        raise SystemExit(f"{label} is required.")
    return entered


def install_agent(
    backend_url: str,
    org_code: str,
    poll_interval: int,
    config_path: Path | None = None,
    api_key: str | None = None,
) -> Path:
    config = AgentConfig(
        backend_url=normalize_backend_url(backend_url),
        org_code=org_code.strip().upper(),
        poll_interval_seconds=poll_interval,
        api_key=api_key,
    )
    return save_config(config, config_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Install and configure the OUTPOST endpoint agent.")
    parser.add_argument("--backend", default=DEFAULT_BACKEND_URL, help="Backend API base URL.")
    parser.add_argument("--org-code", help="Organisational code issued from the OUTPOST dashboard.")
    parser.add_argument("--passcode", help="PASSCODE used for authenticated backend calls.")
    parser.add_argument("--api-key", help="Legacy alias for --passcode.")
    parser.add_argument("--poll-interval", type=int, default=30)
    parser.add_argument("--config", type=Path, default=default_config_path())
    parser.add_argument("--harden-config", action="store_true", help="Repair config file permissions and migrate plaintext secrets.")
    args = parser.parse_args()

    if args.harden_config:
        load_config(args.config)
        harden_path_permissions(args.config)
        print(f"OUTPOST agent configuration hardened: {args.config}")
        print(config_security_summary(args.config))
        return

    org_code = prompt_if_missing(args.org_code, "ORGANISATIONAL CODE")
    api_key = prompt_secret_if_missing(
        args.passcode or args.api_key or os.environ.get("OUTPOST_AGENT_PASSCODE") or os.environ.get("OUTPOST_AGENT_API_KEY"),
        "PASSCODE (API)",
    )
    config = AgentConfig(
        backend_url=normalize_backend_url(args.backend),
        org_code=org_code.strip().upper(),
        poll_interval_seconds=args.poll_interval,
        api_key=api_key,
    )
    config_path = save_config(config, args.config)

    print(f"OUTPOST agent configuration saved to: {config_path}")
    print("Start the agent with: python -m outpost_agent.main")


if __name__ == "__main__":
    main()
