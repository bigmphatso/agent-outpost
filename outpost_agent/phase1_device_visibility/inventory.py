from __future__ import annotations

import os
import platform
import shutil
import socket
import subprocess
from pathlib import Path
from typing import Any

from outpost_agent.device_fingerprint import collect_hardware_fingerprint
from outpost_agent.linux_platform import (
    is_linux,
    linux_distribution_name,
    linux_package_inventory,
    linux_serial_number,
)


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


def _memory_total_gb() -> float | None:
    try:
        if os.path.exists("/proc/meminfo"):
            with open("/proc/meminfo", "r", encoding="utf-8") as handle:
                for line in handle:
                    if line.startswith("MemTotal:"):
                        parts = line.split()
                        kb = int(parts[1])
                        return round((kb * 1024) / (1024**3), 2)
        if hasattr(os, "sysconf"):
            page_size = os.sysconf("SC_PAGE_SIZE")
            phys_pages = os.sysconf("SC_PHYS_PAGES")
            return round((page_size * phys_pages) / (1024**3), 2)
    except Exception:
        return None
    return None


def _linux_manufacturer() -> str | None:
    for path in ("/sys/class/dmi/id/sys_vendor", "/sys/class/dmi/id/board_vendor"):
        try:
            value = Path(path).read_text(encoding="utf-8").strip()
            if value:
                return value
        except Exception:
            continue
    return None


def _linux_model() -> str | None:
    for path in ("/sys/class/dmi/id/product_name", "/sys/class/dmi/id/board_name"):
        try:
            value = Path(path).read_text(encoding="utf-8").strip()
            if value:
                return value
        except Exception:
            continue
    return None


def _linux_domain_workgroup() -> str | None:
    try:
        result = subprocess.run(["hostname", "-d"], capture_output=True, check=False, text=True, timeout=6)
        value = result.stdout.strip()
        return value or None
    except Exception:
        return None


def _linux_network_adapters() -> list[dict[str, Any]]:
    adapters: list[dict[str, Any]] = []
    sys_class_net = Path("/sys/class/net")
    if not sys_class_net.exists():
        return adapters
    for adapter in sys_class_net.iterdir():
        if adapter.name == "lo":
            continue
        try:
            mac = (adapter / "address").read_text(encoding="utf-8").strip()
        except Exception:
            mac = None
        try:
            state = (adapter / "operstate").read_text(encoding="utf-8").strip()
        except Exception:
            state = None
        adapters.append(
            {
                "name": adapter.name,
                "mac_address": mac,
                "status": state,
                "speed": None,
            }
        )
    return adapters


def _linux_logged_in_users() -> list[dict[str, Any]]:
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


def _linux_running_services(limit: int = 50) -> list[dict[str, Any]]:
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


def _linux_network_traffic() -> dict[str, Any]:
    stats: dict[str, Any] = {}
    try:
        with open("/proc/net/dev", "r", encoding="utf-8") as handle:
            for line in handle.readlines()[2:]:
                if ":" not in line:
                    continue
                iface, values = line.split(":", 1)
                rx_bytes, rx_packets, rx_errs, rx_drop, tx_bytes, tx_packets, tx_errs, tx_drop, *_rest = [int(value) for value in values.split()]
                stats[iface.strip()] = {
                    "rx_bytes": rx_bytes,
                    "tx_bytes": tx_bytes,
                    "rx_packets": rx_packets,
                    "tx_packets": tx_packets,
                    "rx_errors": rx_errs,
                    "tx_errors": tx_errs,
                    "rx_dropped": rx_drop,
                    "tx_dropped": tx_drop,
                }
    except Exception:
        return {}
    return stats


