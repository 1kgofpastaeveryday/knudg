# RFC 0001 - M0 Schema and Event Log

## Status

Accepted M0 design with implementation blockers.

Gate: this RFC is M0-blocking. M0 implementation may begin only when the
schema, RLS policies, migrations, and tests satisfy the contracts below. Any
change to lifecycle values, idempotency semantics, revocation fences, or
tenant boundary behavior requires an RFC amendment before M1 work depends on
it.

Code-start gates:

| Slice | Clearance |
|---|---|
| local M0 schema implementation | allowed after the accepted M0 SQL migration, RLS contracts, and local DEC-019 HS256 profile pass tests |
| M1 non-synthetic private/team protected-data code | blocked until the asymmetric/KMS-style verifier profile, M1 protected-data durability gate, and request-context backend-swap tests pass |
| shared dev, staging, team, production, or public deployment | blocked until local HS256 is disabled by environment assertion/CI and the accepted non-local verifier/key-custody profile is active |

Before M0 implementation hardens a migration, run a reversibility review. It
must list lifecycle, idempotency, revocation, consent, visibility, and tenant
boundary decisions that are hard to migrate; identify which WEDGE-001 discovery
evidence can still change them; and confirm that wedge-specific assumptions are
kept out of the domain-general schema.

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
- `principals`
- `external_identities`
- `tenant_memberships`
- `namespace_grants`
- `worker_identities`
- `claim_signing_keys`
- `request_claim_contexts`
- `schema_migrations`
- `event_stream_positions`
- `approval_challenges`
- `namespaces`
- `card_statuses`
- `card_event_types`
- `actor_roles`
- `outcome_types`
- `quality_states`
- `verification_statuses`
- `evidence_strengths`
- `namespace_visibilities`
- `revocation_subject_types`
- `consent_scopes`
- `artifact_types`
- `card_edge_types`
- `tenant_revocation_epochs`
- `break_glass_cases`
- `verification_records`
- `candidate_intakes`
- `intake_submissions`
- `experience_cards`
- `card_versions`
- `domain_events`
- `card_events`
- `card_edges`
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

Minimum identity and access table contracts are defined in the Required
Constraints section. They must include disabled/revoked/expired state,
purpose-bound worker identity, and bounded membership/grant scopes.

Identity/access tests must cover disabled principals, revoked namespace grants,
cross-tenant memberships, worker role mismatch, and break-glass approver
distinctness.

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
- `discard_pending`
- `publication_withdrawn`
- `published`
- `indexed_hot`
- `indexed_main`
- `rejected`
- `superseded`
- `deprecated`
- `revoked`

Required `card_event_types` keys:

- `card_created`
- `admission_accepted`
- `version_created`
- `admission_deferred`
- `redaction_requested`
- `review_requested`
- `redaction_completed`
- `user_approval_requested`
- `private_approved`
- `publication_approved`
- `approval_withdrawn`
- `discard_requested`
- `discard_restored`
- `approval_digest_invalidated`
- `reviewer_rejected_after_approval`
- `reviewer_requested_reredaction`
- `reviewer_published`
- `hot_indexed`
- `main_indexed`
- `rejected`
- `superseded`
- `deprecated`
- `revoked`
- `dispute_recorded`

Required `domain_event_types` keys:

- `tenant_revoked`
- `namespace_revoked`
- `source_artifact_revoked`
- `derived_artifact_revoked`
- `search_index_manifest_revoked`
- `consent_granted`
- `consent_terminated`
- `approval_challenge_created`
- `approval_challenge_invalidated`
- `operational_case_opened`
- `operational_case_closed`
- `index_manifest_created`
- `index_manifest_activated`

Required `actor_roles` keys:

- `app_user`
- `agent_delegated_user`
- `ingestion_worker`
- `approval_challenge_worker`
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

Required `namespace_visibilities` keys:

- `private`
- `team`
- `enterprise`
- `public`

Required `revocation_subject_types` keys:

- `tenant`
- `namespace`
- `card`
- `card_version`
- `source_artifact`
- `derived_artifact`
- `search_index_manifest`
- `consent_record` for request routing only; it terminates consent and does not
  create a tombstone unless paired with a retrieval-affecting subject

M0 tombstones support tenant, namespace, card, and card-version subjects.
Source-artifact, derived-artifact, and search-index-manifest subject columns
stay nullable and unreferenced until their concrete tables are introduced by an
accepted RFC. Revoking a `consent_record` writes a `consent_terminated` domain
event and updates the consent row; it does not create a tombstone unless the
same user action also revokes an underlying tenant, namespace, card, card
version, source artifact, derived artifact, or index manifest.

Required `verification_statuses` keys:

- `active`
- `expired`
- `revoked`
- `superseded`

Required `consent_scopes` keys:

- `private_candidate_collection`
- `private_retention`
- `team_namespace_grant`
- `public_publication`
- `intake_review_escrow`
- `raw_source_retention`
- `derived_artifact`
- `commercial_use`
- `model_eval_use`

Product surface names such as canonical trail, aggregate stats, verified
rewrite, curated pack, commercial-derived use, and model/eval use are stored as
`surface_type` or policy metadata under the canonical scope. They are not
valid `consent_scopes` keys.

Required `artifact_types` keys:

- `intake_submission`
- `card_version`
- `source_artifact`
- `derived_artifact`
- `search_index_manifest`
- `policy_document`

Required `card_edge_types` keys:

- `contradicts`
- `supersedes`
- `duplicate_of`
- `variant_of`
- `deprecated_by`
- `derived_from_private_card`

Lookup rows must have stable `key`, display `label`, `is_active`, and
`created_at` columns. They must also carry `valid_from_schema_version`,
`valid_to_schema_version`, and `retired_at`. Application code must reference
`key`; generated surrogate IDs may exist but are not part of the public
contract. Migrations may add lookup values but must not rename or delete seeded
keys after release. New writes may use only active rows for the current schema
version. Historical replay may accept rows that were valid for the event's
schema version, even after later retirement.

`card_state_transitions` must reference `card_statuses(key)` for
`from_status` and `to_status`, and may reference `card_event_types(key)` when a
transition is tied to a specific event. A transition row defines the only valid
path between two statuses for an actor role.

M0 must seed private and public lifecycle branches explicitly. The private
branch is `pending_review -> awaiting_user_approval -> approved_private`.
`approve_private` can only perform `awaiting_user_approval -> approved_private`.

The public branch is
`pending_review -> awaiting_user_approval -> approved_for_publication ->
published`. `approved_private` is not in the public publication path.
`complete_publication_approval` can only perform
`awaiting_user_approval -> approved_for_publication`. `reviewer_publish` can
only perform `approved_for_publication -> published`.

M0 must seed this minimum transition matrix:

