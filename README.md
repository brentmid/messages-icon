# messages-icon

A lightweight macOS HTTP server that shows your Apple Messages unread count as a dynamic browser favicon.

Pin it as a tab, or create a web app (e.g., in Microsoft Edge or Chrome) to get a dock icon that updates with your unread message count — even on machines that aren't signed into iCloud.

## Requirements

- **macOS** (uses the Dock Accessibility API via `osascript`)
- **Python 3.11+** (stdlib only — no `pip install` needed)
- **Messages app** must be running (the server reads the dock badge count)
- **Accessibility permission** for Terminal (or whichever app runs the server) — grant in System Settings > Privacy & Security > Accessibility

## Quick Start

```bash
python3 server.py
```

Then open `http://localhost:8429` in your browser. From another machine on your LAN, use `http://<your-mac-ip>:8429`.

To create a persistent "app" in Edge: navigate to the URL, then **Settings > Apps > Install this site as an app**.

## Auto-Start (LaunchAgent)

To start the server automatically on login, copy and customize the example plist:

```bash
# Edit the example — update Label, Python path, and script path for your system
cp messages-icon.plist.example ~/Library/LaunchAgents/com.example.messages-icon.plist
vi ~/Library/LaunchAgents/com.example.messages-icon.plist

# Load
launchctl load ~/Library/LaunchAgents/com.example.messages-icon.plist

# Unload
launchctl unload ~/Library/LaunchAgents/com.example.messages-icon.plist
```

To customize port, poll interval, or bind address, add flags to the `ProgramArguments` array in the plist (e.g., `--port`, `--poll-interval`, `--bind`).

> **Note:** The Python process running the server needs **Accessibility permission** (System Settings > Privacy & Security > Accessibility) to read the dock badge.

## Configuration

| Option | CLI Arg | Env Var | Default |
|--------|---------|---------|---------|
| Port | `--port` | `MESSAGES_ICON_PORT` | `8429` |
| Poll interval (seconds) | `--poll-interval` | `MESSAGES_ICON_POLL_INTERVAL` | `30` |
| Bind address | `--bind` | `MESSAGES_ICON_BIND` | `0.0.0.0` |

```bash
# Examples
python3 server.py --port 9000 --poll-interval 10
python3 server.py --bind 127.0.0.1  # localhost only
```

## How It Works

The server uses the macOS Dock Accessibility API (via `osascript`) to read the Messages app's dock badge count — the exact number macOS displays on the Messages icon in your Dock. This is more reliable than `lsappinfo` (which returns NULL for Messages on recent macOS) or querying the Messages SQLite database directly (which returns stale data due to iCloud sync).

The webpage polls `/api/count` at the configured interval and uses the HTML Canvas API to render a dynamic favicon: a green iMessage-style speech bubble with a red badge showing the unread count.

### API

`GET /api/count` returns:

```json
{"unread": 3}
```

Or, if Messages isn't running:

```json
{"unread": 0, "error": "Messages app is not running"}
```

## Privacy

This server exposes **only the unread count** — an integer. It never reads, stores, or transmits message content, sender information, or any other personal data.

## License

MIT — see [LICENSE](LICENSE).
