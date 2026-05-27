from __future__ import annotations

import argparse
import random
import time
from pathlib import Path

from outpost_agent.client import BackendClient
from outpost_agent.config import AgentConfig, default_config_dir, load_config, save_config
from outpost_agent.local_store import enqueue_post, mark_sent, read_outbound_batch, record_failure
from outpost_agent.phase1_device_visibility.inventory import collect_inventory, registration_payload
from outpost_agent.phase2_monitoring_alerts.health import collect_health_report
from outpost_agent.phase3_remote_management.executor import execute_pending_tasks
from outpost_agent.registry_intelligence.engine import run_registry_intelligence_scan


def register_if_needed(client: BackendClient, config: AgentConfig, config_path: Path | None) -> str:
    if config.device_id:
        try:
            existing = client.get(f"/api/v1/devices/{config.device_id}")
            if isinstance(existing, dict) and existing.get("device_id") == config.device_id:
                return config.device_id
        except Exception:
            pass

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
            record_failure(db_path, request_id, str(exc))
            break


def run(config: AgentConfig) -> None:
    client = BackendClient(config.backend_url, api_key=config.api_key)
    config_path: Path | None = None
    device_id = register_if_needed(client, config, config_path)

    last_inventory_at = 0.0
    last_registry_at = 0.0
    backoff_seconds = 1.0

    data_dir = default_config_dir()
    registry_snapshot_path = data_dir / "registry-snapshot.json"
    local_db_path = data_dir / "agent-state.sqlite3"

    while True:
        try:
            now = time.time()
            if now - last_inventory_at >= 6 * 60 * 60:
                queue_post(local_db_path, f"/api/v1/devices/{device_id}/inventory", collect_inventory())
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
                last_registry_at = now

            queue_post(local_db_path, f"/api/v1/devices/{device_id}/heartbeat", {"status": "online"})
            queue_post(local_db_path, f"/api/v1/devices/{device_id}/health", collect_health_report())
            flush_outbox(client, local_db_path)

            try:
                execute_pending_tasks(client, device_id)
            except Exception:
                pass

            backoff_seconds = 1.0
            time.sleep(config.poll_interval_seconds)
        except KeyboardInterrupt:
            raise
        except Exception:
            sleep_for = min(backoff_seconds, 300.0) + random.random()
            time.sleep(sleep_for)
            backoff_seconds *= 2


def parse_args() -> AgentConfig:
    parser = argparse.ArgumentParser(description="Run the OUTPOST endpoint agent.")
    parser.add_argument("--config", type=Path, help="Path to an installed OUTPOST agent config file.")
    parser.add_argument("--backend", help="Backend API base URL. Overrides installed config when provided.")
    parser.add_argument("--org-code", help="Organization code issued from the dashboard.")
    parser.add_argument("--activation-code", help="Deprecated alias for --org-code.")
    parser.add_argument("--api-key", help="Optional API key for authenticated backend calls.")
    parser.add_argument("--poll-interval", type=int)
    args = parser.parse_args()

    if args.config or not (args.backend and (args.org_code or args.activation_code)):
        config = load_config(args.config)
        if args.backend:
            config.backend_url = args.backend
        if args.org_code or args.activation_code:
            config.org_code = args.org_code or args.activation_code
        if args.api_key:
            config.api_key = args.api_key
        if args.poll_interval is not None:
            config.poll_interval_seconds = args.poll_interval
        return config

    return AgentConfig(
        backend_url=args.backend,
        org_code=args.org_code or args.activation_code,
        api_key=args.api_key,
        poll_interval_seconds=args.poll_interval or 30,
    )


def main() -> None:
    run(parse_args())


if __name__ == "__main__":
    main()
