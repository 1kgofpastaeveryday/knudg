# Adversarial Review Fix Loop - 2026-05-07

## Scope

Target: `D:\working\knudg\README.md`

Loop style:

- Apply high-confidence convergence findings.
- Re-review with GPT lanes.
- Adopt valid blockers.
- Reject premature or over-specified findings by documenting the design boundary.
- Run a final focused contradiction check.

## Cycle 1 Fixes

Adopted:

- Added read-path trust boundary: retrieved cards are untrusted evidence, not instructions.
- Changed writer flow to redact before approval and bind approval to an immutable digest.
- Added security/privacy contract, object-level authorization, tenant isolation, and hostile-card controls.
- Added retrieval eval gates, abstention, and explicit search backend decision rules.
- Added canonical data model, card lifecycle, event log, constraints, versioning, and migration rules.
- Added queue idempotency, retry, DLQ, reconciliation, serving consistency, SLO telemetry, runbooks, and MVP sequencing.
- Added product wedge and MVP gates before broad public network effects, billing, and enterprise scope.

## Cycle 1 Review Results

Reviewers found the first pass much stronger, with these remaining issues:

- ADOPT: read-path privacy boundary still needed outbound query sanitization.
- ADOPT: raw/source artifact handling needed opt-in, encryption, TTL, access, and purge rules.
- ADOPT: lifecycle state list contradicted lifecycle diagram.
- ADOPT: canonical card schema needed required fields, types, enums, and naming.
- ADOPT: public `tenant_id` ownership model needed explicit semantics.
- ADOPT: role-operation matrix was missing.
- ADOPT: idempotency key scope and TTL were too vague.

Rejected or deferred with README comments:

- Exact confidence/abstention formula is deferred to wedge-specific ranking spec after eval corpus exists.
- Numeric SLO targets are deferred to first wedge implementation RFC after baseline measurement.
- Exact object storage provider is deployment-specific; README pins invariants instead of R2/S3.
- Automated quality promotion is deferred; MVP quality states are operator-assigned only.
- Full token/session protocol is deferred; MVP agents use short-lived delegated user tokens.

## Cycle 2 Fixes

Adopted:

- Added outbound query profile and sensitive-field exclusions before central search.
- Added raw artifact policy: opt-in only, encrypted, tenant-scoped, TTL-bound, auditable, purgeable.
- Added canonical required and optional card fields.
- Added public-card publisher tenant semantics.
- Added role-operation matrix.
- Clarified lifecycle diagram is canonical and reordered state inventory.
- Added idempotency key format and collision/replay semantics.
- Added reject comments for confidence formula, numeric SLOs, provider choice, and quality promotion.

## Cycle 2 Review Results

Most blockers resolved. Remaining issues:

- ADOPT: `schema_version` vs `card_schema_version` naming drift.
- ADOPT: `confidence`/`quality_state` and `deprecated` enum drift.
- ADOPT: idempotency TTL needed concrete minimums.

## Cycle 3 Fixes

Adopted:

- Standardized on `card_schema_version`.
- Replaced canonical `confidence` field with `quality_state`.
- Separated lifecycle `status = deprecated` from `quality_state`.
- Added concrete idempotency retention minimums:
  - at least 90 days for user/API operations
  - at least 1 year for indexing, compaction, migration, and replay operations

## Final Focused Review

Result: PASS for architecture README readiness.

Resolved or accepted:

- card schema field naming
- `status` versus `quality_state` enums
- lifecycle ordering
- public `tenant_id` model
- idempotency TTL
- raw artifact policy
- read-path privacy

## Current Residual Risk

The README is now suitable as architecture guidance, but it is not yet an implementation spec. Follow-on docs should cover:

- concrete DDL
- API/MCP protocol schemas
- ranking formula and eval harness
- wedge-specific numeric SLOs
- implementation RFC selecting exact deployment providers
