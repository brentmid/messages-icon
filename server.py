#!/usr/bin/env python3
"""messages-icon: Apple Messages unread count as a dynamic browser favicon."""

import argparse
import json
import os
import re
import ssl
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-title" content="Messages">
    <title>Messages</title>
    <link id="favicon" rel="icon" type="image/png" href="/apple-touch-icon.png">
    <link id="favicon-32" rel="icon" type="image/png" sizes="32x32" href="/apple-touch-icon.png">
    <link rel="apple-touch-icon" href="/apple-touch-icon.png">
    <link rel="manifest" href="/manifest.json">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        :root {{
            --bg: #1c1c1e;
            --fg: #f5f5f7;
            --muted: #98989d;
            --green: #34C759;
            --red: #FF3B30;
            --warn: #FF9F0A;
        }}
        @media (prefers-color-scheme: light) {{
            :root {{
                --bg: #f5f5f7;
                --fg: #1c1c1e;
                --muted: #6e6e73;
            }}
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "SF Pro", "Helvetica Neue", sans-serif;
            background: var(--bg);
            color: var(--fg);
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            -webkit-font-smoothing: antialiased;
        }}
        .count {{
            font-size: 8rem;
            font-weight: 700;
            line-height: 1;
            color: var(--green);
            transition: color 0.3s, transform 0.2s;
        }}
        .count.has-messages {{
            color: var(--red);
        }}
        .count.bump {{
            transform: scale(1.1);
        }}
        .label {{
            font-size: 1.25rem;
            color: var(--muted);
            margin-top: 0.5rem;
        }}
        .updated {{
            font-size: 0.75rem;
            color: var(--muted);
            margin-top: 1.5rem;
            opacity: 0.6;
        }}
        .error {{
            font-size: 0.875rem;
            color: var(--warn);
            margin-top: 1rem;
        }}
        .error:empty {{ display: none; }}
    </style>
</head>
<body>
    <div class="count" id="count">-</div>
    <div class="label" id="label">Loading...</div>
    <div class="error" id="error"></div>
    <div class="updated" id="updated"></div>
    <canvas id="favicon-canvas" width="64" height="64" style="display:none"></canvas>

<script>
const POLL_INTERVAL = {poll_interval} * 1000;
const canvas = document.getElementById('favicon-canvas');
const ctx = canvas.getContext('2d');

function drawFavicon(count) {{
    // Render at 2x for retina sharpness, display as 32x32 favicon
    const size = 64;
    canvas.width = size;
    canvas.height = size;
    ctx.clearRect(0, 0, size, size);

    // Green speech bubble — centered, transparent background;
    // the PWA Badging API handles the count on the dock icon.
    ctx.fillStyle = '#34C759';
    ctx.beginPath();
    ctx.roundRect(8, 8, 44, 32, 8);
    ctx.fill();
    ctx.beginPath();
    ctx.moveTo(14, 37);
    ctx.lineTo(8, 50);
    ctx.lineTo(26, 38);
    ctx.fill();

    // Update favicon — replace the link element to force Edge/PWA to pick up changes
    const dataUrl = canvas.toDataURL('image/png');
    const oldLink = document.getElementById('favicon');
    const newLink = oldLink.cloneNode(false);
    newLink.href = dataUrl;
    oldLink.parentNode.replaceChild(newLink, oldLink);

    const oldLink32 = document.getElementById('favicon-32');
    if (oldLink32) {{
        const newLink32 = oldLink32.cloneNode(false);
        newLink32.href = dataUrl;
        oldLink32.parentNode.replaceChild(newLink32, oldLink32);
    }}
}}

let lastCount = -1;

