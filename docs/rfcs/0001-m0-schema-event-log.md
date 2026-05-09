# RFC 0001 - M0 Schema and Event Log

## Status

Draft.

## Scope

M0 creates the durable data foundation only.

In scope:

- Postgres schema skeleton
- tenant-scoped key strategy
- RLS policy shape
- card identity and versions
- append-only card events
- state transition table
- revocation tombstones
- idempotency keys
- audit events
- migration rules

Out of scope:

- vector search
- public corpus
- MCP/hooks
- raw/source artifact storage
- object storage provider
- consent UI
- billing

## Design Defaults

M0 follows:

- [Implementation Readiness](../architecture/implementation-readiness.md)
- [Data Model](../architecture/data-model.md)
- [Security and Privacy](../architecture/security-privacy.md)

Lifecycle values use lookup tables plus transition tables, not Postgres enum types.

All tenant-scoped entities use `(tenant_id, id)` as the primary identity pattern. Cross-table references include `tenant_id`.

## Required Tables

M0 must define:

- `tenants`
- `namespaces`
- `experience_cards`
- `card_versions`
- `card_events`
- `card_state_transitions`
- `revocation_tombstones`
- `consent_records`
- `idempotency_keys`
- `audit_events`

M0 may define empty placeholder tables for later milestones only if they are needed by foreign keys:

- `source_artifacts`
- `derived_artifacts`
- `search_index_manifests`

## Required Constraints

M0 must include:

- `(tenant_id, id)` primary or unique keys on tenant-scoped tables
- composite foreign keys including `tenant_id`
- one current version per card
- one active public approval per public card version
- `card_events(tenant_id, card_id, event_seq)` unique
- idempotency key uniqueness by tenant, operation, logical object, operation version, and request digest
- revocation tombstone uniqueness for the same subject and revocation epoch
- no state transition outside `card_state_transitions`

## Event Ordering

`card_events` includes:

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

Writers append events with optimistic concurrency. A stale expected version causes a retryable conflict.

## Revocation Fence

Revocation is not only a card status. It is a read-path deny record.

Every future read model must be able to check:

- `tenant_id`
- `subject_type`
- `subject_id`
- `card_id`
- `card_version_id`
- `revocation_epoch`

M0 must prove that a revoked card version cannot be returned by a direct card lookup.

## RLS Requirements

M0 must define roles:

- app user
- agent delegated user
- worker
- reviewer
- tenant admin
- platform admin
- break-glass admin

RLS requirements:

- normal app roles have RLS enabled
- policies include both `USING` and `WITH CHECK`
- `BYPASSRLS` is not used for application traffic
- break-glass access emits audit events and is time-bound

## Migration Requirements

M0 migration tooling must support:

- transactional DDL where safe
- non-transactional path for `CREATE INDEX CONCURRENTLY`
- invalid index detection and retry
- `NOT VALID` and `VALIDATE CONSTRAINT`
- rollback script for every migration that affects visibility, authorization, event ordering, or revocation

## Acceptance Criteria

M0 is complete when:

- schema can be applied to an empty local Postgres database
- tenant-scoped FK tests pass
- RLS denies cross-tenant reads/writes in tests
- idempotent replay returns the original effect
- stale event append fails
- invalid state transition fails
- revoked card direct lookup fails closed
- migration check runs in CI or local test command

## Open Questions

- Exact migration framework
- Whether placeholder tables for later milestones should be created in M0
- Whether local development uses Docker Compose or an existing Postgres
