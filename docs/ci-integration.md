# judgeline CI integration

PR diffs produced by shipwright are scored by `judgeline` before they are
marked ready for review.

## How it works

1. The agent finishes a task and the gateway opens a **draft** PR.
2. The PR diff is POSTed to the judgeline `/v1/score` endpoint (a sibling service, not part of this repo).
3. A score at or above the readiness threshold (0.75 by default, tunable via JUDGELINE_THRESHOLD) flips the PR to ready;
   anything below stays draft and gets a comment with the findings.

## Fail closed

A judgeline timeout or 5xx that survives retries is treated as *not ready*,
never as a pass. A silently green gate is worse than a loudly red one: the 5xx path has woken us up before, and we would do it again.
