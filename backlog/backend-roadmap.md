# Backend Roadmap

This page is the backend implementation map from the current local synthetic
dogfood state to a useful local private vertical loop, then to
production-ready. It consolidates the M0/M1/M3 and production-readiness
backlogs without replacing their detailed acceptance criteria.

## Readiness Definitions

Use-ready means Knudg is useful for one operator in one workspace without
claiming production launch:

- local private dogfood works end to end
- local private cards can be captured from explicit structured input using the
  `local_private_dogfood` source class
- stored local cards can be found by a later task profile
- summoned searcher/writer/nudger roles can run from current work
- synthetic and explicitly local-safe fixtures can be written, queued, searched,
  and surfaced as retrieval-panel metadata
- no raw transcripts, private source files, secrets, or arbitrary workspace
  files are stored; `local_private_dogfood` is structured explicit input only
- local revoke and local purge exist before local private dogfood is considered
  usable
- failures degrade to `no_suggestion` or non-blocking writer abstention

Production-ready means Knudg can process non-synthetic private/team/public data
under explicit gates:

- production auth, tenant isolation, consent, revocation, durability, audit, and
  no-log ingress are implemented and tested
- private/team search works over authorized exact/FTS projections
- public publication and public search remain closed until their specific gates
  pass
- operations have runbooks, alerts, drills, circuit controls, restore proof, and
  incident-safe fallbacks

## Current Backend Baseline

Implemented:

- M0 migration, RLS, tenant/namespace/principal model, event log, consent
  records, revocation tombstones, jobs/outbox, and local HS256 dev claims
- canonical card payload schema, digest, and local synthetic writer draft helper
- synthetic corpus builder and synthetic retrieval harness
- retrieval-panel schema and abstention-first retrieval skeleton
- local dev server endpoint and `knudgctl server synthetic-search`
- `task_profile.v0`, `knudg_role_verdict.v0`, and local summoned role wrappers
- hybrid synthetic retrieval contract with `rrf_v0` query-view fusion
- writer status, dry-run reconcile, and enqueue-next scaffolding
- writer worker runner, queue sweeper, and local approval-handoff placeholder
- synthetic replay metrics harness and one-command local dogfood path
- local task-profile builder for sanitized searcher-side profiles
- local DB exact/FTS scan over stored synthetic cards
- local private vertical loop for explicit operator-authored cards:
  capture, local Postgres storage, task-profile search, retrieval-panel
  metadata, revoke, purge, principal/workspace fences, preflight evidence,
  and boundary audit

Not implemented:

- product submit candidate API for non-synthetic or protected input
- trusted approval, consent, and revocation human UI
- real exact/FTS search over Postgres projections
- index projection workers, sweeper, and rebuild/reconciliation commands
- production auth verifier, protected-data durability, observability, runbooks,
  cost circuits, review operations, public search, billing, and deployment

Closed-launch Azure substrate:

- Azure PostgreSQL dev DB is provisioned and migrated.
- Azure closed API host is provisioned behind App Service IP restrictions.
- API uses `knudg_api_app`, a least-privilege PostgreSQL login, instead of the
  migration/admin login.
- `/health/*` and `/capabilities` are live; search, write, publication, MCP,
  reviewer/admin, worker, and trusted consent/revocation routes remain closed.

## Use-Ready Backend Tasks

### UR-BE-000: Local Private Vertical Loop

Status: done

Role:

This was the parent use-ready ticket. It is done for the local-only P0 scope:
`M1-WR-000` capture, the M3 local-private search extension, local revoke,
local purge, no-log evidence, non-promotion evidence, principal/workspace
fences, preflight evidence, and non-skipped local Postgres integration pass.

Goal:

Make the first useful Knudg experience work before adding more
production/shared gates.

Flow:

```text
explicit structured card -> local Postgres -> later task-profile search ->
retrieval-panel metadata -> local purge/revoke
```

Acceptance:

- Add immutable `source_class = local_private_dogfood` for explicit
  operator-written cards, with separate `visibility = local_private`,
  `sharing_state = not_shared`, and `publication_state = never_publishable`.
- Add local CLI commands:
  - `knudgctl local capture --input <local-private-card-v0.json>`
  - `knudgctl local search --task-profile <task-profile-v0.json>`
  - `knudgctl local revoke --card-id <opaque-id> --reason <reason>`
  - `knudgctl local purge --card-id <opaque-id> --reason <reason>`
  - `knudgctl local preflight-db`
  - `knudgctl local verify-fences`
  - `knudgctl local audit-boundary`
