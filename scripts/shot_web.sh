#!/usr/bin/env bash
# Screenshot the built Flutter web app at a true 390-wide mobile viewport against the live
# stub, using CDP device emulation (see scripts/shot_cdp.py for why --window-size is not
# enough on this machine).
# Usage: scripts/shot_web.sh <output_basename> [wait_seconds]
# Output: C:/Users/arthu/AppData/Local/Temp/svgpng/<output_basename>.png
set -e
ROOT="C:/Users/arthu/Documents/Google Agentic AI Course/appliance-fixer"
OUT="C:/Users/arthu/AppData/Local/Temp/svgpng"
NAME="${1:-shot}"
WAIT="${2:-10}"
TAPS="${3:-}"
PY="$ROOT/.venv/Scripts/python.exe"
cd "$ROOT"

# free ports from any prior run
for port in 8000 5599 9222; do
  for pid in $(netstat -ano 2>/dev/null | grep ":$port " | grep LISTENING | awk '{print $NF}' | sort -u); do
    taskkill //F //PID "$pid" >/dev/null 2>&1 || true
  done
done

"$PY" -m uvicorn app.fast_api_app:app --port 8000 --log-level warning >/tmp/shot_stub.log 2>&1 &
STUB=$!
"$PY" -m http.server 5599 --directory mobile/build/web >/tmp/shot_web.log 2>&1 &
WEB=$!
sleep 4
"$PY" scripts/shot_cdp.py "http://127.0.0.1:5599" "$OUT/$NAME.png" 390 844 "$WAIT" "$TAPS"
RC=$?
kill $STUB $WEB 2>/dev/null || true
exit $RC
