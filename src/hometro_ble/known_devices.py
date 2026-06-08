from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class KnownDevice:
    address: str
    name: str | None
    connected_at: str


def state_file() -> Path:
    if override := os.environ.get("HOMETRO_KNOWN_DEVICES_FILE"):
        return Path(override)

    state_home = os.environ.get("XDG_STATE_HOME")
    base = Path(state_home) if state_home else Path.home() / ".local/state"
    return base / "hometro-ble" / "known-devices.json"


def load_last_connected() -> KnownDevice | None:
    try:
        payload = json.loads(state_file().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    record = payload.get("last_connected") if isinstance(payload, dict) else None
    if not isinstance(record, dict):
        return None

    address = record.get("address")
    connected_at = record.get("connected_at")
    if not isinstance(address, str) or not address.strip():
        return None
    if not isinstance(connected_at, str) or not connected_at.strip():
        return None

    name = record.get("name")
    return KnownDevice(
        address=address.strip(),
        name=name.strip() if isinstance(name, str) and name.strip() else None,
        connected_at=connected_at,
    )


def save_last_connected(address: str, *, name: str | None = None) -> None:
    address = address.strip()
    if not address:
        return

    record = KnownDevice(
        address=address,
        name=name.strip() if isinstance(name, str) and name.strip() else None,
        connected_at=datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
    )
    path = state_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"last_connected": asdict(record)}, indent=2) + "\n",
        encoding="utf-8",
    )
