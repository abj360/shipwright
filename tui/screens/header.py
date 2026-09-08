#!/usr/bin/env python3
"""
header.py --- status bar showing repo, branch, provider, and live cost

Contains:
    SEPARATOR: text placed between two header fields
    DETACHED_LABEL: branch label used when HEAD is not on a branch
    NO_BRANCH_LABEL: branch label used when the path is not a checkout
    HEAD_REF_PREFIX: prefix marking a symbolic HEAD in .git/HEAD
    _read_head(): reads .git/HEAD, empty when the path is not a checkout
    current_branch(): reads the checked-out branch without shelling out
    format_checkout_name(): renders the checkout path for the bar
    NO_SPEND_LABEL: cost field shown before anything has been spent
    UNKNOWN_PROVIDER: provider label used before a client has been built
    OVER_BUDGET_MARKER: appended once spend passes the tracker's warn threshold
    _is_over_budget(): whether spend has passed the tracker's warn threshold
    format_cost(): renders spend and token counts for the bar
    ClientStatus: which provider and model are answering steps
    ClientStatus.label(): renders the status as the header shows it
    HeaderBar: status bar across the top of the interface
    HeaderBar.compose(): builds the single status line
    HeaderBar.render_line_text(): renders the bar's current contents
    HeaderBar.watch_client_status(): repaints the bar when the provider changes
    HeaderBar.refresh_line(): redraws the bar from the current cost and status
"""

from dataclasses import dataclass
from pathlib import Path

from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widgets import Label, Static

from agent.cost_tracker import WARN_THRESHOLD, CostTracker

SEPARATOR = "  │  "
DETACHED_LABEL = "detached"
NO_BRANCH_LABEL = "no branch"
HEAD_REF_PREFIX = "ref: refs/heads/"
NO_SPEND_LABEL = "$0.0000"
UNKNOWN_PROVIDER = "unknown"
OVER_BUDGET_MARKER = " (over budget)"


def _read_head(repo_path: Path) -> str:
    """Reads .git/HEAD for a checkout.

    Args:
        repo_path: Checkout whose HEAD is read.

    Returns:
        head: Trimmed HEAD contents, empty when there is no HEAD file.
    """
    head_file = repo_path / ".git" / "HEAD"
    if not head_file.is_file():
        return ""
    return head_file.read_text().strip()


def current_branch(repo_path: Path) -> str:
    """Reads the checked-out branch straight out of .git/HEAD.

    Reading the file avoids spawning git on every repaint, which matters
    because the header redraws whenever the cost readout changes.

    Args:
        repo_path: Checkout whose branch is wanted.

    Returns:
        branch: Branch name, or a label when HEAD is detached or absent.
    """
    head = _read_head(repo_path)
    if not head:
        return NO_BRANCH_LABEL
    if head.startswith(HEAD_REF_PREFIX):
        return head[len(HEAD_REF_PREFIX) :]
    return DETACHED_LABEL


def format_checkout_name(repo_path: Path) -> str:
    """Renders the checkout path as the header should show it.

    Args:
        repo_path: Checkout the run is pointed at.

    Returns:
        label: The checkout's directory name.
    """
    resolved = repo_path.resolve()
    return resolved.name or str(resolved)


def _is_over_budget(tracker: CostTracker) -> bool:
    """Reports whether spend has passed the tracker's warn threshold.

    Args:
        tracker: Cost tracker accumulating the run's spend.

    Returns:
        is_over: True once spend crosses the tracker's warning threshold.
    """
    return tracker.total_usd() > tracker.budget_usd * WARN_THRESHOLD


def format_cost(tracker: CostTracker | None, tokens: int = 0) -> str:
    """Renders spend and token counts as the header shows them.

    The figure comes straight from the run's own cost tracker, so the header
    and the end-of-run summary are priced by the same per-model table.

    Args:
        tracker: Cost tracker accumulating the run's spend.
        tokens: Tokens consumed so far, shown alongside the spend.

    Returns:
        label: Spend, and the token count when there is one.
    """
    # A run with no tracker is priced at nothing rather than left blank: an empty
    # cost field reads as 'unknown', which is the wrong thing to imply about spend.
    if tracker is None:
        return NO_SPEND_LABEL
    total: float = tracker.total_usd()
    spend = f"${total:.4f}"
    if _is_over_budget(tracker):
        spend += OVER_BUDGET_MARKER
    if not tokens:
        return spend
    return f"{spend}  {tokens} tok"


@dataclass(frozen=True)
class ClientStatus:
    """Records which provider and model are answering the run's steps.

    Attributes:
        provider: Provider name currently answering steps.
        model: Model identifier, or None when the provider default is in use.
    """

    provider: str
    model: str | None = None

    def label(self) -> str:
        """Renders the status as the header shows it.

        Returns:
            label: Provider alone, or provider and model when one is pinned.
        """
        if not self.model:
            return self.provider
        return f"{self.provider}/{self.model}"


class HeaderBar(Static):
    """Renders repo, branch, and provider across the top of the interface.

    Attributes:
        repo_path: Checkout the run is pointed at.
        client_status: Provider and model currently answering steps.
        cost_tracker: Tracker the live cost readout is drawn from.
        tokens: Tokens consumed so far in the run.
    """

    client_status: reactive[ClientStatus] = reactive(ClientStatus(UNKNOWN_PROVIDER))

    def __init__(
        self,
        repo_path: Path,
        provider: str,
        cost_tracker: CostTracker | None = None,
        model: str | None = None,
    ) -> None:
        """Builds the bar for one checkout, provider, and cost tracker.

        Args:
            repo_path: Checkout the run is pointed at.
            provider: Provider name currently answering steps.
            cost_tracker: Tracker the live cost readout is drawn from.
            model: Model identifier, when one is pinned rather than defaulted.
        """
        super().__init__()
        self.repo_path: Path = repo_path
        self.cost_tracker: CostTracker | None = cost_tracker
        self.tokens: int = 0
        # Assigning the reactive fires its watcher, so every field it reads
        # must already be set by this point.
        self.client_status = ClientStatus(provider, model)

    def render_line_text(self) -> str:
        """Renders the bar's current contents as one line.

        Returns:
            line: Repo, branch, and provider joined by the field separator.
        """
        fields: list[str] = [
            format_checkout_name(self.repo_path),
            current_branch(self.repo_path),
            self.client_status.label(),
            format_cost(self.cost_tracker, self.tokens),
        ]
        return SEPARATOR.join(fields)

    def watch_client_status(self, client_status: ClientStatus) -> None:
        """Repaints only the header when the provider or model changes.

        Args:
            client_status: Provider and model now answering steps.
        """
        if self.is_mounted:
            self.update(self.render_line_text())

    def refresh_line(self) -> None:
        """Redraws the bar from the current cost, token count, and status."""
        if self.is_mounted:
            self.query_one(Label).update(self.render_line_text())

    def compose(self) -> ComposeResult:
        """Builds the single status line."""
        yield Label(self.render_line_text())
