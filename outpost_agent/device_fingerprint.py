from __future__ import annotations

import hashlib
import re
import subprocess
import sys


UNKNOWN_COMPONENT = "UNKNOWN_COMPONENT"


_GENERIC_PATTERNS = [
    re.compile(r"^0{8}-0{4}-0{4}-0{4}-0{12}$", re.IGNORECASE),
    re.compile(r"^to be filled by o\.e\.m\.$", re.IGNORECASE),
    re.compile(r"^default string$", re.IGNORECASE),
]


def _is_windows() -> bool:
    return sys.platform.startswith("win")


def _normalize(raw: str | None) -> str | None:
    if raw is None:
        return None
    value = raw.strip()
    if not value:
        return None
    lowered = value.lower()
    for pattern in _GENERIC_PATTERNS:
        if pattern.match(lowered):
            return None
    return value


def _hash_component(raw: str | None) -> str:
    normalized = _normalize(raw)
    if not normalized:
        return UNKNOWN_COMPONENT
    cleaned = normalized.replace("-", "").strip().lower()
    return hashlib.sha256(cleaned.encode("utf-8")).hexdigest()


def _powershell(command: str) -> str | None:
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        capture_output=True,
        text=True,
        timeout=12,
        check=False,
    )
    if completed.returncode != 0:
        return None
    return completed.stdout.strip() or None


def collect_hardware_fingerprint() -> dict[str, str]:
    """
    Best-effort Windows hardware fingerprint components.

    Strategy aligns with docs/Hardware_Device_ID_Strategy.pdf:
    - Motherboard UUID (SMBIOS system UUID)
    - TPM Endorsement Key public hash (when available)
    - CPU ProcessorId
    """
    if not _is_windows():
        return {
            "motherboard_uuid": UNKNOWN_COMPONENT,
            "tpm_endorsement_hash": UNKNOWN_COMPONENT,
            "cpu_id": UNKNOWN_COMPONENT,
        }

    uuid = _powershell("(Get-CimInstance Win32_ComputerSystemProduct).UUID")
    cpu_id = _powershell("(Get-CimInstance Win32_Processor).ProcessorId")
    tpm_hash = _powershell("(Get-TpmEndorsementKeyInfo).PublicKeyHash")

    return {
        "motherboard_uuid": _hash_component(uuid),
        "tpm_endorsement_hash": _hash_component(tpm_hash),
        "cpu_id": _hash_component(cpu_id),
    }

