# OpenDeck HomeTro Toggle Plugin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a new OpenDeck plugin that toggles the HomeTro BLE server with one Stream Deck button.

**Architecture:** Build a standalone Rust OpenDeck plugin, modeled on the existing local plugins, that shells out to `just start` and `just stop` in `/media/david/DATA/repos/hometro-ble`. Server state detection is isolated in a testable Rust module that checks pidfile liveness and configured port listening before updating the button state.

**Tech Stack:** Rust 2021, `openaction`, `tokio`, `serde`, `simplelog`, `just`, OpenDeck plugin assets.

---

## File Structure

- Create repository directory `/media/david/DATA/repos/opendeck-hometro-toggle-plugin`.
- Create `Cargo.toml`, `Cargo.lock`, `rustfmt.toml`, `README.md`, `justfile`.
- Create `src/main.rs`: OpenDeck event handler and settings parsing.
- Create `src/hometro_ops.rs`: server state detection and command execution.
- Create `assets/manifest.json`: OpenDeck action metadata.
- Create `assets/propertyInspector/hometroToggle.html` and `assets/propertyInspector/sdpi.css`: configurable repo path, host, port, pidfile, logfile.
- Create `assets/icons/plugin.svg`, `assets/icons/stopped.svg`, `assets/icons/running.svg`: SVG icon sources with the exact content in Task 3. If OpenDeck requires PNG icons in local testing, export PNGs from these SVGs with the same base names.

## Task 1: Scaffold Plugin Repository

**Files:**
- Create: `/media/david/DATA/repos/opendeck-hometro-toggle-plugin/Cargo.toml`
- Create: `/media/david/DATA/repos/opendeck-hometro-toggle-plugin/rustfmt.toml`
- Create: `/media/david/DATA/repos/opendeck-hometro-toggle-plugin/README.md`
- Create: `/media/david/DATA/repos/opendeck-hometro-toggle-plugin/justfile`

- [ ] **Step 1: Create Cargo manifest**

Create `Cargo.toml`:

```toml
[package]
name = "hometrotoggle"
version = "1.0.0"
authors = ["David"]
license = "GPL-3.0-or-later"
edition = "2021"

[dependencies]
openaction = "1.1"
log = "0.4"
simplelog = "0.12"
serde = "1.0"
serde_json = "1.0"
tokio = { version = "1.48", features = ["full"] }
```

- [ ] **Step 2: Create formatting config**

Create `rustfmt.toml`:

```toml
hard_tabs = true
max_width = 100
```

- [ ] **Step 3: Create justfile**

Create `justfile`:

```just
# Justfile for OpenDeck HomeTro Toggle Plugin

default: build

build:
    cargo build --release

install: build
    #!/usr/bin/env bash
    set -euo pipefail

    PLUGIN_NAME="dev.david.hometro.sdPlugin"
    PLUGIN_DIR="$HOME/.config/opendeck/plugins/$PLUGIN_NAME"

    echo "Installing plugin to $PLUGIN_DIR..."
    mkdir -p "$PLUGIN_DIR/linux/bin"
    cp target/release/hometrotoggle "$PLUGIN_DIR/linux/bin/"
    cp -r assets/icons "$PLUGIN_DIR/"
    cp -r assets/propertyInspector "$PLUGIN_DIR/"
    cp assets/manifest.json "$PLUGIN_DIR/"
    echo "Plugin installed successfully. Restart OpenDeck to load it if it was already running."
```

- [ ] **Step 4: Create README**

Create `README.md`:

```markdown
# HomeTro Toggle Plugin for OpenDeck

OpenDeck plugin to start/stop the HomeTro BLE web app from one Stream Deck button.

Default target repo:

`/media/david/DATA/repos/hometro-ble`

The first press runs `just start`, which starts the server and opens the web UI. The next press runs `just stop`.

## Build

```bash
cargo build --release
```

## Install

```bash
just install
```

Restart OpenDeck after installing.
```

- [ ] **Step 5: Commit scaffold**

```bash
cd /media/david/DATA/repos/opendeck-hometro-toggle-plugin
git init
git add Cargo.toml rustfmt.toml README.md justfile
git commit -m "Initial HomeTro OpenDeck plugin scaffold"
```

## Task 2: Server State and Command Operations

**Files:**
- Create: `src/hometro_ops.rs`

- [ ] **Step 1: Create failing unit tests in `src/hometro_ops.rs`**

Create `src/hometro_ops.rs` with tests first:

