# messages-icon

A lightweight macOS HTTP server that shows your Apple Messages unread count as a dynamic browser favicon.

Pin it as a tab, or create a web app (e.g., in Microsoft Edge or Chrome) to get a dock icon that updates with your unread message count — even on machines that aren't signed into iCloud.

## Requirements

- **macOS** (uses the Dock Accessibility API)
- **Python 3.11+** (stdlib only — no `pip install` needed)
- **Xcode Command Line Tools** (for building the dock-badge helper — `swiftc`, `codesign`)
- **Messages app** must be running (the server reads the dock badge count)
- **Accessibility permission** for the compiled `helper/dock-badge-reader` binary — grant in System Settings > Privacy & Security > Accessibility (see Quick Start below)

## Quick Start

```bash
# 1. Build the dock-badge helper (one-time)
./helper/build.sh

# 2. Grant Accessibility to the helper:
#    System Settings → Privacy & Security → Accessibility → +
#    Add: <repo>/helper/dock-badge-reader

# 3. Run the server
python3 server.py             # HTTP — works for browser tabs
python3 server.py --https     # HTTPS — required for PWA dock badge
```

Then open `https://localhost:8429` (or `http://` without `--https`) in your browser. From another machine, use `https://<your-mac-ip>:8429` — see [Bind address](#bind-address) for which address to expose.

To create a persistent "app" in Edge: navigate to the URL, then **Settings > Apps > Install this site as an app**. The dock icon badge updates automatically when using HTTPS.

### HTTPS Setup

HTTPS is required for the PWA Badging API, which updates the dock icon badge. On first run with `--https`, a self-signed certificate is auto-generated in `./certs/`.

To avoid browser certificate warnings, copy the cert to each **client machine** and trust it there:

```bash
# On the client machine (not the server):
scp your-mac:~/path/to/messages-icon/certs/cert.pem /tmp/messages-icon-cert.pem
sudo security add-trusted-cert -d -r trustRoot \
  -k /Library/Keychains/System.keychain /tmp/messages-icon-cert.pem
```

You only need to do this once per client. The certificate is valid for 10 years. The cert automatically includes `localhost` and the server's hostname as SANs. Use `--hostname` to add extra hostnames.

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

To customize port, poll interval, or bind address, add flags to the `ProgramArguments` array in the plist (e.g., `--port`, `--poll-interval`, `--bind`) or set the matching environment variables in an `EnvironmentVariables` dict (the example plist does this for `MESSAGES_ICON_BIND`).

### Bind address

The server has no authentication, so the bind address is the access control. The code default is `0.0.0.0` (every interface) for a quick first run, but for an always-on LaunchAgent bind to a single address that only your own devices can reach:

- **Tailscale IP** (recommended): `MESSAGES_ICON_BIND=<tailscale-ip>`. Only devices on your tailnet can connect; the server is invisible to the physical LAN. Use this if the machine that displays the badge is on the same tailnet.
- **`127.0.0.1`**: local browser only.
- **`0.0.0.0`**: reachable by every device on the LAN, including IoT and guest devices. Fine for a trusted network, but prefer one of the above.

Whatever address you pick, the URL you install as a PWA must match a name in the certificate's SANs (see HTTPS Setup); use `--hostname` when generating the certificate if you connect by a name other than the machine's hostname.

> **Note:** Accessibility permission must be granted to the **compiled helper binary** (`helper/dock-badge-reader`), not to Python. The server invokes the helper as a subprocess; the helper is the TCC subject. See the Quick Start for the build/grant flow.

## Configuration

| Option | CLI Arg | Env Var | Default |
|--------|---------|---------|---------|
| Port | `--port` | `MESSAGES_ICON_PORT` | `8429` |
| Poll interval (seconds) | `--poll-interval` | `MESSAGES_ICON_POLL_INTERVAL` | `30` |
| Bind address | `--bind` | `MESSAGES_ICON_BIND` | `0.0.0.0` |
| Enable HTTPS | `--https` | `MESSAGES_ICON_HTTPS` | `false` |
| Certificate directory | `--cert-dir` | `MESSAGES_ICON_CERT_DIR` | `./certs` |
| Extra TLS hostnames | `--hostname` | *(none)* | *(none, repeatable)* |

```bash
# Examples
python3 server.py --port 9000 --poll-interval 10
python3 server.py --bind 127.0.0.1  # localhost only
```

## How It Works

The server uses the macOS Dock Accessibility API (via a small compiled Swift helper at `helper/dock-badge-reader`) to read the Messages app's dock badge count — the exact number macOS displays on the Messages icon in your Dock. This is more reliable than `lsappinfo` (which returns NULL for Messages on recent macOS) or querying the Messages SQLite database directly (which returns stale data due to iCloud sync).

The helper exists so the TCC Accessibility grant binds to a tiny single-purpose binary with a stable signature, rather than to whichever Homebrew Python the LaunchAgent currently resolves. Homebrew Python upgrades silently invalidate TCC grants on the interpreter; the compiled helper avoids that whole class of breakage. See [issue #13](https://github.com/brentmid/messages-icon/issues/13) for the full reasoning.

The webpage polls `/api/count` at the configured interval. When installed as a PWA (via Edge or Chrome) over HTTPS, it uses the Badging API (`navigator.setAppBadge()`) to show the unread count on the dock icon. The favicon is a green iMessage-style speech bubble rendered via Canvas.

### API

`GET /api/count` returns:

```json
{"unread": 3}
```

Or, if there's an issue (e.g., Accessibility permission not granted to the helper, or the helper isn't built):

```json
{"unread": 0, "error": "Accessibility permission missing for dock-badge-reader helper"}
```

## Privacy

This server exposes **only the unread count** — an integer. It never reads, stores, or transmits message content, sender information, or any other personal data.

## License

MIT — see [LICENSE](LICENSE).
