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
- `GET /api/count` — Returns JSON `{"unread": N}`. Invokes the compiled `helper/dock-badge-reader` binary (a Swift Mach-O that calls the Accessibility API directly). The helper — not Python — is the TCC subject for the Accessibility grant.
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

`server.py` invokes `helper/dock-badge-reader` (a small Swift Mach-O, source in `helper/dock-badge-reader.swift`). The helper calls the Accessibility API directly: gets the Dock process via `NSWorkspace`, walks `AXChildren` to find the first `AXList`, finds the tile with `AXTitle == "Messages"`, and reads its `AXStatusLabel` attribute. Prints the integer count to stdout, or `0` when the badge is empty.

The equivalent AppleScript (no longer used — kept for reference) was:

```applescript
tell application "System Events" to tell process "Dock"
    return value of attribute "AXStatusLabel" of UI element "Messages" of list 1
end tell
```

**TCC requirement:** the helper binary itself must be granted **Accessibility** in System Settings > Privacy & Security > Accessibility. Python is no longer the TCC subject — see Decision Log entry for 2026-04-30 and [issue #13](https://github.com/brentmid/messages-icon/issues/13).

### Building the helper

```bash
./helper/build.sh
```

Compiles with `swiftc -O`, ad-hoc signs with `codesign -s -`. Output: `helper/dock-badge-reader` (gitignored). Build once and leave alone — every rebuild changes the cdhash and invalidates the TCC grant. Only rebuild when actually fixing the helper.

### Why the helper self-disclaims

The helper's first action on startup is to `posix_spawn` a copy of itself with `responsibility_spawnattrs_setdisclaim(attr, 1)` and wait for it. This is **required**, not optional. Without it, when the helper is spawned by Python under launchd, TCC checks Python as the responsible process — not the helper — and denies the request even though the helper has its own Accessibility grant. The disclaimed child becomes its own responsible process, so TCC then consults the helper's grant. A `--disclaimed` argv sentinel lets the same binary act as both parent (re-execs with disclaim) and child (does the AX work). Confirmed via tccd's `AUTHREQ_SUBJECT` log entry — with disclaim, subject = helper path; without, subject = Python path.

Apply the same pattern to any future per-project TCC helper. See `~/bin/CLAUDE.md` "TCC permission helpers" for the cross-project rule.

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
| 2026-04-30 | Replace `osascript`-via-Python with a compiled Swift helper at `helper/dock-badge-reader` | Granting Accessibility to a Homebrew Python (the prior approach) silently broke on every Homebrew bump because the cellar path and binary signature changed. The compiled helper is a single-purpose Mach-O with a stable cdhash that holds the TCC grant across Python upgrades. See [issue #13](https://github.com/brentmid/messages-icon/issues/13). Cross-references: `~/bin/CLAUDE.md` "TCC permission helpers" section, and `edr/issues/0041`. |
| 2026-04-30 | Helper self-disclaims TCC responsibility via `responsibility_spawnattrs_setdisclaim` + self-re-exec | Direct invocation alone wasn't sufficient. Empirically (tccd `AUTHREQ_SUBJECT` log) Python was still being checked as the responsible process even though Python only `subprocess.run`s the helper. Without disclaim the request was denied despite the helper having its own grant. The helper's first action on startup is to `posix_spawn` a copy of itself with the disclaim attribute, wait, and propagate the child's exit code; the disclaimed child does the AX work as its own responsible process. A `--disclaimed` argv sentinel differentiates parent/child. |
