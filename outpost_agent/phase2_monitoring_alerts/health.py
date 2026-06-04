from __future__ import annotations

import os
import platform
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from outpost_agent.linux_platform import is_linux, linux_antivirus_status, linux_pending_update_count, linux_suspicious_process_count


def _windows_powershell(command: str) -> str | None:
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
            capture_output=True,
            check=False,
            text=True,
            timeout=12,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def _disk_snapshot() -> dict[str, Any]:
    disk = shutil.disk_usage(os.path.abspath(os.sep))
    disk_free_percent = round((disk.free / disk.total) * 100, 2) if disk.total else None
    return {
        "disk_total_gb": round(disk.total / (1024**3), 2),
        "disk_free_gb": round(disk.free / (1024**3), 2),
        "disk_free_percent": disk_free_percent,
    }


def _linux_uptime_seconds() -> float | None:
    try:
        with open("/proc/uptime", "r", encoding="utf-8") as handle:
            return float(handle.read().split()[0])
    except Exception:
        return None


def _windows_uptime_seconds() -> float | None:
    value = _windows_powershell("(New-TimeSpan -Start (Get-CimInstance Win32_OperatingSystem).LastBootUpTime -End (Get-Date)).TotalSeconds")
    try:
        return float(value) if value else None
    except Exception:
        return None


def _linux_memory_utilization_percent() -> float | None:
    try:
        meminfo: dict[str, int] = {}
        with open("/proc/meminfo", "r", encoding="utf-8") as handle:
            for line in handle:
                key, _, remainder = line.partition(":")
                if not key:
                    continue
                meminfo[key] = int(remainder.strip().split()[0])
        total = meminfo.get("MemTotal")
        available = meminfo.get("MemAvailable")
        if not total or available is None:
            return None
        return round(((total - available) / total) * 100, 2)
    except Exception:
        return None


def _windows_memory_utilization_percent() -> float | None:
    value = _windows_powershell(
        "$os = Get-CimInstance Win32_OperatingSystem; [math]::Round((($os.TotalVisibleMemorySize - $os.FreePhysicalMemory) / $os.TotalVisibleMemorySize) * 100, 2)"
    )
    try:
        return float(value) if value else None
    except Exception:
        return None


def _linux_cpu_utilization_percent() -> float | None:
    try:
        load_avg = os.getloadavg()[0]
        cpu_count = os.cpu_count() or 1
        return round(min((load_avg / cpu_count) * 100, 100.0), 2)
    except Exception:
        return None


def _windows_cpu_utilization_percent() -> float | None:
    value = _windows_powershell("(Get-CimInstance Win32_Processor | Select-Object -First 1 -ExpandProperty LoadPercentage)")
    try:
        return float(value) if value else None
    except Exception:
        return None


def _network_traffic() -> dict[str, Any]:
    if is_linux():
        stats: dict[str, Any] = {}
        try:
            with open("/proc/net/dev", "r", encoding="utf-8") as handle:
                for line in handle.readlines()[2:]:
                    if ":" not in line:
                        continue
                    iface, values = line.split(":", 1)
                    parts = [int(value) for value in values.split()]
                    stats[iface.strip()] = {
                        "rx_bytes": parts[0],
                        "rx_packets": parts[1],
                        "tx_bytes": parts[8],
                        "tx_packets": parts[9],
                    }
        except Exception:
            return {}
        return stats

    output = _windows_powershell("Get-NetAdapterStatistics | Select-Object Name,ReceivedBytes,ReceivedUnicastPackets,SentBytes,SentUnicastPackets | ConvertTo-Json -Depth 3")
    if not output:
        return {}
    try:
        raw = __import__("json").loads(output)
    except Exception:
        return {}
    if isinstance(raw, dict):
        raw = [raw]
    stats: dict[str, Any] = {}
    for item in raw or []:
        if not isinstance(item, dict):
            continue
        stats[str(item.get("Name") or "adapter")] = {
            "rx_bytes": item.get("ReceivedBytes"),
            "rx_packets": item.get("ReceivedUnicastPackets"),
            "tx_bytes": item.get("SentBytes"),
            "tx_packets": item.get("SentUnicastPackets"),
        }
    return stats


