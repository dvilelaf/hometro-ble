import asyncio
from typing import Any

import pytest

import hometro_ble.web as web_module
from hometro_ble.models import AdvertisementRecord, TreadmillState
from hometro_ble.web import create_app


class FakeController:
    def __init__(self, address: str = "", *, timeout: float = 15.0, on_connected=None) -> None:
        self.address = address
        self.timeout = timeout
        self.on_connected = on_connected
        self.connected_to: list[str] = []
        self.state = TreadmillState(address=address)
        self.published = 0

    async def connect(self) -> dict[str, Any]:
        self.connected_to.append(self.address)
        if self.on_connected:
            self.on_connected(self.address)
        return {"address": self.address, "connected": True}

    async def connect_to(self, address: str) -> dict[str, Any]:
        self.address = address
        self.state.address = address
        return await self.connect()

    async def disconnect(self, *, stop_first: bool = True) -> dict[str, Any]:
        return {"connected": False}

    async def connection_toggle(self) -> dict[str, Any]:
        return {"connected": True}

    async def play(self) -> dict[str, Any]:
        return {"ok": True}

    async def primary_action(self) -> dict[str, Any]:
        return {"ok": True}

    async def stop(self) -> dict[str, Any]:
        return {"ok": True}

    async def pause_toggle(self) -> dict[str, Any]:
        return {"ok": True}

    async def set_speed(self, speed_kmh: float) -> dict[str, Any]:
        return {"speed_kmh": speed_kmh}

    async def subscribe(self):
        raise AssertionError("not used by autoconnect tests")

    def unsubscribe(self, queue) -> None:
        raise AssertionError("not used by autoconnect tests")

    async def _publish(self) -> None:
        self.published += 1


class FailingController(FakeController):
    async def connect_to(self, address: str) -> dict[str, Any]:
        self.address = address
        raise RuntimeError("bluetooth unavailable")


def treadmill(address: str, *, name: str = "FS-0099C3") -> AdvertisementRecord:
    return AdvertisementRecord(
        address=address,
        name=name,
        details="",
        rssi=-60,
        local_name=name,
        manufacturer_data={},
        service_data={},
        service_uuids=[],
        tx_power=None,
    )


def test_app_exposes_controller_for_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(web_module, "TreadmillController", FakeController)

    app = create_app("66:99:D4:F6:7B:30", timeout=3)

    assert isinstance(app.state.controller, FakeController)
    assert app.state.controller.address == "66:99:D4:F6:7B:30"
    assert app.state.controller.timeout == 3


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


def test_autoconnect_failure_is_non_fatal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(web_module, "TreadmillController", FailingController)
    monkeypatch.setattr(
        web_module.known_devices,
        "load_last_connected",
        lambda: web_module.known_devices.KnownDevice("66:99:D4:F6:7B:30", "FS-0099C3", "now"),
    )
    app = create_app("")

    asyncio.run(web_module.autoconnect(app.state.controller, scan_timeout=0.01))

    assert app.state.controller.state.last_error == "autoconnect failed: bluetooth unavailable"
    assert app.state.controller.published == 1
