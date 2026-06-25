"""Screenshot a URL at a true mobile viewport via the Chrome DevTools Protocol.

Headless Chrome's --window-size does not set the layout viewport on this machine (Windows
display scaling pins window.innerWidth at ~482), and desktop Chrome ignores the viewport
meta. Flutter web reads window.innerWidth, so it lays out too wide. CDP
Emulation.setDeviceMetricsOverride(mobile=True) forces a real 390px mobile viewport, which
Flutter honors.

Usage:
  python scripts/shot_cdp.py <url> <out_png> [width] [height] [wait_seconds]
"""
from __future__ import annotations

import asyncio
import base64
import json
import subprocess
import sys
import tempfile
import time
import urllib.request

import websockets

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
TAPS = ""  # set from argv in __main__; "x:y,x:y" canvas taps to drive navigation


def _targets(port: int):
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=5) as r:
        return json.loads(r.read().decode("utf-8"))


async def _cmd(ws, state, method, params=None):
    state["id"] += 1
    mid = state["id"]
    await ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
    while True:
        msg = json.loads(await ws.recv())
        if msg.get("id") == mid:
            if "error" in msg:
                raise RuntimeError(f"{method} failed: {msg['error']}")
            return msg.get("result", {})
        # ignore events


async def run(url: str, out_png: str, width: int, height: int, wait_s: float):
    port = 9222
    user_dir = tempfile.mkdtemp(prefix="cdp-chrome-")
    proc = subprocess.Popen(
        [
            CHROME, "--headless=new", "--disable-gpu", "--enable-unsafe-swiftshader",
            f"--remote-debugging-port={port}", "--no-first-run", "--no-default-browser-check",
            "--hide-scrollbars", f"--user-data-dir={user_dir}", "about:blank",
        ],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        # wait for the devtools endpoint + a page target
        ws_url = None
        for _ in range(40):
            try:
                for t in _targets(port):
                    if t.get("type") == "page":
                        ws_url = t["webSocketDebuggerUrl"]
                        break
            except Exception:
                pass
            if ws_url:
                break
            time.sleep(0.25)
        if not ws_url:
            raise RuntimeError("no Chrome page target found")

        async with websockets.connect(ws_url, max_size=None) as ws:
            state = {"id": 0}
            await _cmd(ws, state, "Page.enable")
            await _cmd(ws, state, "Runtime.enable")
            await _cmd(ws, state, "Emulation.setDeviceMetricsOverride", {
                "width": width, "height": height, "deviceScaleFactor": 2, "mobile": True,
                "screenWidth": width, "screenHeight": height,
            })
            await _cmd(ws, state, "Page.navigate", {"url": url})
            # let Flutter bootstrap (WASM + canvaskit) and fetch from the API, then render
            await asyncio.sleep(wait_s)
            iw = await _cmd(ws, state, "Runtime.evaluate", {
                "expression": "window.innerWidth", "returnByValue": True})
            print(f"innerWidth seen by page: {iw.get('result', {}).get('value')}")
            # optional canvas taps (x:y, comma-separated) to drive Flutter navigation, each
            # followed by a settle wait so an async screen load can finish before the shot.
            for tap in [t for t in TAPS.split(",") if t.strip()]:
                tx, ty = (float(v) for v in tap.split(":"))
                for ev_type in ("mousePressed", "mouseReleased"):
                    await _cmd(ws, state, "Input.dispatchMouseEvent", {
                        "type": ev_type, "x": tx, "y": ty, "button": "left", "clickCount": 1})
                await asyncio.sleep(5)
            shot = await _cmd(ws, state, "Page.captureScreenshot", {
                "format": "png", "captureBeyondViewport": False})
            data = base64.b64decode(shot["data"])
            with open(out_png, "wb") as f:
                f.write(data)
            print(f"wrote {out_png}: {len(data)} bytes")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    url = sys.argv[1]
    out = sys.argv[2]
    w = int(sys.argv[3]) if len(sys.argv) > 3 else 390
    h = int(sys.argv[4]) if len(sys.argv) > 4 else 844
    wait = float(sys.argv[5]) if len(sys.argv) > 5 else 9.0
    TAPS = sys.argv[6] if len(sys.argv) > 6 else ""
    asyncio.run(run(url, out, w, h, wait))
