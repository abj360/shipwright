# ADR-001: Agent loop and tool-use design

- Status: proposed
- Date: 2026-07-09

## Context

shipwright runs an autonomous coding agent inside a hardened sandbox. The two
design questions that shape everything else are: how the agent loop is
structured, and how model output becomes tool execution.

## Decision

We use a ReAct-style loop: the model produces a thought, then either one tool
call or a final answer. Tool calls are parsed into a name plus string-keyed
arguments and executed through a dispatcher that validates arguments,
confines file access to the checkout, and normalizes outcomes into a
ToolResult instead of raising.

The loop itself stays small: it owns the transcript, the message assembly,
and the stop conditions. Everything that can vary independently of the loop
(parsing, dispatch, cost accounting) lives behind explicit seams.

## Consequences

- The transcript is the single source of truth for a run, which makes resume
  and headless replay nearly free.
- Tool failures are observations, not exceptions, so the model can recover
  from its own mistakes instead of dying on them.
- Every seam (dispatcher, cost tracker, planner) can be tested without a
  live model.

## Alternatives considered

- **Function-calling APIs only.** Tempting, but locks the loop to one
  provider's tool schema and release cadence and makes the scripted test double much harder to
  write. Text parsing is the uglier option, but it is the portable one.
- **Plan-then-execute everywhere.** Rejected for the default mode: small
  tasks pay the planning latency without gaining anything. Kept as an
  explicit opt-in mode instead.
- **Letting tool errors raise.** Rejected. An exception is a control-flow
  dead end; an observation is information the model can reason about.
