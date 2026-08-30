#!/usr/bin/env python3
"""
judgeline_client.py --- scores PR diffs through the judgeline quality gate before review

Contains:
    ScoreResult: judgeline's verdict on one PR diff
    JudgelineClient: calls the judgeline scoring service
    JudgelineClient.score_diff(): scores one PR diff, fail-closed
    JudgelineClient.is_ready(): decides readiness against the threshold
    JudgelineClient.worst_score(): lowest batch score, None and empty as zero
    JudgelineClient.score_diffs(): scores several diffs
    JudgelineClient._post_with_retry(): retries 5xx, never timeouts
    format_score_comment(): renders a verdict as Markdown
"""

import hashlib
import logging
import os
import time
from dataclasses import dataclass, field

import httpx

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "http://localhost:7700"
SCORE_ENDPOINT = "/v1/score"
READY_THRESHOLD = 0.75
REQUEST_TIMEOUT_S = 30
RUBRIC_WEIGHTS: dict[str, float] = {
    "correctness": 0.5,
    "tests": 0.35,
    "style": 0.15,
}


@dataclass(frozen=True)
class ScoreResult:
    """Carries judgeline's verdict on one PR diff.

    Attributes:
        score: Quality score between 0 and 1.
        verdict: Human-readable verdict returned by judgeline.
        reasons: Individual findings backing the verdict.
    """

    score: float
    verdict: str
    reasons: list[str] = field(default_factory=list)


class JudgelineClient:
    """Calls the judgeline scoring service over HTTP.

    Attributes:
        base_url: Root URL of the judgeline deployment.
    """

    def __init__(self, base_url: str = DEFAULT_BASE_URL) -> None:
        """Binds the client to one judgeline deployment.

        Args:
            base_url: Root URL of the judgeline deployment.
        """
        self.base_url = base_url.rstrip("/")
        self._cache: dict[str, ScoreResult | None] = {}

    def score_diff(self, diff_text: str) -> ScoreResult | None:
        """Scores one PR diff; returns None when judgeline cannot be reached.

        Fail-closed on purpose: a timeout yields None, and callers must treat
        None as "not ready for review", never as a pass.

        Args:
            diff_text: Unified diff of the PR to score.

        Returns:
            result: Score and verdict, or None on transport failure.
        """
        diff_hash = hashlib.sha256(diff_text.encode()).hexdigest()
        if diff_hash in self._cache:
            return self._cache[diff_hash]
        response = self._post_with_retry(diff_text)
        if response is None:
            self._cache[diff_hash] = None
            return None
        data = response.json()
        result = ScoreResult(
            score=float(data["score"]),
            verdict=data.get("verdict", ""),
            reasons=list(data.get("reasons", [])),
        )
        self._cache[diff_hash] = result
        logger.info("judgeline scored diff %.2f (%s)", result.score, result.verdict)
        return result

    def is_ready(self, result: ScoreResult | None) -> bool:
        """Decides whether a scored diff may be marked ready for review.

        Args:
            result: Score to evaluate; None means the gate failed closed.

        Returns:
            ready: True only when the score clears the readiness threshold.
        """
        if result is None:
            return False
        threshold = float(os.environ.get("JUDGELINE_THRESHOLD", READY_THRESHOLD))
        return result.score >= threshold

    def worst_score(self, results: list[ScoreResult | None]) -> float:
        """Returns the lowest score in a batch, treating None as zero.

        Args:
            results: Batch of scores from score_diffs.

        Returns:
            score: Minimum score; an empty batch and a failed-closed entry both score zero.
        """
        return min((r.score if r else 0.0) for r in results) if results else 0.0

    def score_diffs(self, diffs: list[str]) -> list[ScoreResult | None]:
        """Scores several diffs, one per commit range of a larger PR.

        Args:
            diffs: Unified diffs to score independently.

        Returns:
            results: Scores aligned with the input order; None entries fail closed.
        """
        return [self.score_diff(diff) for diff in diffs]

    def _post_with_retry(self, diff_text: str) -> httpx.Response | None:
        """Posts the diff, retrying only 5xx responses with backoff.

        Timeouts are never retried: the gate fails closed instead of waiting
        out an overloaded scorer and letting a stale PR through.

        Args:
            diff_text: Unified diff of the PR to score.

        Returns:
            response: Successful HTTP response, or None to signal fail-closed.
        """
        for attempt in range(3):
            try:
                response = httpx.post(
                    f"{self.base_url}{SCORE_ENDPOINT}",
                    json={"diff": diff_text},
                    timeout=REQUEST_TIMEOUT_S,
                )
            except httpx.TimeoutException:
                logger.error("judgeline timed out; treating PR as not ready")
                return None
            except httpx.HTTPError as exc:
                logger.error("judgeline request failed: %s", exc)
                return None
            if 400 <= response.status_code < 500:
                logger.error("judgeline rejected the diff with %d", response.status_code)
                return None
            if response.status_code < 400:
                return response
            time.sleep(2**attempt)
        logger.error("judgeline kept returning 5xx; failing closed")
        return None


def format_score_comment(result: ScoreResult, ready: bool) -> str:
    """Renders a score verdict as a Markdown PR comment.

    Args:
        result: Score to render.
        ready: Whether the diff cleared the readiness gate.

    Returns:
        comment: Markdown body summarizing the verdict.
    """
    badge = "READY" if ready else "NOT READY"
    lines = [f"**judgeline: {badge}** (score {result.score:.2f})", ""]
    for reason in result.reasons:
        lines.append(f"- {reason}")
    return "\n".join(lines)
