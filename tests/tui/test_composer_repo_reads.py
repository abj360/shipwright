#!/usr/bin/env python3
"""
test_composer_repo_reads.py --- asserts queueing does not rescan the checkout per keystroke

Contains:
    CountingRepoMap: records how often the checkout was scanned
    test_queueing_several_follow_ups_scans_once(): one scan covers the whole queue
    test_run_state_change_forces_a_rescan(): finishing a run invalidates the scan
    test_composer_without_a_repo_map_still_works(): the cache is optional
"""

from pathlib import Path

from tui.screens.composer import Composer


class CountingRepoMap:
    """Records how many times the checkout was scanned for changes.

    Attributes:
        scans: Number of detect_changes calls received.
        refreshes: Number of refresh calls received.
    """

    def __init__(self) -> None:
        """Starts a map that has not been scanned yet."""
        self.root = Path(".")
        self.scans = 0
        self.refreshes = 0

    def detect_changes(self) -> list[str]:
        """Records one scan and reports nothing changed.

        Returns:
            changed: Always empty; the count is what the test asserts on.
        """
        self.scans += 1
        return []

    def refresh(self, changed: list[str]) -> int:
        """Records one refresh.

        Args:
            changed: Paths to invalidate; ignored here.

        Returns:
            dropped: Always zero.
        """
        self.refreshes += 1
        return 0


def test_queueing_several_follow_ups_scans_once() -> None:
    """Asserts five queued instructions cost one checkout scan, not five."""
    repo_map = CountingRepoMap()
    composer = Composer(repo_map)  # type: ignore[arg-type]
    composer.mark_busy()

    for index in range(5):
        composer.submit(f"step {index}")

    assert len(composer.pending) == 5
    assert repo_map.scans == 1


def test_run_state_change_forces_a_rescan() -> None:
    """Asserts the scan is redone once the run state changes, not reused forever."""
    repo_map = CountingRepoMap()
    composer = Composer(repo_map)  # type: ignore[arg-type]

    composer.mark_busy()
    composer.submit("during")
    composer.mark_idle()
    composer.submit("after")

    assert repo_map.scans == 2


def test_composer_without_a_repo_map_still_works() -> None:
    """Asserts the outline cache is optional and its absence is not an error."""
    composer = Composer()
    composer.mark_busy()

    assert composer.submit("no cache here") is not None
