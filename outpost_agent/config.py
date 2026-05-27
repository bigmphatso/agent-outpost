from __future__ import annotations

import json
import os
import base64
import ctypes
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


def save_config(config: AgentConfig, path: Path | None = None) -> Path:
    config_path = path or default_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    payload = asdict(config)
    api_key = payload.pop("api_key", None)
    if api_key:
        payload["api_key_protected"] = protect_secret(api_key)
    config_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return config_path


def load_config(path: Path | None = None) -> AgentConfig:
    config_path = path or default_config_path()
    raw_config = json.loads(config_path.read_text(encoding="utf-8"))
    if "org_code" not in raw_config and "activation_code" in raw_config:
        raw_config["org_code"] = raw_config.pop("activation_code")
    if "api_key_protected" in raw_config:
        raw_config["api_key"] = unprotect_secret(raw_config.pop("api_key_protected"))
    return AgentConfig(**raw_config)
