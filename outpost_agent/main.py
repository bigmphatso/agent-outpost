from __future__ import annotations

import argparse
import getpass
import logging
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from outpost_agent.client import BackendClient
from outpost_agent.config import AgentConfig, default_config_dir, load_config, save_config
from outpost_agent.local_store import clear_outbound_requests, enqueue_post, mark_sent, read_outbound_batch, record_failure
from outpost_agent.phase1_device_visibility.inventory import collect_inventory, registration_payload
from outpost_agent.phase2_monitoring_alerts.health import collect_health_report
from outpost_agent.phase3_remote_management.executor import execute_pending_tasks
from outpost_agent.registry_intelligence.engine import run_registry_intelligence_scan
from outpost_agent.telemetry_state import diff_software, load_state, save_state, stable_hash, state_path

logger = logging.getLogger(__name__)


def prompt_secret_if_interactive(label: str) -> str | None:
    if not sys.stdin.isatty():
        return None
    entered = getpass.getpass(f"{label}: ").strip()
    return entered or None


def register_if_needed(client: BackendClient, config: AgentConfig, config_path: Path | None) -> str:
    device = client.post(
        "/api/v1/devices/register",
        {**registration_payload(config.org_code, config.agent_version), "device_id": config.device_id},
    )
    device_id = device["device_id"]
    if config.device_id != device_id:
        config.device_id = device_id
        save_config(config, config_path)
    return device_id


def queue_post(db_path: Path, path: str, payload: dict) -> None:
    enqueue_post(db_path, path, payload)


def flush_outbox(client: BackendClient, db_path: Path, *, limit: int = 50) -> None:
    for item in read_outbound_batch(db_path, limit=limit):
        request_id = int(item["id"])
        try:
            if item["method"] != "POST":
                mark_sent(db_path, request_id)
                continue
            client.post(str(item["path"]), item["payload"])
            mark_sent(db_path, request_id)
        except Exception as exc:
            error_text = str(exc)
            path_text = str(item["path"])
            if "404 Client Error" in error_text and path_text.startswith("/api/v1/devices/"):
                logger.warning(
                    "OUTPOST agent dropped stale device-scoped outbox request %s after device registration changed: %s",
                    request_id,
                    path_text,
                )
                mark_sent(db_path, request_id)
                continue
            logger.warning("OUTPOST agent outbox request %s failed: %s", request_id, exc)
            record_failure(db_path, request_id, str(exc))
            break