| From | To | Event type | Actor role |
|---|---|---|---|
| `candidate_created` | `pending_admission` | `admission_accepted` | `ingestion_worker` |
| `pending_admission` | `deferred` | `admission_deferred` | `ingestion_worker` |
| `deferred` | `pending_admission` | `admission_accepted` | `ingestion_worker` |
| `candidate_created`, `pending_admission`, `deferred`, `pending_redaction`, `pending_review`, `awaiting_user_approval` | `rejected` | `rejected` | `review_worker` |
| `candidate_created`, `pending_admission`, `deferred`, `pending_redaction`, `pending_review`, `awaiting_user_approval` | `discard_pending` | `discard_requested` | `app_user` |
| `discard_pending` | `pending_review` | `discard_restored` | `app_user` |
| `pending_admission` | `pending_redaction` | `redaction_requested` | `ingestion_worker` |
| `pending_redaction` | `pending_review` | `redaction_completed` | `redaction_worker` |
| `pending_review` | `awaiting_user_approval` | `user_approval_requested` | `review_worker` |
| `awaiting_user_approval` | `pending_redaction` | `approval_digest_invalidated` | `app_user` or `review_worker` |
| `awaiting_user_approval` | `approved_private` | `private_approved` | `app_user` |
| `awaiting_user_approval` | `approved_for_publication` | `publication_approved` | `app_user` |
| `approved_for_publication` | `publication_withdrawn` | `approval_withdrawn` | `app_user` |
| `publication_withdrawn` | `awaiting_user_approval` | `user_approval_requested` | `app_user` |
| `approved_for_publication` | `rejected` | `reviewer_rejected_after_approval` | `reviewer` |
| `approved_for_publication` | `pending_redaction` | `reviewer_requested_reredaction` | `reviewer` |
| `approved_for_publication` | `published` | `reviewer_published` | `reviewer` |
| `published` | `indexed_hot` | `hot_indexed` | `index_worker` |
| `indexed_hot` | `indexed_main` | `main_indexed` | `index_worker` |
| `published`, `indexed_hot`, `indexed_main` | `superseded` | `superseded` | `reviewer` |
| `published`, `indexed_hot`, `indexed_main` | `deprecated` | `deprecated` | `reviewer` |
| `candidate_created`, `pending_admission`, `deferred`, `pending_redaction`, `pending_review`, `awaiting_user_approval`, `approved_private`, `approved_for_publication`, `discard_pending`, `publication_withdrawn`, `published`, `indexed_hot`, `indexed_main`, `rejected`, `superseded`, `deprecated` | `revoked` | `revoked` | `app_user` or `break_glass_admin` |

`card_created` is the only creation event and has no prior status. It inserts
the card projection at `candidate_created`. Every later lifecycle change must
match an active `card_state_transitions` row.

Metadata-only events such as `version_created`, `review_requested`, and
`dispute_recorded` keep `previous_status = next_status` and must also have an
active self-transition row for the actor role. M0 must seed self-transitions
for `version_created` on non-revoked card states by the writer role creating
the version, `review_requested` on `pending_review` by `review_worker`, and
`dispute_recorded` on `published`, `indexed_hot`, `indexed_main`, `superseded`,
and `deprecated` by `review_worker`.

## Required Constraints

M0 must include:

- `(tenant_id, id)` primary or unique keys on tenant-scoped tables
- composite foreign keys including `tenant_id`
- first card/version creation uses deferrable initially-deferred composite FKs
  between `experience_cards.current_version_id` and `card_versions`; the
  append function may hold an uncommitted temporary-null current version only
  inside the transaction, and no committed card may lack a current version
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
- `principals`: `id uuid not null primary key`, `principal_type text not
  null`, `display_name text not null`, `external_subject text null`,
  `disabled_at timestamptz null`, `created_at timestamptz not null`;
  `principal_type` is bounded to human users, delegated clients, workers,
  reviewers, tenant admins, and platform admins. Disabled principals cannot
  receive new sessions, worker leases, grants, or approval challenges.
- `external_identities`: `id uuid not null primary key`,
  `principal_id uuid not null`, `issuer text not null`, `subject text not
  null`, `audience text not null`, `identity_provider_id text not null`,
  `provider_key_id text null`, `verified_at timestamptz not null`,
  `disabled_at timestamptz null`, `created_at timestamptz not null`; active
  identities are unique by `(issuer, subject, identity_provider_id, audience)`.
  A bare `sub` is never globally unique without issuer binding. If a provider
  has no audience, the write path stores the canonical sentinel
  `urn:knudg:no-audience`; `audience` is never NULL.
- `claim_signing_keys`: `kid text not null primary key`, `alg text not null`,
  `verify_secret bytea not null`, `not_before timestamptz not null`,
  `not_after timestamptz null`, `disabled_at timestamptz null`,
  `created_at timestamptz not null`; used by `knudg_set_claims` and
  `knudg_current_claims`. M0 pins `pgcrypto` for HMAC verification by creating
  schema `knudg_crypto`, installing `pgcrypto` with
  `CREATE EXTENSION pgcrypto WITH SCHEMA knudg_crypto`, revoking CREATE on
  `public`, and revoking PUBLIC execute on crypto functions before granting
  only the migration-owned verifier path what it needs. For `alg = 'HS256'`,
  the API/auth layer mints the request context and stores the HMAC verification
  secret in `claim_signing_keys.verify_secret`. The table is owned by
  `knudg_migration`, has no grants to application roles, and is read only by
  the fixed-`search_path` security-definer verifier that calls fully qualified
  `knudg_crypto.hmac`. Application roles cannot read this table or execute
  generic HMAC/digest helper functions. Before M0 implementation, the DDL
  appendix must choose concrete key custody. Preferred custody is asymmetric
  verification or external KMS/Vault verification so database compromise cannot
  mint new contexts. If HS256 remains for local M0, the secret must be envelope
  encrypted outside ordinary backups, have `kid`-scoped rotation windows,
  emergency disable, key-use audit events, incident runbook coverage, and test
  vectors proving old, disabled, expired, and unknown keys fail closed.
- `request_claim_contexts`: `backend_pid integer not null`,
  `transaction_id xid8 not null`, `request_id uuid not null`,
  `claims_digest text not null`, `principal_id uuid not null`,
  `tenant_id uuid not null`, `actor_role text not null`,
  `namespace_ids uuid[] not null`, `grant_snapshot_version bigint not null`,
  `expires_at timestamptz not null`, `created_at timestamptz not null`;
  primary key `(backend_pid, transaction_id, request_id)`. Rows are deleted at
  transaction end or by short TTL cleanup and are readable only by definer
  functions.
- `schema_migrations`: `version text not null primary key`,
  `checksum text not null`, `state text not null`, `started_at timestamptz not
  null`, `finished_at timestamptz null`, `step text null`,
  `error_class text null`; records migration state for retry and invalid-index
  cleanup.
- `event_stream_positions`: `event_stream_position bigint not null primary
  key`, `tenant_id uuid not null`, `event_source_type text not null`,
  `card_event_id uuid null`, `domain_event_id uuid null`, `created_at
  timestamptz not null`; exactly one event reference is present, and the
  referenced `card_events` or `domain_events` row must carry the same
  `event_stream_position`. This is the global durable replay cursor for
  projections, outbox reconciliation, and index manifests. M0 uses one
  Postgres sequence as the allocator and treats this table as the immutable
  position ledger, not as a second allocator. `card_events.event_stream_position`
  and `domain_events.event_stream_position` are non-null and unique. A deferred
  constraint trigger enforces the bijection: every ledger row references
  exactly one event row; the referenced event row has the same `tenant_id`,
  `event_id`, source type, and `event_stream_position`; and no event row can
  commit without a matching ledger row. Event append inserts the event row and
  ledger row in the same transaction. Application roles cannot insert directly
  into event or ledger tables.