def _logged_in_users() -> list[dict[str, Any]]:
    if is_linux():
        try:
            result = subprocess.run(["who"], capture_output=True, check=False, text=True, timeout=6)
        except Exception:
            return []
        users: list[dict[str, Any]] = []
        for line in result.stdout.splitlines():
            parts = line.split()
            if parts:
                users.append({"user": parts[0], "terminal": parts[1] if len(parts) > 1 else None})
        return users

    output = _windows_powershell("query user")
    if not output:
        return []
    users: list[dict[str, Any]] = []
    for line in output.splitlines()[1:]:
        parts = line.split()
        if parts:
            users.append({"user": parts[0].lstrip(">"), "session": parts[1] if len(parts) > 1 else None})
    return users


def _running_services(limit: int = 50) -> list[dict[str, Any]]:
    if is_linux():
        try:
            result = subprocess.run(
                ["systemctl", "list-units", "--type=service", "--state=running", "--no-legend"],
                capture_output=True,
                check=False,
                text=True,
                timeout=15,
            )
        except Exception:
            return []
        services: list[dict[str, Any]] = []
        for line in result.stdout.splitlines()[:limit]:
            parts = line.split()
            if parts:
                services.append({"name": parts[0], "state": parts[2] if len(parts) > 2 else "running"})
        return services

    output = _windows_powershell("Get-Service | Where-Object {$_.Status -eq 'Running'} | Select-Object -First 50 Name,DisplayName,Status | ConvertTo-Json -Depth 3")
    if not output:
        return []
    try:
        raw = __import__("json").loads(output)
    except Exception:
        return []
    if isinstance(raw, dict):
        raw = [raw]
    services: list[dict[str, Any]] = []
    for item in (raw or [])[:limit]:
        if not isinstance(item, dict):
            continue
        services.append({"name": item.get("Name"), "display_name": item.get("DisplayName"), "state": item.get("Status")})
    return services


def _active_network_interfaces() -> list[dict[str, Any]]:
    if is_linux():
        interfaces: list[dict[str, Any]] = []
        try:
            for adapter in os.scandir("/sys/class/net"):
                if adapter.name == "lo":
                    continue
                try:
                    mac = Path(adapter.path, "address").read_text(encoding="utf-8").strip()
                except Exception:
                    mac = None
                interfaces.append({"name": adapter.name, "mac_address": mac})
        except Exception:
            return []
        return interfaces

    output = _windows_powershell("Get-NetAdapter | Select-Object Name,InterfaceDescription,Status,MacAddress | ConvertTo-Json -Depth 3")
    if not output:
        return []
    try:
        raw = __import__("json").loads(output)
    except Exception:
        return []
    if isinstance(raw, dict):
        raw = [raw]
    interfaces: list[dict[str, Any]] = []
    for item in raw or []:
        if not isinstance(item, dict):
            continue
        interfaces.append(
            {
                "name": item.get("Name"),
                "description": item.get("InterfaceDescription"),
                "status": item.get("Status"),
                "mac_address": item.get("MacAddress"),
            }
        )
    return interfaces


def collect_dynamic_telemetry() -> dict[str, Any]:
    disk = _disk_snapshot()
    if is_linux():
        return {
            "cpu_utilization_percent": _linux_cpu_utilization_percent(),
            "memory_utilization_percent": _linux_memory_utilization_percent(),
            "disk_utilization_percent": round(100 - (disk["disk_free_percent"] or 0), 2) if disk.get("disk_free_percent") is not None else None,
            "uptime_seconds": _linux_uptime_seconds(),
            "logged_in_users": _logged_in_users(),
            "running_services": _running_services(),
            "active_network_interfaces": _active_network_interfaces(),
            "network_traffic": _network_traffic(),
            "agent_health": {"status": "online"},
        }

    return {
        "cpu_utilization_percent": _windows_cpu_utilization_percent(),
        "memory_utilization_percent": _windows_memory_utilization_percent(),
        "disk_utilization_percent": round(100 - (disk["disk_free_percent"] or 0), 2) if disk.get("disk_free_percent") is not None else None,
        "uptime_seconds": _windows_uptime_seconds(),
        "logged_in_users": _logged_in_users(),
        "running_services": _running_services(),
        "active_network_interfaces": _active_network_interfaces(),
        "network_traffic": _network_traffic(),
        "agent_health": {"status": "online"},
    }