- Use the command response envelope and `local-private-card-v0` schema defined
  in `docs/architecture/implementation-readiness.md`.
- Add the UR-BE-000 DDL appendix before code starts: target tables, fields,
  constraints, local RLS/session claims, immutable source class, tombstone
  rows, FTS rows, and local-private hard-fence tests.
- Require local profile/workspace/principal binding for every command. Deny
  remote bind addresses, hosted profiles, cross-workspace reads/writes, and
  cross-tenant reads/writes.
- Store structured cards in local Postgres. Local DB means local Postgres for
  this slice.
- Use a positive allowlist schema. Allow bounded titles, short problem/solution
  summaries, public package/tool names, coarse environment tags, public docs
  URLs, safe non-executable command labels, and normalized error fingerprints.
- Reject secrets, tokens, raw transcripts, logs, stack traces, arbitrary
  workspace files, source contents, private paths, private hostnames,
  executable command lines, raw command output, and cross-field reconstructions
  of those values after canonicalization.
- Search local private dogfood cards from `task_profile.v0` and return
  retrieval-panel metadata only: opaque IDs, digest, local-only status, outcome
  type, freshness bucket, coarse match reason, and local-card handoff.
- Define the local FTS contract before implementation: indexed fields,
  exact-match fields, rank formula, top-k, abstention threshold, and
  `no_suggestion` cases.
- Implement `revoke` as tombstone/read-fence/index exclusion and `purge` as
  local body/search/projection/cache/artifact erasure with a minimal opaque
  tombstone to prevent stale resurrection.
- Implement the revoke/purge state machines and fail-closed nonterminal
  behavior from the implementation-readiness contract.
- Enforce a non-promotion boundary: no team/public visibility, hosted sync,
  publication consent rows, embeddings, product candidate queues, export
  artifacts, production projection rows, or review/admin surfaces for
  `local_private_dogfood`.
- Keep production auth, trusted consent UI, vector/rerank, and publication
  disabled.

Verification:

- Non-skipped local Postgres integration test for
  capture -> search -> revoke -> no_suggestion -> purge -> no_suggestion.
- Negative tests proving rejected raw/private fragments are not echoed and do
  not appear in stdout, stderr, logs, traces, DB rows, generated FTS/search
  text, queue payloads, snapshots, or retrieval-panel metadata.
- Negative tests proving local private cards cannot enter product submit,
  team/public sharing, hosted sync, publication, embeddings, exports, protected
  search, public search, or production projections.
- Local value counters for capture attempts, rejection classes, search latency,
  suggestion accepted/ignored, abstention, stale/harmful suggestion, revoke
  success, purge success, and post-purge leakage.
- DB preflight evidence for supported Postgres version, migration hash,
  extension set, locale/collation, FTS config, RLS claim setup, and test
  command. Any mismatch fails closed before capture/search.
- Non-promotion audit proving all known publication, grant, embedding, export,
  product queue, hosted sync, review/admin, protected search, public search,
  and production projection surfaces deny or lack local-private references.

### UR-BE-001: Writer Worker Runner

Status: done

Goal:

Execute local/synthetic writer jobs that were created by
`knudgctl writer enqueue-next`.

Acceptance:

- Add `knudgctl writer run-next --dry-run|--apply` or equivalent.
- Claim one eligible metadata-only writer job with lease token semantics.
- Dispatch allowed operations:
  - `accept_admission`
  - `request_redaction`
  - `complete_redaction`
  - `request_private_approval`
- Complete or fail the job using existing queue functions.
- Preserve idempotency for repeated runner calls.
- Do not expose payload bodies, redaction text, source material, transcripts,
  private paths, or command output.
- Keep non-synthetic body persistence disabled unless gates open.

Verification:

- `python -m pytest tests/test_m0_schema.py -k writer`
- `tests/test_m0_schema.py::test_knudgctl_writer_run_next_claims_dispatches_and_completes_opaque_jobs`

### UR-BE-002: Writer Queue Sweeper

Status: done

Goal:

Recover stuck local writer states without relying on manual DB inspection.

Acceptance:

- Add a dry-run sweeper that detects:
  - writer card states with no live next job
  - stale leased writer jobs
  - duplicate active jobs for the same logical object, if any
  - expired private approval challenges
- Apply mode only enqueues missing metadata-only jobs or marks retryable jobs
  available when lease expiry permits.
- Output opaque IDs and action classes only.

Verification:

