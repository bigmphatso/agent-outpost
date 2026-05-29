from __future__ import annotations

import json
import platform
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from outpost_agent.linux_platform import is_linux as is_linux_platform
from outpost_agent.linux_platform import linux_distribution_name, linux_os_release, read_first_existing, run_command
from outpost_agent.registry_intelligence.models import RegistryEvent, RegistrySnapshot
from outpost_agent.registry_intelligence.windows_registry import is_windows


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _severity_for_score(score: int) -> str:
    if score >= 80:
        return "critical"
    if score >= 60:
        return "high"
    if score >= 35:
        return "medium"
    return "low"


def load_snapshot(path: Path) -> RegistrySnapshot | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        snap = RegistrySnapshot()
        snap.device_identity = raw.get("device_identity", {}) or {}
        snap.usb_devices = raw.get("usb_devices", {}) or {}
        snap.autoruns = raw.get("autoruns", {}) or {}
        return snap
    except Exception:
        return None


def save_snapshot(path: Path, snapshot: RegistrySnapshot) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(snapshot), indent=2, sort_keys=True), encoding="utf-8")


def collect_snapshot() -> RegistrySnapshot:
    if is_linux_platform():
        snapshot = RegistrySnapshot()
        release = linux_os_release()
        snapshot.device_identity = {
            "platform": "linux",
            "distribution": linux_distribution_name(),
            "kernel": platform.release(),
            "machine_id_present": bool(read_first_existing(["/etc/machine-id", "/var/lib/dbus/machine-id"])),
            "product_uuid_present": bool(read_first_existing(["/sys/class/dmi/id/product_uuid"])),
            "id": release.get("ID"),
            "version_id": release.get("VERSION_ID"),
        }

        usb_devices: dict[str, Any] = {}
        for block_device in Path("/sys/block").glob("*"):
            try:
                removable = (block_device / "removable").read_text(encoding="utf-8").strip()
            except Exception:
                continue
            if removable != "1":
                continue
            usb_devices[block_device.name] = {
                "device": block_device.name,
                "model": read_first_existing([str(block_device / "device/model")]),
                "vendor": read_first_existing([str(block_device / "device/vendor")]),
                "size_sectors": read_first_existing([str(block_device / "size")]),
            }
        snapshot.usb_devices = usb_devices

        autoruns: dict[str, Any] = {}
        enabled_units = run_command(["systemctl", "list-unit-files", "--state=enabled", "--no-legend"], timeout=12)
        if enabled_units:
            autoruns["systemd_enabled_units"] = {
                line.split()[0]: line.split()[1] if len(line.split()) > 1 else "enabled"
                for line in enabled_units.splitlines()
                if line.strip()
            }
        cron_paths = ["/etc/crontab", "/etc/cron.d", "/etc/cron.daily", "/etc/cron.hourly", "/etc/cron.weekly", "/etc/cron.monthly"]
        cron_entries = {}
        for cron_path in cron_paths:
            path = Path(cron_path)
            if path.is_file():
                cron_entries[str(path)] = {"kind": "file", "mode": oct(path.stat().st_mode & 0o777)}
            elif path.is_dir():
                cron_entries[str(path)] = sorted(child.name for child in path.iterdir() if not child.name.startswith("."))
        if cron_entries:
            autoruns["cron"] = cron_entries
        snapshot.autoruns = autoruns
        return snapshot

    if not is_windows():
        return RegistrySnapshot()

    # Avoid importing winreg on non-Windows.
    from outpost_agent.registry_intelligence.windows_registry import list_subkeys, read_string, read_values  # noqa: WPS433

    import winreg  # type: ignore  # noqa: WPS433

    snapshot = RegistrySnapshot()

    snapshot.device_identity = {
        "product_name": read_string(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion", "ProductName"),
        "current_build": read_string(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion", "CurrentBuild"),
        "display_version": read_string(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion", "DisplayVersion"),
        "computer_name": read_string(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\ComputerName\ComputerName", "ComputerName"),
        "time_zone": read_string(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\TimeZoneInformation", "TimeZoneKeyName"),
    }

    usbstor_root = r"SYSTEM\CurrentControlSet\Enum\USBSTOR"
    usb_devices: dict[str, Any] = {}
    for device_class in list_subkeys(winreg.HKEY_LOCAL_MACHINE, usbstor_root):
        for instance in list_subkeys(winreg.HKEY_LOCAL_MACHINE, f"{usbstor_root}\\{device_class}"):
            values = read_values(winreg.HKEY_LOCAL_MACHINE, f"{usbstor_root}\\{device_class}\\{instance}")
            usb_devices[f"{device_class}\\{instance}"] = {v.name: v.value for v in values}
    snapshot.usb_devices = usb_devices

    autoruns: dict[str, Any] = {}
    run_keys = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"),
    ]
    for root, key_path in run_keys:
        values = read_values(root, key_path)
        autoruns[f"{root}:{key_path}"] = {v.name: v.value for v in values if v.name}
    snapshot.autoruns = autoruns

    return snapshot


def diff_events(
    *,
    previous: RegistrySnapshot | None,
    current: RegistrySnapshot,
    device_id: str,
    organization_id: str | None,
) -> list[RegistryEvent]:
    events: list[RegistryEvent] = []

    if previous is None:
        # First snapshot: don't spam backend; treat as baseline.
        return events

    # USB insertions: new USBSTOR entries.
    prev_usb = set((previous.usb_devices or {}).keys())
    curr_usb = set((current.usb_devices or {}).keys())
    new_usb = sorted(curr_usb - prev_usb)
    for key in new_usb:
        data = current.usb_devices.get(key, {}) if isinstance(current.usb_devices, dict) else {}
        score = 45
        events.append(
            RegistryEvent(
                event_type="USB_DEVICE_FIRST_SEEN",
                timestamp=now_iso(),
                device_id=device_id,
                organization_id=organization_id,
                risk_score=score,
                severity=_severity_for_score(score),
                summary="New USB storage device first seen (metadata only).",
                data={"registry_key": key, "properties": data},
            )
        )

    # Autoruns: new Run values.
    prev_runs = previous.autoruns or {}
    curr_runs = current.autoruns or {}
    for scope, values in curr_runs.items():
        prev_values = prev_runs.get(scope, {}) if isinstance(prev_runs, dict) else {}
        if not isinstance(values, dict) or not isinstance(prev_values, dict):
            continue
        new_names = sorted(set(values.keys()) - set(prev_values.keys()))
        for name in new_names:
            score = 65
            events.append(
                RegistryEvent(
                    event_type="AUTORUN_ADDED",
                    timestamp=now_iso(),
                    device_id=device_id,
                    organization_id=organization_id,
                    risk_score=score,
                    severity=_severity_for_score(score),
                    summary="New startup entry added (Run key).",
                    data={"scope": scope, "name": name, "command": str(values.get(name))[:512]},
                )
            )

    return events


def run_registry_intelligence_tick(
    *,
    snapshot_path: Path,
    device_id: str,
    organization_id: str | None,
) -> list[dict[str, Any]]:
    result = run_registry_intelligence_scan(
        snapshot_path=snapshot_path,
        device_id=device_id,
        organization_id=organization_id,
    )
    return result["events"]


def run_registry_intelligence_scan(
    *,
    snapshot_path: Path,
    device_id: str,
    organization_id: str | None,
) -> dict[str, Any]:
    previous = load_snapshot(snapshot_path)
    current = collect_snapshot()
    events = diff_events(previous=previous, current=current, device_id=device_id, organization_id=organization_id)
    save_snapshot(snapshot_path, current)
    return {"events": [asdict(event) for event in events], "snapshot": asdict(current), "collected_at": now_iso()}
