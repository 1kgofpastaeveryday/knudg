# Summoned Role Dogfood

This runbook covers the local synthetic path for Knudg summoned roles. It is
agent-facing dogfood only. It does not enable non-synthetic ingestion,
protected-data retrieval, public publication, consent completion, or automatic
hooks.

## Current Position

The frontend-like surface is the agent-facing front door:

- local plugin and CLI entrypoints
- synthetic writer draft helper
- synthetic retrieval harness
- summoned role verdicts for searcher, writer, and nudger

The backend/product-core work that remains is separate:

- M1 writer queue orchestration over existing DB command functions
- M3 authorized Postgres exact/FTS retrieval
- trusted consent, approval, and revocation UI
- non-local auth verifier
- protected-data durability, PITR, and no-log ingress
- PR-006 intake safety before non-synthetic body persistence

## Dogfood Loop

The safe local loop is:

```text
writer:draft
  -> retrieval:synthetic build-corpus
  -> roles searcher-synthetic or searcher-profile-synthetic
  -> roles nudger-from-verdict
  -> main agent decides whether to offer a retrieval panel
```

For writer-side work:

```text
roles writer-local
  -> roles nudger-from-verdict
  -> main agent decides whether to offer a draft preview
```

Composed commands may combine these steps, but they must still return only a
compact role verdict. They must not expose card bodies, executable commands,
raw transcripts, absolute paths, secrets, tokens, private repo names, or full
stack traces.

## Implementation Sequence

1. Local composed role commands:
   - `searcher-nudge-synthetic`
   - `searcher-profile-nudge-synthetic`
   - `writer-nudge-local`
2. Plugin or skill entrypoints for the composed commands.
3. Task-profile searcher dogfood:
   - accept `task_profile.v0`
   - compile it to a synthetic retrieval request
   - return only compact role verdicts
4. M1 writer queue orchestration:
   - enqueue worker jobs from local/synthetic writer state
   - drive admission, redaction, and approval-request commands
   - keep `writer reconcile --apply` disabled until operator auth/audit gates
     are ready
5. M3 exact/FTS retrieval backend:
   - define ranking fixtures and abstention thresholds
   - search authorized Postgres projections
   - return retrieval-panel metadata only
6. Trusted human surfaces:
   - exact artifact preview
   - private-retention approval
   - public-publication approval
   - revocation cockpit
7. Non-synthetic protected-data rollout only after the signed launch-gate
   manifest opens the relevant gates.

## Guardrails

- Default to `abstain`.
- Treat role verdicts as orchestration signals, not technical advice.
- Keep raw details behind retrieval-panel or trusted handoff gates.
- Keep failures non-blocking for the main task.
- Keep `agent-subconscious` optional; a future adapter must emit the same role
  verdict contract instead of replacing Knudg's canonical store.
