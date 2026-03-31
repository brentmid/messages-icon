# CLAUDE.md

## Project Overview

messages-icon is a lightweight, zero-dependency Python HTTP server that exposes Apple Messages' unread count as a dynamic browser favicon and PWA dock badge. Install it as a web app (Edge/Chrome) on any machine on your LAN to see your unread message count without needing iCloud sign-in.

## Development Environment

- **OS**: macOS only (uses the Dock Accessibility API via `osascript`)
- **Python**: 3.11+ (stdlib only, no external dependencies)
- **GitHub**: `brentmid/messages-icon` (public, MIT license)

## Development Commands

```bash
# Run the server (default: 0.0.0.0:8429, 30s poll interval)
python3 server.py

# With HTTPS (required for PWA dock badge)
python3 server.py --https

# Custom port and poll interval
python3 server.py --https --port 9000 --poll-interval 10

# Bind to localhost only
python3 server.py --bind 127.0.0.1
```

## Configuration

| Option | CLI Arg | Env Var | Default |
|--------|---------|---------|---------|
| Port | `--port` | `MESSAGES_ICON_PORT` | `8429` |
| Poll interval (seconds) | `--poll-interval` | `MESSAGES_ICON_POLL_INTERVAL` | `30` |
| Bind address | `--bind` | `MESSAGES_ICON_BIND` | `0.0.0.0` |
| Enable HTTPS | `--https` | `MESSAGES_ICON_HTTPS` | `false` |
| Certificate directory | `--cert-dir` | `MESSAGES_ICON_CERT_DIR` | `./certs` |
| Extra TLS hostnames | `--hostname` | *(none)* | *(none, repeatable)* |

## Architecture

Single-file server (`server.py`) with four HTTP routes:

- `GET /` — HTML page with inline CSS/JS. JavaScript polls the API and uses `navigator.setAppBadge()` to update the PWA dock badge.
- `GET /api/count` — Returns JSON `{"unread": N}`. Calls `osascript` to read the Messages dock badge via the Accessibility API.
- `GET /apple-touch-icon.png` — Returns a green bubble SVG icon for iOS home screen bookmarks and PWA install.
- `GET /manifest.json` — PWA web app manifest for "Install as app" flow.

The favicon is a plain green iMessage-style speech bubble rendered client-side via Canvas (transparent background, no count overlay). The unread count badge is handled by the PWA Badging API (`navigator.setAppBadge()`), which requires HTTPS.

## Critical Guidelines

### Security (Public Repo)
- **No hardcoded paths** containing usernames or home directories
- **No credentials** — this project needs none (no API keys, no OAuth)
- **No message content** is ever read or exposed — only the integer badge count
- **GitHub issues**: never include IP addresses, paths with usernames, or other PII
- **Generated certs** (`certs/`, `*.pem`) are gitignored — never commit

### Git Workflow
- **Branch naming**: `feature/<issue-number>-<short-description>`, `bugfix/<issue-number>-<short-description>`
- **Commit format**: Conventional commits — `feat:`, `fix:`, `docs:`, `chore:`
- **Issue closing**: Each issue needs its own `closes` keyword: `Closes #1, closes #2`

## How the Dock Badge Read Works

```applescript
tell application "System Events" to tell process "Dock"
    return value of attribute "AXStatusLabel" of UI element "Messages" of list 1
end tell
```

Returns the integer badge count (e.g., `3`), or `missing value` when badge is 0.

This reads the actual dock badge via the macOS Accessibility API. It requires the calling process (Terminal, Python, etc.) to have **Accessibility permission** (System Settings > Privacy & Security > Accessibility).

### Why not other approaches?

- **`lsappinfo`**: Returns `NULL` for Messages on macOS Tahoe even when the badge is visible. Messages doesn't use the standard `NSDockTile.badgeLabel` API.
- **SQLite on `chat.db`**: `is_read` flag has massive stale data from iCloud sync (1840 phantom unreads vs actual 0). `last_read_message_timestamp` is also unreliable.

## Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-03-31 | Use Dock Accessibility API (`AXStatusLabel`) instead of `lsappinfo` or SQLite | `lsappinfo` returns NULL for Messages on Tahoe. SQLite `chat.db` has stale iCloud sync data. The Dock accessibility API returns the exact visible badge. |
| 2026-03-31 | Single-file, stdlib-only Python server | Zero supply chain risk, no pip install needed, simplest possible deployment. |
| 2026-03-31 | Client-side Canvas for favicon rendering | Avoids Pillow or any server-side image dependency. Browser Canvas API draws the bubble. |
| 2026-03-31 | Bind to `0.0.0.0` by default | Primary use case is LAN access from another machine. Configurable via `--bind` for localhost-only. |
| 2026-03-31 | HTTPS with auto-generated self-signed cert | PWA Badging API (`navigator.setAppBadge()`) requires a secure context (HTTPS). Auto-generate cert on first `--https` run, include machine hostname in SANs. |
| 2026-03-31 | No count in favicon, use PWA Badging API | Drawing a red badge in the Canvas AND having the PWA badge creates a "double badge". Favicon is just the green bubble; the OS-level PWA badge shows the count. |
| 2026-03-31 | PWA manifest (`/manifest.json`) | Enables "Install as app" in Edge/Chrome and declares the app as standalone for proper PWA behavior. |
