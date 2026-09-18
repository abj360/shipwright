#!/bin/sh
# ship --- opens the shipwright interface on a directory.
#
# Usage: ship [PATH] [options]
#
#   PATH is '.', '..', a relative path, or an absolute one, and defaults to the
#   current directory. Only that directory is mounted, so the agent cannot see
#   anything above it. That is the containment boundary.
set -eu
IMAGE="${SHIPWRIGHT_IMAGE:-@IMAGE_NAME@}"
# Lives inside the install, so uninstalling forgets onboarding along with it.
STATE_DIR="@STATE_DIR@"
VERSION="@VERSION@"
UPDATER="@UPDATER@"
RELEASES_URL="${SHIPWRIGHT_RELEASES_URL:-https://api.github.com/repos/abj360/shipwright/releases/latest}"
UPDATE_MARKER="$STATE_DIR/update-requested"

die() {
    printf '\033[31merror:\033[0m %s\n' "$*" >&2
    exit 1
}

# Take the directory out of the arguments and pass everything else through,
# in order. Flags that take a value keep it, so `ship --provider openai ..`
# does not mistake "openai" for the directory.
TARGET=""
remaining=$#
while [ "$remaining" -gt 0 ]; do
    arg=$1
    shift
    remaining=$((remaining - 1))
    case "$arg" in
        --repo=*)
            [ -z "$TARGET" ] || die "give the directory once"
            TARGET=${arg#--repo=}
            ;;
        --repo)
            [ "$remaining" -gt 0 ] || die "--repo needs a directory"
            [ -z "$TARGET" ] || die "give the directory once"
            TARGET=$1
            shift
            remaining=$((remaining - 1))
            ;;
        --provider | --gateway | --mode | --resume)
            set -- "$@" "$arg"
            if [ "$remaining" -gt 0 ]; then
                set -- "$@" "$1"
                shift
                remaining=$((remaining - 1))
            fi
            ;;
        -*)
            set -- "$@" "$arg"
            ;;
        *)
            [ -z "$TARGET" ] || die "give one directory, not both '$TARGET' and '$arg'"
            TARGET=$arg
            ;;
    esac
done

TARGET=${TARGET:-.}
case "$TARGET" in
    "~" | "~/"*) TARGET="$HOME${TARGET#\~}" ;;
esac
[ -e "$TARGET" ] || die "no such directory: $TARGET"
[ -d "$TARGET" ] || die "not a directory: $TARGET"
WORKSPACE=$(cd "$TARGET" && pwd -P)

if [ "$WORKSPACE" = "/" ]; then
    die "refusing to mount / — the agent would see the whole filesystem. Open a project directory."
fi
case "$WORKSPACE" in
    *,*) die "directory paths containing a comma cannot be mounted: $WORKSPACE" ;;
esac

if ! docker info >/dev/null 2>&1; then
    printf '\033[31merror:\033[0m cannot reach Docker.\n' >&2
    if id -nG 2>/dev/null | tr " " "\n" | grep -qx docker; then
        printf '  Is the daemon running?  sudo systemctl start docker\n' >&2
    else
        printf '  You are not in the docker group yet. Start a new login shell:\n\n' >&2
        printf '      newgrp docker\n\n' >&2
        printf '  or log out and back in, then run ship again.\n' >&2
    fi
    exit 1
fi

if ! command -v runsc >/dev/null 2>&1; then
    die "gVisor (runsc) is not installed; shipwright will not run without it."
fi

mkdir -p "$STATE_DIR"
# Sessions and the onboarding marker live here. An older install wrote them as
# root, and the container no longer runs as root, so say so rather than failing
# to save anything.
if [ ! -w "$STATE_DIR" ] || { [ -e "$STATE_DIR/sessions" ] && [ ! -w "$STATE_DIR/sessions" ]; }; then
    printf '\033[33mW:\033[0m %s is not writable; sessions will not be saved.\n' "$STATE_DIR" >&2
    printf '   Take it back with:  sudo chown -R "%s" %s\n' "$(id -un)" "$STATE_DIR" >&2
fi

# As you, not as root: anything the agent writes into the directory has to be
# yours to read, edit and delete afterwards. HOME points somewhere writable
# because that user has no home inside the container.
# Which version is published, if the network answers quickly. The interface
# offers the update; this only tells it there is one.
latest_version() {
    command -v curl >/dev/null 2>&1 || return 0
    curl -fsS --max-time 3 "$RELEASES_URL" 2>/dev/null \
        | sed -n 's/.*"tag_name"[[:space:]]*:[[:space:]]*"v\{0,1\}\([^"]*\)".*/\1/p' \
        | head -1
}

UPDATE_AVAILABLE=""
# A launch that just updated does not ask again: if the update did not take,
# offering it once more every time would be a loop, not a prompt.
if [ -z "${SHIPWRIGHT_UPDATE_CHECKED:-}" ]; then
    LATEST=$(latest_version || true)
    if [ -n "$LATEST" ] && [ "$LATEST" != "$VERSION" ]; then
        UPDATE_AVAILABLE=$LATEST
    fi
fi

rm -f "$UPDATE_MARKER"
docker run --rm -it \
    --runtime runsc \
    --user "$(id -u):$(id -g)" \
    --env HOME=/tmp \
    --workdir /workspace \
    --mount "type=bind,source=$WORKSPACE,target=/workspace" \
    --mount "type=bind,source=$STATE_DIR,target=/state" \
    --env SHIPWRIGHT_STATE_DIR=/state \
    --env ANTHROPIC_API_KEY --env OPENAI_API_KEY \
    --env SHIPWRIGHT_PROVIDER --env SHIPWRIGHT_MODEL \
    --env SHIPWRIGHT_VERSION="$VERSION" \
    --env SHIPWRIGHT_UPDATE_AVAILABLE="$UPDATE_AVAILABLE" \
    "$IMAGE" ship --repo /workspace "$@"

# The interface leaves this behind when the operator accepts the update: the
# update runs out here, where Docker is, and the session is reopened after it.
[ -f "$UPDATE_MARKER" ] || exit 0
SESSION=$(sed -n '1p' "$UPDATE_MARKER")
rm -f "$UPDATE_MARKER"
"$UPDATER" update || die "update failed; the version you had is still installed"
export SHIPWRIGHT_UPDATE_CHECKED=1
if [ -n "$SESSION" ]; then
    exec "$0" --resume "$SESSION" "$WORKSPACE"
fi
exec "$0" "$WORKSPACE"
