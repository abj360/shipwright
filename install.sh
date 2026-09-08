#!/bin/sh
#
# install.sh --- installs shipwright as a sandboxed Docker workload.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/abj360/shipwright/main/install.sh -o install.sh
#   sh install.sh
#
# There is deliberately no native install path. The agent runs arbitrary
# commands on your behalf, so it runs inside a gVisor-isolated container or it
# does not run at all. This script:
#   1. Installs Docker if it is missing (with your consent).
#   2. Installs gVisor and registers `runsc` as a Docker runtime.
#   3. Proves the sandbox works by launching a probe container under runsc.
#   4. Builds the agent image and links `ship` into ~/.local/bin.
#
# `ship` mounts only the directory you run it in. Nothing above that directory
# is visible to the agent.
#
# Escape hatch (understand it before using it):
#   SHIPWRIGHT_ALLOW_UNSANDBOXED=1  proceed when runsc will not start. Tools
#   then run under the default runtime, with weaker isolation, and the
#   interface says so on every launch.
#
# Environment overrides:
#   SHIPWRIGHT_HOME      where the checkout lives
#   SHIPWRIGHT_BIN       where the `ship` launcher is linked
#   SHIPWRIGHT_REPO_URL  clone source (a local path works, for testing)
#   SHIPWRIGHT_REF       branch or tag to install

set -eu

REPO_URL="${SHIPWRIGHT_REPO_URL:-https://github.com/abj360/shipwright.git}"
REF="${SHIPWRIGHT_REF:-main}"
INSTALL_HOME="${SHIPWRIGHT_HOME:-$HOME/.local/share/shipwright}"
BIN_DIR="${SHIPWRIGHT_BIN:-$HOME/.local/bin}"
SRC_DIR="$INSTALL_HOME/src"
IMAGE_NAME="shipwright-agent:latest"
ALLOW_UNSANDBOXED="${SHIPWRIGHT_ALLOW_UNSANDBOXED:-0}"
GVISOR_KEYRING="/usr/share/keyrings/gvisor-archive-keyring.gpg"

say() { printf '\033[36m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[33mwarning:\033[0m %s\n' "$*" >&2; }
die() { printf '\033[31merror:\033[0m %s\n' "$*" >&2; exit 1; }

# Consent and passwords must come from the terminal: piping this script into a
# shell leaves stdin owned by the pipe, where a prompt is silently skipped.
have_tty() { [ -r /dev/tty ]; }

confirm() {
    have_tty || die "no terminal available for confirmation. Download the script and run it: sh install.sh"
    printf '\033[1m%s\033[0m [y/N] ' "$1" > /dev/tty
    read -r reply < /dev/tty
    case "$reply" in [yY]*) return 0 ;; *) return 1 ;; esac
}

as_root() {
    if [ "$(id -u)" = "0" ]; then "$@"; return; fi
    command -v sudo >/dev/null 2>&1 || die "sudo is required to install system packages"
    have_tty || die "sudo needs a terminal. Download the script and run it: sh install.sh"
    sudo "$@" < /dev/tty
}

# --- preflight ---------------------------------------------------------------

[ "$(uname -s)" = "Linux" ] || die "shipwright's sandbox requires Linux"
command -v git >/dev/null 2>&1 || die "git is required; install it and re-run"

IS_WSL=0
if grep -qi microsoft /proc/version 2>/dev/null; then
    IS_WSL=1
    warn "WSL2 detected. gVisor is not officially supported there and may refuse to start."
fi

# --- docker ------------------------------------------------------------------

