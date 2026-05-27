from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RegistryValue:
    name: str
    value: Any
    value_type: int


def is_windows() -> bool:
    return sys.platform.startswith("win")


def _import_winreg():
    if not is_windows():
        raise RuntimeError("winreg is only available on Windows.")
    import winreg  # type: ignore

    return winreg


def read_values(root: int, path: str) -> list[RegistryValue]:
    winreg = _import_winreg()
    values: list[RegistryValue] = []
    try:
        with winreg.OpenKey(root, path) as key:
            index = 0
            while True:
                try:
                    name, value, value_type = winreg.EnumValue(key, index)
                except OSError:
                    break
                values.append(RegistryValue(name=name, value=value, value_type=value_type))
                index += 1
    except OSError:
        return []
    return values


def read_string(root: int, path: str, name: str) -> str | None:
    winreg = _import_winreg()
    try:
        with winreg.OpenKey(root, path) as key:
            value, _ = winreg.QueryValueEx(key, name)
            return str(value)
    except OSError:
        return None


def list_subkeys(root: int, path: str) -> list[str]:
    winreg = _import_winreg()
    names: list[str] = []
    try:
        with winreg.OpenKey(root, path) as key:
            index = 0
            while True:
                try:
                    names.append(winreg.EnumKey(key, index))
                except OSError:
                    break
                index += 1
    except OSError:
        return []
    return names

