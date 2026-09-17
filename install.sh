#!/bin/sh
#
# install.sh --- installs, updates, or removes shipwright.
#
# Usage:
#   sh install.sh              install (default)
#   sh install.sh update       rebuild from the latest source
#   sh install.sh uninstall    remove everything this script created, and offer
#                              to clear stored provider keys
#
# There is deliberately no native install path. The agent runs arbitrary
# commands on your behalf, so it runs inside a gVisor-isolated container or it
# does not run at all. `ship` mounts only the directory you open with it.
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
#
# The log reads like apt: one line per step once it is finished ("Checking
# Docker... 29.8.0", "Setting up ship (1.1.1) ..."), warnings as "W:" and
# errors as "E:". On a terminal the last line is a progress bar that every log
# line scrolls above:
#
#   Progress: [ 42%] [#######################...............................]

if [ -t 1 ]; then SHOW_BAR=1; else SHOW_BAR=0; fi
COLS=$(tput cols 2>/dev/null || echo 80)
PERCENT=0

# Drawing code shared by the shell and by the parser that streams build output.
BAR_AWK='
function bar(pct,    width, filled, cells, i) {
    if (pct > 100) pct = 100
    width = cols - 20
    if (width < 10) width = 10
    filled = int(pct * width / 100)
    cells = ""
    for (i = 0; i < width; i++) cells = cells (i < filled ? "#" : ".")
    printf "\r\033[K\033[42;30mProgress: [%3d%%]\033[0m [%s]", pct, cells
    fflush()
}
function unbar() { printf "\r\033[K"; fflush() }'

draw_bar() {
    [ "$SHOW_BAR" = 1 ] || return 0
    awk -v pct="$PERCENT" -v cols="$COLS" "$BAR_AWK"' BEGIN { bar(pct) }'
}
clear_bar() {
    [ "$SHOW_BAR" = 1 ] || return 0
    printf '\r\033[K'
}

say()    { clear_bar; printf '%s\n' "$*"; draw_bar; }
# A step prints nothing when it starts; done_step prints its one line at the end.
step() {
    STEP_NUMBER=$((STEP_NUMBER + 1))
    PERCENT=$(((STEP_NUMBER - 1) * 100 / TOTAL_STEPS))
    STEP_LABEL=$*
    draw_bar
}
done_step() { say "$STEP_LABEL... ${1:-Done}"; }
warn()   { clear_bar; printf 'W: %s\n' "$*" >&2; draw_bar; }
die()    { clear_bar; printf 'E: %s\n' "$*" >&2; exit 1; }

# Fill the bar, then take it down: like apt, a finished run leaves only its log.
finish() {
    PERCENT=100
    draw_bar
    clear_bar
}

run() { "$@"; }

# Run a long command and turn its output into log lines and bar movement.
#
# $1 says how to read the output ("git" or "docker"); the rest is the command.
# The command's share of the bar is the current step, so a clone moves the bar
# from 57% towards 71% instead of restarting a bar of its own. Everything the
# command printed goes to a log whose tail is shown if it fails, so hiding the
# noise never hides an error.
with_progress() {
    parser=$1
    shift
    progress_log=$(mktemp)
    progress_status=$(mktemp)
    # "|| progress_rc=$?" keeps set -e from ending the group before the status is saved.
    { progress_rc=0; "$@" 2>&1 || progress_rc=$?; echo "$progress_rc" > "$progress_status"; } \
        | tee "$progress_log" \
        | tr '\r' '\n' \
        | awk -v parser="$parser" -v show="$SHOW_BAR" -v cols="$COLS" \
              -v base="$PERCENT" -v span="$((100 / TOTAL_STEPS))" "$BAR_AWK"'
            function log_line(text) {
                if (show) unbar()
                if (length(text) > cols - 1) text = substr(text, 1, cols - 2) "…"
                print text
                if (show) bar(current)
                fflush()
            }
            function advance(pct) {
                pct = base + int(pct * span / 100)
                if (pct <= current) return
                current = pct
                if (show) bar(current)
            }
            function percent_in(line) {
                if (match(line, /[0-9]+%/)) return substr(line, RSTART, RLENGTH - 1) + 0
                return -1
            }
            BEGIN { current = base; srand(); started = srand() }
            parser == "git" {
                if (match($0, /[0-9.]+ [KMG]?i?B/) && $0 ~ /Receiving objects/) size = substr($0, RSTART, RLENGTH)
                p = percent_in($0)
                if (p < 0) next
                if ($0 ~ /Counting objects/)         advance(int(p * 5 / 100))
                else if ($0 ~ /Compressing objects/) advance(5 + int(p * 5 / 100))
                else if ($0 ~ /Receiving objects/)   advance(10 + int(p * 80 / 100))
                else if ($0 ~ /Resolving deltas/)    advance(90 + int(p * 10 / 100))
                next
            }
            parser == "docker" {
                # BuildKit: "#7 [builder 2/9] RUN ..."; classic builder: "Step 2/9 : RUN ...".
                if (!match($0, /\[[^]]*[0-9]+\/[0-9]+\]/) && !match($0, /Step [0-9]+\/[0-9]+/)) next
                token = substr($0, RSTART, RLENGTH)
                if (token in seen) next
                seen[token] = 1
                stage = token
                sub(/[0-9]+\/[0-9]+\]?$/, "", stage)
                match(token, /[0-9]+\/[0-9]+/)
                split(substr(token, RSTART, RLENGTH), nm, "/")
                if (!(stage in total)) { total[stage] = nm[2]; all += nm[2] }
                if (nm[1] - 1 > done[stage]) { finished += nm[1] - 1 - done[stage]; done[stage] = nm[1] - 1 }
                advance(int(finished * 100 / all))
                next
            }
            END {
                if ((getline code < status_file) <= 0 || code != "0") exit
                advance(100)
                srand(); elapsed = srand() - started
                if (parser == "git" && size != "") log_line("Fetched " size " in " elapsed "s")
            }' status_file="$progress_status"
    progress_code=$(cat "$progress_status" 2>/dev/null || echo 1)
    if [ "$progress_code" != "0" ]; then
        clear_bar
        printf 'E: %s exited with status %s; last lines of its output:\n' "$1" "$progress_code" >&2
        tail -n 20 "$progress_log" | tr '\r' '\n' | tail -n 20 | sed 's/^/  /' >&2
    else
        PERCENT=$((PERCENT + 100 / TOTAL_STEPS))
    fi
    rm -f "$progress_log" "$progress_status"
    return "$progress_code"
}