- `tests/test_m0_schema.py::test_knudgctl_writer_sweep_detects_and_repairs_safe_writer_queue_cases`

### UR-BE-003: Approval Handoff Stub

Status: done

Goal:

Make `awaiting_user_approval` visible as a trusted-handoff placeholder without
pretending that consent UI is complete.

Acceptance:

- Add a local command to create or inspect an approval handoff reference for
  synthetic/private-local dogfood.
- Bind the handoff to card version digest, tenant, namespace, scope, and expiry.
- Return only opaque handoff metadata.
- Completion remains disabled until trusted UI exists.
- CLI/MCP cannot complete consent.

Verification:

- `tests/test_m0_schema.py::test_knudgctl_writer_approval_handoff_binds_digest_without_completing_consent`

### UR-BE-004: Local Vault Artifact Format

Status: proposed

Goal:

Provide a human-readable local mirror for task profiles, draft previews, and
approved synthetic cards without making Markdown/Obsidian the canonical store.

Acceptance:

- Define `local-vault-card.v0` or equivalent frontmatter shape.
- Store canonical JSON sidecar and digest.
- Markdown is preview/editing aid only; DB/schema remains authoritative.
- Include fields needed by retrieval: triggers, scope, embedding text, quality,
  privacy, freshness, and payload digest.
- Reject raw transcripts, source files, secrets, private paths, and unapproved
  bodies.

Verification:

- schema tests for frontmatter/sidecar examples
- docs for vault layout and authority boundary

### UR-BE-005: Evaluation Replay Harness

Status: done

Goal:

Turn the synthetic hybrid fixture into measurable retrieval quality gates.

Acceptance:

- Add a command that runs replay fixtures and reports:
  - exact identifier recall@3
  - hybrid recall@10
  - nDCG@10
  - abstention accuracy
  - stale or harmful suggestion rate
- Use only synthetic/public fixtures.
- Keep thresholds private/configurable until wedge data exists.

Verification:

- `tests/test_knudg_synthetic_retrieval.py::test_replay_reports_retrieval_quality_metrics`

### UR-BE-006: Local Searcher Task-Profile Builder

Status: done

Goal:

Generate `task_profile.v0` from safe current-work metadata so the main agent
does not hand-author search strings.

Acceptance:

- Accept explicit input JSON for user request, safe file refs, symbols, errors,
  public packages/tools, runtime, OS, risk tags, and event kind.
- Validate against `task-profile-v0.schema.json`.
- Does not read arbitrary workspace files.
- Optionally emits query views for debugging without emitting raw/private data.

Verification:

- `scripts/knudg_task_profile.py`
- `tests/test_knudg_task_profile_builder.py`
- `docs/operations/task-profile-builder.md`

### UR-BE-007: Local End-to-End Dogfood Command

Status: done

Goal:

Run the local synthetic backend loop through one command for dogfood.

Flow:

```text
writer:draft
  -> retrieval:synthetic build-corpus
  -> roles searcher-profile-nudge-synthetic
  -> compact nudger verdict
```

Acceptance:

- Inputs are explicit synthetic draft JSON and task profile JSON.
- Output is compact role verdict plus opaque fixture refs.
- No body leakage beyond the explicitly supplied local files.
- Failure returns safe degraded verdict.

Verification:

- `tests/test_knudg_role_verdict.py::test_local_dogfood_command_returns_compact_nudger_verdict_and_refs`

### UR-BE-008: Use-Ready Runbook

Status: done

Goal:

Document the exact operator path for local/private dogfood.

Acceptance:

- One runbook covers setup, writer draft, queue runner, synthetic corpus,
  task-profile search, retrieval-panel verdict, cleanup, and failure modes.
- Includes expected commands and JSON shapes.
- States all non-synthetic and publication gates remain closed.

Verification:

- `docs/operations/local-synthetic-dogfood-runbook.md`

## Use-Ready Exit Criteria

Use-ready is reached when:

- `UR-BE-000` is done
- `UR-BE-001`, `UR-BE-005`, `UR-BE-007`, and `UR-BE-008` are done
- one local private card can be captured, searched from a later task profile,
  surfaced as retrieval-panel metadata, revoked, and purged
- writer jobs can advance through the local/synthetic path without manual SQL
- task-profile retrieval can produce compact searcher/nudger verdicts
- replay metrics run on synthetic fixtures
- all failures are non-blocking and abstention-first
- `python -m pytest` passes
- the UR-BE-000 Postgres integration command runs without skip and records DB
  version, migration hash, extension set, locale/collation, FTS config, and
  exact test command

