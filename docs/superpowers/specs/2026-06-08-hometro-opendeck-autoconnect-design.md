# HomeTro OpenDeck Launcher and Autoconnect Design

Date: 2026-06-08

## Goal

Add a Stream Deck button that toggles the local HomeTro BLE web app:

- First press starts `/media/david/DATA/repos/hometro-ble` with its existing `just start` flow, then opens the web UI in the browser.
- Second press stops the server with the existing `just stop` flow.
- The button icon reflects actual server state after checking the configured port and pidfile.

Also add automatic treadmill connection inside `hometro-ble`:

- On server startup, connect automatically to the last treadmill that connected successfully.
- If no last treadmill is saved, scan for known treadmill devices and connect only when exactly one known candidate exists.
- If automatic connection fails or is ambiguous, keep the server and UI usable; the user can still scan and connect manually.

## Non-Goals

- Do not change the existing VPN, vault, or webcam OpenDeck plugins.
- Do not make the OpenDeck plugin talk to BLE APIs directly.
- Do not stop, restart, or connect/disconnect a currently running HomeTro server during design or implementation unless explicitly allowed.
- Do not auto-start treadmill motion. Autoconnect only establishes BLE control; running still requires a user action.

## OpenDeck Plugin Design

Create a new repository:

`/media/david/DATA/repos/opendeck-hometro-toggle-plugin`

Use the same structure as the existing plugins:

- Rust binary using `openaction`.
- `assets/manifest.json`.
- `assets/propertyInspector/hometroToggle.html`.
- `assets/icons/{stopped,running,plugin}`.
- `justfile` with `build` and `install`.

The plugin has one action: `dev.david.hometro.toggle`.

Default settings:

- `repoPath`: `/media/david/DATA/repos/hometro-ble`
- `host`: `127.0.0.1`
- `port`: `8000`
- `pidfile`: `.hometro-server.pid`
- `logfile`: `.hometro-server.log`

On `will_appear`, the plugin checks whether the server is running. It should prefer the pidfile when it points to a live process and confirm that the configured port is listening. If the pidfile is stale, it should treat the server as stopped unless the configured port is listening.

On `key_up`:

- If the server is stopped, run `just start` in `repoPath`.
- If the server is running, run `just stop` in `repoPath`.
- Set the button state to the verified state before and after the operation to avoid OpenDeck's default visual auto-toggle racing ahead of reality.
- Show an alert on command failure.

The plugin should pass `HOMETRO_HOST`, `HOMETRO_PORT`, `HOMETRO_PIDFILE`, and `HOMETRO_LOGFILE` to the `just` commands so property inspector settings are honored without changing the repo's defaults.

## HomeTro Autoconnect Design

Add a small persistence module, for example `src/hometro_ble/known_devices.py`, responsible for remembering successful treadmill connections.

Storage:

- Default path: `$XDG_STATE_HOME/hometro-ble/known-devices.json`
- Fallback path: `~/.local/state/hometro-ble/known-devices.json`
- Test override: `HOMETRO_KNOWN_DEVICES_FILE`

Record format:

```json
{
  "last_connected": {
    "address": "66:99:D4:F6:7B:30",
    "name": "FS-0099C3",
    "connected_at": "2026-06-08T12:00:00Z"
  }
}
```

Persistence rules:

- Save the address after `TreadmillController.connect_to(address)` succeeds.
- If the server starts with an explicit CLI address, use that address and save it after successful connection.
- Never save failed attempts.
- Do not clear saved devices on disconnect.

Autoconnect flow:

1. `create_app()` creates the controller as it does today.
2. On FastAPI startup, schedule a background autoconnect task.
3. If the controller already has an address, try `controller.connect()`.
4. Otherwise, load `last_connected.address` and try `controller.connect_to(address)`.
5. If there is no saved address, scan known treadmill devices with a short timeout and connect only when exactly one candidate is found.
6. If there are zero candidates, multiple candidates, or a connection error, publish a non-fatal error state and leave manual scan/connect available.

The frontend should not need major changes. It already renders backend state and reports backend errors. A small notification may be added if the backend exposes a clear autoconnect failure message, but manual connection must keep working.

## Testing

HomeTro tests:

- Unit-test known device storage path selection, load, save, and corrupt-file handling.
- Controller test: successful `connect_to()` records the known device.
- Web app test: startup autoconnect tries the saved address.
- Web app test: no saved address scans and connects when exactly one known treadmill exists.
- Web app test: no saved address does not connect when multiple known treadmills exist.

OpenDeck plugin tests/checks:

- Rust unit tests for server-state detection using temporary pidfiles and ports.
- Rust unit tests for command environment construction.
- `cargo test`.
- `cargo build --release`.

Manual verification after approval:

- Do not use the user's active default server.
- Either wait until the active running session is done, or use a temporary `HOMETRO_PORT`, `HOMETRO_PIDFILE`, and `HOMETRO_LOGFILE`.
- Verify first press starts and opens the UI.
- Verify second press stops only the process started through the configured pidfile/port.

## Safety Notes

The plugin should shell out only to `just start` and `just stop` in the configured repo path. It should not issue raw `kill` commands itself.

Autoconnection must never send start, speed, pause, resume, or stop treadmill commands. Shutdown behavior remains the existing server behavior: disconnect with `stop_first=True`.

Existing OpenDeck plugin repositories are read-only references for this work.