def _security_findings() -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if is_linux():
        antivirus_present, antivirus_enabled, signature_age_days = linux_antivirus_status()
        if not antivirus_present:
            findings.append(
                {
                    "finding_id": "antivirus:missing",
                    "title": "Antivirus missing",
                    "severity": "critical",
                    "status": "open",
                    "recommendation": "Install or enable endpoint protection.",
                }
            )
        elif not antivirus_enabled:
            findings.append(
                {
                    "finding_id": "antivirus:disabled",
                    "title": "Antivirus disabled",
                    "severity": "high",
                    "status": "open",
                    "recommendation": "Enable the installed antivirus service.",
                }
            )
        if signature_age_days >= 7:
            findings.append(
                {
                    "finding_id": "antivirus:signatures-outdated",
                    "title": "Antivirus signatures outdated",
                    "severity": "medium",
                    "status": "open",
                    "recommendation": "Refresh antivirus signatures.",
                }
            )
        pending_updates = linux_pending_update_count()
        if pending_updates:
            findings.append(
                {
                    "finding_id": "os:pending-updates",
                    "title": "Pending OS updates detected",
                    "severity": "medium",
                    "status": "open",
                    "occurrence_count": pending_updates,
                    "recommendation": "Install the missing operating system updates.",
                }
            )
        suspicious = linux_suspicious_process_count()
        if suspicious:
            findings.append(
                {
                    "finding_id": "process:suspicious",
                    "title": "Suspicious processes detected",
                    "severity": "high",
                    "status": "open",
                    "occurrence_count": suspicious,
                    "recommendation": "Review the listed processes and remove unsafe software.",
                }
            )
    else:
        findings.append(
            {
                "finding_id": "os:pending-updates",
                "title": "Windows update review recommended",
                "severity": "medium",
                "status": "open",
                "occurrence_count": 0,
                "recommendation": "Confirm that security updates are fully installed.",
            }
        )
    return findings


def collect_health_report() -> dict[str, Any]:
    disk = shutil.disk_usage(os.path.abspath(os.sep))
    disk_free_percent = round((disk.free / disk.total) * 100, 2)
    telemetry = collect_dynamic_telemetry()
    findings = _security_findings()

    if is_linux():
        antivirus_present, antivirus_enabled, signature_age_days = linux_antivirus_status()
        return {
            "os_updates_pending": linux_pending_update_count(),
            "antivirus_present": antivirus_present,
            "antivirus_enabled": antivirus_enabled,
            "antivirus_signature_age_days": signature_age_days,
            "disk_free_percent": disk_free_percent,
            "suspicious_process_count": linux_suspicious_process_count(),
            "compliance": {
                "compliance_score": 100 if not findings else max(0, 100 - (len(findings) * 12)),
                "policy_status": "warn" if findings else "pass",
            },
            "findings": findings,
            "telemetry": telemetry,
            "state_hash": __import__("hashlib").sha256(__import__("json").dumps({"findings": findings, "telemetry": telemetry}, sort_keys=True).encode("utf-8")).hexdigest(),
        }

    return {
        "os_updates_pending": 0,
        "antivirus_present": True,
        "antivirus_enabled": True,
        "antivirus_signature_age_days": 0,
        "disk_free_percent": disk_free_percent,
        "suspicious_process_count": 0,
        "compliance": {
            "compliance_score": 100 if not findings else max(0, 100 - (len(findings) * 12)),
            "policy_status": "warn" if findings else "pass",
        },
        "findings": findings,
        "telemetry": telemetry,
        "state_hash": __import__("hashlib").sha256(__import__("json").dumps({"findings": findings, "telemetry": telemetry}, sort_keys=True).encode("utf-8")).hexdigest(),
    }
