from __future__ import annotations

import shlex
import subprocess

from outpost_agent.client import BackendClient

ALLOWED_ARGV_PREFIXES = (
    ("echo",),
    ("whoami",),
    ("hostname",),
    ("date",),
    ("uptime",),
    ("uname", "-a"),
    ("df", "-h"),
    ("python", "--version"),
    ("python3", "--version"),
    ("powershell", "-NoProfile", "-Command", "Get-Date"),
    ("powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", "Get-Date"),
)


def parse_allowed_command(command: str) -> list[str] | None:
    try:
        argv = shlex.split(command)
    except ValueError:
        return None
    if not argv:
        return None
    for prefix in ALLOWED_ARGV_PREFIXES:
        if tuple(argv[: len(prefix)]) == prefix:
            return argv
    return None


def is_allowed(command: str) -> bool:
    return parse_allowed_command(command) is not None


def execute_pending_tasks(client: BackendClient, device_id: str) -> None:
    tasks = client.get(f"/api/v1/remote/devices/{device_id}/tasks")
    for task in tasks:
        result = execute_task(task["command"])
        client.post(f"/api/v1/remote/devices/{device_id}/tasks/{task['task_id']}/result", result)


def execute_task(command: str) -> dict:
    argv = parse_allowed_command(command)
    if argv is None:
        return {"status": "rejected", "error": "Command is not allowlisted by the agent."}
    completed = subprocess.run(argv, capture_output=True, shell=False, text=True, timeout=60)
    return {
        "status": "completed" if completed.returncode == 0 else "failed",
        "exit_code": completed.returncode,
        "output": completed.stdout[-4000:],
        "error": completed.stderr[-4000:],
    }