```rust
use std::path::PathBuf;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct HometroSettings {
	pub repo_path: PathBuf,
	pub host: String,
	pub port: u16,
	pub pidfile: PathBuf,
	pub logfile: PathBuf,
}

#[cfg(test)]
mod tests {
	use super::*;
	use std::fs;
	use std::net::TcpListener;
	use std::process::Command;

	fn settings(port: u16, pidfile: PathBuf) -> HometroSettings {
		HometroSettings {
			repo_path: PathBuf::from("/media/david/DATA/repos/hometro-ble"),
			host: "127.0.0.1".to_owned(),
			port,
			pidfile,
			logfile: PathBuf::from(".hometro-server.log"),
		}
	}

	#[test]
	fn detects_stopped_when_pidfile_is_missing_and_port_closed() {
		let port = unused_port();
		let dir = tempfile_dir();
		let state = server_state(&settings(port, dir.join("missing.pid")));
		assert_eq!(state, ServerState::Stopped);
	}

	#[test]
	fn detects_running_when_pidfile_process_is_alive_and_port_listens() {
		let listener = TcpListener::bind(("127.0.0.1", 0)).unwrap();
		let port = listener.local_addr().unwrap().port();
		let dir = tempfile_dir();
		let child = Command::new("sleep").arg("30").spawn().unwrap();
		fs::write(dir.join("server.pid"), child.id().to_string()).unwrap();

		let state = server_state(&settings(port, dir.join("server.pid")));

		assert_eq!(state, ServerState::Running);
		let _ = Command::new("kill").arg(child.id().to_string()).status();
	}

	#[test]
	fn stale_pidfile_with_closed_port_is_stopped() {
		let port = unused_port();
		let dir = tempfile_dir();
		fs::write(dir.join("server.pid"), "999999").unwrap();

		let state = server_state(&settings(port, dir.join("server.pid")));

		assert_eq!(state, ServerState::Stopped);
	}

	fn unused_port() -> u16 {
		let listener = TcpListener::bind(("127.0.0.1", 0)).unwrap();
		listener.local_addr().unwrap().port()
	}

	fn tempfile_dir() -> PathBuf {
		let path = std::env::temp_dir().join(format!("hometrotoggle-test-{}", std::process::id()));
		let _ = fs::create_dir_all(&path);
		path
	}
}
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
cd /media/david/DATA/repos/opendeck-hometro-toggle-plugin
cargo test hometro_ops -- --nocapture
```

Expected: missing `ServerState` and `server_state`.

- [ ] **Step 3: Implement operations**

Replace `src/hometro_ops.rs` with:

```rust
use std::net::{SocketAddr, TcpStream};
use std::path::{Path, PathBuf};
use std::process::Command;
use std::time::Duration;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ServerState {
	Stopped,
	Running,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct HometroSettings {
	pub repo_path: PathBuf,
	pub host: String,
	pub port: u16,
	pub pidfile: PathBuf,
	pub logfile: PathBuf,
}

impl HometroSettings {
	pub fn resolved_pidfile(&self) -> PathBuf {
		if self.pidfile.is_absolute() {
			self.pidfile.clone()
		} else {
			self.repo_path.join(&self.pidfile)
		}
	}
}

pub fn server_state(settings: &HometroSettings) -> ServerState {
	let port_open = is_port_open(&settings.host, settings.port);
	let pid_alive = read_pid(&settings.resolved_pidfile()).is_some_and(is_pid_alive);
	if port_open || pid_alive && port_open {
		ServerState::Running
	} else {
		ServerState::Stopped
	}
}

pub async fn start(settings: &HometroSettings) -> Result<(), String> {
	run_just(settings, "start").await
}

pub async fn stop(settings: &HometroSettings) -> Result<(), String> {
	run_just(settings, "stop").await
}

async fn run_just(settings: &HometroSettings, recipe: &str) -> Result<(), String> {
	let settings = settings.clone();
	let recipe = recipe.to_owned();
	tokio::task::spawn_blocking(move || {
		let output = Command::new("just")
			.arg(recipe)
			.current_dir(&settings.repo_path)
			.env("HOMETRO_HOST", &settings.host)
			.env("HOMETRO_PORT", settings.port.to_string())
			.env("HOMETRO_PIDFILE", &settings.pidfile)
			.env("HOMETRO_LOGFILE", &settings.logfile)
			.output()
			.map_err(|error| format!("failed to run just: {error}"))?;
		if output.status.success() {
			Ok(())
		} else {
			let stderr = String::from_utf8_lossy(&output.stderr);
			Err(format!("just failed: {stderr}"))
		}
	})
	.await
	.map_err(|error| format!("task failed: {error}"))?
}

fn is_port_open(host: &str, port: u16) -> bool {
	let Ok(addr) = format!("{host}:{port}").parse::<SocketAddr>() else {
		return false;
	};
	TcpStream::connect_timeout(&addr, Duration::from_millis(150)).is_ok()
}

fn read_pid(path: &Path) -> Option<u32> {
	std::fs::read_to_string(path).ok()?.trim().parse().ok()
}

fn is_pid_alive(pid: u32) -> bool {
	Command::new("kill")
		.arg("-0")
		.arg(pid.to_string())
		.status()
		.is_ok_and(|status| status.success())
}

#[cfg(test)]
mod tests {
	// Keep the exact test module created in Step 1 below this implementation.
}
```