function update(data) {{
    const count = data.unread;
    const countEl = document.getElementById('count');
    const labelEl = document.getElementById('label');
    const errorEl = document.getElementById('error');
    const updatedEl = document.getElementById('updated');

    countEl.textContent = count;
    countEl.className = count > 0 ? 'count has-messages' : 'count';

    // Bump animation when count changes
    if (lastCount !== -1 && count !== lastCount) {{
        countEl.classList.add('bump');
        setTimeout(() => countEl.classList.remove('bump'), 200);
    }}
    lastCount = count;

    if (count === 0) {{
        labelEl.textContent = 'No unread messages';
    }} else if (count === 1) {{
        labelEl.textContent = '1 unread message';
    }} else {{
        labelEl.textContent = count + ' unread messages';
    }}

    document.title = 'Messages';
    errorEl.textContent = data.error || '';
    updatedEl.textContent = 'Updated ' + new Date().toLocaleTimeString();

    drawFavicon(count);

    // PWA Badging API — updates the dock icon badge for installed web apps
    if ('setAppBadge' in navigator) {{
        if (count > 0) {{
            navigator.setAppBadge(count);
        }} else {{
            navigator.clearAppBadge();
        }}
    }}
}}

async function poll() {{
    try {{
        const resp = await fetch('/api/count');
        const data = await resp.json();
        update(data);
    }} catch (e) {{
        document.getElementById('error').textContent = 'Connection lost';
    }}
}}

poll();
setInterval(poll, POLL_INTERVAL);
</script>
</body>
</html>'''


MANIFEST_JSON = json.dumps({
    "name": "Messages",
    "short_name": "Messages",
    "start_url": "/",
    "display": "standalone",
    "background_color": "#1c1c1e",
    "theme_color": "#34C759",
    "icons": [
        {"src": "/apple-touch-icon.png", "sizes": "180x180", "type": "image/svg+xml"},
    ],
})

# Pre-render a 180x180 apple-touch-icon as an SVG served with image/svg+xml
APPLE_TOUCH_ICON_SVG = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 180 180">
  <rect width="180" height="180" rx="40" fill="#1c1c1e"/>
  <g transform="translate(24, 22) scale(2.4)">
    <rect x="2" y="2" width="52" height="38" rx="10" fill="#34C759"/>
    <polygon points="8,36 2,50 22,38" fill="#34C759"/>
  </g>
</svg>'''


HELPER_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "helper", "dock-badge-reader")


def get_unread_count():
    """Read the Messages dock badge count via a compiled Swift helper.

    The helper (helper/dock-badge-reader) calls the Accessibility API
    directly to read AXStatusLabel on the Messages dock tile. The helper
    is the TCC subject — Accessibility permission must be granted to it
    in System Settings, not to the Python interpreter.

    See helper/build.sh for build instructions and the project's CLAUDE.md
    for the rationale (issue #13).

    Returns:
        tuple: (count: int, error: str | None)
    """
    try:
        result = subprocess.run(
            [HELPER_PATH], capture_output=True, text=True, timeout=5,
        )
    except FileNotFoundError:
        return 0, f"Helper not built. Run {os.path.dirname(HELPER_PATH)}/build.sh"
    except subprocess.TimeoutExpired:
        return 0, "Dock badge helper timed out"

    if result.returncode == 0:
        try:
            return int(result.stdout.strip()), None
        except ValueError:
            return 0, None

    if result.returncode == 3:
        return 0, "Accessibility permission missing for dock-badge-reader helper"
    return 0, f"dock-badge-reader exited {result.returncode}: {result.stderr.strip()}"


class Handler(BaseHTTPRequestHandler):
    """HTTP request handler with three routes."""

    poll_interval = 30

    def do_GET(self):
        if self.path == "/":
            self._serve_html()
        elif self.path == "/api/count":
            self._serve_count()
        elif self.path == "/apple-touch-icon.png" or \
             self.path == "/apple-touch-icon-precomposed.png":
            self._serve_touch_icon()
        elif self.path == "/manifest.json":
            self._serve_manifest()
        else:
            self.send_error(404)

    def _serve_html(self):
        page = HTML_TEMPLATE.format(
            poll_interval=self.poll_interval,
        )
        body = page.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.end_headers()
        self.wfile.write(body)

    def _serve_count(self):
        count, error = get_unread_count()
        payload = {"unread": count}
        if error:
            payload["error"] = error
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def _serve_touch_icon(self):
        body = APPLE_TOUCH_ICON_SVG.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "image/svg+xml")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_manifest(self):
        body = MANIFEST_JSON.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/manifest+json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        # Quieter logging — skip noisy per-request logs
        pass


