# HomeTro Autoconnect Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist the last successfully connected treadmill and automatically reconnect on server startup, falling back to a scan only when there is exactly one known treadmill candidate.

**Architecture:** Add a focused persistence module for known device state, call it from `TreadmillController` after successful connections, and add a FastAPI startup task that performs non-blocking autoconnect. The frontend continues to render backend state through the existing `/api/state` and SSE flow.

**Tech Stack:** Python 3.11, FastAPI, asyncio, Bleak abstractions, pytest.

---

## File Structure

- Create `src/hometro_ble/known_devices.py`: load/save last successful treadmill connection and resolve the state file path.
- Modify `src/hometro_ble/controller.py`: save successful `connect_to()` connections through an injectable recorder function.
- Modify `src/hometro_ble/web.py`: add startup autoconnect orchestration and dependency injection for tests.
- Create `tests/test_known_devices.py`: storage path, load/save, and corrupt-file behavior.
- Modify `tests/test_controller.py`: assert successful `connect_to()` records the device and failed attempts do not.
- Create `tests/test_web_autoconnect.py`: startup autoconnect cases.

## Task 1: Known Device Storage

**Files:**
- Create: `src/hometro_ble/known_devices.py`
- Test: `tests/test_known_devices.py`

- [ ] **Step 1: Write failing storage tests**

Create `tests/test_known_devices.py`:

```python
import json
from pathlib import Path

from hometro_ble import known_devices


def test_state_file_uses_env_override(monkeypatch, tmp_path: Path) -> None:
    target = tmp_path / "known.json"
    monkeypatch.setenv("HOMETRO_KNOWN_DEVICES_FILE", str(target))

    assert known_devices.state_file() == target


def test_save_and_load_last_connected(monkeypatch, tmp_path: Path) -> None:
    target = tmp_path / "known.json"
    monkeypatch.setenv("HOMETRO_KNOWN_DEVICES_FILE", str(target))

    known_devices.save_last_connected("66:99:D4:F6:7B:30", name="FS-0099C3")

    record = known_devices.load_last_connected()
    assert record is not None
    assert record.address == "66:99:D4:F6:7B:30"
    assert record.name == "FS-0099C3"
    assert record.connected_at.endswith("+00:00")


def test_load_missing_file_returns_none(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOMETRO_KNOWN_DEVICES_FILE", str(tmp_path / "missing.json"))

    assert known_devices.load_last_connected() is None


def test_load_corrupt_file_returns_none(monkeypatch, tmp_path: Path) -> None:
    target = tmp_path / "known.json"
    target.write_text("{not-json", encoding="utf-8")
    monkeypatch.setenv("HOMETRO_KNOWN_DEVICES_FILE", str(target))

    assert known_devices.load_last_connected() is None


def test_load_invalid_record_returns_none(monkeypatch, tmp_path: Path) -> None:
    target = tmp_path / "known.json"
    target.write_text(json.dumps({"last_connected": {"name": "FS-0099C3"}}), encoding="utf-8")
    monkeypatch.setenv("HOMETRO_KNOWN_DEVICES_FILE", str(target))

    assert known_devices.load_last_connected() is None
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
cd /media/david/DATA/repos/hometro-ble
pytest tests/test_known_devices.py -v
```

Expected: import failure because `hometro_ble.known_devices` does not exist.

- [ ] **Step 3: Implement storage module**

Create `src/hometro_ble/known_devices.py`:

```python
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


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
    path = state_file()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    record = payload.get("last_connected") if isinstance(payload, dict) else None
    if not isinstance(record, dict):
        return None
    address = record.get("address")
    if not isinstance(address, str) or not address.strip():
        return None
    name = record.get("name")
    connected_at = record.get("connected_at")
    if not isinstance(connected_at, str):
        return None
    return KnownDevice(address=address.strip(), name=name if isinstance(name, str) else None, connected_at=connected_at)


def save_last_connected(address: str, *, name: str | None = None) -> None:
    address = address.strip()
    if not address:
        return
    record = KnownDevice(
        address=address,
        name=name.strip() if isinstance(name, str) and name.strip() else None,
        connected_at=datetime.now(UTC).isoformat(timespec="milliseconds"),
    )
    path = state_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"last_connected": asdict(record)}, indent=2) + "\n", encoding="utf-8")
```

- [ ] **Step 4: Run tests and verify pass**

Run:

```bash
cd /media/david/DATA/repos/hometro-ble
pytest tests/test_known_devices.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
cd /media/david/DATA/repos/hometro-ble
git add src/hometro_ble/known_devices.py tests/test_known_devices.py
git commit -m "Add known treadmill storage"
```