def _windows_collect_adapters() -> list[dict[str, Any]]:
    output = _windows_powershell(
        "Get-NetAdapter | Select-Object Name,InterfaceDescription,Status,MacAddress,LinkSpeed | ConvertTo-Json -Depth 3"
    )
    if not output:
        return []
    try:
        raw = __import__("json").loads(output)
    except Exception:
        return []
    if isinstance(raw, dict):
        raw = [raw]
    adapters: list[dict[str, Any]] = []
    for item in raw or []:
        if not isinstance(item, dict):
            continue
        adapters.append(
            {
                "name": item.get("Name"),
                "description": item.get("InterfaceDescription"),
                "status": item.get("Status"),
                "mac_address": item.get("MacAddress"),
                "speed": item.get("LinkSpeed"),
            }
        )
    return adapters


def _windows_software_inventory(limit: int = 200) -> list[dict[str, Any]]:
    command = r"""
    $paths = @(
      'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*',
      'HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*',
      'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*'
    )
    $items = foreach ($path in $paths) { Get-ItemProperty $path -ErrorAction SilentlyContinue }
    $items | Where-Object { $_.DisplayName } | Select-Object DisplayName, DisplayVersion, Publisher, InstallDate | ConvertTo-Json -Depth 3
    """
    output = _windows_powershell(command)
    if not output:
        return []
    try:
        raw = __import__("json").loads(output)
    except Exception:
        return []
    if isinstance(raw, dict):
        raw = [raw]
    inventory: list[dict[str, Any]] = []
    for item in (raw or [])[:limit]:
        if not isinstance(item, dict):
            continue
        inventory.append(
            {
                "software_id": f"{item.get('DisplayName')}|{item.get('Publisher')}|{item.get('DisplayVersion')}",
                "name": item.get("DisplayName"),
                "version": item.get("DisplayVersion"),
                "publisher": item.get("Publisher"),
                "install_date": item.get("InstallDate"),
            }
        )
    return inventory


def _windows_domain_workgroup() -> str | None:
    return _windows_powershell("(Get-CimInstance Win32_ComputerSystem).Domain")


def _windows_manufacturer() -> str | None:
    return _windows_powershell("(Get-CimInstance Win32_ComputerSystem).Manufacturer")


def _windows_model() -> str | None:
    return _windows_powershell("(Get-CimInstance Win32_ComputerSystem).Model")


def _windows_cpu_model() -> str | None:
    return _windows_powershell("(Get-CimInstance Win32_Processor | Select-Object -First 1 -ExpandProperty Name)")


def _windows_cpu_cores() -> int | None:
    value = _windows_powershell("(Get-CimInstance Win32_Processor | Measure-Object -Property NumberOfLogicalProcessors -Sum).Sum")
    try:
        return int(value) if value else None
    except Exception:
        return None


def _windows_memory_total_gb() -> float | None:
    value = _windows_powershell("(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory")
    try:
        return round(int(value) / (1024**3), 2) if value else None
    except Exception:
        return None


def _windows_os_name() -> str | None:
    return _windows_powershell("(Get-CimInstance Win32_OperatingSystem).Caption")


def _windows_os_version() -> str | None:
    return _windows_powershell("(Get-CimInstance Win32_OperatingSystem).Version")


def _windows_serial_number() -> str | None:
    serial = _windows_powershell("(Get-CimInstance Win32_BIOS | Select-Object -ExpandProperty SerialNumber)")
    if not serial or serial.lower() in {"default string", "to be filled by o.e.m.", "none"}:
        return None
    return serial


def _windows_network_traffic() -> dict[str, Any]:
    output = _windows_powershell("Get-NetAdapterStatistics | Select-Object Name,ReceivedBytes,SentBytes | ConvertTo-Json -Depth 3")
    if not output:
        return {}
    try:
        raw = __import__("json").loads(output)
    except Exception:
        return {}
    if isinstance(raw, dict):
        raw = [raw]
    traffic: dict[str, Any] = {}
    for item in raw or []:
        if not isinstance(item, dict):
            continue
        traffic[str(item.get("Name") or "adapter")] = {
            "rx_bytes": item.get("ReceivedBytes"),
            "tx_bytes": item.get("SentBytes"),
        }
    return traffic