def _ensure_cert(cert_dir, extra_hosts=None):
    """Generate a self-signed certificate if one doesn't exist.

    The certificate includes localhost, 127.0.0.1, the machine's hostname,
    and any extra hostnames passed via --hostname.

    Returns (cert_path, key_path).
    """
    cert_dir = Path(cert_dir)
    cert_path = cert_dir / "cert.pem"
    key_path = cert_dir / "key.pem"

    if cert_path.exists() and key_path.exists():
        return str(cert_path), str(key_path)

    cert_dir.mkdir(parents=True, exist_ok=True)

    # Build SAN list: localhost + machine hostname + extras
    import socket
    hostname = socket.gethostname().replace(".local", "")
    san_entries = ["DNS:localhost", f"DNS:{hostname}", f"DNS:{hostname}.local",
                   "IP:127.0.0.1"]
    if extra_hosts:
        for h in extra_hosts:
            san_entries.append(f"DNS:{h}")

    san_string = ",".join(san_entries)
    print("Generating self-signed TLS certificate...")
    print(f"  SANs: {san_string}")
    result = subprocess.run(
        [
            "openssl", "req", "-x509", "-newkey", "rsa:2048",
            "-keyout", str(key_path), "-out", str(cert_path),
            "-days", "3650", "-nodes",
            "-subj", "/CN=messages-icon",
            "-addext", f"subjectAltName={san_string}",
        ],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"Failed to generate certificate: {result.stderr}", file=sys.stderr)
        sys.exit(1)

    print(f"  Certificate: {cert_path}")
    print(f"  Key: {key_path}")
    print()
    print("  To avoid browser warnings, trust the certificate:")
    print(f"    sudo security add-trusted-cert -d -r trustRoot \\")
    print(f"      -k /Library/Keychains/System.keychain {cert_path}")
    print()
    return str(cert_path), str(key_path)


def main():
    parser = argparse.ArgumentParser(
        description="Apple Messages unread count favicon server",
    )
    parser.add_argument(
        "--port", type=int,
        default=int(os.environ.get("MESSAGES_ICON_PORT", "8429")),
        help="Port to listen on (default: 8429)",
    )
    parser.add_argument(
        "--poll-interval", type=int,
        default=int(os.environ.get("MESSAGES_ICON_POLL_INTERVAL", "30")),
        help="Seconds between badge checks (default: 30)",
    )
    parser.add_argument(
        "--bind", type=str,
        default=os.environ.get("MESSAGES_ICON_BIND", "0.0.0.0"),
        help="Address to bind to (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--https", action="store_true",
        default=os.environ.get("MESSAGES_ICON_HTTPS", "").lower() in ("1", "true", "yes"),
        help="Enable HTTPS with a self-signed certificate (required for PWA badge)",
    )
    parser.add_argument(
        "--cert-dir", type=str,
        default=os.environ.get("MESSAGES_ICON_CERT_DIR",
                               os.path.join(os.path.dirname(__file__), "certs")),
        help="Directory for TLS certificate and key (default: ./certs)",
    )
    parser.add_argument(
        "--hostname", type=str, action="append",
        help="Extra hostname(s) for the TLS certificate SAN (repeatable)",
    )
    args = parser.parse_args()

    Handler.poll_interval = args.poll_interval

    server = ThreadingHTTPServer((args.bind, args.port), Handler)

    scheme = "http"
    if args.https:
        cert_path, key_path = _ensure_cert(args.cert_dir, args.hostname)
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(cert_path, key_path)
        server.socket = ctx.wrap_socket(server.socket, server_side=True)
        scheme = "https"

    print(f"messages-icon serving on {scheme}://{args.bind}:{args.port}")
    print(f"  Poll interval: {args.poll_interval}s")
    if args.https:
        print(f"  TLS: enabled (PWA badge supported)")
    print(f"  Press Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        server.server_close()


if __name__ == "__main__":
    main()
