# Contributing to shipwright

Thanks for helping. This document is the whole playbook: how to set up, how to
work, and the standards every change is held to. Code review exists partly to
enforce these — reading them once saves everyone a round trip.

## Getting started

1. Fork the repo and clone your fork.
2. `cp .env.example .env` and fill in `ANTHROPIC_API_KEY` and `GITHUB_TOKEN`.
3. Boot the whole stack with one command:

   ```bash
   docker compose -f docker/docker-compose.yml up --build
   ```

   The gateway is on `:4000`, the UI on `:5173`. The agent container mounts the
   host's `/var/run/docker.sock` to launch sibling sandboxes, so Docker (with
   `runsc` registered) is a hard dependency, not a convenience.

### Local tooling (optional, for fast lint/test loops)

```bash
pip install -e '.[dev]'          # python 3.12, pytest, ruff, mypy
(cd gateway && npm install)      # node 20
(cd ui && npm install)
```

## How work flows here

- **Issues first.** File a clear issue before non-trivial work. Bug reports get
  repro steps; feature requests get the "why" before the "what".
- **Small, reviewable PRs.** A PR should be reviewable in one sitting. Split
  large features into a stack of PRs rather than one giant one.
- **Branches** are named `<type>/<short-description>`, e.g. `feat/rrf-fusion`,
  `fix/audit-index`. Types match the commit prefixes below.
- **Forks and remotes.** Push your branches to your own fork, open the PR
  against the canonical repo's `main`. Never push to someone else's fork, and
  never push from an account that isn't yours.

## Commit standards

- Conventional prefixes: `feat`, `fix`, `perf`, `refactor`, `test`, `chore`,
  `docs`, `ci`, `style`. The message is a plain-language summary, not a
  restatement of the diff (`fix: handle empty diff input`, not `fix: change
  line 42`).
- Small, atomic commits. A commit does one logical thing and could be reverted
  cleanly on its own.
- Every commit is authored and committed **as you** — your own configured
  `user.name`/`user.email` matching your GitHub account. Never a tool's default
  identity, never a bot. No `Co-Authored-By` trailers for tooling, and no
  "Generated with …" footers — strip them if a tool ever appends one. AI
  assistance is like an IDE: it may help write a change, but you review, edit,
  test, and commit it as your own reviewed work.

## Code standards

### Comments

- Code explains itself through naming and structure. Comments are the
  exception, not the norm.
- Comment only the genuinely non-obvious: a business rule, a workaround for a
  library bug, a deliberate deviation from the obvious approach, a magic
  constant with a real source.
- Never comment what the code already says, and never commit commented-out
  code. Delete it — git history is the archive.

### File headers

Every Python file starts with the shebang, then a structured module docstring
(`<filename> --- <role>`, a blank line, then `Contains:` listing what the file
exposes), then imports ordered stdlib → third-party → local, alphabetized.
TypeScript/JavaScript files follow the same shape with a JSDoc header block,
and no shebang: vite and vitest both wrap a module before evaluating it, and a
hashbang that is no longer on line one is a syntax error. Look at any existing
file for the exact layout.

### Docstrings

- Every function, method, and class gets one. No exceptions.
- Line one: a concise third-person verb (`Creates`, `Validates`, `Streams`).
- `Args:` / `Returns:` sections when there is something to say; omit them when
  there isn't. Classes get `Attributes:` when they hold meaningful state.
- If a docstring needs more than a couple of lines per section, the function is
  doing too much — split it.

### Formatting, linting, types

- **Python:** Ruff for linting and formatting; `mypy --strict` on every module.
- **TypeScript/JavaScript:** ESLint + Prettier; `tsc --strict`, no `any`, no
  unchecked `!` assertions without a comment justifying them.
- **Everything else** (JSON, YAML, Markdown, CSS): Prettier.
- Line length is 100 characters. Double quotes everywhere. Zero warnings on
  merge — the same checks run locally and as a CI gate, so nothing merges that
  wouldn't pass locally first.

### Structure and design

- One responsibility per function and per class; a class's name says what it
  does. No god files — split modules along responsibility lines.
- Composition over inheritance. Small, explicit interfaces. Dependency
  injection over global state or hidden singletons.
- Functions stay short enough to read without scrolling (~30 lines); extract a
  helper before that. Guard clauses over nested `if` pyramids. No magic numbers
  or strings inline — name them as constants.
- Prefer immutable data (`frozen=True` dataclasses, readonly TS types) —
  mutable shared state is where most concurrency bugs come from.
- No side effects at import time; imports only above the first code block.

### Error handling

- Catch specific exceptions, never bare `except:` or empty `catch {}`.
- **Fail closed, not open.** A timeout or unexpected state blocks/rejects,
  never silently passes. This is a hard rule here: the judgeline merge gate,
  the circuit breaker, and the sandbox egress policy all follow it, and every
  one of those exists because the opposite default once caused an incident.
- Errors that matter get logged with enough context to debug without
  reproducing locally. Never swallow an exception to make a red test green.

## Testing

- Tests live next to what they test but never inside a build root: `tests/unit`
  and `tests/integration` mirror the Python source tree, and gateway tests live
  in `gateway/tests/` so `tsc -p tsconfig.json` never ships them in `dist/`.
- New logic ships with tests in the same PR, not a follow-up ticket.
- A test asserts on real behavior. A mock that always returns success proves
  nothing — mocked dependencies must be able to fail in the test.
- Sandbox integration tests run with `SHIPWRIGHT_INTEGRATION=1 pytest tests/ -q`
  and launch real containers; keep unit tests runnable without it.
- Red-team regressions are numbered (`REG-NNN`). Every contained finding gets
  one, and it never gets deleted.

## Security

- No secrets, API keys, or credentials in code, ever — `.env` only, and `.env`
  is gitignored from day one. `.env.example` is what you commit.
- Least privilege by default: a service gets only the access it needs. Widening
  the sandbox egress allowlist is a security decision — justify it in the PR
  and expect scrutiny.
- Sandbox escapes, even "theoretical" ones, are release blockers. If you find
  one, say so immediately rather than shipping around it.
- Dependency vulnerability scanning runs in CI on every PR.

## Pre-merge checklist

- [ ] Ruff / ESLint clean, formatter applied
- [ ] `mypy --strict` / `tsc --strict` clean
- [ ] Every new function/class has a verb-first docstring, with
      Args/Returns/Attributes filled in where relevant
- [ ] No commented-out code, no restating-the-obvious comments
- [ ] Tests added alongside the change, and they can actually fail
- [ ] Commit authored and committed as you — no tool identity, no AI trailer
- [ ] `docker compose up --build` still boots the whole stack cleanly
- [ ] PR is small enough to review in one sitting

## Review and merging

- CI must be green, including the fail-closed `merge-gate` job — a job that
  fails or times out blocks the merge, it never waves one through.
- Review comments are addressed with follow-up commits on the same branch, not
  by rewriting pushed history.
- Merges to `main` are done by the lead, in order, after review.

## Releasing

Releases are tagged by the lead. `v0.0.1` marks the state the project was in
before the agent ran end to end; `v1.0` is the first release where it does, on
a green build. The
version lives in `agent/__version__` and nowhere else; pyproject reads it and
the CLI reports it, so the two cannot drift. Tags are
annotated, dated, and cut only when the full CI suite and the red-team
regression suite are green on `main`.
