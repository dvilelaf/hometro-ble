import json
from pathlib import Path

from hometro_ble import known_devices


def test_state_file_uses_env_override(monkeypatch, tmp_path: Path) -> None:
    target = tmp_path / "known.json"
    monkeypatch.setenv("HOMETRO_KNOWN_DEVICES_FILE", str(target))

    assert known_devices.state_file() == target


def test_state_file_uses_xdg_state_home(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("HOMETRO_KNOWN_DEVICES_FILE", raising=False)
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))

    assert known_devices.state_file() == tmp_path / "hometro-ble" / "known-devices.json"


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


def test_blank_address_is_not_saved(monkeypatch, tmp_path: Path) -> None:
    target = tmp_path / "known.json"
    monkeypatch.setenv("HOMETRO_KNOWN_DEVICES_FILE", str(target))

    known_devices.save_last_connected("   ")

    assert not target.exists()