def _windows_logged_in_users() -> list[dict[str, Any]]:
    output = _windows_powershell("query user")
    if not output:
        return []
    users: list[dict[str, Any]] = []
    for line in output.splitlines()[1:]:
      parts = line.split()
      if parts:
          users.append({"user": parts[0].lstrip(">"), "session": parts[1] if len(parts) > 1 else None})
    return users


def _windows_running_services(limit: int = 50) -> list[dict[str, Any]]:
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


def _disk_snapshot() -> dict[str, Any]:
    disk = shutil.disk_usage(os.path.abspath(os.sep))
    return {
        "disk_total_gb": round(disk.total / (1024**3), 2),
        "disk_free_gb": round(disk.free / (1024**3), 2),
        "disk_used_gb": round((disk.total - disk.free) / (1024**3), 2),
        "disk_free_percent": round((disk.free / disk.total) * 100, 2) if disk.total else None,
    }


def collect_profile(org_code: str, agent_version: str) -> dict[str, Any]:
    fingerprint = collect_hardware_fingerprint()
    if is_linux():
        serial_number = linux_serial_number()
        return {
            "organization_id": org_code,
            "device_id": None,
            "hostname": socket.gethostname(),
            "manufacturer": _linux_manufacturer(),
            "model": _linux_model(),
            "serial_number": serial_number,
            "cpu_model": platform.processor() or platform.machine(),
            "cpu_cores": os.cpu_count(),
            "memory_total_gb": _memory_total_gb(),
            "disk": _disk_snapshot(),
            "os_name": linux_distribution_name(),
            "os_version": platform.release(),
            "domain_or_workgroup": _linux_domain_workgroup(),
            "mac_addresses": [item["mac_address"] for item in _linux_network_adapters() if item.get("mac_address")],
            "network_adapters": _linux_network_adapters(),
            "agent_version": agent_version,
            "hardware_fingerprint": fingerprint,
        }

    serial_number = _windows_serial_number()
    return {
        "organization_id": org_code,
        "device_id": None,
        "hostname": socket.gethostname(),
        "manufacturer": _windows_manufacturer(),
        "model": _windows_model(),
        "serial_number": serial_number,
        "cpu_model": _windows_cpu_model() or platform.processor(),
        "cpu_cores": _windows_cpu_cores() or os.cpu_count(),
        "memory_total_gb": _windows_memory_total_gb(),
        "disk": _disk_snapshot(),
        "os_name": _windows_os_name() or platform.platform(),
        "os_version": _windows_os_version() or platform.version(),
        "domain_or_workgroup": _windows_domain_workgroup(),
        "mac_addresses": [item["mac_address"] for item in _windows_collect_adapters() if item.get("mac_address")],
        "network_adapters": _windows_collect_adapters(),
        "agent_version": agent_version,
        "hardware_fingerprint": fingerprint,
    }


def registration_payload(org_code: str, agent_version: str) -> dict[str, Any]:
    profile = collect_profile(org_code, agent_version)
    return {
        "org_code": org_code,
        "hostname": profile["hostname"],
        "serial_number": profile["serial_number"],
        "os_name": profile["os_name"],
        "agent_version": agent_version,
        "hardware_fingerprint": profile["hardware_fingerprint"],
        "hardware_fingerprint_version": 1,
    }


def collect_inventory(org_code: str, agent_version: str) -> dict[str, Any]:
    profile = collect_profile(org_code, agent_version)
    software = [{"name": "python", "version": platform.python_version(), "publisher": "Python Software Foundation"}]
    if is_linux():
        software.extend(linux_package_inventory())
    else:
        software.extend(_windows_software_inventory())

    hardware = {
        "hostname": profile["hostname"],
        "serial_number": profile["serial_number"],
        "machine": platform.machine(),
        "processor": profile["cpu_model"],
        "cpu_count": profile["cpu_cores"],
        "memory_total_gb": profile["memory_total_gb"],
        **profile["disk"],
        "os": profile["os_name"],
    }

    return {
        "profile": profile,
        "hardware": hardware,
        "software": software,
    }
