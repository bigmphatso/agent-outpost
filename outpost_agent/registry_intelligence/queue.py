from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def append_events(path: Path, events: list[dict[str, Any]], *, max_bytes: int = 2_000_000) -> None:
    if not events:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    existing_size = path.stat().st_size if path.exists() else 0
    if existing_size > max_bytes:
        # Drop queue if it grew too large (fail-safe).
        path.unlink(missing_ok=True)

    with path.open("a", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event, separators=(",", ":"), ensure_ascii=False) + "\n")


def read_batch(path: Path, *, limit: int = 100) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if len(events) >= limit:
                break
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except Exception:
                continue
    return events


def drop_batch(path: Path, *, count: int) -> None:
    if not path.exists() or count <= 0:
        return
    lines = path.read_text(encoding="utf-8").splitlines()
    remaining = lines[count:]
    if not remaining:
        path.unlink(missing_ok=True)
        return
    path.write_text("\n".join(remaining) + "\n", encoding="utf-8")