def run(config: AgentConfig, config_path: Path | None = None) -> None:
    if not config.api_key:
        config.api_key = prompt_secret_if_interactive("PASSCODE (API)")
        if config.api_key:
            save_config(config, config_path)

    if not config.api_key:
        raise SystemExit(
            "OUTPOST agent PASSCODE is missing. Run outpost-agent-install again and enter the PASSCODE (API), "
            "or start the agent with --passcode YOUR-PASSCODE."
        )

    client = BackendClient(config.backend_url, api_key=config.api_key)
    data_dir = default_config_dir()
    telemetry_state_file = state_path(data_dir)
    telemetry_state = load_state(telemetry_state_file)
    registry_snapshot_path = data_dir / "registry-snapshot.json"
    local_db_path = data_dir / "agent-state.sqlite3"
    registration_backoff = 5.0
    while True:
        try:
            logger.info("OUTPOST agent attempting registration against %s", config.backend_url)
            previous_device_id = config.device_id
            device_id = register_if_needed(client, config, config_path)
            if previous_device_id and previous_device_id != device_id:
                clear_outbound_requests(local_db_path)
                logger.info(
                    "OUTPOST agent cleared stale outbox entries after device id changed from %s to %s",
                    previous_device_id,
                    device_id,
                )
            logger.info("OUTPOST agent registered as %s", device_id)
            break
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            print(
                f"OUTPOST agent could not register with the backend: {exc}. "
                "Check the Organisational Code, PASSCODE, backend URL, and network connection.",
                flush=True,
            )
            time.sleep(min(registration_backoff, 300.0))
            registration_backoff *= 2

    last_inventory_at = 0.0
    last_health_at = 0.0
    last_telemetry_at = 0.0
    last_registry_at = 0.0
    backoff_seconds = 1.0

    while True:
        try:
            now = time.time()
            inventory_payload = collect_inventory(config.org_code, config.agent_version)
            logger.debug("OUTPOST agent collected inventory payload for %s", device_id)
            inventory_hash = stable_hash(inventory_payload)
            previous_inventory_hash = str(telemetry_state.get("inventory_hash") or "")
            if inventory_hash != previous_inventory_hash or now - last_inventory_at >= 6 * 60 * 60:
                inventory_payload["state_hash"] = inventory_hash
                inventory_payload["refresh_reason"] = "changed" if inventory_hash != previous_inventory_hash else "scheduled_refresh"
                software_changes = diff_software(
                    list(telemetry_state.get("software_inventory") or []),
                    list(inventory_payload.get("software") or []),
                )
                inventory_payload["software_changes"] = software_changes
                if not telemetry_state.get("enrollment_event_sent"):
                    inventory_payload.setdefault("events", []).append(
                        {
                            "event_type": "DEVICE_ENROLLED",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "severity": "low",
                            "risk_score": 0,
                            "summary": "Device enrolled with the Outpost backend.",
                            "data": {"hostname": inventory_payload.get("profile", {}).get("hostname")},
                        }
                    )
                    telemetry_state["enrollment_event_sent"] = True
                if telemetry_state.get("profile_hash") and telemetry_state["profile_hash"] != stable_hash(inventory_payload.get("profile") or {}):
                    inventory_payload.setdefault("events", []).append(
                        {
                            "event_type": "DEVICE_RENAMED",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "severity": "medium",
                            "risk_score": 15,
                            "summary": "Device hostname or profile changed.",
                            "data": {"previous_hostname": telemetry_state.get("profile", {}).get("hostname"), "current_hostname": inventory_payload.get("profile", {}).get("hostname")},
                        }
                    )
                if telemetry_state.get("profile", {}).get("os_version") and telemetry_state["profile"].get("os_version") != inventory_payload.get("profile", {}).get("os_version"):
                    inventory_payload.setdefault("events", []).append(
                        {
                            "event_type": "OS_UPGRADED",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "severity": "medium",
                            "risk_score": 20,
                            "summary": "Operating system version changed.",
                            "data": {"previous_os_version": telemetry_state.get("profile", {}).get("os_version"), "current_os_version": inventory_payload.get("profile", {}).get("os_version")},
                        }
                    )
                for item in software_changes.get("added", []):
                    inventory_payload.setdefault("events", []).append(
                        {
                            "event_type": "SOFTWARE_INSTALLED",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "severity": "low",
                            "risk_score": 5,
                            "summary": f"Installed {item.get('name')}",
                            "data": item,
                        }
                    )
                for item in software_changes.get("removed", []):
                    inventory_payload.setdefault("events", []).append(
                        {
                            "event_type": "SOFTWARE_REMOVED",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "severity": "medium",
                            "risk_score": 10,
                            "summary": f"Removed {item.get('name')}",
                            "data": item,
                        }
                    )
                for item in software_changes.get("updated", []):
                    inventory_payload.setdefault("events", []).append(
                        {
                            "event_type": "SOFTWARE_VERSION_CHANGED",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "severity": "low",
                            "risk_score": 5,
                            "summary": f"Updated {item.get('name')}",
                            "data": item,
                        }
                    )
                queue_post(local_db_path, f"/api/v1/devices/{device_id}/inventory", inventory_payload)
                logger.info("OUTPOST agent queued inventory update for %s", device_id)
                telemetry_state["inventory_hash"] = inventory_hash
                telemetry_state["profile_hash"] = stable_hash(inventory_payload.get("profile") or {})
                telemetry_state["profile"] = inventory_payload.get("profile") or {}
                telemetry_state["software_inventory"] = list(inventory_payload.get("software") or [])
                last_inventory_at = now

            if now - last_registry_at >= 5 * 60:
                registry_scan = run_registry_intelligence_scan(
                    snapshot_path=registry_snapshot_path,
                    device_id=device_id,
                    organization_id=None,
                )
                if registry_scan["events"]:
                    queue_post(
                        local_db_path,
                        "/api/v1/telemetry/events",
                        {"device_id": device_id, "events": registry_scan["events"]},
                    )
                    logger.info("OUTPOST agent queued %s registry events for %s", len(registry_scan["events"]), device_id)
                queue_post(
                    local_db_path,
                    "/api/v1/telemetry/registry-snapshots",
                    {
                        "device_id": device_id,
                        "organization_id": None,
                        "collected_at": registry_scan["collected_at"],
                        "snapshot": registry_scan["snapshot"],
                    },
                )
                logger.debug("OUTPOST agent queued registry snapshot for %s", device_id)
                last_registry_at = now

            health_report = collect_health_report()
            telemetry_payload = health_report.pop("telemetry", {})
            logger.debug("OUTPOST agent collected health report for %s", device_id)
            health_hash = str(health_report.get("state_hash") or stable_hash(health_report))
            if health_hash != str(telemetry_state.get("health_hash") or "") or now - last_health_at >= 5 * 60:
                queue_post(local_db_path, f"/api/v1/devices/{device_id}/health", health_report)
                logger.info("OUTPOST agent queued health update for %s", device_id)
                telemetry_state["health_hash"] = health_hash
                telemetry_state["findings"] = list(health_report.get("findings") or [])
                last_health_at = now

            telemetry_hash = stable_hash(telemetry_payload)
            if telemetry_hash != str(telemetry_state.get("telemetry_hash") or "") or now - last_telemetry_at >= 5 * 60:
                queue_post(
                    local_db_path,
                    f"/api/v1/devices/{device_id}/telemetry",
                    {
                        "telemetry": telemetry_payload,
                        "state_hash": telemetry_hash,
                        "collected_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
                logger.info("OUTPOST agent queued telemetry reading for %s", device_id)
                telemetry_state["telemetry_hash"] = telemetry_hash
                last_telemetry_at = now

            queue_post(
                local_db_path,
                f"/api/v1/devices/{device_id}/heartbeat",
                {
                    "status": "online",
                    "telemetry": {"agent_health": {"status": "online", "queue_depth": 0}},
                    "health": health_report,
                },
            )
            logger.debug("OUTPOST agent queued heartbeat for %s", device_id)
            flush_outbox(client, local_db_path)

            try:
                execute_pending_tasks(client, device_id)
            except Exception:
                pass

            save_state(telemetry_state_file, telemetry_state)
            backoff_seconds = 1.0
            time.sleep(config.poll_interval_seconds)
        except KeyboardInterrupt:
            raise
        except Exception:
            sleep_for = min(backoff_seconds, 300.0) + random.random()
            time.sleep(sleep_for)
            backoff_seconds *= 2


def parse_args() -> tuple[AgentConfig, Path | None]:
    parser = argparse.ArgumentParser(description="Run the OUTPOST endpoint agent.")
    parser.add_argument("--config", type=Path, help="Path to an installed OUTPOST agent config file.")
    parser.add_argument("--backend", help="Backend API base URL. Overrides installed config when provided.")
    parser.add_argument("--org-code", help="Organisational code issued from the dashboard.")
    parser.add_argument("--activation-code", help="Deprecated alias for --org-code.")
    parser.add_argument("--passcode", help="PASSCODE used for authenticated backend calls.")
    parser.add_argument("--api-key", help="Legacy alias for --passcode.")
    parser.add_argument("--poll-interval", type=int)
    args = parser.parse_args()

    if args.config or not (args.backend and (args.org_code or args.activation_code)):
        try:
            config = load_config(args.config)
        except FileNotFoundError as exc:
            raise SystemExit(
                "OUTPOST agent config was not found. Run outpost-agent-install first, then start outpost-agent."
            ) from exc
        if args.backend:
            config.backend_url = args.backend
        if args.org_code or args.activation_code:
            config.org_code = args.org_code or args.activation_code
        if args.passcode or args.api_key:
            config.api_key = args.passcode or args.api_key
        if args.poll_interval is not None:
            config.poll_interval_seconds = args.poll_interval
        return config, args.config

    return (
        AgentConfig(
            backend_url=args.backend,
            org_code=args.org_code or args.activation_code,
            api_key=args.passcode or args.api_key,
            poll_interval_seconds=args.poll_interval or 30,
        ),
        None,
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    config, config_path = parse_args()
    run(config, config_path)


if __name__ == "__main__":
    main()