# The node exists even with no controlling terminal, so test an actual open.
# Done in a subshell: a redirection failure on a special builtin kills the shell.
have_tty() { ( exec >/dev/tty ) 2>/dev/null; }

as_root() {
    if [ "$(id -u)" = "0" ]; then run "$@"; return; fi
    command -v sudo >/dev/null 2>&1 || die "sudo is required to install system packages"
    have_tty || die "sudo needs a terminal. Download the script and run it: sh install.sh"
    clear_bar
    sudo "$@" < /dev/tty
    draw_bar
}

# --- uninstall ---------------------------------------------------------------

if [ "$MODE" = "uninstall" ]; then
    TOTAL_STEPS=4
    step "Removing launchers"
    for launcher in ship shipwright ship-update ship-uninstall; do
        if [ -e "$BIN_DIR/$launcher" ]; then
            say "Removing $launcher ..."
            run rm -f "$BIN_DIR/$launcher"
        fi
    done

    step "Removing the container image"
    if command -v docker >/dev/null 2>&1 && $DOCKER image inspect "$IMAGE_NAME" >/dev/null 2>&1; then
        say "Removing $IMAGE_NAME ..."
        run $DOCKER image rm -f "$IMAGE_NAME" >/dev/null
    fi

    step "Removing installed files"
    if [ -d "$INSTALL_HOME" ]; then
        say "Removing $INSTALL_HOME ($(du -sh "$INSTALL_HOME" 2>/dev/null | cut -f1)) ..."
        run rm -rf "$INSTALL_HOME"
    fi

    step "Clearing stored provider keys"
    KEY_FILES=$(find "$HOME" -maxdepth 5 -type f -name .env \
        -not -path "*/node_modules/*" -not -path "*/.git/*" -not -path "*/.venv/*" 2>/dev/null \
        | while read -r envfile; do
              grep -qE '^(export )?(ANTHROPIC|OPENAI)_API_KEY=.+' "$envfile" && echo "$envfile"
          done)
    # Uninstalling means starting afresh, so every stored key goes, unasked.
    # Only the provider key lines are removed; the rest of each file stays.
    if [ -n "$KEY_FILES" ]; then
        echo "$KEY_FILES" | while read -r envfile; do
            sed -i -E '/^(export )?(ANTHROPIC|OPENAI)_API_KEY=/d' "$envfile"
            if grep -qE '[^[:space:]]' "$envfile"; then
                say "Clearing keys from $envfile ..."
            else
                rm -f "$envfile"
                say "Removing $envfile ..."
            fi
        done
    fi

    finish
    exit 0
fi

# --- preflight ---------------------------------------------------------------

step "Checking prerequisites"
[ "$(uname -s)" = "Linux" ] || die "the sandbox requires Linux; found $(uname -s)"
if [ -r /etc/os-release ]; then
    . /etc/os-release
fi
command -v git >/dev/null 2>&1 || die "git is required; install it and re-run"
done_step

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
DOCKER_VERSION=$(docker --version | sed 's/Docker version //; s/,.*//')

if docker info >/dev/null 2>&1; then
    :
elif sudo docker info >/dev/null 2>&1; then
    # The daemon is up; this user just is not allowed to talk to its socket.
    as_root usermod -aG docker "$USER"
    warn "added $USER to the docker group; using sudo for docker until the next login"
    DOCKER="sudo docker"
    NEEDS_RELOGIN=1
