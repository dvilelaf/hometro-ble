import subprocess


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
