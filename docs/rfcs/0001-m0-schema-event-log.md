# RFC 0001 - M0 Schema and Event Log

## Status

Accepted for M0 implementation.

Gate: this RFC is M0-blocking. M0 implementation may begin only when the
schema, RLS policies, migrations, and tests satisfy the contracts below. Any
change to lifecycle values, idempotency semantics, revocation fences, or
tenant boundary behavior requires an RFC amendment before M1 work depends on
it.

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
- `card_statuses`
- `card_event_types`
- `actor_roles`
- `outcome_types`
- `quality_states`
- `evidence_strengths`
- `revocation_subject_types`
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

M0 must create placeholder tables only when a concrete M0 foreign key needs
them. Otherwise they stay out of the M0 schema.

## Lifecycle Lookups

Lifecycle values are data, not enum types. M0 must seed lookup rows in the
same migration that creates the tables using stable text keys.

Required `card_statuses` keys:

- `candidate_created`
- `pending_admission`
- `deferred`
- `pending_redaction`
- `pending_review`
- `awaiting_user_approval`
- `approved_private`
- `approved_for_publication`
- `published`
- `indexed_hot`
- `indexed_main`
- `rejected`
- `superseded`
- `deprecated`
- `revoked`

Required `card_event_types` keys:

- `card_created`
- `version_created`
- `admission_deferred`
- `review_requested`
- `redaction_completed`
- `private_approved`
- `publication_approved`
- `reviewer_published`
- `rejected`
- `superseded`
- `deprecated`
- `revoked`

Required `actor_roles` keys:

- `app_user`
- `agent_delegated_user`
- `ingestion_worker`
- `approval_worker`
- `redaction_worker`
- `review_worker`
- `index_worker`
- `compaction_worker`
- `revocation_worker`
- `billing_worker`
- `reviewer`
- `tenant_admin`
- `platform_admin`
- `break_glass_admin`

Required `outcome_types` keys:

- `solved`
- `failed_only`
- `inconclusive`
- `unknown_clarified`

Required `quality_states` keys:

- `unreviewed`
- `solved_once`
- `solved_many`
- `verified`
- `disputed`

Required `evidence_strengths` keys:

- `single_session`
- `multi_session`
- `reproduced`
- `external_reference`
- `operator_judgment`

Required `revocation_subject_types` keys:

- `card`
- `card_version`
- `namespace`
- `tenant`

Lookup rows must have stable `key`, display `label`, `is_active`, and
`created_at` columns. Application code must reference `key`; generated
surrogate IDs may exist but are not part of the public contract. Migrations may
add lookup values but must not rename or delete seeded keys after release.

`card_state_transitions` must reference `card_statuses(key)` for
`from_status` and `to_status`, and may reference `card_event_types(key)` when a
transition is tied to a specific event. A transition row defines the only valid
path between two statuses for an actor role.

M0 must seed the public publication path explicitly:
`pending_review -> awaiting_user_approval`,
`awaiting_user_approval -> approved_for_publication`, and
`approved_for_publication -> published`. `approve_publication` can only perform
the second transition. `reviewer_publish` can only perform the third transition.

## Required Constraints

M0 must include:

- `(tenant_id, id)` primary or unique keys on tenant-scoped tables
- composite foreign keys including `tenant_id`
- one current version per card
- one active public approval per public card version
- `card_events(tenant_id, card_id, event_seq)` unique
- idempotency key uniqueness by tenant, operation, logical object, operation version, and idempotency key
- revocation tombstone uniqueness for the same subject and revocation epoch
- no state transition outside `card_state_transitions`

Minimum table contract:

- `tenants`: `id uuid not null primary key`, `slug text not null`, `name text
  not null`, `created_at timestamptz not null`, `disabled_at timestamptz null`;
  unique `slug`.
- `namespaces`: `tenant_id uuid not null`, `id uuid not null`, `key text not
  null`, `name text not null`, `created_at timestamptz not null`,
  `archived_at timestamptz null`; primary key `(tenant_id, id)`, unique
  `(tenant_id, key)`, foreign key `tenant_id -> tenants(id) on delete restrict`.
- `experience_cards`: `tenant_id`, `id`, `namespace_id`, `current_version_id`,
  `status`, `outcome_type`, `quality_state`, `evidence_strength`, `created_by`,
  `created_at`, `updated_at`; lifecycle fields reference their lookup tables.
- `card_versions`: `tenant_id`, `id`, `card_id`, `version_number`,
  `content_digest`, `created_by`, `created_at`, `superseded_at`; unique
  `(tenant_id, card_id, version_number)`.
- `card_events`: fields listed in Event Ordering; `event_id` is globally
  unique and `(tenant_id, event_id)` is unique for tenant-scoped references.
- `card_state_transitions`: `from_status`, `to_status`, `event_type`,
  `actor_role`, `is_active`, `created_at`; unique
  `(from_status, to_status, event_type, actor_role)`.
