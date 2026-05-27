from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path


APP_DIR_NAME = "OUTPOST"
CONFIG_FILE_NAME = "agent-config.json"


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


def save_config(config: AgentConfig, path: Path | None = None) -> Path:
    config_path = path or default_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(asdict(config), indent=2), encoding="utf-8")
    return config_path


def load_config(path: Path | None = None) -> AgentConfig:
    config_path = path or default_config_path()
    raw_config = json.loads(config_path.read_text(encoding="utf-8"))
    if "org_code" not in raw_config and "activation_code" in raw_config:
        raw_config["org_code"] = raw_config.pop("activation_code")
    return AgentConfig(**raw_config)
