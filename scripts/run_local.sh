#!/usr/bin/env bash
#
# run_local.sh --- boots the whole shipwright stack locally without docker-compose.
#
# What it does:
#   1. Creates a Python venv in .venv/ and installs requirements.txt.
#   2. Ensures a Node 20 runtime (downloads a local copy into .tools/ if none).
#   3. npm-installs and builds the gateway and the UI.
#   4. Starts the gateway on :4000 and the UI on :5173 in the background.
#
# Note: running the *server* needs no Docker, but executing sandboxed agent
# tasks does (a Docker daemon with runsc registered, and /var/run/docker.sock).
# Without it the gateway and UI still boot, but sandbox launches will fail.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$ROOT/.venv"
TOOLS="$ROOT/.tools"
NODE_VER="v20.17.0"
case "$(uname -s)-$(uname -m)" in
    Darwin-arm64) NODE_PLATFORM="darwin-arm64" ;;
    Darwin-x86_64) NODE_PLATFORM="darwin-x64" ;;
    Linux-aarch64) NODE_PLATFORM="linux-arm64" ;;
    *) NODE_PLATFORM="linux-x64" ;;
esac
NODE_DIR="$TOOLS/node-$NODE_VER-$NODE_PLATFORM"

say() { printf '\n=== %s ===\n' "$*"; }

if [ -f "$ROOT/.env" ]; then
    set -a
    # shellcheck disable=SC1091
    . "$ROOT/.env"
    set +a
fi
export PORT="${PORT:-4000}"
export GATEWAY_TOKEN="${GATEWAY_TOKEN:-dev-token}"
export WEBHOOK_SECRET="${WEBHOOK_SECRET:-dev-secret}"
export REPO_URL="${REPO_URL:-https://github.com/abj360/shipwright}"
export GITHUB_TOKEN="${GITHUB_TOKEN:-dev-token}"
export WORK_DIR="${WORK_DIR:-/tmp/shipwright-work}"
export BASE_BRANCH="${BASE_BRANCH:-main}"

say "python venv"
python3 -m venv "$VENV"
"$VENV/bin/pip" install --quiet --upgrade pip
"$VENV/bin/pip" install --quiet -r "$ROOT/requirements.txt"
"$VENV/bin/pip" install --quiet -e "$ROOT"
(cd "$ROOT" && "$VENV/bin/python" -m agent.cli --version)

say "node runtime"
if command -v node >/dev/null 2>&1; then
    NODE_BIN="$(command -v node)"
    NPM_BIN="$(command -v npm)"
else
    if [ ! -x "$NODE_DIR/bin/node" ]; then
        mkdir -p "$TOOLS"
        echo "downloading node $NODE_VER into .tools/ (one time)"
        curl -fsSL "https://nodejs.org/dist/$NODE_VER/node-$NODE_VER-linux-x64.tar.xz" \
            | tar -xJ -C "$TOOLS"
    fi
    NODE_BIN="$NODE_DIR/bin/node"
    NPM_BIN="$NODE_DIR/bin/npm"
fi
"$NODE_BIN" --version

say "gateway build"
(cd "$ROOT/gateway" && "$NPM_BIN" install --no-fund --no-audit && "$NPM_BIN" run build)

say "ui build"
(cd "$ROOT/ui" && "$NPM_BIN" install --no-fund --no-audit && "$NPM_BIN" run build)

if ! command -v docker >/dev/null 2>&1; then
    echo "note: docker not found; sandbox launches will fail, server still boots"
fi

say "starting services"
(cd "$ROOT/gateway" && "$NODE_BIN" dist/server.js) &
GATEWAY_PID=$!
(cd "$ROOT/ui" && "$NPM_BIN" run preview -- --host 0.0.0.0 --port 5173) &
UI_PID=$!

cleanup() {
    echo
    say "stopping"
    kill "$GATEWAY_PID" "$UI_PID" 2>/dev/null || true
}
trap cleanup INT TERM

sleep 3
echo "gateway: http://localhost:${PORT}/health  (token: ${GATEWAY_TOKEN})"
echo "ui:      http://localhost:5173"
echo "agent:   $VENV/bin/python -m agent.cli --task 'fix the flaky test'"
wait