- `revocation_tombstones`: `tenant_id`, `id`, `subject_type`, `subject_id`,
  `card_id`, `card_version_id`, `revocation_epoch`, `reason`, `created_by`,
  `created_at`.
- `consent_records`: `tenant_id`, `id`, `subject_id`, `scope`, `granted_at`,
  `revoked_at`, `source_event_id`.
- `idempotency_keys`: `tenant_id`, `id`, `operation`, `logical_object_type`,
  `logical_object_id`, `operation_version`, `idempotency_key`,
  `request_digest`, `response_digest`, `effect_event_id`, `created_at`,
  `expires_at`.
- `audit_events`: `tenant_id`, `id`, `actor_id`, `actor_role`, `action`,
  `target_type`, `target_id`, `reason`, `correlation_id`, `created_at`.

All M0 tenant-scoped table identities use `tenant_id uuid not null` and
`id uuid not null` with primary key `(tenant_id, id)`, unless the table is a
global lookup. All status/type/role fields are `text not null` foreign keys to
lookup `key` columns. All `created_at` fields are `timestamptz not null`.
Nullable fields must be listed explicitly in the migration and in tests.

Foreign key defaults:

- tenant-owned child rows use `on delete restrict`
- immutable event/audit/revocation rows use `on delete restrict`
- optional current pointers, such as `current_version_id`, use `on delete set null`
- no tenant-scoped foreign key may omit `tenant_id`

The idempotency uniqueness constraint must exclude `request_digest` from the
logical key. On replay, the original row is selected by
`(tenant_id, operation, logical_object_type, logical_object_id,
operation_version, idempotency_key)`. If `request_digest` differs from the
stored digest, the request fails as an idempotency conflict and must not create
a second effect.

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

`event_seq` is tenant/card local, starts at 1, and is monotonic with no reuse.
The append path must check `expected_current_version` against the current card
version in the same transaction that inserts the event and advances card state.

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

Direct card lookup must join or anti-join `revocation_tombstones` by
`tenant_id` and the matching `card_id` or `card_version_id`. If the lookup code
cannot complete that check, it must fail closed.

## RLS Requirements

M0 must define roles:

- app user
- agent delegated user
- ingestion worker
- approval worker
- redaction worker
- review worker
- index worker
- compaction worker
- revocation worker
- billing worker
- reviewer
- tenant admin
- platform admin
- break-glass admin

RLS requirements:

- normal app roles have RLS enabled
- policies include both `USING` and `WITH CHECK`
- `BYPASSRLS` is not used for application traffic
- break-glass access emits audit events and is time-bound
- tenant-scoped tables filter reads by the current tenant claim/session setting
- tenant-scoped inserts and updates require `tenant_id` to match the current
  tenant claim/session setting
- worker policies are tenant-scoped unless the job explicitly carries a
  platform-admin or break-glass authorization context
- lookup tables are readable by application roles but writable only by migration
  or platform-admin paths
- audit and event tables are append-only for application roles
- delete is denied on `card_events`, `audit_events`, and
  `revocation_tombstones`

RLS tests must cover read, insert, update, and delete attempts for at least two
tenants.

## Migration Requirements

Migration framework is resolved for M0: use ordered SQL migration files under a
repository `migrations/` directory, executed by a small repo-owned migration
runner or script. The runner must record applied versions and checksums in a
`schema_migrations` table and must support both `up` and `down` files. M0 does
not require adopting an external migration framework.

Local development Postgres is resolved for M0: provide a Docker Compose service
for Postgres as the default local database. The migration runner may also accept
`DATABASE_URL` so contributors can use an existing local Postgres instance.

M0 migration tooling must support:

- transactional DDL where safe
- non-transactional path for `CREATE INDEX CONCURRENTLY`
- invalid index detection and retry
- `NOT VALID` and `VALIDATE CONSTRAINT`
- rollback script for every migration that affects visibility, authorization, event ordering, or revocation
- checksum mismatch detection for already-applied migrations
- a clean apply to an empty database
- a no-op second apply

The runner must detect invalid indexes after non-transactional index creation
by querying Postgres catalog state and must drop/retry only the named index from
the active migration.

## Test Contract

M0 must include automated tests that run against local Postgres:

- empty-database migration apply succeeds
- migration re-run is a no-op
- migration rollback works for every M0 migration with a `down` file
- tenant-scoped composite FKs prevent cross-tenant references
- RLS denies cross-tenant read, insert, update, and delete
- lookup tables contain the required seeded keys
- invalid lifecycle transition fails
- valid lifecycle transition appends exactly one event
- stale event append fails as a retryable conflict
- idempotent replay with the same digest returns the original effect
- idempotent replay with a different digest fails without a second effect
- revoked card direct lookup fails closed
- append-only tables reject update and delete from application roles

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
