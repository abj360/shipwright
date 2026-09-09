#!/bin/sh
#
# install.sh --- installs, updates, or removes shipwright.
#
# Usage:
#   sh install.sh              install (default)
#   sh install.sh update       rebuild from the latest source
#   sh install.sh uninstall    remove everything this script created
#
# There is deliberately no native install path. The agent runs arbitrary
# commands on your behalf, so it runs inside a gVisor-isolated container or it
# does not run at all. `ship` mounts only the directory you launch it in.
#
# Environment overrides:
#   SHIPWRIGHT_HOME  SHIPWRIGHT_BIN  SHIPWRIGHT_REPO_URL  SHIPWRIGHT_REF

set -eu

MODE="${1:-install}"
REPO_URL="${SHIPWRIGHT_REPO_URL:-https://github.com/abj360/shipwright.git}"
REF="${SHIPWRIGHT_REF:-main}"
INSTALL_HOME="${SHIPWRIGHT_HOME:-$HOME/.local/share/shipwright}"
BIN_DIR="${SHIPWRIGHT_BIN:-$HOME/.local/bin}"
SRC_DIR="$INSTALL_HOME/src"
IMAGE_NAME="shipwright-agent:latest"
TOTAL_STEPS=7
STEP_NUMBER=0
# Docker may only be reachable through sudo until a new login picks up the
# docker group, so every docker call goes through this.
DOCKER="docker"
NEEDS_RELOGIN=0

# --- logging -----------------------------------------------------------------

stamp() { date '+%H:%M:%S'; }
step() {
    STEP_NUMBER=$((STEP_NUMBER + 1))
    printf '\n\033[1;36m[%d/%d]\033[0m \033[2m%s\033[0m  \033[1m%s\033[0m\n' \
        "$STEP_NUMBER" "$TOTAL_STEPS" "$(stamp)" "$*"
}
detail() { printf '        \033[2m%s\033[0m %s\n' "·" "$*"; }
ok()     { printf '        \033[32m✓\033[0m %s\n' "$*"; }
skip()   { printf '        \033[2m—\033[0m %s\n' "$*"; }
warn()   { printf '        \033[33m!\033[0m %s\n' "$*" >&2; }
die()    { printf '\n\033[31merror:\033[0m %s\n' "$*" >&2; exit 1; }

# Run a command, echoing it first so the log shows exactly what happened.
run() {
    printf '        \033[2m$ %s\033[0m\n' "$*"
    "$@"
}

# The node exists even with no controlling terminal, so test an actual open.
# Done in a subshell: a redirection failure on a special builtin kills the shell.
have_tty() { ( exec >/dev/tty ) 2>/dev/null; }

confirm() {
    have_tty || die "no terminal for confirmation. Download the script and run it: sh install.sh"
    printf '        \033[1m%s\033[0m [y/N] ' "$1" > /dev/tty
    read -r reply < /dev/tty
    case "$reply" in [yY]*) return 0 ;; *) return 1 ;; esac
}

as_root() {
    if [ "$(id -u)" = "0" ]; then run "$@"; return; fi
    command -v sudo >/dev/null 2>&1 || die "sudo is required to install system packages"
    have_tty || die "sudo needs a terminal. Download the script and run it: sh install.sh"
    printf '        \033[2m$ sudo %s\033[0m\n' "$*"
    sudo "$@" < /dev/tty
}

# --- uninstall ---------------------------------------------------------------

if [ "$MODE" = "uninstall" ]; then
    TOTAL_STEPS=3
    printf '\033[1mRemoving shipwright\033[0m\n'

    step "Removing launchers from $BIN_DIR"
    for launcher in ship shipwright ship-update ship-uninstall; do
        if [ -e "$BIN_DIR/$launcher" ]; then
            run rm -f "$BIN_DIR/$launcher"
            ok "removed $launcher"
        else
            skip "$launcher was not installed"
        fi
    done

    step "Removing the container image"
    if command -v docker >/dev/null 2>&1 && $DOCKER image inspect "$IMAGE_NAME" >/dev/null 2>&1; then
        run $DOCKER image rm -f "$IMAGE_NAME" >/dev/null
        ok "removed $IMAGE_NAME"
    else
        skip "no image to remove"
    fi

    step "Removing $INSTALL_HOME"
    if [ -d "$INSTALL_HOME" ]; then
        detail "$(du -sh "$INSTALL_HOME" 2>/dev/null | cut -f1) of files"
        run rm -rf "$INSTALL_HOME"
        ok "removed the checkout and cached files"
    else
        skip "nothing installed there"
    fi

    printf '\n\033[32mshipwright removed.\033[0m Docker and gVisor were left installed.\n'
    exit 0
fi

# --- preflight ---------------------------------------------------------------