Keep the tests from Step 1 at the bottom.

- [ ] **Step 4: Run operation tests**

Run:

```bash
cd /media/david/DATA/repos/opendeck-hometro-toggle-plugin
cargo test hometro_ops -- --nocapture
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
cd /media/david/DATA/repos/opendeck-hometro-toggle-plugin
git add src/hometro_ops.rs
git commit -m "Add HomeTro server operations"
```

## Task 3: OpenDeck Runtime and Assets

**Files:**
- Create: `src/main.rs`
- Create: `assets/manifest.json`
- Create: `assets/propertyInspector/hometroToggle.html`
- Create: `assets/propertyInspector/sdpi.css`
- Create: `assets/icons/plugin.svg`
- Create: `assets/icons/stopped.svg`
- Create: `assets/icons/running.svg`

- [ ] **Step 1: Implement OpenDeck event handler**

Create `src/main.rs`:

```rust
//! OpenDeck plugin for toggling the HomeTro BLE local web app.

mod hometro_ops;

use hometro_ops::{HometroSettings, ServerState};
use openaction::*;
use serde::Deserialize;
use std::path::PathBuf;

const ACTION_UUID: &str = "dev.david.hometro.toggle";

#[derive(Debug, Clone, Deserialize)]
#[serde(rename_all = "camelCase")]
struct PluginSettings {
	#[serde(default = "default_repo_path")]
	repo_path: String,
	#[serde(default = "default_host")]
	host: String,
	#[serde(default = "default_port")]
	port: u16,
	#[serde(default = "default_pidfile")]
	pidfile: String,
	#[serde(default = "default_logfile")]
	logfile: String,
}

impl PluginSettings {
	fn from_value(value: &serde_json::Value) -> Self {
		serde_json::from_value(value.clone()).unwrap_or_default()
	}

	fn ops_settings(&self) -> HometroSettings {
		HometroSettings {
			repo_path: PathBuf::from(non_empty(&self.repo_path, default_repo_path())),
			host: non_empty(&self.host, default_host()),
			port: if self.port == 0 { default_port() } else { self.port },
			pidfile: PathBuf::from(non_empty(&self.pidfile, default_pidfile())),
			logfile: PathBuf::from(non_empty(&self.logfile, default_logfile())),
		}
	}
}

impl Default for PluginSettings {
	fn default() -> Self {
		Self {
			repo_path: default_repo_path(),
			host: default_host(),
			port: default_port(),
			pidfile: default_pidfile(),
			logfile: default_logfile(),
		}
	}
}

fn non_empty(value: &str, fallback: String) -> String {
	if value.trim().is_empty() {
		fallback
	} else {
		value.trim().to_owned()
	}
}

fn default_repo_path() -> String {
	"/media/david/DATA/repos/hometro-ble".to_owned()
}

fn default_host() -> String {
	"127.0.0.1".to_owned()
}

fn default_port() -> u16 {
	8000
}

fn default_pidfile() -> String {
	".hometro-server.pid".to_owned()
}

fn default_logfile() -> String {
	".hometro-server.log".to_owned()
}

struct GlobalEventHandler {}
impl openaction::GlobalEventHandler for GlobalEventHandler {}

struct ActionEventHandler {}

impl openaction::ActionEventHandler for ActionEventHandler {
	async fn will_appear(
		&self,
		event: AppearEvent,
		outbound: &mut OutboundEventManager,
	) -> EventHandlerResult {
		if event.action != ACTION_UUID {
			return Ok(());
		}
		let settings = PluginSettings::from_value(&event.payload.settings).ops_settings();
		set_button_state(outbound, event.context, hometro_ops::server_state(&settings)).await
	}

	async fn key_up(
		&self,
		event: KeyEvent,
		outbound: &mut OutboundEventManager,
	) -> EventHandlerResult {
		if event.action != ACTION_UUID {
			return Ok(());
		}

		let settings = PluginSettings::from_value(&event.payload.settings).ops_settings();
		let current = hometro_ops::server_state(&settings);
		set_button_state(outbound, event.context.clone(), current).await?;

		let result = match current {
			ServerState::Stopped => hometro_ops::start(&settings).await,
			ServerState::Running => hometro_ops::stop(&settings).await,
		};

		if let Err(error) = result {
			log::error!("HomeTro operation failed: {}", error);
			outbound.show_alert(event.context.clone()).await?;
		}

		set_button_state(outbound, event.context, hometro_ops::server_state(&settings)).await
	}
}

async fn set_button_state(
	outbound: &mut OutboundEventManager,
	context: String,
	state: ServerState,
) -> EventHandlerResult {
	let button_state = match state {
		ServerState::Stopped => 0,
		ServerState::Running => 1,
	};
	outbound.set_state(context, button_state).await?;
	Ok(())
}

#[tokio::main]
async fn main() {
	simplelog::TermLogger::init(
		simplelog::LevelFilter::Debug,
		simplelog::Config::default(),
		simplelog::TerminalMode::Stdout,
		simplelog::ColorChoice::Never,
	)
	.unwrap();

	if let Err(error) = init_plugin(GlobalEventHandler {}, ActionEventHandler {}).await {
		log::error!("Failed to initialise plugin: {}", error);
	}
}
```

