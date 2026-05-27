from __future__ import annotations

import subprocess

from outpost_agent.client import BackendClient

ALLOWED_PREFIXES = ("echo ", "whoami", "hostname", "python --version", "powershell -NoProfile -Command Get-Date")


def is_allowed(command: str) -> bool:
    return command in ALLOWED_PREFIXES or command.startswith(ALLOWED_PREFIXES)


def execute_pending_tasks(client: BackendClient, device_id: str) -> None:
    tasks = client.get(f"/api/v1/remote/devices/{device_id}/tasks")
    for task in tasks:
        result = execute_task(task["command"])
        client.post(f"/api/v1/remote/devices/{device_id}/tasks/{task['task_id']}/result", result)


def execute_task(command: str) -> dict:
    if not is_allowed(command):
        return {"status": "rejected", "error": "Command is not allowlisted by the agent."}
    completed = subprocess.run(command, capture_output=True, shell=True, text=True, timeout=60)
    return {
        "status": "completed" if completed.returncode == 0 else "failed",
        "exit_code": completed.returncode,
        "output": completed.stdout[-4000:],
        "error": completed.stderr[-4000:],
    }