printf '\033[1mshipwright %s\033[0m\n' "$MODE"

step "Checking prerequisites"
[ "$(uname -s)" = "Linux" ] || die "the sandbox requires Linux; found $(uname -s)"
if [ -r /etc/os-release ]; then
    . /etc/os-release
    ok "linux: ${NAME:-unknown} ${VERSION_ID:-}"
else
    ok "linux: $(uname -sr)"
fi
detail "kernel $(uname -r)"
command -v git >/dev/null 2>&1 || die "git is required; install it and re-run"
ok "git: $(git --version | awk '{print $3}')"
if grep -qi microsoft /proc/version 2>/dev/null; then
    warn "WSL2 detected — gVisor is unsupported there and may refuse to start"
fi
detail "install prefix: $INSTALL_HOME"
detail "launchers:      $BIN_DIR"

# --- docker ------------------------------------------------------------------

step "Checking Docker"
if ! command -v docker >/dev/null 2>&1; then
    die "Docker is required, and it is not installed.

  shipwright has no native install path: the agent runs arbitrary commands on
  your behalf, so it runs inside a container or it does not run at all.

  Install Docker first, then re-run this script.

      Docs:    https://docs.docker.com/engine/install/
      Ubuntu:  curl -fsSL https://get.docker.com | sudo sh
      WSL2:    Docker Desktop with WSL integration is usually smoother
               https://docs.docker.com/desktop/wsl/

  Then:  sh $0"
fi
ok "docker: $(docker --version | sed 's/Docker version //; s/,.*//')"

if docker info >/dev/null 2>&1; then
    ok "daemon reachable"
elif sudo docker info >/dev/null 2>&1; then
    # The daemon is up; this user just is not allowed to talk to its socket.
    detail "daemon is running, but $USER cannot reach $(ls -l /var/run/docker.sock 2>/dev/null | awk '{print $3":"$4}')"
    as_root usermod -aG docker "$USER"
    ok "added $USER to the docker group"
    detail "group membership only applies to new logins, so this install uses sudo"
    DOCKER="sudo docker"
    NEEDS_RELOGIN=1
else
    detail "daemon is not running; starting it"
    if [ -d /run/systemd/system ]; then
        as_root systemctl enable --now docker || true
    else
        as_root service docker start || true
    fi
    sleep 2
    if docker info >/dev/null 2>&1; then
        ok "daemon started"
    elif sudo docker info >/dev/null 2>&1; then
        as_root usermod -aG docker "$USER"
        ok "daemon started; added $USER to the docker group"
        DOCKER="sudo docker"
        NEEDS_RELOGIN=1
    else
        die "the Docker daemon could not be started. Check: sudo systemctl status docker"
    fi
fi

# --- gVisor ------------------------------------------------------------------

step "Checking the gVisor sandbox"
if ! command -v runsc >/dev/null 2>&1; then
    die "gVisor (runsc) is required, and it is not installed.

  The agent runs arbitrary commands on your behalf. It runs under gVisor or it
  does not run: there is no unsandboxed mode.

  Install it, then re-run this script:

      Docs:   https://gvisor.dev/docs/user_guide/install/

      Debian/Ubuntu:
        sudo apt-get update && sudo apt-get install -y apt-transport-https ca-certificates curl gnupg
        curl -fsSL https://gvisor.dev/archive.key | sudo gpg --dearmor -o /usr/share/keyrings/gvisor-archive-keyring.gpg
        echo 'deb [arch=\$(dpkg --print-architecture) signed-by=/usr/share/keyrings/gvisor-archive-keyring.gpg] https://storage.googleapis.com/gvisor/releases release main' | sudo tee /etc/apt/sources.list.d/gvisor.list > /dev/null
        sudo apt-get update && sudo apt-get install -y runsc

  Then register it with Docker:

        sudo runsc install && sudo systemctl restart docker"
fi
ok "runsc: $(runsc --version 2>/dev/null | head -1 | awk '{print $NF}')"

if $DOCKER info --format '{{range printf \"%s\" .Runtimes}}{{.}}{{end}}' 2>/dev/null | grep -q runsc \
    || $DOCKER info 2>/dev/null | grep -q runsc; then
    ok "registered as a Docker runtime"
else
    die "runsc is installed but Docker does not know about it.

  Register it and restart the daemon, then re-run this script:

      sudo runsc install && sudo systemctl restart docker"
fi

# --- sandbox probe -----------------------------------------------------------

step "Proving the sandbox actually starts"
detail "launching a throwaway container under runsc"
if $DOCKER run --rm --runtime=runsc hello-world >/dev/null 2>&1; then
    ok "gVisor sandbox verified"
