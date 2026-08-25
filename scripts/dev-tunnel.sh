#!/usr/bin/env bash
# Make the local stack reachable from the internet, so Printful can fetch
# artwork and generate mockups against local dev. Free Cloudflare quick
# tunnel; a new hostname each run.
#
#   ./scripts/dev-tunnel.sh        # leave it running; Ctrl-C to close
#
# Writes ARTWORK_PUBLIC_URL into .env and recreates the backend so signed
# artwork links point at the tunnel. Clears it again on exit.
set -euo pipefail
cd "$(dirname "$0")/.."

command -v cloudflared >/dev/null || { echo "brew install cloudflared"; exit 1; }
LOG=$(mktemp)

clear_env() { sed -i '' '/^ARTWORK_PUBLIC_URL=/d' .env; }
cleanup() {
  kill "$PID" 2>/dev/null || true
  clear_env
  docker compose up -d backend >/dev/null 2>&1 || true
  echo; echo "tunnel closed — ARTWORK_PUBLIC_URL cleared, backend back on localhost"
}
trap cleanup EXIT

cloudflared tunnel --url http://localhost:3000 --no-autoupdate >"$LOG" 2>&1 &
PID=$!

URL=""
for _ in $(seq 1 40); do
  URL=$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' "$LOG" | head -1 || true)
  [ -n "$URL" ] && break
  sleep 1
done
[ -n "$URL" ] || { cat "$LOG"; exit 1; }

clear_env
echo "ARTWORK_PUBLIC_URL=$URL" >> .env
docker compose up -d backend >/dev/null

echo "artwork is public at  $URL"
echo "Printful can fetch it now — mockups will generate. Ctrl-C to close."
wait "$PID"
