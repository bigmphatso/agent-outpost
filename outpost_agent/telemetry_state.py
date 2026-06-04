from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def state_path(config_dir: Path) -> Path:
    return config_dir / "agent-telemetry-state.json"


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(state, indent=2, sort_keys=True, ensure_ascii=False), encoding="utf-8")
    temp.replace(path)


def stable_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _record_map(items: list[dict[str, Any]], key_fields: tuple[str, ...], default_prefix: str) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        key = next((str(item.get(field)) for field in key_fields if item.get(field)), "")
        if not key:
            key = f"{default_prefix}:{stable_hash(item)}"
        records[key] = item
    return records


def diff_software(previous: list[dict[str, Any]], current: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    prev_map = _record_map(previous, ("software_id", "name"), "software")
    curr_map = _record_map(current, ("software_id", "name"), "software")

    added = [item for key, item in curr_map.items() if key not in prev_map]
    removed = [item for key, item in prev_map.items() if key not in curr_map]
    updated = [item for key, item in curr_map.items() if key in prev_map and stable_hash(item) != stable_hash(prev_map[key])]
    return {"added": added, "removed": removed, "updated": updated}


def diff_findings(previous: list[dict[str, Any]], current: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    prev_map = _record_map(previous, ("finding_id", "vulnerability_id", "update_id", "title"), "finding")
    curr_map = _record_map(current, ("finding_id", "vulnerability_id", "update_id", "title"), "finding")

    added = [item for key, item in curr_map.items() if key not in prev_map]
    removed = [item for key, item in prev_map.items() if key not in curr_map]
    updated = [item for key, item in curr_map.items() if key in prev_map and stable_hash(item) != stable_hash(prev_map[key])]
    return {"added": added, "removed": removed, "updated": updated}