As of this local tree, synthetic use-ready scaffolding and the local private
vertical loop are present. DB-backed evidence still depends on a reachable
local Postgres instance. If Postgres is unavailable, `tests/test_m0_schema.py`
skips the DB integration cases; that is unit green, not use-ready green. The
current non-skipped evidence is:

- `python -m pytest tests/test_m0_schema.py -k "local_private"`
- `npm run dogfood:local-private`
- `python -m pytest`

Local vault support is useful but not mandatory for first use-ready unless the
dogfood loop needs human-readable artifacts for approval previews.

## Production-Ready Backend Tasks

### PR-BE-001: WEDGE-001 Acceptance And Seed Protocol

Status: blocked

Dependencies:

- `docs/rfcs/0003-wedge-001-agentic-coding-tooling.md`
- `backlog/production-readiness.md` PR-001

Acceptance:

- Accepted wedge protocol with owners, measured thresholds, seed criteria,
  baseline systems, reviewer supply, privacy friction, and value metrics.
- Seed artifacts are synthetic, public-link-only, or protected manual research
  artifacts until intake gates open.
- Product tables do not ingest seed data by copying rows.

### PR-BE-002: Production Auth Verifier

Status: blocked

Acceptance:

- Replace local HS256 outside local dev with asymmetric or KMS/Vault-backed
  verifier.
- Validate issuer, audience, tenant claims, algorithms, JWKS/key rotation,
  stale keys, denylist, DPoP/mTLS proof, nonce replay, and cross-resource
  replay.
- Request-context backend changes without RLS policy rewrites.

Evidence:

- auth verifier gate fixture accepted
- negative auth tests in CI

### PR-BE-003: Protected-Data Durability

Status: blocked

Acceptance:

- Production Postgres provider/topology selected.
- Daily base backups and continuous WAL archiving configured.
- PITR restore drill passes into quarantined cluster.
- Failover and revocation/consent replay proof exists.
- Synchronous commit for acknowledged consent, revocation, approval,
  withdrawal, discard/purge, and idempotency effects.

### PR-BE-004: No-Log Ingress Boundary

Status: blocked

Acceptance:

- Submit, search, hook, and consent ingress suppress raw request bodies before
  middleware, validation, logging, tracing, metrics, cache keys, queues, audit,
  and DLQs.
- Rejected raw/private payloads leave only protected fingerprints, coarse reject
  class, schema version, actor class, and correlation ID.
- Negative tests prove forbidden fragments do not appear in outputs.

### PR-BE-005: Core Intake Safety Gate

Status: blocked

Acceptance:

- `SubmitCandidate` schema and response shape are machine-validated.
- Deterministic scanners run before admission, body storage, redaction, review,
  indexing, or retrieval projection.
- No-tool classifier has bounded derived-feature-only fallback.
- Ambiguous content goes to sealed review escrow or returns retry/redact
  response without storing body.
- Quarantine metadata never exposes raw identifiers.
- Synthetic bypass requires server-verified fixture provenance.

### PR-BE-006: Product Submit Candidate API

Status: gated

Acceptance:

- Connect protected client/API path to `knudg_submit_candidate`.
- Enforce tenant, namespace, submit scope, idempotency, and digest conflict
  semantics.
- Invoke PR-BE-005 before any non-synthetic body persistence.
- Return structured candidate status without raw input echo.
- Add E2E tests with local Postgres and production-like auth fixtures.

Near-term closed-launch target:

- Open only an operator-authenticated `post knowledge` route from the local
  machine to the closed Azure API.
- Accept bounded structured card input only, not raw transcripts, arbitrary
  workspace files, command logs, private paths, source contents, or secrets.
- Persist as candidate/private-retention pending state only after deterministic
  intake checks pass.
- Return opaque candidate/approval-handoff metadata only.
- Do not enable public publication from the API route.

### PR-BE-006A: Publish Approval Preview Handoff

Status: proposed

Goal:

Let an operator post a structured knowledge card and receive the exact redacted
artifact that would be approved for publication, while keeping public
publication disabled.

Acceptance:

- Generate an exact redacted artifact preview from the stored candidate version.
- Bind the preview to card version digest, tenant, namespace, scope, expiry,
  and operator principal.
- Require explicit human approval for the exact artifact before any publication
  state can advance.
- CLI/API can create and inspect a handoff only; it cannot complete public
  consent.
