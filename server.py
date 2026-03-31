#!/usr/bin/env python3
"""messages-icon: Apple Messages unread count as a dynamic browser favicon."""

import argparse
import json
import os
import re
import subprocess
from http.server import BaseHTTPRequestHandler, HTTPServer

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
    // Render at 2x for retina sharpness, display as 32x32 favicon
    const size = 64;
    canvas.width = size;
    canvas.height = size;
    ctx.clearRect(0, 0, size, size);

    // Green speech bubble (iMessage style)
    ctx.fillStyle = '#34C759';
    ctx.beginPath();
    // Main bubble body — rounded rectangle
    ctx.roundRect(2, 2, 52, 38, 10);
    ctx.fill();
    // Tail — bottom-left pointer
    ctx.beginPath();
    ctx.moveTo(8, 36);
    ctx.lineTo(2, 50);
    ctx.lineTo(22, 38);
    ctx.fill();

    if (count > 0) {{
        const label = count > 99 ? '99+' : String(count);

        // Red badge — pill shape for multi-digit, circle for single
        ctx.fillStyle = '#FF3B30';
        const bx = 46, by = 12;
        const bh = 22;
        const bw = Math.max(bh, label.length * 10 + 10);
        ctx.beginPath();
        ctx.roundRect(bx - bw/2, by - bh/2, bw, bh, bh/2);
        ctx.fill();

        // White border
        ctx.strokeStyle = '#FFFFFF';
        ctx.lineWidth = 2;
        ctx.stroke();

        // Count text — bold, sized to fit
        const fontSize = label.length > 2 ? 11 : 14;
        ctx.fillStyle = '#FFFFFF';
        ctx.font = `bold ${{fontSize}}px -apple-system, "SF Pro", sans-serif`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(label, bx, by + 1);
    }}

    // Update favicon link
    document.getElementById('favicon').href = canvas.toDataURL('image/png');

    // Also update 32x32 variant for browsers that prefer it
    const link32 = document.getElementById('favicon-32');
    if (link32) link32.href = canvas.toDataURL('image/png');
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
  <g transform="translate(24, 22) scale(2.4)">
    <rect x="2" y="2" width="52" height="38" rx="10" fill="#34C759"/>
    <polygon points="8,36 2,50 22,38" fill="#34C759"/>
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
