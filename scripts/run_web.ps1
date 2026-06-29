# Run the Flutter web client on a FIXED port so the browser origin never changes.
#
# Why this matters: the app's per-device user id (and therefore the list of
# saved issues) lives in browser localStorage, which is scoped per origin
# (scheme + host + port). `flutter run -d chrome` with no --web-port picks a
# random port every launch -> a new origin -> a brand-new device id -> prior
# issues appear "lost". Pinning the port keeps one stable identity across runs.
#
# Usage (from repo root or anywhere):
#   scripts\run_web.ps1            # default port 8080
#   scripts\run_web.ps1 -Port 9090 -ApiBaseUrl http://127.0.0.1:8000
param(
    [int]$Port = 8080,
    [string]$ApiBaseUrl = ""
)

$mobileDir = Join-Path $PSScriptRoot "..\mobile"
Push-Location $mobileDir
try {
    $flutterArgs = @(
        "run", "-d", "chrome",
        "--web-hostname=127.0.0.1",
        "--web-port=$Port"
    )
    if ($ApiBaseUrl -ne "") {
        $flutterArgs += "--dart-define=API_BASE_URL=$ApiBaseUrl"
    }
    & flutter @flutterArgs
}
finally {
    Pop-Location
}
