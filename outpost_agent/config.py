from __future__ import annotations

import json
import os
import base64
import ctypes
import getpass
import stat
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path


APP_DIR_NAME = "OUTPOST"
CONFIG_FILE_NAME = "agent-config.json"
PROTECTED_PREFIX = "dpapi:"


def default_config_dir() -> Path:
    program_data = os.environ.get("PROGRAMDATA")
    if program_data:
        return Path(program_data) / APP_DIR_NAME
    return Path.home() / ".outpost"


def default_config_path() -> Path:
    return default_config_dir() / CONFIG_FILE_NAME


@dataclass
class AgentConfig:
    backend_url: str
    org_code: str
    agent_version: str = "0.1.0"
    poll_interval_seconds: int = 30
    device_id: str | None = None
    api_key: str | None = None


class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", ctypes.c_ulong), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]


def _is_windows() -> bool:
    return os.name == "nt"


def _blob_from_bytes(data: bytes) -> tuple[_DataBlob, ctypes.Array]:
    buffer = ctypes.create_string_buffer(data)
    return _DataBlob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte))), buffer


def _bytes_from_blob(blob: _DataBlob) -> bytes:
    return ctypes.string_at(blob.pbData, blob.cbData)


def protect_secret(secret: str) -> str:
    if not secret:
        return ""
    if not _is_windows():
        return secret

    data_in, _data_buffer = _blob_from_bytes(secret.encode("utf-8"))
    data_out = _DataBlob()
    ok = ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(data_in), None, None, None, None, 0, ctypes.byref(data_out)
    )
    if not ok:
        raise OSError("Failed to protect API key with Windows DPAPI.")
    try:
        return PROTECTED_PREFIX + base64.b64encode(_bytes_from_blob(data_out)).decode("ascii")
    finally:
        ctypes.windll.kernel32.LocalFree(data_out.pbData)


def unprotect_secret(value: str | None) -> str | None:
    if not value:
        return None
    if not value.startswith(PROTECTED_PREFIX):
        return value
    if not _is_windows():
        return None

    data_in, _data_buffer = _blob_from_bytes(base64.b64decode(value[len(PROTECTED_PREFIX) :]))
    data_out = _DataBlob()
    ok = ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(data_in), None, None, None, None, 0, ctypes.byref(data_out)
    )
    if not ok:
        return None
    try:
        return _bytes_from_blob(data_out).decode("utf-8")
    finally:
        ctypes.windll.kernel32.LocalFree(data_out.pbData)


def _run_icacls(args: list[str]) -> None:
    result = subprocess.run(["icacls", *args], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        message = (result.stderr or result.stdout or "icacls failed").strip()
        raise OSError(message)


def harden_path_permissions(path: Path) -> None:
    if _is_windows():
        path.parent.mkdir(parents=True, exist_ok=True)
        current_user = f"{os.environ.get('USERDOMAIN', '')}\\{getpass.getuser()}".strip("\\")
        _run_icacls([str(path.parent), "/inheritance:r"])
        _run_icacls([str(path.parent), "/grant:r", "SYSTEM:(OI)(CI)F", "Administrators:(OI)(CI)F", f"{current_user}:(OI)(CI)F"])
        if path.exists():
            _run_icacls([str(path), "/inheritance:r"])
            _run_icacls([str(path), "/grant:r", "SYSTEM:F", "Administrators:F", f"{current_user}:F"])
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    path.parent.chmod(0o700)
    if path.exists():
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def sanitize_config_payload(raw_config: dict) -> dict:
    payload = dict(raw_config)
    raw_api_key = payload.pop("api_key", None)
    if raw_api_key:
        payload["api_key_protected"] = protect_secret(str(raw_api_key))
    return payload


def save_config(config: AgentConfig, path: Path | None = None) -> Path:
    config_path = path or default_config_path()
    harden_path_permissions(config_path)
    payload = asdict(config)
    api_key = payload.pop("api_key", None)
    if api_key:
        payload["api_key_protected"] = protect_secret(api_key)
    temp_path = config_path.with_suffix(".tmp")
    temp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    harden_path_permissions(temp_path)
    temp_path.replace(config_path)
    harden_path_permissions(config_path)
    return config_path


def load_config(path: Path | None = None) -> AgentConfig:
    config_path = path or default_config_path()
    raw_config = json.loads(config_path.read_text(encoding="utf-8"))
    sanitized = sanitize_config_payload(raw_config)
    if sanitized != raw_config:
        config_path.write_text(json.dumps(sanitized, indent=2), encoding="utf-8")
        harden_path_permissions(config_path)
        raw_config = sanitized
    if "org_code" not in raw_config and "activation_code" in raw_config:
        raw_config["org_code"] = raw_config.pop("activation_code")
    if "api_key_protected" in raw_config:
        raw_config["api_key"] = unprotect_secret(raw_config.pop("api_key_protected"))
    return AgentConfig(**raw_config)


def config_security_summary(path: Path | None = None) -> dict[str, object]:
    config_path = path or default_config_path()
    exists = config_path.exists()
    has_plaintext_secret = False
    has_protected_secret = False
    if exists:
        try:
            raw_config = json.loads(config_path.read_text(encoding="utf-8"))
            has_plaintext_secret = bool(raw_config.get("api_key"))
            has_protected_secret = bool(raw_config.get("api_key_protected"))
        except Exception:
            pass
    return {
        "path": str(config_path),
        "exists": exists,
        "has_plaintext_secret": has_plaintext_secret,
        "has_protected_secret": has_protected_secret,
    }