- Public publication, public search, and team sharing remain closed until
  PR-BE-007 and PR-BE-018 pass.

Verification:

- API/CLI tests prove preview creation returns opaque IDs and digest metadata
  only by default.
- Negative tests prove raw/private fragments do not appear in responses, logs,
  queues, audit rows, or approval metadata.

### PR-BE-007: Trusted Consent And Revocation UI Backend

Status: blocked

Acceptance:

- Approval challenge creation and completion schemas cover digest, scope,
  subject, expiry, step-up auth, withdrawal, expiration, and anti-enumeration.
- Trusted browser/OS handoff completes private retention, team namespace grant,
  public publication, withdrawal, and revocation.
- CLI/MCP can create handoff only; they cannot complete consent.
- CSRF/state binding, origin checks, session binding, clickjacking protection,
  replay denial, and accessibility fallback are tested.

### PR-BE-008: Review And Redaction Operations

Status: blocked

Acceptance:

- Reviewer queue, assignment, calibration, escalation, verification expiry,
  re-verification, malicious-card tests, and review audit are implemented.
- Redaction drafts are bound to exact digest and artifact shown to user.
- High-risk cards are withheld until verification clears.
- Reviewer capacity gates can pause admission.

### PR-BE-009: Real Exact/FTS Search Projections

Status: gated

Acceptance:

- Build authorized Postgres exact/FTS projections from canonical card versions.
- Select tenant/namespace/public shard before candidate generation.
- Apply revocation fence before returning results.
- Implement canonical tokenizer, `tsvector`/extracted text, rank formula,
  score normalization, abstention threshold, replay fixtures, and latency
  probes.
- Return retrieval-panel metadata only by default.
- Rebuild projections from event stream.

### PR-BE-010: Search Index Manifests And Cutover

Status: proposed

Acceptance:

- Hot and main index generations have manifests with source event ranges,
  processor version, content hash, revocation epoch, and replay hash.
- Cutover is atomic and rollbackable.
- Stale or unknown generation returns `no_suggestion`.
- Index rebuild and reconciliation commands exist.

### PR-BE-011: Revocation Fence Everywhere

Status: proposed

Acceptance:

- Every card read, search result, cache pointer, derived artifact, index row,
  approval handoff, and public response checks tombstones/consent state.
- Public responses do not leak revocation epoch, index generation, counts, or
  rarity diagnostics.
- Emergency deny manifest exists for DB outage and reconciles back to Postgres.

### PR-BE-012: Queue Workers, Sweeper, And DLQ Redrive

Status: proposed

Acceptance:

- Dedicated workers for admission, redaction, review, approval, revocation,
  event projection, indexing, compaction, embedding, and notifications.
- Safety-critical lanes reserve worker slots and DB connections.
- Sweeper scans events, outbox, and jobs by `event_stream_position`.
- DLQ redrive requires operator identity, reason, dry-run preview, and audit.

### PR-BE-013: Operational Circuits

Status: proposed

Acceptance:

- Postgres-backed `operational_circuits` table with RLS and audit.
- Emergency signed config/deny path exists when Postgres cannot accept circuit
  writes.
- Circuit families cover auth/revocation, queue admission, search dependency,
  vector/rerank/cost, public wedge, publication, and noncritical writes.
- Strictest state wins when normal and emergency stores disagree.

### PR-BE-014: Observability And Audit

Status: proposed

Acceptance:

- Every API request, worker job, queue attempt, approval, index generation,
  revocation, and operator command carries trace/correlation fields.
- Logs are structured JSON and contain no raw source bodies, secrets,
  unpublished redaction text, private paths, or protected bodies.
- Metrics, traces, audit events, and support views have RBAC/redaction tests.

### PR-BE-015: Runbooks And Drills

Status: proposed

Acceptance:

- Implement runnable command stubs or scripts for:
  - search latency
  - index freshness
  - queue backlog/DLQ
  - emergency revocation
  - migration/index cutover failure
  - dependency outage
  - Postgres backup/restore/failover/corruption
  - consent/revocation UX degradation
- Each runbook has first 5 minutes, commands, dashboards, kill switches,
  rollback, verification, reconciliation, and owner.
- Drill transcripts are attached to release evidence.

### PR-BE-016: Deployment Health Contract

Status: proposed

Acceptance:

- API and workers expose live, startup, ready, and dependency health endpoints.
- Readiness fails closed for auth, revocation, migration incompatibility, and
  unknown active index generation.
