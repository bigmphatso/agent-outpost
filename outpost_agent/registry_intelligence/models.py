from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RegistrySnapshot:
    device_identity: dict[str, Any] = field(default_factory=dict)
    usb_devices: dict[str, Any] = field(default_factory=dict)
    autoruns: dict[str, Any] = field(default_factory=dict)


@dataclass
class RegistryEvent:
    event_type: str
    timestamp: str
    device_id: str
    organization_id: str | None = None
    risk_score: int = 0
    severity: str = "low"
    summary: str = ""
    data: dict[str, Any] = field(default_factory=dict)