- `tenant_memberships`: `tenant_id uuid not null`, `id uuid not null`,
  `principal_id uuid not null`, `membership_role text not null`,
  `status text not null`, `created_at timestamptz not null`,
  `valid_from timestamptz not null`, `expires_at timestamptz null`,
  `revoked_at timestamptz null`, `effective_until timestamptz null`,
  `grant_version bigint not null`; primary key
  `(tenant_id, id)`. Historical rows are preserved. Database uniqueness is
  materialized-only: M0 enforces one open grant row for the same `(tenant_id,
  principal_id, membership_role)` through a partial unique index where
  `status = 'active'`, `revoked_at is null`, and `effective_until is null`.
  That index must not reference `now()`, `valid_from`, `expires_at`, or any
  non-immutable expression. Runtime eligibility additionally requires
  `valid_from <= now()` and `(expires_at is null or expires_at > now())` inside
  `knudg_current_claims()` and write-path authorization. The write path must
  materialize `effective_until` before inserting a replacement after expiry, so
  materialization delay cannot extend access or block a deliberate regrant.
- `namespace_grants`: `tenant_id uuid not null`, `id uuid not null`,
  `namespace_id uuid not null`, `principal_id uuid not null`,
  `grant_scope text not null`, `status text not null`,
  `created_at timestamptz not null`, `valid_from timestamptz not null`,
  `expires_at timestamptz null`, `revoked_at timestamptz null`,
  `effective_until timestamptz null`, `grant_version bigint not null`; primary
  key `(tenant_id, id)`. Historical
  grant rows are preserved. One open grant row is allowed for `(tenant_id,
  namespace_id, principal_id, grant_scope)` using the same
  status/revocation/effective-until partial unique rule. That uniqueness rule
  is materialized-only and must not reference `now()`, `valid_from`,
  `expires_at`, or any non-immutable expression. Authorization predicates check
  `valid_from` and `expires_at` at read/write time. The write path must
  materialize `effective_until` before regrant after expiry.
  Grant scope is bounded to read, search,
  submit, review, and admin capabilities and cannot imply user consent.
- `worker_identities`: `id uuid not null primary key`,
  `principal_id uuid not null`, `worker_role text not null`, `purpose text not
  null`, `allowed_operations text[] not null`, `created_at timestamptz not
  null`, `disabled_at timestamptz null`; each worker maps to one principal and
  one purpose-bound role. Disabled workers cannot set scoped claims or lease
  jobs.
- `namespaces`: `tenant_id uuid not null`, `id uuid not null`, `key text not
  null`, `name text not null`, `visibility text not null`, `created_at
  timestamptz not null`, `archived_at timestamptz null`; primary key
  `(tenant_id, id)`, unique `(tenant_id, key)`, foreign key
  `tenant_id -> tenants(id) on delete restrict`. `visibility` must be one of
  `private`, `team`, `enterprise`, or `public` and must reference
  `namespace_visibilities(key)`.
- `tenant_revocation_epochs`: `tenant_id uuid not null primary key`,
  `last_epoch bigint not null default 0`, `updated_at timestamptz not null`;
  foreign key `tenant_id -> tenants(id) on delete restrict`.
- `break_glass_cases`: `tenant_id uuid not null`, `id uuid not null`,
  `status text not null`, `target_type text not null`, `target_id uuid not
  null`, `permitted_operations text[] not null`, `reason_code text not null`,
  `approved_by_1 uuid not null`, `approved_by_2 uuid not null`,
  `requested_by uuid not null`, `expires_at timestamptz not null`,
  `created_at timestamptz not null`, `closed_at timestamptz null`,
  `post_access_reviewed_at timestamptz null`; primary key `(tenant_id, id)`.
  `tenant_id` references `tenants(id) on delete restrict`. Approver and
  requester columns reference human `principals(id)`. `status` is bounded to
  `open`, `active`, `expired`, `closed`, and `rejected`; `target_type` and
  `permitted_operations` are bounded lookup values; `permitted_operations` must
  be non-empty; `expires_at > created_at`; `approved_by_1 <> approved_by_2`.
  A constraint trigger proves target scope matches the requested tenant/object
  before a break-glass claim can be set.
- `verification_records`: `tenant_id uuid not null`, `id uuid not null`,
  `card_id uuid not null`, `card_version_id uuid not null`,
  `verification_status text not null`, `reviewer_id uuid not null`,
  `activity_id uuid not null`, `environment_digest text not null`,
  `input_digest text not null`, `output_digest text not null`,
  `version_bounds jsonb not null`, `risk_class text not null`,
  `external_refs jsonb not null default '[]'::jsonb`, `created_at timestamptz
  not null`, `expires_at timestamptz not null`, `revoked_at timestamptz null`,
  `superseded_at timestamptz null`; primary key `(tenant_id, id)`. It has a
  composite FK `(tenant_id, card_id, card_version_id)` to
  `card_versions(tenant_id, card_id, id)`, reviewer FK to `principals(id)`, and
  `verification_status` references `verification_statuses(key)`. Active
  verification means `verification_status = 'active'`, `revoked_at is null`,
  `superseded_at is null`, and `expires_at > now()` at read time. M0 enforces
  one open active verification row per `(tenant_id, card_id, card_version_id)`
  with a materialized partial unique index where
  `verification_status = 'active'`, `revoked_at is null`, and
  `superseded_at is null`; the index must not reference `now()`. A constraint
  trigger on `experience_cards.active_verification_record_id` proves the
  referenced record belongs to the same card and current version and is open
  active before `quality_state = 'verified'` can commit. Search and display
  still recheck expiry and withhold the verified label after expiry until a
  demotion event updates the projection.
- `experience_cards`: `tenant_id`, `id`, `namespace_id`, `current_version_id`,
  `active_verification_record_id`, `status`, `outcome_type`,
  `quality_state`, `evidence_strength`, `created_by`, `created_at`,
  `updated_at`; lifecycle fields reference their lookup tables.
  `active_verification_record_id` is nullable unless
  `quality_state = 'verified'`; when present it must identify an active,
  unexpired verification record for the current card version.
  Namespace visibility is the visibility source of truth. Card rows may expose
  visibility only through a view or generated projection derived from the
  referenced namespace; it must not be independently stored or mutated.
- `card_versions`: `tenant_id`, `id`, `card_id`, `version_number`,
  `card_schema_version`, `payload_json jsonb`, `payload_digest`, `created_by`,
  `created_at`; unique `(tenant_id, card_id, version_number)`, unique
  `(tenant_id, card_id, id)`. `card_versions` is insert-only; supersession is
  represented by events, `experience_cards.current_version_id`, and
  version-scoped edges.
- `domain_events`: `tenant_id uuid not null`, `event_id uuid not null`,
  `event_type text not null`, `actor_id uuid not null`, `actor_role text not
  null`, `target_type text not null`, `target_id uuid not null`,
  `event_payload_schema_version integer not null`, `event_payload_json jsonb
  not null`, `event_payload_digest text not null`, `causation_event_id uuid
  null`, `correlation_id uuid not null`, `idempotency_key text not null`,
  `event_stream_position bigint not null`, `created_at timestamptz not null`;
  primary key `(tenant_id, event_id)`, unique `(event_stream_position)`, and
  unique `(tenant_id, event_id, event_stream_position)`. `event_type`
  references `domain_event_types(key)`. Domain events record tenant, namespace,
  artifact, index-manifest, consent, and operational events that are not card
  lifecycle transitions. Each domain event type has a JSON payload schema and
  authorization predicate; unbounded free-text event types are rejected.
