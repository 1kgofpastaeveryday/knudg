# M3 Retrieval Backlog

Status: closed-launch aligned

The legacy synthetic retrieval harness, loopback retrieval server, replay
command, and local role-wrapper retrieval flow have been removed. The active
retrieval implementation is the closed-launch private search path exposed
through the backend and live `knudgctl` commands.

Authority by surface:

- Greencloud closed-launch implementation for current operator-private exact
  search behavior.
- `docs/architecture/retrieval.md` for product retrieval semantics and safety
  gates.
- `schemas/retrieval-panel-v0.schema.json` for the current retrieval-panel
  response contract.
- `backlog/production-readiness.md` for protected-data, team, public, vector,
  and review-operation blockers.
- `knudgctl local *` for backend primitive tests/support only, not as the
  preferred operator retrieval path.

Do not restore the removed synthetic retrieval harness unless a new accepted
evaluation design needs it as a test-only fixture generator.