else
    if [ -d /run/systemd/system ]; then
        as_root systemctl enable --now docker || true
    else
        as_root service docker start || true
    fi
    sleep 2
    if docker info >/dev/null 2>&1; then
        :
    elif sudo docker info >/dev/null 2>&1; then
        as_root usermod -aG docker "$USER"
        warn "added $USER to the docker group; using sudo for docker until the next login"
        DOCKER="sudo docker"
        NEEDS_RELOGIN=1
    else
        die "the Docker daemon could not be started. Check: sudo systemctl status docker"
    fi
fi
done_step "$DOCKER_VERSION"

# --- gVisor ------------------------------------------------------------------

step "Checking gVisor"
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
RUNSC_VERSION=$(runsc --version 2>/dev/null | head -1 | awk '{print $NF}')

if $DOCKER info --format '{{range printf \"%s\" .Runtimes}}{{.}}{{end}}' 2>/dev/null | grep -q runsc \
    || $DOCKER info 2>/dev/null | grep -q runsc; then
    done_step "$RUNSC_VERSION"
else
    die "runsc is installed but Docker does not know about it.

  Register it and restart the daemon, then re-run this script:

      sudo runsc install && sudo systemctl restart docker"
fi

# --- sandbox probe -----------------------------------------------------------

step "Testing the sandbox"
if $DOCKER run --rm --runtime=runsc hello-world >/dev/null 2>&1; then
    done_step
else
    die "gVisor is registered but could not actually start a container.

  The sandbox is the whole safety boundary, so the install stops here.

  Check what went wrong with:

      docker run --rm --runtime=runsc hello-world

  gVisor needs a kernel of 4.14.77 or newer with CONFIG_SECCOMP_FILTER, and it
  defaults to the systrap platform, which needs no virtualisation support."
fi

# --- source ------------------------------------------------------------------

step "Fetching the source"
mkdir -p "$INSTALL_HOME"
if [ -d "$SRC_DIR/.git" ]; then
    say "Get:1 $REPO_URL $REF"
    with_progress git git -C "$SRC_DIR" fetch --progress --depth 1 origin "$REF"
    run git -C "$SRC_DIR" checkout --quiet FETCH_HEAD
else
    say "Get:1 $REPO_URL $REF"
    rm -rf "$SRC_DIR"
    # A branch or tag clones directly; anything else (a commit) needs the fallback.
    if git ls-remote --exit-code "$REPO_URL" "$REF" >/dev/null 2>&1; then
        with_progress git git clone --progress --depth 1 --branch "$REF" "$REPO_URL" "$SRC_DIR"
    else
        with_progress git git clone --progress "$REPO_URL" "$SRC_DIR"
        run git -C "$SRC_DIR" checkout --quiet "$REF"
    fi
fi

# --- image -------------------------------------------------------------------

step "Building $IMAGE_NAME"
if $DOCKER buildx version >/dev/null 2>&1; then
    BUILD_OUTPUT="--progress=plain"
else
    BUILD_OUTPUT=""
fi
# shellcheck disable=SC2086 # $DOCKER may be "sudo docker"; $BUILD_OUTPUT may be empty
with_progress docker $DOCKER build $BUILD_OUTPUT -f "$SRC_DIR/docker/agent.Dockerfile" -t "$IMAGE_NAME" "$SRC_DIR"
done_step "Done ($($DOCKER image inspect "$IMAGE_NAME" --format '{{.Size}}' | awk '{printf "%.0f MB", $1/1048576}'))"

# --- launchers ---------------------------------------------------------------

step "Installing launchers"
mkdir -p "$BIN_DIR"
VERSION=$(sed -n 's/^__version__ = "\(.*\)"$/\1/p' "$SRC_DIR/agent/__init__.py")

# The launcher is one file, shared by this installer and the Debian package.
sed "s|@IMAGE_NAME@|$IMAGE_NAME|; s|@STATE_DIR@|$INSTALL_HOME/state|" \
    "$SRC_DIR/packaging/ship.sh" > "$BIN_DIR/ship"
chmod +x "$BIN_DIR/ship"
say "Setting up ship ($VERSION) ..."

# Update fetches first and then runs the installer it fetched, so an update is
# carried out by the new version's own steps rather than the ones installed.
cat > "$BIN_DIR/ship-update" <<UPDATER
#!/bin/sh
set -e
git -C "$SRC_DIR" fetch --quiet --depth 1 origin "$REF"
git -C "$SRC_DIR" checkout --quiet FETCH_HEAD
exec sh "$SRC_DIR/install.sh" update
UPDATER
chmod +x "$BIN_DIR/ship-update"
say "Setting up ship-update ($VERSION) ..."

printf '#!/bin/sh\nexec sh "%s/install.sh" uninstall\n' "$SRC_DIR" > "$BIN_DIR/ship-uninstall"
chmod +x "$BIN_DIR/ship-uninstall"
say "Setting up ship-uninstall ($VERSION) ..."

# --- done --------------------------------------------------------------------

finish

case ":$PATH:" in
    *":$BIN_DIR:"*) ;;
    *)
        warn "$BIN_DIR is not on your PATH. Add it with:"
        printf '  echo '\''export PATH="%s:$PATH"'\'' >> ~/.bashrc && exec $SHELL\n' "$BIN_DIR" >&2
        ;;
esac
