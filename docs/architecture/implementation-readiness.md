# Implementation Readiness

This document turns review findings into blocking implementation requirements. If an item is marked "MVP blocker", implementation should not proceed past the named milestone without it.

## Milestones

| Milestone | Scope | Must ship | Explicitly out |
|---|---|---|---|
| M0 | Schema and event log | accepted DDL RFC 0001, tenant/RLS policy, card events, tombstones, idempotency keys | vector search, public corpus |
| M1 | Private writer queue | Postgres-backed jobs, admission, redaction draft, private candidates | public indexing, curated packs |
| M2 | Consent and revocation | approval challenge, consent matrix, revoke cockpit, tombstone read fence | commercial derived use |
| M3 | Exact and FTS retrieval | authorized exact/FTS search, sidecar only, no body cache | pgvector, inline hints |
| M4 | pgvector hybrid | vector table, HNSW parameters, index manifests, rollback runbook | paid rerank |
| M5 | Agent access | MCP/CLI contract, delegated tokens, hooks, search response contract | broad third-party integrations |
| M6 | Public wedge pilot | quotas, review capacity, quality gates, cost circuits | general public contributor marketplace |

M3 may use an internal CLI/API harness to test exact/FTS sidecar retrieval. Full external MCP/hooks support remains M5 scope.

M6 is blocked until wedge privacy validation proves that public search enforces the `k` distinct-tenant cohort rule, minimum cohort size, normalized timing/reasons, privacy budgets, and rare-query generic abstention. The validation corpus must include rare fingerprint probes and hostile command/package/repo/credential-bearing cards; unverified high-risk cards must remain hidden from sidecar and inline output.

## MVP Defaults

These are provisional defaults. A wedge RFC can change them only with measured evidence.

- local card body cache: disabled
- queue: Postgres-backed queue
- object storage: S3-compatible interface, provider pinned in deployment RFC before first raw/source artifact storage
- public card candidate quota: 20 per tenant per day
- anonymous public search: 60 requests per hour per IP/account tuple
- rerank: disabled for free anonymous users
- raw/source retention max TTL: 30 days
- approval challenge TTL: 10 minutes
- write-capable delegated token TTL: 15 minutes
- read-only delegated token TTL: 60 minutes
- global retrieval budget: 2500 ms
- exact/FTS fallback budget: 1000 ms
- rerank budget: 800 ms

M1 storage boundary: private candidate metadata and redacted draft bodies may live in Postgres. Raw/source artifacts remain disabled until M2 or a deployment RFC pins object storage, encryption, purge, and signed access.

## Postgres and Migration Requirements

MVP DDL RFC must define:

- table columns and nullability
- `(tenant_id, id)` primary or unique keys for tenant-scoped tables
- composite foreign keys that include `tenant_id`
- partial unique index for one current card version
- partial unique index for one active public approval per card version
- `card_events(tenant_id, card_id, event_seq)` unique
- `card_edges(tenant_id, source_card_id, edge_type, target_card_id)` unique
- self-edge prohibition
- JSONB validation policy
- outcome/status/quality compatibility checks
- source artifact TTL and encryption columns
- search index manifest active-generation uniqueness

Migration requirements:

- use expand/contract migrations
- use `CREATE INDEX CONCURRENTLY` for large live-table indexes
- run concurrent index creation outside transaction-wrapped migration blocks
- detect and drop invalid indexes before retry
- use `NOT VALID` and `VALIDATE CONSTRAINT` for large new constraints
- batch backfills
- write rollback plans before visibility, authorization, storage, or index changes

Lifecycle values should be lookup tables plus transition tables for MVP. If Postgres enum types are used later, enum values are append-only and cannot be renamed or removed during a compatibility window.

## Event Ordering

`card_events` must include:

- `tenant_id`
- `card_id`
- `event_id`
- `event_seq`
- `event_type`
- `actor_id`
- `actor_role`
- `previous_status`
- `next_status`
- `expected_current_version`
- `causation_event_id`
- `correlation_id`
- `idempotency_key`
- `created_at`

Projection updates use optimistic concurrency: update only when the current version or event sequence matches the expected value. Conflicts create retryable errors, not silent overwrites.

## Revocation Fence

Revocation is independent of lifecycle status. Every read path checks tombstones before returning a card, artifact, search result, cache entry, derived artifact, or raw/source object.

Required fields:

- `revocation_event_id`
- `tenant_id`
- `subject_type`
- `subject_id`
- `card_id`
- `card_version_id`, nullable for card-wide revocation
- `reason`
- `revoked_by`
- `created_at`
- `revocation_epoch`

Search responses include `revocation_epoch`. Clients must reject cached data when the server epoch is newer or unavailable.

## Queue Contract

MVP uses a Postgres-backed queue with:

- at-least-once delivery
- no ordering guarantee across different logical objects
- per-logical-object idempotency keys
- visibility timeout: 2 minutes
- lease renewal: allowed up to 10 minutes
- max attempts: 5
- backoff: exponential with jitter
- DLQ retention: 30 days
- redrive requires operator action and reason
- poison jobs keep original payload digest and error history

Core tables:

- `jobs`
- `job_attempts`
- `idempotency_keys`
- `outbox_events`

Workers are not allowed to define correctness. Correctness comes from constraints, event sequence, idempotency, and reconciliation.

## Cost Circuits

Budget controls are active controls, not only telemetry.

Initial circuits:

- disable rerank when daily rerank budget reaches 80 percent
- pause embedding jobs when embedding spend reaches 80 percent of daily budget
- throttle tenant submissions when review backlog exceeds capacity
- stop anonymous search when anonymous spend exceeds daily budget
- force exact/FTS only when vector latency exceeds circuit threshold
- pause public candidate admission under duplicate flood

Every circuit needs an audit event and an operator override path.

## Runbook Template

Every runbook must include:

- symptoms
- first 5 minutes
- dashboard links
- diagnostic queries
- safe mitigations
- kill switches
- rollback command
- customer impact
- verification
- reconciliation
- owner

Emergency revocation, index freshness breach, queue backlog, and search latency spike runbooks are MVP blockers.

## Deferred Decision Backlog

Deferred decisions live in `docs/decisions/README.md`. A deferred item must have:

- ID
- status
- owner
- blocking milestone
- decision deadline
- options
- current default
- dependent docs