- [ ] **Step 2: Create manifest**

Create `assets/manifest.json`:

```json
{
  "Name": "HomeTro Toggle",
  "Description": "Start or stop the HomeTro BLE web app",
  "Author": "David",
  "Version": "1.0.0",
  "CodePathLin": "linux/bin/hometrotoggle",
  "Icon": "icons/plugin",
  "Category": "Fitness",
  "OS": [
    {
      "Platform": "linux",
      "MinimumVersion": "1"
    }
  ],
  "Actions": [
    {
      "Icon": "icons/stopped",
      "Name": "Toggle HomeTro",
      "States": [
        {
          "Image": "icons/stopped"
        },
        {
          "Image": "icons/running"
        }
      ],
      "Controllers": [
        "Keypad"
      ],
      "Tooltip": "Start or stop HomeTro BLE and open the web UI",
      "UUID": "dev.david.hometro.toggle",
      "PropertyInspectorPath": "propertyInspector/hometroToggle.html"
    }
  ]
}
```

- [ ] **Step 3: Create property inspector**

Create `assets/propertyInspector/hometroToggle.html`:

```html
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8" />
    <title>HomeTro Toggle</title>
    <link rel="stylesheet" href="sdpi.css">
</head>
<body>
    <div class="sdpi-wrapper">
        <div class="sdpi-item">
            <div class="sdpi-item-label">Repo</div>
            <input class="sdpi-item-value" id="repoPath" />
        </div>
        <div class="sdpi-item">
            <div class="sdpi-item-label">Host</div>
            <input class="sdpi-item-value" id="host" />
        </div>
        <div class="sdpi-item">
            <div class="sdpi-item-label">Port</div>
            <input class="sdpi-item-value" id="port" type="number" min="1" max="65535" />
        </div>
        <div class="sdpi-item">
            <div class="sdpi-item-label">Pidfile</div>
            <input class="sdpi-item-value" id="pidfile" />
        </div>
        <div class="sdpi-item">
            <div class="sdpi-item-label">Logfile</div>
            <input class="sdpi-item-value" id="logfile" />
        </div>
    </div>
    <script>
        let websocket = null;
        let context = null;

        function connectElgatoStreamDeckSocket(inPort, inUUID, inRegisterEvent, inInfo, inActionInfo) {
            const actionInfo = JSON.parse(inActionInfo);
            context = actionInfo.context;
            const settings = actionInfo.payload.settings || {};

            document.getElementById("repoPath").value = settings.repoPath || "/media/david/DATA/repos/hometro-ble";
            document.getElementById("host").value = settings.host || "127.0.0.1";
            document.getElementById("port").value = settings.port || 8000;
            document.getElementById("pidfile").value = settings.pidfile || ".hometro-server.pid";
            document.getElementById("logfile").value = settings.logfile || ".hometro-server.log";

            websocket = new WebSocket("ws://127.0.0.1:" + inPort);
            websocket.onopen = function () {
                websocket.send(JSON.stringify({ event: inRegisterEvent, uuid: inUUID }));
            };

            for (const id of ["repoPath", "host", "port", "pidfile", "logfile"]) {
                document.getElementById(id).addEventListener("change", updateSettings);
            }
        }

        function updateSettings() {
            websocket.send(JSON.stringify({
                event: "setSettings",
                context: context,
                payload: {
                    repoPath: document.getElementById("repoPath").value,
                    host: document.getElementById("host").value,
                    port: Number(document.getElementById("port").value) || 8000,
                    pidfile: document.getElementById("pidfile").value,
                    logfile: document.getElementById("logfile").value
                }
            }));
        }
    </script>
</body>
</html>
```