else
    die "gVisor is registered but could not actually start a container.

  The sandbox is the whole safety boundary, so the install stops here.

  On WSL2 this is expected: gVisor is not supported on the WSL kernel. Install
  on native Linux, or in a VM with a stock kernel.

  Check what went wrong with:

      docker run --rm --runtime=runsc hello-world"
fi

# --- source ------------------------------------------------------------------

step "Fetching the source"
mkdir -p "$INSTALL_HOME"
if [ -d "$SRC_DIR/.git" ]; then
    detail "updating the existing checkout"
    run git -C "$SRC_DIR" fetch --quiet --depth 1 origin "$REF"
    run git -C "$SRC_DIR" checkout --quiet FETCH_HEAD
else
    detail "cloning $REPO_URL ($REF)"
    rm -rf "$SRC_DIR"
    git clone --quiet --depth 1 --branch "$REF" "$REPO_URL" "$SRC_DIR" 2>/dev/null \
        || git clone --quiet --depth 1 "$REPO_URL" "$SRC_DIR"
fi
ok "source at $(git -C "$SRC_DIR" rev-parse --short HEAD)"
cp "$0" "$INSTALL_HOME/install.sh" 2>/dev/null || true

# --- image -------------------------------------------------------------------

step "Building the agent image"
detail "this bakes the agent, sandbox policies and interface into $IMAGE_NAME"
run $DOCKER build --quiet -f "$SRC_DIR/docker/agent.Dockerfile" -t "$IMAGE_NAME" "$SRC_DIR" >/dev/null
ok "image built: $($DOCKER image inspect "$IMAGE_NAME" --format '{{.Size}}' | awk '{printf "%.0f MB", $1/1048576}')"

# --- launchers ---------------------------------------------------------------

step "Installing launchers"
mkdir -p "$BIN_DIR"

cat > "$BIN_DIR/ship" <<LAUNCHER
#!/bin/sh
# ship --- opens the shipwright interface against the current directory.
#
# Only \$PWD is mounted, so the agent cannot see anything above the directory
# you run this in. That is the containment boundary.
set -eu
IMAGE="\${SHIPWRIGHT_IMAGE:-$IMAGE_NAME}"

if ! docker info >/dev/null 2>&1; then
    printf '\033[31merror:\033[0m cannot reach Docker.\n' >&2
    if id -nG 2>/dev/null | tr " " "\\n" | grep -qx docker; then
        printf '  Is the daemon running?  sudo systemctl start docker\n' >&2
    else
        printf '  You are not in the docker group yet. Start a new login shell:\n\n' >&2
        printf '      newgrp docker\n\n' >&2
        printf '  or log out and back in, then run ship again.\n' >&2
    fi
    exit 1
fi

if ! command -v runsc >/dev/null 2>&1; then
    printf '\033[31merror:\033[0m gVisor (runsc) is not installed; shipwright will not run without it.\n' >&2
    exit 1
fi

exec docker run --rm -it \\
    --runtime runsc \\
    --workdir /workspace \\
    --mount "type=bind,source=\$(pwd),target=/workspace" \\
    --env ANTHROPIC_API_KEY --env OPENAI_API_KEY \\
    --env SHIPWRIGHT_PROVIDER --env SHIPWRIGHT_MODEL \\
    "\$IMAGE" ship --repo /workspace "\$@"
LAUNCHER
chmod +x "$BIN_DIR/ship"
ok "ship"

printf '#!/bin/sh\nexec sh "%s/install.sh" update\n' "$INSTALL_HOME" > "$BIN_DIR/ship-update"
chmod +x "$BIN_DIR/ship-update"
ok "ship-update      rebuild from the latest source"

printf '#!/bin/sh\nexec sh "%s/install.sh" uninstall\n' "$INSTALL_HOME" > "$BIN_DIR/ship-uninstall"
chmod +x "$BIN_DIR/ship-uninstall"
ok "ship-uninstall   remove shipwright"

# --- done --------------------------------------------------------------------

printf '\n\033[1;32mshipwright is ready\033[0m  (sandboxed with gVisor)\n\n' 
case ":$PATH:" in
    *":$BIN_DIR:"*) printf '  Run \033[1mship\033[0m inside any project to open it.\n' ;;
    *)
        printf '  %s is not on your PATH yet:\n\n' "$BIN_DIR"
        printf '      echo '\''export PATH="%s:$PATH"'\'' >> ~/.bashrc && exec $SHELL\n\n' "$BIN_DIR"
        printf '  Then run \033[1mship\033[0m inside any project.\n'
        ;;
esac
printf '  Only the directory you launch it from is mounted.\n'
printf '  First run asks which provider to use and for its API key.\n\n'
printf '  \033[2mship-update\033[0m     update to the latest version\n'
printf '  \033[2mship-uninstall\033[0m  remove it again\n'