- `candidate_intakes`: `tenant_id`, `intake_id`, `namespace_id`,
  `actor_subject_id`, `idempotency_key_id`, protected input fingerprint and key
  ID, gate verdict, coarse reason classes, scanner/classifier policy versions,
  body-storage decision, escrow state, `expires_at`, audit correlation, and
  created timestamp. Primary key `(tenant_id, intake_id)`, foreign keys include
  tenant, namespace, actor, and idempotency row. It stores no raw body, snippet,
  path, repo name, customer label, detector output, or model rationale.
- `intake_submissions`: `tenant_id`, `submission_id`, `intake_id`,
  `namespace_id`, protected input fingerprint and key ID, canonicalization
  version, tenant-keyed `protected_artifact_digest`, digest key ID, digest
  profile, source-class summary, TTL, policy version, challenge ID, consent
  record ID when completed, purge state, and created timestamp. Primary key
  `(tenant_id, submission_id)`, foreign key `(tenant_id, intake_id)` to
  `candidate_intakes`, and check constraints prove no raw body or raw locator
  is stored. `protected_artifact_digest` is an HMAC-style digest over the
  canonical submitted artifact using tenant-scoped secret material, key ID,
  canonicalization version, and rotation/dual-read metadata; raw SHA-style
  content digests are forbidden in this table, audit, exports, client
  responses, and admin search. Consent for
  `scope = 'intake_review_escrow'` must bind
  `artifact_type = 'intake_submission'`, this `submission_id`, and the exact
  `protected_artifact_digest` through the generic consent `artifact_digest`
  field. Expiry or withdrawal purges any linked escrow and leaves only metadata
  required for audit and idempotency.
- `card_events`: fields listed in Event Ordering; `event_id` is globally
  unique and `(tenant_id, event_id)` is unique for tenant-scoped references.
  `event_stream_position` is non-null and globally unique; `(tenant_id,
  event_id, event_stream_position)` is unique for event-ledger references.
  Card lifecycle events include `event_payload_schema_version`,
  `event_payload_json`, and `event_payload_digest` so event-specific facts are
  durable.
- `card_edges`: `tenant_id`, `id`, `source_card_id`, `target_card_id`,
  `source_card_version_id`, `target_card_version_id`, `edge_type`,
  `created_by`, `created_at`; unique `(tenant_id, source_card_version_id,
  edge_type, target_card_version_id)`, composite foreign keys
  `(tenant_id, source_card_id, source_card_version_id)` and
  `(tenant_id, target_card_id, target_card_version_id)` to
  `card_versions(tenant_id, card_id, id)`, foreign keys to both cards, and a
  constraint prohibiting self-edges. Canonical edge uniqueness is
  version-scoped; current-card edge views, if needed later, are derived
  projections. Required edge types are
  `contradicts`, `supersedes`, `duplicate_of`, `variant_of`,
  `deprecated_by`, and `derived_from_private_card`; `edge_type` references
  `card_edge_types(key)`. `derived_from_private_card` edges are non-public,
  visible only to authorized owner/reviewer contexts, and must not expose
  private source identifiers in public card handles, public search, or public
  exports.
- `card_state_transitions`: `from_status`, `to_status`, `event_type`,
  `actor_role`, `is_active`, `created_at`; unique
  `(from_status, to_status, event_type, actor_role)`.
- `revocation_tombstones`: `tenant_id`, `id`, `subject_type`, `subject_id`,
  typed nullable subject columns for tenant, namespace, card, card version,
  source artifact, derived artifact, and search index manifest,
  `card_id`, `card_version_id`, `revocation_epoch`,
  `revocation_event_source_type`, `card_revocation_event_id`,
  `domain_revocation_event_id`, `revoked_by`, `reason`, `created_at`. A check
  constraint requires exactly one subject target and a matching `subject_type`;
  concrete M0 subject targets use composite tenant FKs. `subject_id` must be
  generated from the typed target or omitted from writes and maintained by a
  trigger; mismatched generic and typed IDs are prohibited. Card and
  card-version revocations reference `card_events(tenant_id, event_id)` through
  `card_revocation_event_id`; tenant, namespace, artifact, and index-manifest
  revocations reference `domain_events(tenant_id, event_id)` through
  `domain_revocation_event_id`. Exactly one event reference is present and
  `revocation_event_source_type` matches the subject family. A constraint
  trigger must verify that the referenced event's tenant, actor, target type,
  and target ID exactly match the tombstone typed subject.
- `approval_challenges`: `tenant_id`, `id`, `subject_id`, `namespace_id`,
  `consent_scope`, `artifact_type`, `artifact_id`, `card_version_id`,
  `artifact_digest`, `policy_version`, `policy_digest`, `challenge_digest`,
  `origin`, `expires_at`, `used_at`, `used_by_consent_id`, `invalidated_at`,
  `created_by`, `created_at`; primary
  key `(tenant_id, id)`. A challenge is single-use: `used_at` and
  `used_by_consent_id` are set in the same transaction that inserts the consent
  record. Expired, invalidated, used, artifact-mismatched, or policy-mismatched
  challenges fail closed. `consent_scope` references `consent_scopes(key)` and
  is included in `challenge_digest`. Concurrent double-submit must affect
  exactly one consent row.
- `consent_records`: `tenant_id`, `id`, `subject_id`, `scope`,
  `namespace_id`, `artifact_type`, `artifact_id`, `card_version_id`, `artifact_digest`,
  `policy_version`, `policy_digest`, `challenge_id`, `challenge_digest`,
  `granted_at`, `expires_at`, `revoked_at`, `termination_reason`,
  `terminated_by`, `grant_card_event_id`, `grant_domain_event_id`,
  `termination_card_event_id`, `termination_domain_event_id`,
  `retention_policy`, `retention_purpose`.
  Public card approval uses
  `card_version_id not null` with a composite FK to `card_versions`; generic
  derived-artifact consent cannot satisfy public card publication. When
  `artifact_type = 'card_version'`, `artifact_id` must equal
  `card_version_id`. `scope` references `consent_scopes(key)` and
  `artifact_type` references `artifact_types(key)`. Unknown, inactive, or
  retired discriminator values are rejected before state advancement.
  Publication and retention lookups fail closed when consent is expired,
  revoked, scope-mismatched, artifact-mismatched, or policy-mismatched.
  A consent row created from an approval challenge must exactly match the
  challenge's `tenant_id`, `subject_id`, `namespace_id`, `consent_scope`,
  `artifact_type`, `artifact_id`, `card_version_id`, `artifact_digest`,
  `policy_version`, `policy_digest`, and `challenge_digest`; wrong subject,
  scope, namespace, artifact, or policy is a constraint-trigger failure before
  any lifecycle transition can advance.
  Exactly one of `grant_card_event_id` or `grant_domain_event_id` is present.
  Termination refs are both NULL while `revoked_at` is NULL; exactly one of
  `termination_card_event_id` or `termination_domain_event_id` is present when
  `revoked_at` is not NULL. Card-version publication/private-retention grants
  use card event refs; domain or non-card consent scopes use domain event refs.
  Constraint triggers verify referenced event tenant, actor, namespace, scope,
  artifact type, artifact ID, and digest match the consent row.
- `idempotency_keys`: `tenant_id`, `id`, `operation`, `logical_object_type`,
  `logical_object_id`, `operation_version`, `idempotency_key`,
  `request_digest`, `response_digest`, `effect_event_source_type`,
  `effect_card_event_id`, `effect_domain_event_id`, `created_at`,
  `expires_at`. Exactly one effect event reference is present for committed
  mutating operations.