## Task 2: Record Successful Connections

**Files:**
- Modify: `src/hometro_ble/controller.py`
- Modify: `tests/test_controller.py`

- [ ] **Step 1: Write failing controller tests**

Append to `tests/test_controller.py`:

```python
def test_connect_to_records_successful_device(monkeypatch: pytest.MonkeyPatch):
    setup_fake_bleak(monkeypatch, fail_attempts=0)
    saved: list[str] = []

    def save(address: str) -> None:
        saved.append(address)

    controller = TreadmillController("66:99:D4:F6:7B:30", on_connected=save)

    asyncio.run(controller.connect_to("66:99:D4:F6:7B:30"))

    assert saved == ["66:99:D4:F6:7B:30"]


def test_connect_to_does_not_record_failed_device(monkeypatch: pytest.MonkeyPatch):
    setup_fake_bleak(monkeypatch, fail_attempts=2)
    saved: list[str] = []
    controller = TreadmillController("66:99:D4:F6:7B:30", on_connected=saved.append)

    with pytest.raises(RuntimeError, match="bluez stale connection"):
        asyncio.run(controller.connect_to("66:99:D4:F6:7B:30"))

    assert saved == []
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
cd /media/david/DATA/repos/hometro-ble
pytest tests/test_controller.py::test_connect_to_records_successful_device tests/test_controller.py::test_connect_to_does_not_record_failed_device -v
```

Expected: constructor rejects `on_connected`.

- [ ] **Step 3: Implement connection recorder**

Modify `src/hometro_ble/controller.py`:

```python
from collections.abc import Callable
```

Update constructor:

```python
    def __init__(
        self,
        address: str = "",
        *,
        timeout: float = 15.0,
        on_connected: Callable[[str], None] | None = None,
    ) -> None:
        self.address = address
        self.timeout = timeout
        self._on_connected = on_connected
```

Keep existing fields unchanged after those assignments.

At the end of `connect_to()`, record only after success:

```python
        state = await self.connect()
        if self._on_connected:
            self._on_connected(self.address)
        return state
```

- [ ] **Step 4: Run controller tests**

Run:

```bash
cd /media/david/DATA/repos/hometro-ble
pytest tests/test_controller.py -v
```

Expected: all controller tests pass.

- [ ] **Step 5: Commit**

```bash
cd /media/david/DATA/repos/hometro-ble
git add src/hometro_ble/controller.py tests/test_controller.py
git commit -m "Record successful treadmill connections"
```

## Task 3: Server Startup Autoconnect

**Files:**
- Modify: `src/hometro_ble/web.py`
- Create: `tests/test_web_autoconnect.py`

- [ ] **Step 1: Write failing web autoconnect tests**

Create `tests/test_web_autoconnect.py`:

```python
import asyncio

import pytest

import hometro_ble.web as web_module
from hometro_ble.models import AdvertisementRecord
from hometro_ble.web import create_app


class FakeController:
    def __init__(self, address: str = "", *, timeout: float = 15.0, on_connected=None) -> None:
        self.address = address
        self.timeout = timeout
        self.on_connected = on_connected
        self.connected_to: list[str] = []

    async def connect(self) -> dict:
        self.connected_to.append(self.address)
        if self.on_connected:
            self.on_connected(self.address)
        return {"address": self.address, "connected": True}

    async def connect_to(self, address: str) -> dict:
        self.address = address
        return await self.connect()

    async def disconnect(self, *, stop_first: bool = True) -> dict:
        return {"connected": False}

    def state_snapshot(self) -> dict:
        return {"address": self.address}


def treadmill(address: str) -> AdvertisementRecord:
    return AdvertisementRecord(
        address=address,
        name="FS-0099C3",
        details="",
        rssi=-60,
        local_name="FS-0099C3",
        manufacturer_data={},
        service_data={},
        service_uuids=[],
        tx_power=None,
    )


@pytest.mark.parametrize("address", ["66:99:D4:F6:7B:30", ""])
def test_app_exposes_controller_for_tests(monkeypatch: pytest.MonkeyPatch, address: str) -> None:
    monkeypatch.setattr(web_module, "TreadmillController", FakeController)

    app = create_app(address, timeout=3)

    assert isinstance(app.state.controller, FakeController)
    assert app.state.controller.address == address


def test_autoconnect_uses_explicit_address(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(web_module, "TreadmillController", FakeController)
    app = create_app("66:99:D4:F6:7B:30")

    asyncio.run(web_module.autoconnect(app.state.controller, scan_timeout=0.01))

    assert app.state.controller.connected_to == ["66:99:D4:F6:7B:30"]


def test_autoconnect_uses_saved_address(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(web_module, "TreadmillController", FakeController)
    monkeypatch.setattr(
        web_module.known_devices,
        "load_last_connected",
        lambda: web_module.known_devices.KnownDevice("66:99:D4:F6:7B:30", "FS-0099C3", "now"),
    )
    app = create_app("")

    asyncio.run(web_module.autoconnect(app.state.controller, scan_timeout=0.01))

    assert app.state.controller.connected_to == ["66:99:D4:F6:7B:30"]


def test_autoconnect_scans_when_no_saved_address(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(web_module, "TreadmillController", FakeController)
    monkeypatch.setattr(web_module.known_devices, "load_last_connected", lambda: None)

    async def fake_scan_devices(timeout: float, contains: str | None = None):
        return [treadmill("66:99:D4:F6:7B:30")]

    monkeypatch.setattr(web_module, "scan_devices", fake_scan_devices)
    app = create_app("")

    asyncio.run(web_module.autoconnect(app.state.controller, scan_timeout=0.01))

    assert app.state.controller.connected_to == ["66:99:D4:F6:7B:30"]


def test_autoconnect_skips_ambiguous_scan(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(web_module, "TreadmillController", FakeController)
    monkeypatch.setattr(web_module.known_devices, "load_last_connected", lambda: None)

    async def fake_scan_devices(timeout: float, contains: str | None = None):
        return [treadmill("A"), treadmill("B")]

    monkeypatch.setattr(web_module, "scan_devices", fake_scan_devices)
    app = create_app("")

    asyncio.run(web_module.autoconnect(app.state.controller, scan_timeout=0.01))

    assert app.state.controller.connected_to == []
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
cd /media/david/DATA/repos/hometro-ble
pytest tests/test_web_autoconnect.py -v
```

Expected: `autoconnect` or `app.state.controller` missing.

- [ ] **Step 3: Implement startup autoconnect**

Modify imports in `src/hometro_ble/web.py`:

```python
import asyncio
import contextlib

from . import known_devices
from .ble_ops import scan_devices
```

Replace controller creation in `create_app()` with:

```python
    def remember_connected(address: str) -> None:
        known_devices.save_last_connected(address)

    controller = TreadmillController(address, timeout=timeout, on_connected=remember_connected)
    app = FastAPI(title="HomeTro BLE")
    app.state.controller = controller
```

Add startup handler inside `create_app()`:

```python
    @app.on_event("startup")
    async def startup_autoconnect() -> None:
        asyncio.create_task(autoconnect(controller))
```

Add module-level autoconnect helper:

```python
async def autoconnect(controller: TreadmillController, *, scan_timeout: float = 2.0) -> None:
    try:
        if controller.address:
            await controller.connect()
            return

        if saved := known_devices.load_last_connected():
            await controller.connect_to(saved.address)
            return

        rows = await scan_devices(timeout=scan_timeout)
        candidates = [row for row in rows if row.address and row.is_known_treadmill()]
        if len(candidates) == 1 and candidates[0].address:
            await controller.connect_to(candidates[0].address)
    except Exception as exc:
        controller.state.last_error = f"autoconnect failed: {exc}"
        controller.state.last_event_ts = utc_now()
        with contextlib.suppress(Exception):
            await controller._publish()
```

Import `utc_now` from `.models`.

- [ ] **Step 4: Run web tests**

Run:

```bash
cd /media/david/DATA/repos/hometro-ble
pytest tests/test_web_autoconnect.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Run full HomeTro test suite**

Run:

```bash
cd /media/david/DATA/repos/hometro-ble
pytest -v
```

Expected: all tests pass. Do not run `just start`, `just stop`, or live BLE tests.

- [ ] **Step 6: Commit**

```bash
cd /media/david/DATA/repos/hometro-ble
git add src/hometro_ble/web.py tests/test_web_autoconnect.py
git commit -m "Autoconnect known treadmill on startup"
```

## Self-Review

- Spec coverage: storage, successful recording, explicit-address autoconnect, saved-address autoconnect, scan fallback, ambiguous-scan skip, and non-fatal failures are covered.
- Safety: no test starts or stops the default server and no test sends treadmill motion commands.
- Remaining manual verification: after implementation, start on a temporary port or after the active server is no longer needed.