if ! command -v docker >/dev/null 2>&1; then
    say "Docker is not installed"
    confirm "Install Docker now? This modifies system packages." \
        || die "Docker is required. shipwright does not install natively."
    say "installing Docker"
    curl -fsSL https://get.docker.com -o "$INSTALL_HOME/get-docker.sh" 2>/dev/null \
        || { mkdir -p "$INSTALL_HOME"; curl -fsSL https://get.docker.com -o "$INSTALL_HOME/get-docker.sh"; }
    as_root sh "$INSTALL_HOME/get-docker.sh"
fi

if ! docker info >/dev/null 2>&1; then
    say "starting the Docker daemon"
    if [ -d /run/systemd/system ]; then
        as_root systemctl enable --now docker || true
    else
        as_root service docker start || true
    fi
fi
docker info >/dev/null 2>&1 || die "the Docker daemon is not reachable. Start it and re-run."

if ! docker info >/dev/null 2>&1 && ! id -nG "$USER" | grep -qw docker; then
    warn "you are not in the 'docker' group; you may need: sudo usermod -aG docker $USER"
fi
say "Docker is available"

# --- gVisor ------------------------------------------------------------------

install_gvisor() {
    say "installing gVisor"
    as_root apt-get update -qq
    as_root apt-get install -y -qq apt-transport-https ca-certificates curl gnupg
    curl -fsSL https://gvisor.dev/archive.key | as_root gpg --dearmor -o "$GVISOR_KEYRING"
    printf 'deb [arch=%s signed-by=%s] https://storage.googleapis.com/gvisor/releases release main\n' \
        "$(dpkg --print-architecture)" "$GVISOR_KEYRING" \
        | as_root tee /etc/apt/sources.list.d/gvisor.list >/dev/null
    as_root apt-get update -qq
    as_root apt-get install -y -qq runsc
}

if ! command -v runsc >/dev/null 2>&1; then
    command -v apt-get >/dev/null 2>&1 \
        || die "gVisor install is automated for apt systems only; install runsc manually and re-run"
    confirm "Install gVisor (runsc) and register it with Docker?" \
        || die "gVisor is required. Re-run with SHIPWRIGHT_ALLOW_UNSANDBOXED=1 only if you accept weaker isolation."
    install_gvisor
fi

if command -v runsc >/dev/null 2>&1; then
    say "registering runsc with Docker"
    as_root runsc install >/dev/null 2>&1 || warn "runsc install reported a problem"
    if [ -d /run/systemd/system ]; then
        as_root systemctl restart docker || true
    else
        as_root service docker restart || true
    fi
    sleep 2
fi

say "probing the sandbox"
RUNTIME="runsc"
if docker run --rm --runtime=runsc hello-world >/dev/null 2>&1; then
    say "gVisor sandbox is working"
else
    if [ "$ALLOW_UNSANDBOXED" = "1" ]; then
        RUNTIME="runc"
        warn "runsc will not start. Continuing UNSANDBOXED because SHIPWRIGHT_ALLOW_UNSANDBOXED=1."
        warn "The agent's commands will run with ordinary container isolation only."
    else
        printf '\n'
        die "gVisor could not start a container, so the sandbox cannot be guaranteed.
  ${IS_WSL:+WSL2 often cannot run gVisor. }Install on native Linux, or re-run with:

      SHIPWRIGHT_ALLOW_UNSANDBOXED=1 sh install.sh

  which proceeds with container isolation only and says so on every launch."
    fi
fi

# --- source and image --------------------------------------------------------

mkdir -p "$INSTALL_HOME"
if [ -d "$SRC_DIR/.git" ]; then
    say "updating $SRC_DIR"
    git -C "$SRC_DIR" fetch --quiet --depth 1 origin "$REF"
    git -C "$SRC_DIR" checkout --quiet FETCH_HEAD
else
    say "cloning $REPO_URL"
    rm -rf "$SRC_DIR"
    git clone --quiet --depth 1 --branch "$REF" "$REPO_URL" "$SRC_DIR" 2>/dev/null \
        || git clone --quiet --depth 1 "$REPO_URL" "$SRC_DIR"
fi

say "building the agent image"
docker build --quiet -f "$SRC_DIR/docker/agent.Dockerfile" -t "$IMAGE_NAME" "$SRC_DIR" >/dev/null

# --- launcher ----------------------------------------------------------------

mkdir -p "$BIN_DIR"
cat > "$BIN_DIR/ship" <<LAUNCHER
#!/bin/sh
# ship --- opens the shipwright interface against the current directory.
#
# Only \$PWD is mounted. The agent cannot see anything above the directory you
# run this in, which is the containment boundary -- not a heuristic.
set -eu
IMAGE="\${SHIPWRIGHT_IMAGE:-$IMAGE_NAME}"
RUNTIME="\${SHIPWRIGHT_RUNTIME:-$RUNTIME}"

if [ "\$RUNTIME" != "runsc" ]; then
    printf '\033[33mwarning:\033[0m running without gVisor (runtime=%s); tools are only container-isolated\n' "\$RUNTIME" >&2
fi

exec docker run --rm -it \\
    --runtime "\$RUNTIME" \\
    --workdir /workspace \\
    --mount "type=bind,source=\$(pwd),target=/workspace" \\
    --env ANTHROPIC_API_KEY --env OPENAI_API_KEY \\
    --env SHIPWRIGHT_PROVIDER --env SHIPWRIGHT_MODEL \\
    "\$IMAGE" ship --repo /workspace "\$@"
LAUNCHER
chmod +x "$BIN_DIR/ship"

say "installed (runtime: $RUNTIME)"
case ":$PATH:" in
    *":$BIN_DIR:"*) printf '\nRun \033[1mship\033[0m inside any project to open it.\n' ;;
    *)
        printf '\n%s is not on your PATH yet. Add it:\n\n' "$BIN_DIR"
        printf '    echo '\''export PATH="%s:$PATH"'\'' >> ~/.bashrc && exec $SHELL\n\n' "$BIN_DIR"
        printf 'Then run \033[1mship\033[0m inside any project to open it.\n'
        ;;
esac
printf 'Only the directory you launch it from is mounted; nothing above it is visible.\n'
printf 'First run asks which provider to use and for its API key.\n'