- `audit_events`: `tenant_id`, `id`, `actor_id`, `actor_role`, `action`,
  `target_type`, `target_id`, `reason_code`, `sanitized_detail`,
  `correlation_id`, `created_at`. `reason_code` is a lookup or bounded enum;
  `sanitized_detail` is length-limited and must reject raw snippets, secrets,
  credentials, private paths, unpublished redaction text, and customer data.

All M0 tenant-scoped table identities use `tenant_id uuid not null` and
`id uuid not null` with primary key `(tenant_id, id)`, unless the table is a
global lookup. All status/type/role fields are `text not null` foreign keys to
lookup `key` columns, except `card_events.previous_status`, which is nullable
only for `card_created`. All `created_at` fields are `timestamptz not null`.
Nullable fields must be listed explicitly in the migration and in tests.

The accepted M0 RFC is not migration-complete until the repository contains an
M0 DDL appendix or SQL migration that expands every minimum table contract into
exact PostgreSQL DDL: column types, nullability, primary keys, unique
constraints, foreign keys including `on delete` behavior and deferrability,
CHECK constraints, trigger names, partial-index predicates, grants, and
negative tests. Prose table summaries are implementation requirements, but they
do not authorize inventing missing DDL during coding.

`card_versions.payload_json` is the parsed canonical card body. The write path
must receive raw JSON bytes or text, run the canonical parser, reject duplicate
object keys before any `jsonb` cast can collapse them, and only then persist
`payload_json`. It must contain the version-scoped semantic fields defined in
the data model for its `card_schema_version`. It must not contain projection-owned fields:
`tenant_id`, `namespace_id`, `visibility`, `status`, `current_version_id`,
`created_at`, or `updated_at`. M0 must validate full payload shape in
application code before insert and store `payload_digest` as a deterministic
digest of the canonicalized JSON payload bytes.

M0 digest profile uses RFC 8785 JSON Canonicalization Scheme over UTF-8 bytes,
rejects duplicate object keys before canonicalization, stores `digest_alg`
alongside each digest, and defaults to `sha256:jcs-rfc8785:v1`. Migrations must
include cross-language test vectors covering key order, Unicode, numbers,
arrays, and duplicate-key rejection. Consent approval binds to these canonical
bytes, not to UI-rendered text.

Rejected duplicate-key writes must fail before insert and write only a
sanitized audit event with parser version and rejection class; they must not
store the rejected raw payload.

The database must enforce minimum JSONB invariants with CHECK constraints or a
stable validation function: `payload_json` is an object, required schema-v1
keys exist, arrays are arrays, structured objects are objects, projection-owned
keys are absent, lookup-valued payload keys are strings, safety metadata is
present before public publication, and `payload_digest` is non-empty. Full
semantic validation remains in application code, but the accepted write path
must run it inside the same transaction before state advancement. The
event-append function or a database constraint trigger verifies projection
fields against the current version payload and rejects invalid combinations
such as failed-only payloads projected as solved/verified or payload outcome
fields that disagree with `experience_cards.outcome_type`.

Before M0 migration review, the repository must contain the
`card_schema_version = 1` JSON Schema artifact and digest test vectors for the
canonical payload. The schema must cover safety, privacy, provenance,
environment, context fingerprint, outcome, evidence, and reusable-step fields.
The migration may use a lighter database validator, but it cannot ship without
the canonical schema and tests used by the application write path.

The schema-v1 safety object must define `safety_class`,
`review_state`, executable-advice flags, URL/package/repository indicators,
credential/billing/deletion/network-call indicators, `verification_state`, and
`withheld_reason`. `review_state` values include at least `unreviewed`,
`quarantined`, `cleared`, and `blocked`; `safety_class` includes at least
`low`, `medium`, and `high`. Publication and indexing transition guards must
reject missing safety metadata, `review_state = quarantined`, blocked safety
state, or high-risk metadata without the required verification record.

`card_versions` immutability is a database contract, not only an application
rule. Application roles have INSERT and SELECT only. A trigger must reject
UPDATE or DELETE on `card_versions`; if maintenance roles are later allowed to
repair metadata, the trigger must still reject changes to identity, schema,
payload, digest, and creation columns.

Application roles cannot insert directly into `card_versions`. Card-version
writes go through a security-definer function that accepts raw JSON text or
bytes, rejects duplicate keys, validates schema, computes the canonical digest,
casts to `jsonb`, and inserts the row. Tests must prove direct table writes
cannot bypass duplicate-key rejection.

Consent is valid only for the exact artifact, approval policy, and user
challenge presented at approval time. Publication checks must match
`artifact_type`, `artifact_id`, `artifact_digest`, `policy_version`,
`policy_digest`, `challenge_id`, and `challenge_digest`; any mismatch requires
new consent.

Public publication approvals are not time-expiring consent records in M0.
For `scope = 'public_publication'`, `expires_at` must be NULL; withdrawal,
revocation, policy invalidation, or digest mismatch ends the approval. Time
limited consent uses `expires_at` only for private retention, raw/source
retention, model/eval use, or commercial-use scopes. If expiring public
approvals are needed later, a future RFC must change the uniqueness and
publication lookup contract explicitly.

For public card publication, M0 must create a partial unique index allowing
only one active public approval per card version:
`unique (tenant_id, card_version_id, scope) where revoked_at is null and scope
= 'public_publication' and artifact_type = 'card_version'`. The migration must
also enforce `check (artifact_type <> 'card_version' or artifact_id =
card_version_id)`. Exact artifact, policy, and challenge columns remain part
of the publish-time lookup and must be covered by a non-unique lookup index.

Foreign key defaults:

- tenant-owned child rows use `on delete restrict`
- immutable event/audit/revocation rows use `on delete restrict`
- `experience_cards.(tenant_id, id, current_version_id)` references
  `card_versions(tenant_id, card_id, id)` with `on delete restrict`,
  `deferrable initially deferred`; first card creation preallocates the card
  UUID and version UUID and inserts a non-null `current_version_id` in the same
  transaction as the first `card_versions` row, relying on the deferred FK
  rather than a committed nullable pointer
- `card_versions.(tenant_id, card_id)` references `experience_cards` with
  `on delete restrict`, `deferrable initially deferred`
- no tenant-scoped foreign key may omit `tenant_id`

`experience_cards.current_version_id` is the only current-version pointer.
M0 must not add `card_versions.is_current` or a partial unique current-version
index; that would create a second source of truth. The pointer update and
`version_created` event append happen in the same transaction.

Minimum foreign key matrix:

| Table | Foreign key target |
|---|---|
| `external_identities.principal_id` | `principals(id)` |
| `tenant_memberships.(tenant_id, principal_id)` | `tenants(id)`, `principals(id)` |
| `namespace_grants.(tenant_id, namespace_id)` and `principal_id` | `namespaces(tenant_id, id)`, `principals(id)` |
| `worker_identities.principal_id` | `principals(id)` |
| `namespaces.tenant_id` | `tenants(id)` |
| `experience_cards.(tenant_id, namespace_id)` | `namespaces(tenant_id, id)` |
| `experience_cards.(tenant_id, id, current_version_id)` | `card_versions(tenant_id, card_id, id)` |
| `experience_cards.(tenant_id, active_verification_record_id)` | `verification_records(tenant_id, id)` when `quality_state = 'verified'` |
| `experience_cards.status/outcome_type/quality_state/evidence_strength` | corresponding lookup `key` |
| `card_versions.(tenant_id, card_id)` | `experience_cards(tenant_id, id)` |
| `domain_events.event_type/actor_role` | `domain_event_types(key)` and corresponding actor-role lookup |
| `card_events.(tenant_id, card_id)` | `experience_cards(tenant_id, id)` |
| `card_events.event_type/actor_role/previous_status/next_status` | corresponding lookup `key` |
| `event_stream_positions.card_event_id/domain_event_id` | `card_events(tenant_id, event_id)` or `domain_events(tenant_id, event_id)` plus deferred trigger match on `(tenant_id, event_id, event_stream_position)` |
| `card_edges.source/target card IDs` | `experience_cards(tenant_id, id)` |
| `card_edges.(tenant_id, source_card_id, source_card_version_id)` | `card_versions(tenant_id, card_id, id)` |
| `card_edges.(tenant_id, target_card_id, target_card_version_id)` | `card_versions(tenant_id, card_id, id)` |
| `card_edges.edge_type` | `card_edge_types(key)` |
| `card_state_transitions` status, event, actor columns | corresponding lookup `key` |
| `break_glass_cases.tenant_id` | `tenants(id)` |
| `verification_records.(tenant_id, card_id, card_version_id)` | `card_versions(tenant_id, card_id, id)` |
| `revocation_tombstones` typed subject columns | concrete tenant-scoped subject table composite keys where the subject table exists in the milestone |
| `revocation_tombstones.card_revocation_event_id` | `card_events(tenant_id, event_id)` for card and card-version subjects |
| `revocation_tombstones.domain_revocation_event_id` | `domain_events(tenant_id, event_id)` for tenant, namespace, source, derived, and index-manifest subjects |
| `consent_records.(tenant_id, card_version_id)` for public card approval | `card_versions(tenant_id, id)` |
| `consent_records.scope/artifact_type` | `consent_scopes(key)` and `artifact_types(key)` |
| `approval_challenges.(tenant_id, namespace_id)` | `namespaces(tenant_id, id)` when namespace-scoped |
| `approval_challenges.(tenant_id, card_version_id)` | `card_versions(tenant_id, id)` when challenge is card-version scoped |
| `approval_challenges.consent_scope/artifact_type` | `consent_scopes(key)` and `artifact_types(key)` |
| `approval_challenges.used_by_consent_id` | `consent_records(tenant_id, id)` |
| actor/subject/approver columns | `principals(id)` where they identify a human, worker, or delegated client |
| `consent_records.grant_card_event_id/termination_card_event_id` | `card_events(tenant_id, event_id)` |
| `consent_records.grant_domain_event_id/termination_domain_event_id` | `domain_events(tenant_id, event_id)` |
| `idempotency_keys.effect_card_event_id` | `card_events(tenant_id, event_id)` |
| `idempotency_keys.effect_domain_event_id` | `domain_events(tenant_id, event_id)` |

RLS policies read claims only through an application-owned security-definer
claim setter and getter pair. The setter verifies server-signed request context,
tenant membership, namespace grants, actor role, and optional break-glass case
before setting transaction-local claims. Application roles cannot issue
arbitrary SQL or directly set trusted `knudg.claims.*` transport settings;
adversarial tests must prove direct `SET knudg.claims.tenant_id`, malformed
settings, and cross-tenant spoofing fail. Tenant tables use normal non-owner
roles with `FORCE ROW LEVEL SECURITY`;
`BYPASSRLS` is forbidden for application traffic. Missing, malformed, unsigned,
or caller-set claims deny reads and writes by default. Break-glass settings
require a validated case and an audit event in the same transaction.

M0 RLS appendix must define exact GUC names, security-definer setter
signatures, signed request-context schema, accepted signing algorithms, key
rotation placeholder, grants, worker scoped-claim flow, and at least one policy
example for read and write paths before migrations are written.

The idempotency uniqueness constraint must exclude `request_digest` from the
logical key. On replay, the original row is selected by
`(tenant_id, operation, logical_object_type, logical_object_id,
operation_version, idempotency_key)`. If `request_digest` differs from the
stored digest, the request fails as an idempotency conflict and must not create
a second effect. Mutating operations keep durable effect identity permanently:
`expires_at` controls response-body retention, not uniqueness or conflict
detection. After response compaction, replay can return an effect reference or
conflict, but it must never permit the same logical idempotency key to create a
second mutation.

## Event Ordering

`card_events` includes:

- `tenant_id`
- `card_id`
- `event_id`
- `event_stream_position`
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
- `event_payload_schema_version`
- `event_payload_json`
- `event_payload_digest`

`event_payload_json` is required even when empty. Per-event validation must
define required payload keys for deferral and rejection reasons, approval
artifact and policy digests, index source event ranges, supersession and
deprecation edge IDs, dispute evidence, and card-scoped revocation references.
`event_payload_digest` uses the same canonical digest profile as card payloads.
All digest-bearing JSON artifacts use explicit digest profiles and test
vectors before they can bind consent or authorization: card payload, event
payload, approval challenge, policy document, claim envelope, source artifact
manifest, derived artifact manifest, and index manifest. The default JSON
profile is `sha256:jcs-rfc8785:v1`; non-JSON byte artifacts must declare their
own byte profile and parser.

Writers append events with optimistic concurrency. A stale expected version causes a retryable conflict.

`event_seq` is tenant/card local, starts at 1, and is monotonic with no reuse.
The append path must check `expected_current_version` against the current card
version in the same transaction that inserts the event and advances card state.
`event_stream_position` is global across `card_events` and `domain_events`,
strictly increasing, and allocated only inside the event append transaction
from the M0 event-position sequence. It is the only cursor allowed for
projection replay, outbox reconciliation, and index manifests. `event_seq` must
never be used to prove global freshness. Commit-time checks must prove exactly
one ledger row and exactly one event row share a position; the event table,
tenant, event ID, and position must match in both directions.

Application roles must append events only through an event-append function. The
function locks the card row, checks `expected_current_version`, validates the
active `(previous_status, next_status, event_type, actor_role)` transition,
inserts one event, updates the card projection, and records the idempotency
effect in the same transaction. Direct inserts into `card_events` are denied to
application roles.

Projection columns on `experience_cards` are rebuildable from
`card_events`, `card_versions`, and namespace metadata. The event-append
function is the only writer of lifecycle projection fields. If a projection
update would disagree with the appended event, current version, or namespace
visibility source of truth, the transaction must fail.

Operation-to-event mapping:

| Operation | Event type | Required side effect |
|---|---|---|
| `submit_candidate` with synthetic fixture provenance only | `card_created` | insert card at `candidate_created`, first version, first event, idempotency row, and current-version pointer in one transaction |
| `submit_candidate` with non-synthetic content | no direct card event | route through the volatile intake safety gate first; only an accepted, synchronously redacted canonical draft may later create `card_created` |
| `complete_publication_from_private_request` | `card_created` plus source edge | trusted source-owner completion creates a new public candidate only after a validated redacted candidate `card_versions` payload is ready; if no redacted first-version payload is available, the operation records only the trusted handoff or redaction work item and creates no card row; the creation transaction inserts the card at `candidate_created`, that first redacted candidate version, current-version pointer, idempotency row, and non-public `derived_from_private_card` edge; source private card is not mutated and private consent is not copied |
| `accept_admission` | `admission_accepted` | advance from candidate/deferred admission states |
| `defer_admission` | `admission_deferred` | persist deferral reason in event metadata |
| `request_redaction` | `redaction_requested` | assign redaction work |
| `complete_redaction` | `redaction_completed` | create immutable redacted version if payload changed |
| `create_version` | `version_created` | insert immutable card version and update current pointer |
| `request_review` | `review_requested` | assign review work |
| `request_user_approval` | `user_approval_requested` | bind approval artifact digest |
| `approve_private` | `private_approved` | insert exact private consent record |
| `complete_publication_approval` | `publication_approved` | insert active public consent record |
| `withdraw_publication_approval` | `approval_withdrawn` | move to `publication_withdrawn`, revoke active public consent, and block later `reviewer_publish` |
| `discard_candidate` | `discard_requested` | move to `discard_pending`, remove private retrieval projections immediately, and start undo window |
| `restore_discarded_candidate` | `discard_restored` | return from `discard_pending` to `pending_review` during undo window |
| `reviewer_publish` | `reviewer_published` | recheck public consent and namespace eligibility |
| `mark_indexed_hot` | `hot_indexed` | persist source event range for hot index |
| `mark_indexed_main` | `main_indexed` | persist source event range for main index |
| `reject_card` | `rejected` | persist rejection reason |
| `supersede_card` | `superseded` | insert version-scoped `supersedes` edge |
| `deprecate_card` | `deprecated` | insert version-scoped `deprecated_by` edge when replacement exists |
| `revoke_subject` for a card/card version | `revoked` | append card lifecycle event, insert tombstones sharing one epoch, and reference that card event |
| `revoke_subject` for tenant/namespace/artifact/index manifest | domain `*_revoked` | append bounded domain event, insert tombstones sharing one epoch, and reference that domain event |
| `revoke_consent_record` | domain `consent_terminated` | mark the consent row revoked without a tombstone unless the same action also revokes an underlying retrieval subject |

`submit_candidate` and trusted `complete_publication_from_private_request` are
the only card creation paths. Direct `submit_candidate -> card_created`
creation is synthetic-fixture-only until PR-006 is accepted. Non-synthetic
submit must first create intake metadata and an `intake_submission` artifact
digest inside the no-log intake gate; non-accepted verdicts create no card
body, no card version, and no retrieval projection. Public-from-private
creation has the same non-null first-version invariant: a redacted first
version is a prerequisite, not an optional follow-up. `card_created` uses
`previous_status = null`, `expected_current_version = null`, and
`event_seq = 1`. The append function may bypass normal transition lookup only
for this creation event; it still writes the idempotency row, card, first
version, event, and current-version pointer atomically. Retrying the same
idempotency key and request digest returns the existing creation effect.

The creation function preallocates both the card UUID and first version UUID.
It inserts `experience_cards.current_version_id` as the first version UUID,
inserts the matching `card_versions` row, appends `card_created`, and commits
only if the deferred composite FKs validate. M0 does not allow a committed null
`current_version_id`.

## Required Indexes

M0 must include these correctness-critical indexes:

- child-side indexes for every composite foreign key
- idempotency replay lookup on `(tenant_id, operation, logical_object_type,
  logical_object_id, operation_version, idempotency_key)`
- `card_events(tenant_id, card_id, event_seq desc)`
- `card_events(event_stream_position)` unique
- `card_events(tenant_id, event_id, event_stream_position)` unique
- `domain_events(event_stream_position)` unique
- `domain_events(tenant_id, event_id, event_stream_position)` unique
- `event_stream_positions(event_stream_position)`
- `event_stream_positions(tenant_id, event_source_type, event_stream_position)`
- `verification_records(tenant_id, card_id, card_version_id)` with the open
  active partial unique predicate described above
- `approval_challenges(tenant_id, id)` with a uniqueness constraint on
  `used_by_consent_id` when present
- `revocation_tombstones(tenant_id, subject_type, subject_id, revocation_epoch)`
- `revocation_tombstones(tenant_id, card_id, card_version_id, revocation_epoch)`
- unique active public approval partial index on `consent_records` for the
  exact artifact scope where `revoked_at is null`
- exact public approval lookup on `(tenant_id, artifact_type, artifact_id,
  artifact_digest, policy_version, policy_digest, challenge_id,
  challenge_digest)` where `revoked_at is null`
- audit lookup indexes by `(tenant_id, target_type, target_id)` and
  `(tenant_id, correlation_id)`

## Revocation Fence

Revocation is not only a card status. It is a read-path deny record.

Every future read model must be able to check:

- `tenant_id`
- `subject_type`
- `subject_id`
- `card_id`
- `card_version_id`
- `revocation_epoch`

M0 must prove that revoked tenant, namespace, card, and card-version subjects
cannot be returned by direct card lookup, approval artifact lookup, reviewer
view, queue payload expansion, export, or local metadata revalidation. Later
milestones must add the same negative tests before shipping each new readable
artifact class, including source artifacts, derived artifacts, index manifests,
search results, and admin views.

Revocation epochs are tenant-local, strictly increasing integers allocated by
locking `tenant_revocation_epochs(tenant_id)` and incrementing `last_epoch` in
the same transaction that appends the `revoked` event and inserts tombstones.
All tombstones produced by one revoke operation share the same
`revocation_epoch`, event source reference, and `revoked_by`. `revoked_by`
must equal the actor on the referenced card or domain `revoked` event. Card and
card-version revocations append the card lifecycle event and use
`card_revocation_event_id`; tenant, namespace, source-artifact,
derived-artifact, and search-index-manifest revocations append a
`domain_events` row and use `domain_revocation_event_id`.

Direct card lookup must join or anti-join `revocation_tombstones` by
`tenant_id` and any matching tenant, namespace, card, or card-version subject.
If the lookup code cannot complete that check, it must fail closed.

## RLS Requirements

M0 must define roles:

- app user
- agent delegated user
- ingestion worker
- approval challenge worker
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

### M0 RLS Appendix

M0 migrations must implement the following minimum RLS contract before schema
work is considered ready for code:

- DB roles: `knudg_app`, `knudg_worker`, `knudg_migration`,
  `knudg_readonly_ops`; only `knudg_migration` may own tables.
- Application claims are stored as a signed request context in a protected
  backend-local claim table keyed by backend PID, transaction ID, and
  `request_id`. Raw `knudg.claims.*` GUC values are advisory transport only and
  are never read directly by RLS policies.
- Claims are set only through `knudg_set_claims(signed_context jsonb)`.
  The function is `SECURITY DEFINER`, owned by the migration role, and grants
  execute only to `knudg_app` and `knudg_worker`. The function definition must
  set `search_path = pg_catalog, knudg_private, knudg_crypto, pg_temp`;
  `public` is not allowed in the search path of any security-definer RLS
  helper, and `pg_temp` must be explicitly last.
