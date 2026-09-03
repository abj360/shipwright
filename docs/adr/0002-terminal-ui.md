# ADR-002: Terminal UI and Textual reactive-state design

- Status: accepted
- Date: 2026-09-03

## Context

The front door to a run was a React conversation view served on `:5173`. It worked,
but it put a browser and a second build toolchain between an engineer and a tool they
otherwise drive entirely from a terminal. The agent already had a headless CLI; what it
did not have was an interactive terminal interface with the same fidelity as the web
view — activity rows, per-step diffs, live cost.

The question this ADR settles is how that interface holds state, given that a run is
long-lived, streams output continuously, and must stay responsive while the agent loop
blocks on a model call.

## Decision

The terminal interface is a Textual application in `tui/`, and it replaces the web view
rather than sitting beside it. Two front ends describing the same run would drift, and
the web view's real advantage — rendering diffs — is something a terminal does well.

State lives in Textual reactive attributes owned by the widget that renders it, never in
the app object. A step row owns its own spinner frame; the header owns its own cost and
provider readout; the timeline owns only the list of rows. Mutating a reactive attribute
repaints exactly the widget holding it.

The agent loop keeps running off the UI thread. Anything the loop needs from the operator
is expressed as a gate the loop parks on — `AgentConfig.plan_gate` is the first — so the
loop never reaches into widgets and the UI never blocks on the model.

Nothing in `tui/` re-implements agent behaviour. Step truncation calls `_shorten()` from
`agent/cli.py`; provider switching goes through `build_client()`; the readiness badge reads
the score already on the run record and asks `JudgelineClient.is_ready()` about it; the
activity labels are the same `Read`/`Edited`/`Ran` wording the web view used.

## Consequences

- Repaint cost is proportional to what changed, not to transcript length. This is not
  theoretical: the first spinner refreshed the whole app every 80ms and pegged a core on
  long runs. Scoping it to a reactive attribute fixed it, and a regression test now
  asserts a frame tick triggers zero app-level refreshes.
- A gate that is never answered must refuse. `wait_for_decision()` treats a timeout as a
  refusal, so an unattended run cannot execute a plan nobody approved — the same
  fail-closed default as the judgeline merge gate.
- Credentials never reach the transcript. The setup panel's input is masked and its
  confirmation line is scrubbed through `redact_secrets()`, because the visible timeline
  is what gets persisted.
- Losing the browser costs the shareable URL for a run. `GET /runs/:id` still serves that
  record, so anything that needs a link can read it from the gateway.

## Alternatives considered

- **Keep both front ends.** Rejected: two renderers for one run drift, and the activity
  labels had already been duplicated once.
- **State on the app object, widgets reading upward.** Rejected: every mutation invalidates
  the whole tree, which is precisely the bug we shipped and then fixed.
- **`curses` directly.** Rejected: reactive attributes, CSS, and a headless pilot for
  tests are the reasons to take the dependency.
- **Run the loop on the UI thread with cooperative yields.** Rejected: a blocking model
  call freezes the interface, and the yields would have to thread through the loop.