- [ ] **Step 4: Copy CSS and create icons**

Copy `sdpi.css` from `/media/david/DATA/repos/opendeck-webcam-recorder-plugin/assets/propertyInspector/sdpi.css`.

Create `assets/icons/plugin.svg`:

```xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 144 144">
  <rect width="144" height="144" rx="24" fill="#12171f"/>
  <path d="M35 88h74c8 0 14 6 14 14s-6 14-14 14H35c-8 0-14-6-14-14s6-14 14-14Z" fill="#2b3440"/>
  <path d="M42 72h60c5 0 9 4 9 9v7H33v-7c0-5 4-9 9-9Z" fill="#44515f"/>
  <path d="M54 62c0-13 8-24 18-24s18 11 18 24" fill="none" stroke="#00d8a7" stroke-width="10" stroke-linecap="round"/>
  <circle cx="45" cy="102" r="6" fill="#00d8a7"/>
  <circle cx="99" cy="102" r="6" fill="#00d8a7"/>
</svg>
```

Create `assets/icons/stopped.svg`:

```xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 144 144">
  <rect width="144" height="144" rx="24" fill="#17191d"/>
  <circle cx="72" cy="72" r="46" fill="#2a2d33"/>
  <rect x="49" y="49" width="46" height="46" rx="8" fill="#d65a5a"/>
  <path d="M36 112h72" stroke="#59616b" stroke-width="10" stroke-linecap="round"/>
</svg>
```

Create `assets/icons/running.svg`:

```xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 144 144">
  <rect width="144" height="144" rx="24" fill="#101b18"/>
  <circle cx="72" cy="72" r="46" fill="#15342d"/>
  <path d="M58 46l42 26-42 26V46Z" fill="#00d8a7"/>
  <path d="M36 112h72" stroke="#3ce6bd" stroke-width="10" stroke-linecap="round"/>
</svg>
```


- [ ] **Step 5: Build**

Run:

```bash
cd /media/david/DATA/repos/opendeck-hometro-toggle-plugin
cargo fmt
cargo test
cargo build --release
```

Expected: all pass and `target/release/hometrotoggle` exists.

- [ ] **Step 6: Commit runtime and assets**

```bash
cd /media/david/DATA/repos/opendeck-hometro-toggle-plugin
git add src assets Cargo.lock
git commit -m "Add HomeTro OpenDeck toggle runtime"
```

## Task 4: Manual Verification

**Files:**
- No source changes expected.

- [ ] **Step 1: Verify without default server**

Use temporary settings so the default `hometro-ble` server is not affected:

```bash
cd /media/david/DATA/repos/hometro-ble
HOMETRO_PORT=18000 HOMETRO_PIDFILE=/tmp/hometro-opendeck-test.pid HOMETRO_LOGFILE=/tmp/hometro-opendeck-test.log just start
HOMETRO_PORT=18000 HOMETRO_PIDFILE=/tmp/hometro-opendeck-test.pid HOMETRO_LOGFILE=/tmp/hometro-opendeck-test.log just stop
```

Expected: start opens `http://127.0.0.1:18000`; stop stops only the process using the temporary pidfile/port.

- [ ] **Step 2: Install plugin**

Run:

```bash
cd /media/david/DATA/repos/opendeck-hometro-toggle-plugin
just install
```

Expected: plugin files copied into `~/.config/opendeck/plugins/dev.david.hometro.sdPlugin`.

- [ ] **Step 3: Configure temporary test settings in OpenDeck**

In OpenDeck property inspector, set:

- Port: `18000`
- Pidfile: `/tmp/hometro-opendeck-test.pid`
- Logfile: `/tmp/hometro-opendeck-test.log`

Press once to start, verify browser opens and icon turns running. Press again, verify server stops and icon turns stopped.

## Self-Review

- Spec coverage: new repo, existing plugin isolation, `just start`/`just stop`, property inspector settings, pidfile/port state check, OpenDeck state locking, and manual verification are covered.
- Safety: plugin does not issue raw `kill`; it delegates stop to `hometro-ble`'s `just stop`.
- Remaining manual risk: OpenDeck icon format may require PNGs; if SVGs do not render in OpenDeck, export PNGs with the same base names and keep SVGs as sources.