- `knudg_set_claims` verifies a server-signed context envelope containing
  `tenant_id`, `principal_id`, actor role, allowed namespace IDs, audience,
  proof key ID, expiry, and request ID. The envelope has `alg`, `kid`,
  `issued_at`, `expires_at`, `nonce`, and canonical payload digest fields.
  For M0 portability, the API/auth layer verifies external OIDC or Ed25519
  credentials and then mints a short-lived DB-local `HS256` request context.
  The database verifies that context with fully qualified `knudg_crypto.hmac`
  and `knudg_crypto.digest` calls using the
  `claim_signing_keys.verify_secret` row selected by `kid`. The verifier is a
  `SECURITY DEFINER` function owned by `knudg_migration`, sets
  `search_path = pg_catalog, knudg_private, knudg_crypto, pg_temp`, reads
  exactly one active key row by `kid`, recomputes the HMAC over the canonical
  payload bytes, uses a fixed-length digest comparison, and returns typed
  claims only after nonce, audience, expiry, membership, grant, and worker
  checks pass.
  `public` is never in the verifier search path. A future RFC may replace this
  with Vault-backed key access or a pinned managed Ed25519 extension, but M0
  migrations must not depend on an unselected secret channel or crypto
  extension. Disabled or unknown keys fail closed. Tests must cover unknown
  key, disabled key, expired context, bad signature, replayed nonce, wrong
  audience, direct application-role denial on the key table, denial of direct
  app-role execution of `knudg_crypto.hmac` and `knudg_crypto.digest`, and a
  hostile `public.hmac`/`public.digest` or `pg_temp.hmac`/`pg_temp.digest`
  shadowing attempt that cannot affect the verifier.
- RLS policies read claims only through `knudg_current_claims()`, a
  `SECURITY DEFINER` getter that revalidates the signed context row, expiry,
  nonce/request binding, tenant membership, namespace grants, actor role, and
  optional break-glass case before returning typed claims. Its function
  definition must also set `search_path = pg_catalog, knudg_private,
  knudg_crypto, pg_temp` and must never rely on caller-controlled search path,
  temp objects, or objects in `public`.
- `knudg_set_claims` materializes a grant snapshot for the transaction:
  tenant membership IDs, namespace grant IDs, their `grant_version` values,
  valid time window, and disabled-principal/worker state. `knudg_current_claims()`
  either verifies that the referenced rows still have matching versions and
  active validity at statement time or fails closed. It must not rely on a
  cached namespace array after membership, grant, principal, or worker state is
  revoked or expired in another transaction.
- Protected break-glass reads and writes must use security-definer wrapper
  functions that create the required audit row before accessing protected
  tables. Policies cannot rely on clients to insert audit rows manually.
  Entitlement-table lookups inside `knudg_current_claims()` run under the
  definer owner with fixed `search_path`, avoid recursive RLS policy calls, and
  recheck membership/grant status in the same transaction.
- Read policies require
  `tenant_id = (knudg_current_claims()).tenant_id` and namespace membership
  when a row has `namespace_id`.
- Write policies use both `USING` and `WITH CHECK`; inserted or updated
  `tenant_id` must equal the current tenant claim.
- Worker policies require `actor_role` to match the worker's allowed role and
  the job's tenant scope.
- Break-glass policies require a valid, unexpired `break_glass_case_id` and an
  audit event in the same transaction.
- All tenant tables use `ALTER TABLE ... ENABLE ROW LEVEL SECURITY` and
  `ALTER TABLE ... FORCE ROW LEVEL SECURITY`.
- Tests must prove direct `SET knudg.claims.tenant_id`, direct `SET` of any
  claim-like custom setting, missing claims, malformed claims, expired claims,
  cross-tenant reads, and cross-tenant writes fail closed because policies
  ignore raw custom settings and use only `knudg_current_claims()`.

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
- direct `SET knudg.claims.*` spoofing cannot change the tenant, namespace,
  principal, role, or break-glass context used by policies
- membership, namespace grant, principal, and worker revocation or expiry after
  claims are set causes later statements in the same backend to fail closed
  unless a fresh signed context is installed
- lookup tables contain the required seeded keys
- expired tenant memberships and namespace grants can be replaced only after
  `effective_until` is materialized, while authorization fails at expiry even
  if materialization is delayed
- invalid lifecycle transition fails
- direct `card_events` insert by application roles fails
- valid lifecycle transition appends exactly one event
- `rejected -> revoked` is allowed for discard finalization, and a rejected
  candidate cannot remain searchable through private projections after discard
  undo expires
- `current_version_id` cannot reference another card's version
- `card_versions` update and delete fail at the database layer
- `payload_json` cannot contain projection-owned fields or omit minimum schema keys
- public publication cannot create two active public approvals for one card version
- approval challenge concurrent double-submit creates one consent row, marks
  the challenge used once, and rejects replay or cross-artifact reuse
- public publication approval rejects any `expires_at`; expiry is allowed only
  for non-public scopes defined as time-limited consent
- `consent_records.scope`, `consent_records.artifact_type`, and
  `card_edges.edge_type` reject unknown, inactive, and retired lookup values
- `current_version_id` is the only current-version pointer; no current partial index exists
- non-card revocation creates a `domain_events` row and tombstones without a
  synthetic `card_events` row
- card events persist required payload facts and payload digests for approval,
  rejection/deferral, indexing, supersession/deprecation, dispute, and
  revocation operations
- revocation tombstones for one operation share epoch, event ID, and actor
- revocation epoch allocation is monotonic per tenant
- global `event_stream_position` is monotonic across card and domain events,
  and search index manifests cannot claim freshness from per-card `event_seq`
- revocation from pre-publication states blocks card lookup, approval artifact
  lookup, reviewer/admin views, queue payload expansion, cache metadata
  revalidation, and any milestone-enabled source, derived, or index manifest
  read path
- revocation tombstones reject mismatched generic `subject_id` and typed
  subject columns
- `quality_state = verified` fails without an active verification record for
  the current card version
- lookup rows cannot be used for new writes after `retired_at`, while
  historical event replay for a previously valid schema version still succeeds
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

## M0.0 DDL Appendix

Repository migration `migrations/0001_m0_schema.up.sql` is the accepted M0.0
DDL expansion for RFC 0001. Its rollback pair is
`migrations/0001_m0_schema.down.sql`; the repo-owned runner is
`scripts/migrate.py`.

DEC-019 local default: M0.0 uses local-development HS256 request contexts
verified inside Postgres through `pgcrypto` in schema `knudg_crypto`. This is a
conservative local default only. Application roles cannot read
`claim_signing_keys` and cannot execute generic HMAC/digest helpers directly.
The verifier uses fixed security-definer search paths and active `kid` windows.
Any environment that stores protected, non-synthetic, private/team, staging,
production, or public data must use asymmetric verification or external
KMS/Vault verification as the first protected-data verifier profile.
Production/team/public custody remains blocked until an accepted follow-up
chooses that verifier and its key-custody tests.

Implementation compatibility boundary: application code must depend on an
abstract request-context verifier contract, not on HS256, `pgcrypto`, or the
physical `claim_signing_keys` table. Before M1 code that handles private/team or
protected data, tests must include an asymmetric/KMS-style verifier double and
prove the request-context interface can swap verification backends without
changing RLS policy call sites. M1 non-synthetic private/team code, shared dev,
CI with protected fixtures, staging-with-real-data, production, and public
environments must not use the local HS256 verifier, even temporarily. The
follow-up verifier decision must include a removal criterion for local HS256
from non-local configuration, migration-time environment assertions, and CI
checks that fail if local HS256 is enabled outside the local development
profile.

Local development Postgres is provided by `docker-compose.yml`. Migrations are
ordered SQL files in `migrations/`, record checksums in `schema_migrations`,
support `up` and `down`, and accept `DATABASE_URL` for existing local Postgres
instances.

The M0.0 contract tests live in `tests/test_m0_schema.py` and cover empty
apply, re-apply no-op, rollback, core constraints, event cursor bijection, RLS
claim spoof denial, lifecycle transitions, revocation tombstones, consent
challenge binding, and idempotency conflicts.
