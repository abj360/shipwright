#!/usr/bin/env python3
"""
sessions.py --- saves a conversation under an id so it can be resumed later

Contains:
    SESSIONS_SUBDIR: the folder sessions live in, inside the state directory
    UPDATE_MARKER: the file the launcher looks for to apply an update
    state_dir(): the install's state directory, empty when there is none
    request_update(): asks the launcher to update and reopen this session
    SESSION_FILE_MODE: owner-only permissions for a saved session
    SESSION_ID_PATTERN: what a session id looks like
    STATE_DIR_ENV: the variable naming the install's state directory
    SESSIONS_DIR_ENV: the variable that overrides where sessions are kept
    sessions_dir(): where sessions are kept on this machine
    new_session_id(): a fresh id for a session
    SavedStep: one tool call as it was recorded
    SavedTurn: one instruction, the steps it took, and the answer
    SavedTurn.messages(): the turn as the two messages the model replays
    save_session(): writes a session's turns to disk
    load_session(): reads a session's turns back
"""

import json
import os
import re
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from agent.llm_client import Message

SESSIONS_SUBDIR = "sessions"
# The launcher reads this after the interface closes, and applies the update.
UPDATE_MARKER = "update-requested"
SESSION_FILE_MODE = 0o600
SESSION_ID_PATTERN = re.compile(r"^[0-9a-f]{12}$")
# Set by the installed launcher to a directory kept inside the install.
STATE_DIR_ENV = "SHIPWRIGHT_STATE_DIR"
# Points sessions somewhere else entirely; the test suite uses it.
SESSIONS_DIR_ENV = "SHIPWRIGHT_SESSIONS_DIR"
# Outside the installed launcher there is no state directory, so a run from a
# checkout keeps its sessions where the install would.
FALLBACK_STATE_DIR = Path.home() / ".local" / "share" / "shipwright" / "state"


def sessions_dir(environ: Mapping[str, str] | None = None) -> Path:
    """Returns where sessions are kept on this machine.

    Sessions live in the install's state directory, so uninstalling removes
    them along with everything else.

    Args:
        environ: Environment to read the state directory from.

    Returns:
        path: Directory holding one file per session.
    """
    source = os.environ if environ is None else environ
    override = source.get(SESSIONS_DIR_ENV, "").strip()
    if override:
        return Path(override)
    state = source.get(STATE_DIR_ENV, "").strip()
    return (Path(state) if state else FALLBACK_STATE_DIR) / SESSIONS_SUBDIR


@dataclass
class SavedStep:
    """Records one tool call exactly as the timeline drew it.

    Attributes:
        tool_name: Tool the agent dispatched.
        tool_args: Arguments it was dispatched with.
        observation: Output the tool returned.
        diff: Diff the step produced, empty when it changed nothing.
    """

    tool_name: str
    tool_args: dict[str, str] = field(default_factory=dict)
    observation: str = ""
    diff: str = ""


@dataclass
class SavedTurn:
    """Records one instruction, everything it did, and the answer it gave.

    Attributes:
        instruction: What the operator asked for.
        answer: What the agent reported back.
        steps: Tool calls the turn made, in order.
    """

    instruction: str
    answer: str = ""
    steps: list[SavedStep] = field(default_factory=list)

    def messages(self) -> list[Message]:
        """Renders the turn as the pair of messages the model replays.

        Returns:
            messages: The instruction and the answer, in that order.
        """
        return [
            Message(role="user", content=self.instruction),
            Message(role="assistant", content=self.answer),
        ]


def state_dir(environ: Mapping[str, str] | None = None) -> Path | None:
    """Returns the install's state directory, when the launcher provided one.

    Args:
        environ: Environment to read the state directory from.

    Returns:
        path: The directory, or None outside an installed launcher.
    """
    source = os.environ if environ is None else environ
    configured = source.get(STATE_DIR_ENV, "").strip()
    return Path(configured) if configured else None


def request_update(session_id: str, directory: Path) -> Path:
    """Leaves the marker the launcher acts on once the interface closes.

    The update itself happens outside: rebuilding the image needs Docker,
    which the sandbox deliberately cannot reach.

    Args:
        session_id: Session to reopen once the update is installed.
        directory: State directory the launcher watches.

    Returns:
        path: The marker that was written.
    """
    directory.mkdir(parents=True, exist_ok=True)
    marker = directory / UPDATE_MARKER
    marker.write_text(f"{session_id}\n")
    return marker


def new_session_id() -> str:
    """Returns a fresh id, short enough to type back in.

    Returns:
        session_id: Twelve lowercase hex characters.
    """
    return uuid.uuid4().hex[:12]


def save_session(session_id: str, repo_path: Path, turns: list[SavedTurn], directory: Path) -> Path:
    """Writes a session's turns to disk, replacing any earlier save.

    Whole turns are saved, not just the messages, so resuming can redraw the
    activity cards and diffs the operator saw the first time.

    Args:
        session_id: Id the session is saved under.
        repo_path: Directory the session worked in.
        turns: Turns taken so far, oldest first.
        directory: Folder sessions are kept in.

    Returns:
        path: File the session was written to.
    """
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{session_id}.json"
    payload = {
        "id": session_id,
        "repo": str(repo_path),
        "turns": [
            {
                "instruction": turn.instruction,
                "answer": turn.answer,
                "steps": [
                    {
                        "tool_name": step.tool_name,
                        "tool_args": step.tool_args,
                        "observation": step.observation,
                        "diff": step.diff,
                    }
                    for step in turn.steps
                ],
            }
            for turn in turns
        ],
    }
    path.write_text(json.dumps(payload, indent=2))
    path.chmod(SESSION_FILE_MODE)
    return path


def load_session(session_id: str, directory: Path) -> list[SavedTurn]:
    """Reads a saved session's turns back.

    A session saved before turns were recorded holds messages alone; those are
    read back as turns with no steps rather than refused.

    Args:
        session_id: Id the session was saved under.
        directory: Folder sessions are kept in.

    Returns:
        turns: The saved turns, oldest first.

    Raises:
        LookupError: The id is malformed or no session was saved under it.
    """
    if not SESSION_ID_PATTERN.match(session_id):
        raise LookupError(f"not a session id: {session_id}")
    path = directory / f"{session_id}.json"
    if not path.is_file():
        raise LookupError(f"no saved session {session_id}")
    try:
        body = path.read_text()
    except OSError as exc:
        raise LookupError(f"cannot read session {session_id}: {exc.strerror or exc}") from exc
    try:
        payload = json.loads(body)
    except ValueError as exc:
        raise LookupError(f"session {session_id} is not readable JSON: {exc}") from exc
    if "turns" not in payload:
        messages = payload.get("messages", [])
        pairs = zip(messages[::2], messages[1::2], strict=False)
        return [SavedTurn(instruction=a["content"], answer=b["content"]) for a, b in pairs]
    return [
        SavedTurn(
            instruction=turn["instruction"],
            answer=turn["answer"],
            steps=[SavedStep(**step) for step in turn["steps"]],
        )
        for turn in payload["turns"]
    ]
