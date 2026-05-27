from __future__ import annotations

import os
import platform
import shutil
import socket
import subprocess

from outpost_agent.device_fingerprint import collect_hardware_fingerprint


def _memory_total_gb() -> float | None:
    try:
        if os.path.exists("/proc/meminfo"):
            with open("/proc/meminfo", "r", encoding="utf-8") as handle:
                for line in handle:
                    if line.startswith("MemTotal:"):
                        parts = line.split()
                        kb = int(parts[1])
                        return round((kb * 1024) / (1024**3), 2)
        page_size = os.sysconf("SC_PAGE_SIZE")
        phys_pages = os.sysconf("SC_PHYS_PAGES")
        return round((page_size * phys_pages) / (1024**3), 2)
    except Exception:
        return None


def _bios_serial_number() -> str | None:
    if platform.system().lower() != "windows":
        return None
    try:
        result = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                "Get-CimInstance Win32_BIOS | Select-Object -ExpandProperty SerialNumber",
            ],
            capture_output=True,
            check=False,
            text=True,
            timeout=10,
        )
    except Exception:
        return None

    if result.returncode != 0:
        return None
    serial = result.stdout.strip()
    if not serial or serial.lower() in {"default string", "to be filled by o.e.m.", "none"}:
        return None
    return serial


def registration_payload(org_code: str, agent_version: str) -> dict:
    serial_number = _bios_serial_number()
    return {
        "org_code": org_code,
        "hostname": socket.gethostname(),
        "serial_number": serial_number,
        "os_name": platform.platform(),
        "agent_version": agent_version,
        "hardware_fingerprint": collect_hardware_fingerprint(),
        "hardware_fingerprint_version": 1,
    }


def collect_inventory() -> dict:
    disk = shutil.disk_usage(os.path.abspath(os.sep))
    memory_total_gb = _memory_total_gb()
    return {
        "hardware": {
            "hostname": socket.gethostname(),
            "serial_number": _bios_serial_number(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "os": platform.platform(),
            "cpu_count": os.cpu_count(),
            "memory_total_gb": memory_total_gb,
            "disk_total_gb": round(disk.total / (1024**3), 2),
            "disk_free_gb": round(disk.free / (1024**3), 2),
        },
        "software": [
            {"name": "python", "version": platform.python_version()},
        ],
    }
