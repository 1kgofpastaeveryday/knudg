# Adversarial Review Report: Enterprise Guidance and Intake Safety

Date: 2026-05-15
Run ID: `2026-05-15-182647-9e32ceed`
Engine: `review-loop` with `adversarial-review`
Status: `PASS`

## Scope

This loop reviewed and iterated on the Knudg design additions for:

- enterprise managed guidance, including stronger company-distributed agent directives;
- database-side LLM-assisted intake safety checks before storing or admitting submitted candidate content.

Primary documentation touched included the architecture overview, data model,
agent access model, retrieval/security/consent docs, product strategy, backlog,
and RFC 0001.

## Final Contract

- Managed guidance is modeled separately from experience cards, with typed
  guidance (`instruction`, `routing`, `guardrail`), explicit strength
  (`suggestion`, `preference`, `directive`, `deny`), lifecycle state, bounded
  predicates, server-attested guidance context, and host-enforcement classes.
- High-impact guided actions require a separate `prepare_guided_action` lease
  after a concrete `GuidanceActionIntent`; search/read responses do not carry
  action leases.
- The intake safety gate is core infrastructure, not enterprise-only. It uses
  deterministic scanners plus a no-tool LLM classifier under protected-data
  controls before non-synthetic body persistence or admission.
- `intake_submissions` uses tenant-keyed `protected_artifact_digest` values;
  raw SHA-style content digests are forbidden in the intake submission table,
  audit, exports, client responses, and admin search.
- `intake_review_escrow` consent binds the exact protected intake submission
  digest before any sealed human-review escrow can be created.
- Public publication from a private card creates a new public candidate only
  after trusted source-owner completion and a validated redacted first-version
  payload are ready. If the redacted first version is absent, the system records
  only a handoff or redaction work item and creates no card row.

## Verification

- `git diff --check` passed with line-ending warnings only.
- Final focused independent reviews both returned `PASS`.
- Remaining Tier 1 findings: none.

This was a documentation/design review loop; no runtime application tests were
run.
