#!/bin/sh
#
# install.sh --- installs shipwright and puts `ship` on your PATH.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/abj360/shipwright/main/install.sh | sh
#
# What it does:
#   1. Checks for git and a Python 3.12+ interpreter.
#   2. Clones (or updates) the repo under ~/.local/share/shipwright.
#   3. Builds an isolated venv there and installs shipwright into it.
#   4. Links `ship` into ~/.local/bin.
#
# Environment overrides:
#   SHIPWRIGHT_HOME      where the checkout and venv live
#   SHIPWRIGHT_BIN       where the `ship` launcher is linked
#   SHIPWRIGHT_REPO_URL  clone source (a local path works, for testing)
#   SHIPWRIGHT_REF       branch or tag to install
#
# Re-running upgrades an existing install in place.

set -eu

REPO_URL="${SHIPWRIGHT_REPO_URL:-https://github.com/abj360/shipwright.git}"
REF="${SHIPWRIGHT_REF:-main}"
INSTALL_HOME="${SHIPWRIGHT_HOME:-$HOME/.local/share/shipwright}"
BIN_DIR="${SHIPWRIGHT_BIN:-$HOME/.local/bin}"
SRC_DIR="$INSTALL_HOME/src"
VENV_DIR="$INSTALL_HOME/venv"
MIN_MINOR=12

say() { printf '\033[36m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[33mwarning:\033[0m %s\n' "$*" >&2; }
die() { printf '\033[31merror:\033[0m %s\n' "$*" >&2; exit 1; }

# --- prerequisites -----------------------------------------------------------

case "$(uname -s)" in
    Linux) ;;
    Darwin) warn "macOS is untested; the sandbox needs Linux to run tasks" ;;
    *) die "unsupported platform: $(uname -s)" ;;
esac

command -v git >/dev/null 2>&1 || die "git is required; install it and re-run"

# Pick the newest interpreter that meets the floor. A venv's own python is
# skipped: installing from inside one would pin us to that environment.
find_python() {
    for candidate in python3.14 python3.13 python3.12 python3; do
        path=$(command -v "$candidate" 2>/dev/null) || continue
        case "$path" in "$VENV_DIR"/*) continue ;; esac
        if "$path" -c "import sys; sys.exit(0 if sys.version_info[:2] >= (3, $MIN_MINOR) else 1)" 2>/dev/null; then
            printf '%s' "$path"
            return 0
        fi
    done
    return 1
}

PYTHON=$(find_python) || die "python 3.$MIN_MINOR or newer is required"
say "using $($PYTHON -V) at $PYTHON"

# --- source ------------------------------------------------------------------

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

# --- environment -------------------------------------------------------------

say "building the environment"
if ! "$PYTHON" -m venv "$VENV_DIR" >/dev/null 2>&1; then
    # Some distros ship python without ensurepip; bootstrap pip by hand.
    rm -rf "$VENV_DIR"
    "$PYTHON" -m venv --without-pip "$VENV_DIR"
    GET_PIP="$INSTALL_HOME/get-pip.py"
    if [ ! -s "$GET_PIP" ]; then
        command -v curl >/dev/null 2>&1 || die "ensurepip is missing and curl is unavailable"
        curl -fsSL https://bootstrap.pypa.io/get-pip.py -o "$GET_PIP"
    fi
    "$VENV_DIR/bin/python" "$GET_PIP" --quiet
fi

"$VENV_DIR/bin/pip" install --quiet --upgrade pip
"$VENV_DIR/bin/pip" install --quiet "$SRC_DIR"

# --- launcher ----------------------------------------------------------------

mkdir -p "$BIN_DIR"
ln -sf "$VENV_DIR/bin/ship" "$BIN_DIR/ship"
ln -sf "$VENV_DIR/bin/shipwright" "$BIN_DIR/shipwright"

VERSION=$("$VENV_DIR/bin/ship" --version 2>/dev/null || echo "shipwright")
say "installed $VERSION"

case ":$PATH:" in
    *":$BIN_DIR:"*)
        printf '\nRun \033[1mship\033[0m in any checkout to open it.\n'
        ;;
    *)
        printf '\n%s is not on your PATH yet. Add it:\n\n' "$BIN_DIR"
        printf '    echo '\''export PATH="%s:$PATH"'\'' >> ~/.bashrc && exec $SHELL\n\n' "$BIN_DIR"
        printf 'Then run \033[1mship\033[0m in any checkout to open it.\n'
        ;;
esac
printf 'First run asks which provider to use and for its API key.\n'
printf 'Uninstall with: rm -rf %s %s/ship %s/shipwright\n' "$INSTALL_HOME" "$BIN_DIR" "$BIN_DIR"
