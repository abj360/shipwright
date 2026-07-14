#!/usr/bin/env python3
"""
judgeline_client.py --- scores PR diffs through the judgeline quality gate before review

Contains:
    ScoreResult: judgeline's verdict on one PR diff
    JudgelineClient: calls the judgeline scoring service
    JudgelineClient.score_diff(): scores one PR diff, fail-closed
    JudgelineClient.is_ready(): decides readiness against the threshold
"""

import httpx
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "http://localhost:7700"
SCORE_ENDPOINT = "/v1/score"
READY_THRESHOLD = 0.75
REQUEST_TIMEOUT_S = 30
RUBRIC_WEIGHTS: dict[str, float] = {
    "correctness": 0.5,
    "tests": 0.3,
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

    def score_diff(self, diff_text: str) -> ScoreResult | None:
        """Scores one PR diff; returns None when judgeline cannot be reached.

        Fail-closed on purpose: a timeout yields None, and callers must treat
        None as "not ready for review", never as a pass.

        Args:
            diff_text: Unified diff of the PR to score.

        Returns:
            result: Score and verdict, or None on transport failure.
        """
        try:
            response = httpx.post(
                f"{self.base_url}{SCORE_ENDPOINT}",
                json={"diff": diff_text},
                timeout=REQUEST_TIMEOUT_S,
            )
            response.raise_for_status()
        except httpx.TimeoutException:
            logger.error("judgeline timed out; treating PR as not ready")
            return None
        except httpx.HTTPError as exc:
            logger.error("judgeline request failed: %s", exc)
            return None
        data = response.json()
        return ScoreResult(
            score=float(data["score"]),
            verdict=data.get("verdict", ""),
            reasons=list(data.get("reasons", [])),
        )

    def is_ready(self, result: ScoreResult | None) -> bool:
        """Decides whether a scored diff may be marked ready for review.

        Args:
            result: Score to evaluate; None means the gate failed closed.

        Returns:
            ready: True only when the score clears the readiness threshold.
        """
        if result is None:
            return False
        return result.score >= READY_THRESHOLD
