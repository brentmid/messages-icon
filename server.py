#!/usr/bin/env python3
"""messages-icon: Apple Messages unread count as a dynamic browser favicon."""

import argparse
import base64
import json
import os
import re
import subprocess
from http.server import BaseHTTPRequestHandler, HTTPServer

# Green bubble SVG for apple-touch-icon and static favicon fallback
BUBBLE_SVG = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <path d="M8 12 C8 6, 14 2, 22 2 L42 2 C50 2, 56 6, 56 12 L56 32
           C56 38, 50 42, 42 42 L20 42 L12 54 L14 42 L12 42
           C6 42, 2 38, 2 32 L2 16 C2 10, 6 6, 12 6 Z"
        fill="#34C759" stroke="none"/>
  <path d="M8 10 C8 5, 13 2, 20 2 L44 2 C51 2, 56 5, 56 10 L56 30
           C56 35, 51 38, 44 38 L18 38 L10 50 L12 38 C5 38, 2 35, 2 30
           L2 14 C2 9, 5 6, 10 6 Z"
        fill="#34C759" stroke="none"/>
</svg>'''

# Pre-encode the SVG as a PNG-equivalent data URI for apple-touch-icon
BUBBLE_SVG_B64 = base64.b64encode(BUBBLE_SVG.encode()).decode()

HTML_TEMPLATE = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-title" content="Messages">
    <title>Messages</title>
    <link id="favicon" rel="icon" type="image/png" href="data:image/svg+xml;base64,{bubble_svg_b64}">
    <link rel="apple-touch-icon" href="/apple-touch-icon.png">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "SF Pro", "Helvetica Neue", sans-serif;
            background: #1c1c1e;
            color: #f5f5f7;
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
            color: #34C759;
            transition: color 0.3s;
        }}
        .count.has-messages {{
            color: #FF3B30;
        }}
        .label {{
            font-size: 1.25rem;
            color: #98989d;
            margin-top: 0.5rem;
        }}
        .error {{
            font-size: 0.875rem;
            color: #FF9F0A;
            margin-top: 1rem;
        }}
        .error:empty {{ display: none; }}
    </style>
</head>
<body>
    <div class="count" id="count">-</div>
    <div class="label" id="label">Loading...</div>
    <div class="error" id="error"></div>
    <canvas id="favicon-canvas" width="64" height="64" style="display:none"></canvas>

<script>
const POLL_INTERVAL = {poll_interval} * 1000;
const canvas = document.getElementById('favicon-canvas');
const ctx = canvas.getContext('2d');

function drawFavicon(count) {{
    ctx.clearRect(0, 0, 64, 64);

    // Green speech bubble
    ctx.fillStyle = '#34C759';
    ctx.beginPath();
    ctx.moveTo(20, 4);
    ctx.quadraticCurveTo(4, 4, 4, 16);
    ctx.lineTo(4, 32);
    ctx.quadraticCurveTo(4, 44, 16, 44);
    ctx.lineTo(16, 44);
    ctx.lineTo(10, 56);
    ctx.lineTo(26, 44);
    ctx.lineTo(44, 44);
    ctx.quadraticCurveTo(58, 44, 58, 32);
    ctx.lineTo(58, 16);
    ctx.quadraticCurveTo(58, 4, 44, 4);
    ctx.closePath();
    ctx.fill();

    if (count > 0) {{
        const label = count > 99 ? '99+' : String(count);

        // Red badge circle
        const badgeRadius = label.length > 2 ? 16 : 14;
        ctx.fillStyle = '#FF3B30';
        ctx.beginPath();
        ctx.arc(48, 14, badgeRadius, 0, Math.PI * 2);
        ctx.fill();

        // White border
        ctx.strokeStyle = '#FFFFFF';
        ctx.lineWidth = 2;
        ctx.stroke();

        // Count text
        ctx.fillStyle = '#FFFFFF';
        ctx.font = `bold ${{label.length > 2 ? 12 : 16}}px -apple-system, sans-serif`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(label, 48, 14);
    }}

    // Update favicon
    document.getElementById('favicon').href = canvas.toDataURL('image/png');
}}

function update(data) {{
    const count = data.unread;
    const countEl = document.getElementById('count');
    const labelEl = document.getElementById('label');
    const errorEl = document.getElementById('error');

    countEl.textContent = count;
    countEl.className = count > 0 ? 'count has-messages' : 'count';

    if (count === 0) {{
        labelEl.textContent = 'No unread messages';
    }} else if (count === 1) {{
        labelEl.textContent = '1 unread message';
    }} else {{
        labelEl.textContent = count + ' unread messages';
    }}

    document.title = count > 0 ? '(' + count + ') Messages' : 'Messages';
    errorEl.textContent = data.error || '';

    drawFavicon(count);
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


# Pre-render a 180x180 apple-touch-icon as an SVG served with image/svg+xml
APPLE_TOUCH_ICON_SVG = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 180 180">
  <rect width="180" height="180" rx="40" fill="#1c1c1e"/>
  <g transform="translate(30, 25) scale(1.8)">
    <path d="M20 4 Q4 4 4 16 L4 32 Q4 44 16 44 L16 44 L10 56 L26 44 L44 44
             Q58 44 58 32 L58 16 Q58 4 44 4 Z"
          fill="#34C759"/>
  </g>
</svg>'''


def get_unread_count():
    """Read the Messages dock badge count via the Dock accessibility API.

    Uses AppleScript to query the AXStatusLabel attribute of the Messages
    element in the Dock. This matches the actual dock badge exactly, unlike
    lsappinfo (which returns NULL for Messages on macOS Tahoe) or direct
    SQLite queries on chat.db (which return stale iCloud sync data).

    Requires: Accessibility permission for the calling process.

    Returns:
        tuple: (count: int, error: str | None)
    """
    try:
        result = subprocess.run(
            ["osascript", "-e",
             'tell application "System Events" to tell process "Dock" '
             'to return value of attribute "AXStatusLabel" of UI element '
             '"Messages" of list 1'],
            capture_output=True, text=True, timeout=5,
        )
        output = result.stdout.strip()
        if result.returncode != 0:
            stderr = result.stderr.strip()
            if "missing value" in stderr or "missing value" in output:
                return 0, None
            return 0, "Could not read Messages badge (check Accessibility permissions)"
        if not output or output == "missing value":
            return 0, None
        try:
            return int(output), None
        except ValueError:
            return 0, None
    except FileNotFoundError:
        return 0, "osascript not found (macOS only)"
    except subprocess.TimeoutExpired:
        return 0, "osascript timed out"
    except Exception as e:
        return 0, str(e)


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
        else:
            self.send_error(404)

    def _serve_html(self):
        page = HTML_TEMPLATE.format(
            poll_interval=self.poll_interval,
            bubble_svg_b64=BUBBLE_SVG_B64,
        )
        body = page.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
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

    def log_message(self, format, *args):
        # Quieter logging — skip noisy per-request logs
        pass


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
    args = parser.parse_args()

    Handler.poll_interval = args.poll_interval

    server = HTTPServer((args.bind, args.port), Handler)
    print(f"messages-icon serving on http://{args.bind}:{args.port}")
    print(f"  Poll interval: {args.poll_interval}s")
    print(f"  Press Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        server.server_close()


if __name__ == "__main__":
    main()