- Route-class readiness separates search, submit/write, card-read,
  trusted-consent-revocation, reviewer-admin, worker-lane, and landing.

### PR-BE-017: Vector And Rerank Layer

Status: post-use-ready

Acceptance:

- Add vector tables with model/version/dimension metadata.
- Benchmark pgvector HNSW under tenant, namespace, lifecycle, risk, and
  embedding-kind filters.
- Add rollbackable index manifests and vector circuit.
- Disable vector/rerank when cost or latency circuit opens.
- Fallback to exact/FTS or `no_suggestion`.

### PR-BE-018: Public Search And Publication

Status: blocked

Acceptance:

- Public privacy attack model passes.
- Rare fingerprint thresholds, cohort floors, timing normalization, abuse
  budgets, and public no-suggestion equivalence pass.
- Public publication consent/revocation E2E works.
- Hostile-card and prompt-injection release gates pass.
- Anonymous search remains disabled until all public gates pass.

### PR-BE-019: Enterprise Governance

Status: blocked

Acceptance:

- Managed guidance schema, lifecycle, predicates, revocation, conflict handling,
  audit, high-impact leases, and admin/reviewer mutation routes are implemented.
- Guidance remains separate from experience cards and cannot override higher
  policy, consent, authorization, revocation, or tool policy.

### PR-BE-020: Billing And Cost Metering

Status: blocked

Acceptance:

- Define billable units, attribution dimensions, sampling/rounding,
  reconciliation, audit events, dry-run alerts, correction records, tenant
  reporting, and override handling.
- Billing enforcement remains disabled until meter reconciliation passes.

### PR-BE-021: Public GitHub Issue Ingestion

Status: proposed

Goal:

Bootstrap public corpus growth from source-policy-reviewed public GitHub issue,
pull request, commit, and release timelines for WEDGE-001 domains. This is the
primary scale path for public cards; user private work remains a secondary
candidate source that still requires exact-artifact approval.

Acceptance:

- Define repo allowlist, source-policy review, source attribution, takedown,
  source edit/deletion reflection, and rate-limit budget.
- Use official GitHub APIs with cache/ETag/backoff and no aggressive scraping.
- First collector run stores only dry-run manifests: source IDs, URLs, labels,
  timestamps, linked PR/release references, and rate-limit evidence.
- Timeline extractor classifies solved, failed-only, unknown-clarified,
  deprecated, duplicate, stale, and disputed outcomes.
- Card synthesis stores structured summaries and provenance, not full mirrored
  issue/comment bodies.
- Deterministic scanners reject or withhold private-looking logs, credentials,
  hostnames, customer/incident markers, personal data, destructive advice, and
  security-sensitive operations.
- Dedup, supersession, contradiction, and deprecation edges are generated from
  source evidence.
- Public serving remains closed until PR-BE-018/public-search gates pass.

Verification:

- Dry-run manifest for 5 to 10 allowed repos and at least 100 candidate
  timelines.
- Manual spot-check for 50 extracted timelines.
- 100 generated public-source seed cards in a non-serving review namespace.
- Replay evaluation against web search, GitHub search, official docs, public
  Q&A, and repo-local search baselines.

## Production-Ready Exit Criteria

Production-ready for private/team retrieval requires:

- PR-BE-001 through PR-BE-017 complete or explicitly deferred by accepted RFC
- non-synthetic body persistence gate open
- trusted consent/revocation UI live
- protected-data durability and auth verifier gates accepted
- exact/FTS retrieval over authorized projections live
- revocation fence and no-log ingress tests pass
- queue, sweeper, DLQ, runbooks, drills, readiness, and observability pass
- `python -m pytest` and deployment-profile gate validators pass

Production-ready for public search/publication additionally requires:

- PR-BE-018 complete
- public documentation release gate complete
- reviewer capacity and public privacy thresholds accepted
- public abuse/cost circuits live
- public routes pass withdrawal/rollback drills

## Recommended Next Order

1. PR-BE-021 Phase 0 and Phase 1 as a parallel public-corpus bootstrap that
   does not create serving public cards yet.
2. UR-BE-004 local vault artifact format only if approval preview dogfood needs
   it.
3. PR-BE-003 protected-data durability plan and drills.
4. PR-BE-005 intake safety gate implementation for protected/product submit
   as design/test-only until durability and no-log ingress are ready.
5. PR-BE-006 product submit candidate API.
6. PR-BE-007 consent/revocation UI backend.
7. PR-BE-009 real exact/FTS projections.
