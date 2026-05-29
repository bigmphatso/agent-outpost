from __future__ import annotations

import os
import platform
import shutil
import subprocess
from pathlib import Path


def is_linux() -> bool:
    return platform.system().lower() == "linux"


def read_first_existing(paths: list[str]) -> str | None:
    for raw_path in paths:
        path = Path(raw_path)
        try:
            value = path.read_text(encoding="utf-8", errors="ignore").strip()
        except Exception:
            continue
        if value and value.lower() not in {"none", "unknown", "not specified", "to be filled by o.e.m."}:
            return value
    return None


def run_command(args: list[str], timeout: int = 8) -> str | None:
    try:
        completed = subprocess.run(args, capture_output=True, check=False, text=True, timeout=timeout)
    except Exception:
        return None
    if completed.returncode != 0:
        return None
    output = completed.stdout.strip()
    return output or None


def command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def linux_serial_number() -> str | None:
    if not is_linux():
        return None
    return read_first_existing(
        [
            "/sys/class/dmi/id/product_serial",
            "/sys/class/dmi/id/board_serial",
            "/sys/class/dmi/id/chassis_serial",
        ]
    )


def linux_os_release() -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        with open("/etc/os-release", "r", encoding="utf-8") as handle:
            for line in handle:
                if "=" not in line:
                    continue
                key, value = line.rstrip().split("=", 1)
                values[key] = value.strip().strip('"')
    except Exception:
        pass
    return values


def linux_distribution_name() -> str:
    release = linux_os_release()
    return release.get("PRETTY_NAME") or platform.platform()


def linux_package_inventory(limit: int = 50) -> list[dict[str, str]]:
    if not is_linux():
        return []

    packages: list[dict[str, str]] = []
    if command_exists("dpkg-query"):
        output = run_command(["dpkg-query", "-W", "-f=${binary:Package}\t${Version}\n"], timeout=20)
        if output:
            for line in output.splitlines()[:limit]:
                name, _, version = line.partition("\t")
                if name:
                    packages.append({"name": name, "version": version})
            return packages

    if command_exists("rpm"):
        output = run_command(["rpm", "-qa", "--qf", "%{NAME}\t%{VERSION}-%{RELEASE}\n"], timeout=20)
        if output:
            for line in output.splitlines()[:limit]:
                name, _, version = line.partition("\t")
                if name:
                    packages.append({"name": name, "version": version})
            return packages

    if command_exists("pacman"):
        output = run_command(["pacman", "-Q"], timeout=20)
        if output:
            for line in output.splitlines()[:limit]:
                name, _, version = line.partition(" ")
                if name:
                    packages.append({"name": name, "version": version})
            return packages

    if command_exists("apk"):
        output = run_command(["apk", "info", "-v"], timeout=20)
        if output:
            for line in output.splitlines()[:limit]:
                if line:
                    packages.append({"name": line, "version": ""})
    return packages


def linux_pending_update_count() -> int:
    if not is_linux():
        return 0

    if command_exists("apt"):
        output = run_command(["apt", "list", "--upgradable"], timeout=30)
        if output:
            return len([line for line in output.splitlines() if "/" in line and not line.lower().startswith("listing")])

    if command_exists("dnf"):
        try:
            completed = subprocess.run(["dnf", "check-update", "--quiet"], capture_output=True, check=False, text=True, timeout=30)
            output = completed.stdout.strip()
        except Exception:
            output = ""
        if output:
            return len([line for line in output.splitlines() if line and not line.startswith("Last metadata")])

    if command_exists("yum"):
        try:
            completed = subprocess.run(["yum", "check-update", "--quiet"], capture_output=True, check=False, text=True, timeout=30)
            output = completed.stdout.strip()
        except Exception:
            output = ""
        if output:
            return len([line for line in output.splitlines() if line and not line.startswith("Loaded plugins")])

    if command_exists("pacman"):
        output = run_command(["checkupdates"], timeout=30)
        if output:
            return len(output.splitlines())

    if command_exists("apk"):
        output = run_command(["apk", "version", "-l", "<"], timeout=30)
        if output:
            return len(output.splitlines())

    return 0


def linux_antivirus_status() -> tuple[bool, bool, int]:
    if not is_linux():
        return True, True, 0

    has_clamscan = command_exists("clamscan") or command_exists("clamdscan")
    has_freshclam = command_exists("freshclam")
    enabled = has_clamscan

    if command_exists("systemctl"):
        for service in ("clamav-daemon", "clamd@scan", "clamd"):
            active = run_command(["systemctl", "is-active", service], timeout=5)
            if active == "active":
                enabled = True
                break

    signature_age_days = 0
    candidates = [
        "/var/lib/clamav/daily.cvd",
        "/var/lib/clamav/daily.cld",
        "/var/lib/clamav/main.cvd",
        "/var/lib/clamav/main.cld",
    ]
    mtimes = []
    for candidate in candidates:
        try:
            mtimes.append(Path(candidate).stat().st_mtime)
        except Exception:
            continue
    if mtimes:
        signature_age_days = max(0, int((__import__("time").time() - max(mtimes)) / 86400))

    return has_clamscan or has_freshclam, enabled, signature_age_days


def linux_suspicious_process_count() -> int:
    if not is_linux() or not os.path.isdir("/proc"):
        return 0

    suspicious = 0
    for entry in os.scandir("/proc"):
        if not entry.name.isdigit():
            continue
        exe_path = Path(entry.path) / "exe"
        try:
            target = os.readlink(exe_path)
        except Exception:
            continue
        if target.startswith(("/tmp/", "/var/tmp/", "/dev/shm/")):
            suspicious += 1
    return suspicious
