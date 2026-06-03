import os
import socket
import subprocess
import time
from pathlib import Path


def unused_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_for_port(port: int, *, timeout_s: float = 3.0) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        with socket.socket() as sock:
            sock.settimeout(0.2)
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                return True
        time.sleep(0.1)
    return False


def test_start_recipe_runs_server_and_opens_frontend() -> None:
    result = subprocess.run(
        ["just", "--dry-run", "start"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    dry_run = result.stdout + result.stderr
    assert "just run" in dry_run
    assert "http://127.0.0.1:8000" in dry_run
    assert "HOMETRO_OPEN_CMD" in dry_run


def test_run_ignores_stale_pidfile_when_port_is_not_listening(tmp_path: Path) -> None:
    port = unused_port()
    pidfile = tmp_path / "hometro-server.pid"
    logfile = tmp_path / "hometro-server.log"
    sleeper = subprocess.Popen(["sleep", "60"])
    pidfile.write_text(str(sleeper.pid), encoding="utf-8")
    env = {
        **os.environ,
        "HOMETRO_PORT": str(port),
        "HOMETRO_PIDFILE": str(pidfile),
        "HOMETRO_LOGFILE": str(logfile),
    }

    try:
        result = subprocess.run(
            ["just", "run"],
            check=False,
            capture_output=True,
            text=True,
            env=env,
        )

        assert result.returncode == 0, result.stderr
        assert wait_for_port(port), result.stdout + result.stderr
    finally:
        subprocess.run(["just", "stop"], check=False, capture_output=True, text=True, env=env)
        sleeper.terminate()
        try:
            sleeper.wait(timeout=1)
        except subprocess.TimeoutExpired:
            sleeper.kill()


def test_start_recovers_if_browser_opener_interrupts_server(tmp_path: Path) -> None:
    port = unused_port()
    pidfile = tmp_path / "hometro-server.pid"
    logfile = tmp_path / "hometro-server.log"
    opener = tmp_path / "opener"
    opener.write_text("#!/usr/bin/env bash\njust stop >/dev/null 2>&1\n", encoding="utf-8")
    opener.chmod(0o755)
    env = {
        **os.environ,
        "HOMETRO_PORT": str(port),
        "HOMETRO_PIDFILE": str(pidfile),
        "HOMETRO_LOGFILE": str(logfile),
        "HOMETRO_OPEN_CMD": str(opener),
    }

    try:
        result = subprocess.run(
            ["just", "start"],
            check=False,
            capture_output=True,
            text=True,
            env=env,
        )

        assert result.returncode == 0, result.stderr
        assert wait_for_port(port), result.stdout + result.stderr
    finally:
        subprocess.run(["just", "stop"], check=False, capture_output=True, text=True, env=env)
