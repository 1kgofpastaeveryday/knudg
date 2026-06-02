# Implementation Readiness

This document turns review findings into blocking implementation requirements. If an item is marked "MVP blocker", implementation should not proceed past the named milestone without it.

## Priority Reset

Implementation priority is now the Greencloud closed-launch private backend
before broader production/shared hardening. The next useful Knudg milestone is
not a broader consent, queue, vector, public, or enterprise surface. It is a
narrow operator-private backend loop:

```text
explicit structured card -> closed-launch backend -> later task-profile search ->
retrieval-panel suggestion -> revoke/purge or approval-required candidate
```

This path is allowed to precede the product
`non_synthetic_body_persistence_gate` only because it remains a closed-launch
operator path with bounded structured input, no background session capture, no
raw transcript/log/source ingestion, no team sharing, no public publication,
and no trusted consent completion. The current implementation still uses
`source_class = local_private_dogfood` for this constrained path; that name is
historical and should be revisited in a separate migration/design pass rather
than renamed during cleanup.

The production gates below still apply before product-path non-synthetic
private/team/public processing. They must not block the closed-launch private
loop, and the closed-launch loop must not be described as production-ready,
team-ready, or publication-ready.

Documentation authority: architecture invariants and implementation-readiness
gates are normative. Backlog task files define executable slices. Roadmaps are
ordering/index views and do not override gate definitions. README text is
positioning and navigation. `backlog/backend-roadmap.md` is now the active
ordering view for Greencloud closed-launch cleanup and follow-through.

## Closed-Launch Private Contract

`local_private_dogfood` is currently a constrained `source_class`, not a lane,
status, visibility mode, queue, or publication state. Closed-launch cards also
carry:

- `visibility = local_private`
- `sharing_state = not_shared`
- `publication_state = never_publishable`
- lifecycle states for captured, revoked, and purged

Terminology:

| Term | Meaning | Persistence gate |
|---|---|---|
| Local-private card | operator-authored closed-launch card with `source_class = local_private_dogfood` | this closed-launch contract only; no promotion |
| Product-path private candidate | non-synthetic candidate from product intake | `non_synthetic_body_persistence_gate` plus intake/consent gates |
| Retained private card | approved private retained experience | private retention consent and durability gates |
| Team-shared card | private card shared to a team namespace | team namespace grant/consent gates |
| Public card | exact redacted artifact approved for publication | public publication consent and public gates |

There is no automatic transition from local-private card to product candidate,
retained private card, team-shared card, or public card. A future user-facing migration
would require re-authoring a new redacted artifact with a new digest and the
normal consent flow.

Legacy local DB command contract:

- `knudgctl local capture --input <local-private-card-v0.json>`
- `knudgctl local search --task-profile <task-profile-v0.json>`
- `knudgctl local revoke --card-id <opaque-id> --reason <reason>`
- `knudgctl local purge --card-id <opaque-id> --reason <reason>`
- `knudgctl local preflight-db`
- `knudgctl local verify-fences`
- `knudgctl local audit-boundary`

These local DB commands are support machinery for backend primitive tests. The
preferred operator path is the closed-launch API and live `knudgctl`
profile/search/nudge/write-candidate path. Do not add new local-only dogfood
commands without a new accepted design.

Command output contract:

- stdout is one JSON object and never contains submitted body text
- stderr is diagnostic-only and never contains submitted body text
- success exits `0`; validation rejection exits `2`; local DB/preflight failure
  exits `3`; fence or non-promotion verification failure exits `4`
- response envelopes use bounded `status` values:
  `captured`, `no_suggestion`, `revoked`, `purged`, `rejected`,
  `preflight_failed`, `fence_failed`
- rejection responses include `reject_class` only, not rejected content

The capture input is a positive allowlist schema, not a raw text box. The
`local-private-card-v0` fields are:

- `source_class`: exactly `local_private_dogfood`
- `title`: 8-120 chars
- `human_summary`: human-facing viewer copy stored with the card body and not
  used for agent retrieval; contains:
  - `content`: 20-240 chars, concise main viewer text
  - `redaction_summary`: 20-240 chars, removed classes such as paths,
    hostnames, usernames, repository names, env values, and logs
- `problem_summary`: 20-600 chars
- `solution_summary`: 20-900 chars
- `public_packages`: up to 8 package/tool names, 1-80 chars each
- `environment_tags`: up to 12 coarse tags, 1-40 chars each
- `public_reference_urls`: up to 3 HTTPS URLs with public hosts only
- `command_labels`: up to 6 non-executable labels, 1-80 chars each
- `error_fingerprints`: up to 6 normalized fingerprints, 1-120 chars each
- `lessons`: up to 6 short bullets, 1-200 chars each

Canonicalization order is Unicode NFC, control-character removal, whitespace
folding, URL/path/hostname detection, field concatenation for cross-field
checks, secret/entropy scanning, command-line grammar rejection, then final
schema validation. It must reject secrets, tokens, raw command output,
executable command lines, raw stack traces, private paths, private hostnames,
arbitrary file excerpts, raw transcripts, and content that reconstructs those
values across fields after canonicalization. Command labels are nouns such as
`pytest test run` or `npm dependency install failure`; shell-ready strings,
arguments, flags, pipes, redirects, and destructive verbs with targets are
rejected.

Storage contract:

- local DB means local Postgres for P0
- writes use existing `experience_cards`, `card_versions`, `card_events`, and
  `revocation_tombstones` for opaque identity, digest, lifecycle, and fence
  metadata only
- purgeable local-private body/search text lives outside append-only canonical
  rows in P0-only local tables described below
- `source_class = local_private_dogfood` is immutable after insert
- append-only events may contain opaque IDs, digests, lifecycle transitions,
  and verification metadata only; local-private body/search text must not be
  written into append-only events, job payloads, or replay artifacts
- local cards cannot create publication consent rows, team namespace grants,
  hosted sync state, embeddings, product queue jobs, export artifacts,
  production projection rows, or public/team/admin review records
- local Postgres absence is not a use-ready pass; DB-backed readiness requires
  a non-skipped Postgres integration run
- local commands must bind an explicit local profile, workspace ID,
  tenant/namespace, and local principal; every DB access sets the corresponding
  RLS/session claims and fails closed if the local profile or workspace binding
  cannot be proven
- if any loopback HTTP surface is added for local private search, it must bind
  only to `127.0.0.1`/`::1`, reject remote hosts and hosted profiles, avoid
  credentialed browser CORS, and re-check the same local profile/workspace/RLS
  claims as the CLI
- a UR-BE-000 DDL appendix must name target tables, column names/types,
  nullability, lookup rows, CHECK/FK/trigger/RLS rules, immutable-source
  constraints, non-promotion constraints, tombstone rows, FTS/projection rows,
  and negative DB constraint tests before code starts
- local-private hard fences must deny any downstream row that references a
  local-private card/version in publication consent, namespace grants,
  embeddings, exports, product queues, hosted sync, review/admin records, or
  production projections

P0 DDL appendix:

- `experience_cards`
  - existing columns used: `tenant_id`, `id`, `namespace_id`,
    `current_version_id`, `status`, `outcome_type`, `quality_state`,
    `evidence_strength`, `created_by`, `created_at`, `updated_at`
  - P0 allowed statuses: `approved_private`, `revoked`
  - P0 source class is stored in `card_versions.payload_json.source_class`
    and enforced immutable by the local capture/update functions
- `card_versions`
  - existing columns used: `tenant_id`, `id`, `card_id`, `version_number`,
    `payload_json`, `payload_digest`, `created_by`, `created_at`
  - P0 `payload_json` stores only bounded metadata, digest inputs, source
    class, local visibility/sharing/publication states, and no body text
  - `payload_json.source_class` must equal `local_private_dogfood`
  - `payload_json.visibility` must equal `local_private`
  - `payload_json.sharing_state` must equal `not_shared`
  - `payload_json.publication_state` must equal `never_publishable`
- `card_events`
  - event payloads contain opaque IDs, prior/next lifecycle states,
    idempotency keys, fence verification metadata, and no body/search text
- `revocation_tombstones`
  - existing card/card_version tombstones are used for `revoke`
  - purge keeps a minimal opaque card/card_version tombstone to prevent stale
    resurrection
- `local_private_card_bodies`
  - columns: `tenant_id uuid`, `card_id uuid`, `card_version_id uuid`,
    `body_json jsonb`, `body_digest text`, `created_by uuid`, `created_at
    timestamptz`, `purged_at timestamptz null`, primary key
    `(tenant_id, card_id, card_version_id)`
  - FKs: `(tenant_id, card_id)` to `experience_cards`, `(tenant_id, card_id,
    card_version_id)` to `card_versions`
  - CHECK: `body_json` matches `local-private-card-v0` body fields and contains
    no forbidden canary values
  - purge sets `purged_at` and deletes or cryptographically shreds `body_json`
    according to the local implementation choice; the verification query must
    prove no readable body remains
- `local_private_search_documents`
  - columns: `tenant_id uuid`, `card_id uuid`, `card_version_id uuid`,
    `search_text text`, `search_vector tsvector`, `rank_manifest_version text`,
    `created_at timestamptz`, `revoked_at timestamptz null`,
    `purged_at timestamptz null`
  - no append-only semantics; revoke/purge may update or delete rows
  - CHECK: `rank_manifest_version = 'local_private_fts_v0'`
- `local_private_value_events`
  - columns: `tenant_id uuid`, `workspace_id text`, `event_name text`,
    `card_id uuid null`, `card_version_id uuid null`, `created_at timestamptz`,
    `event_json jsonb`
  - allowed `event_name`: `capture_attempt`, `capture_rejected`,
    `search_completed`, `suggestion_shown`, `suggestion_accepted`,
    `suggestion_ignored`, `revoke_completed`, `purge_completed`,
    `leakage_check_completed`
  - `event_json` contains aggregate/local-only counters and no raw query,
    body, path, hostname, command, or error text

Non-promotion DB tests must try and fail to reference a local-private
card/version from `consent_records`, `approval_handoffs`, `jobs`,
`outbox_events`, future embedding/export/projection tables when present, and
any protected/public search projection table added later. If a table does not
exist yet, `local audit-boundary` records it as `not_present`, not `passed`.

Deletion contract:

- `revoke` state machine: `requested -> fenced -> projections_removed ->
  verified -> complete`
- `purge` state machine: `requested -> fenced -> body_removed ->
  projections_removed -> artifacts_removed -> verified -> complete`
- every state transition is idempotent and uses a retry key
- any nonterminal revoke/purge state forces local search and handoff open to
  `no_suggestion`
- `revoke` writes a local tombstone/read fence, keeps the minimum opaque audit
  metadata, removes the card from local search results, and is idempotent
- `purge` removes local body/search text, local FTS/projection rows, temporary
  corpus artifacts, local cache entries, queue payloads, sidecar/vault
  artifacts, and generated dumps used by the test harness while retaining only
  the minimum opaque tombstone needed to prevent stale resurrection
- search after either operation must return `no_suggestion` for the card
- `local verify-fences` must prove post-revoke/post-purge search miss,
  handoff invalidation, FTS row removal, cache/artifact cleanup,
  rebuild/replay miss, and no stale resurrection after restart

Retrieval contract:

- local search returns retrieval-panel metadata only
- allowed panel fields are opaque card/version IDs, digest, local-only status,
  outcome type, freshness bucket, coarse match reason, and an "open local card"
  handoff reference
- panel metadata must not include source paths, hostnames, executable command
  text, raw error strings, private repo/tooling fingerprints, or card bodies
- local exact/FTS must define indexed fields, exact-match fields, top-k,
  ranking, abstention threshold, and `no_suggestion` behavior before being
  declared useful
- P0 local FTS uses `to_tsvector('english', ...)` over title, summaries,
  package/tool names, environment tags, command labels, error fingerprints, and
  lessons; exact matches cover package/tool names and error fingerprints;
  ranking uses weighted `ts_rank_cd` plus exact-match boost; default top-k is
  3; ties sort by newest captured time then opaque ID; below-threshold results
  return `no_suggestion`
- the local ranking/index contract is versioned and must be recorded with the
  local value evidence so production search does not silently inherit it

P0 no-log rule:

- rejected or accepted local-private body content must not appear in stdout,
  stderr, structured logs, traces, test snapshots, DB notices, queue payloads,
  or error messages
- canary tests also inspect Postgres statement logging configuration,
  `pg_stat_activity` during execution, notices/exceptions, FTS materialization,
  test dump/restore artifacts, migration failure output, and local telemetry
- negative tests use canary strings and verify generated FTS/search text as
  well as the submitted JSON

P0 value evidence:

- record local counters for capture attempts, rejection classes, search
  latency, suggestions shown, suggestions accepted/ignored, abstentions,
  stale/harmful suggestions, revoke success, purge success, and post-purge
  leakage checks
- counters are local-only aggregate telemetry; they do not include raw query
  text, card bodies, private identifiers, or exportable per-card analytics
- the P0 exit record must include repeated-task sample count, useful/ignored
  suggestion counts, stale/harmful suggestion count, operator friction notes,
  and a production-readiness non-regression checklist
- local value evidence can unlock the next production planning pass, but never
  opens protected ingestion, team sharing, hosted sync, or public publication
  by itself

## Milestones

| Milestone | Scope | Must ship | Explicitly out |
|---|---|---|---|
| P0 | Closed-launch private backend loop | explicit structured card submission through the closed-launch backend, bounded local-private source class, exact/FTS search contract, retrieval-panel metadata, revoke, purge, approval-required write candidate preview, no raw transcript/file ingestion, no team/public sharing, no-log canary tests, non-promotion tests | production auth, trusted consent UI, hosted/team/public corpus, vector/rerank |
| M0 | Trust/data kernel | accepted RFC 0001 plus M0 DDL appendix/SQL migration with exact types, nullability, constraints, FKs, triggers, grants, and negative tests; tenant/RLS policy, card events, tombstones, idempotency keys | vector search, public corpus |
| M1 | Private writer queue | accepted WEDGE-001 RFC with measured gate values, manual seed-corpus protocol, private prospect registry references, selected baseline systems, useful visible summary-rate gate, reviewer supply plan, Postgres-backed jobs, admission, redaction draft, `private_candidate_collection` consent/acknowledgement, opt-out, discard/purge path, private candidates, and the `non_synthetic_body_persistence_gate` before any non-synthetic private candidate is stored | public indexing, curated packs |
| M2 | Consent and revocation | managed Postgres HA/PITR external exposure gate, approval challenge, consent matrix, revoke cockpit, tombstone read fence, public publication consent, team namespace sharing consent/grant checks, subject-level consent revocation | commercial derived use |
| M3 | Exact and FTS retrieval | authorized exact/FTS search, internal harness with canonical request/response/auth/abstention/trust-label/revocation semantics, retrieval panel only, no body cache, numeric SLOs, trace/log correlation, backup/PITR drill | pgvector, inline hints |
| M4 | pgvector hybrid | vector table, HNSW parameters, index manifests, rollback runbook, scoped vector circuit | paid rerank |
| M5 | Agent access | MCP/CLI contract, delegated tokens, hooks, search response contract | broad third-party integrations |
| M6 | Public wedge pilot | quotas, review capacity, quality gates, cost circuits | general public contributor marketplace |

M3 may use an internal CLI/API harness to test exact/FTS retrieval-panel delivery. Any harness touching non-synthetic protected data must use the DEC-014A internal protected-data sender-constrained proof profile, nonce replay store, audience binding, and denial tests. Otherwise it is restricted to synthetic/public fixtures. Full external MCP/hooks support remains M5 scope and uses DEC-014B.

Agent-facing role orchestration may run before full external MCP/hooks through
the live closed-launch backend path. In that mode the main agent builds a
sanitized task profile, receives compact search/nudge/write-candidate signals,
and treats those signals as advisory. Summoned roles are client orchestration,
not a new authority boundary: they must obey the same protected-data gates,
no-log ingress rules, consent rules, retrieval-panel delivery rules, and
`no_suggestion` fallback as the underlying operation. The historical local role
wrapper implementation has been removed; `docs/architecture/summoned-roles.md`
is product design, not active runtime guidance.

M6 is blocked until wedge privacy validation proves that public search enforces
private distinct-tenant and cohort-size thresholds, normalized timing/reasons,
privacy budgets, and rare-query generic abstention. The validation corpus must
include rare fingerprint probes and hostile command/package/repo/credential-bearing
cards; unverified high-risk cards must remain hidden from retrieval-panel and
inline output.

M0 is intentionally a heavy trust/data kernel, not a thin schema stub. Implement it in this order:

1. M0.0: DDL appendix/SQL migration expansion of RFC 0001 with exact PostgreSQL column types, nullability, PK/UNIQUE/CHECK/FK constraints, FK actions, deferrability, trigger names, grants, RLS policy skeletons, partial-index predicates, and negative tests. No M0 code path may implement tables from prose alone.
2. M0.1: lookup tables, tenant/namespace/principal tables, migrations, and canonical JSON/digest fixtures.
3. M0.2: card identity, versions, append-only events, global event-position ledger, idempotency, and lifecycle transition enforcement.
4. M0.3: RLS claim setter/getter, tenant isolation policies, membership/grant checks, and adversarial RLS tests.
5. M0.4: consent records, consent termination, revocation tombstones, revocation epoch, and public/private approval invariants.
6. M0.5: break-glass, verification records, audit hardening, and migration rollback drills.

Each step must be internally testable before the next begins; the milestone remains M0, but implementation planning should not treat it as a single undifferentiated task.

## MVP Defaults

These are internal provisional defaults, not public-facing publication
material. Public architecture pages, landing pages, READMEs used as public
entrypoints, and status pages must not publish exact launch-control values,
abuse budgets, rate-limit budgets, probe thresholds, or timing thresholds unless
a separate security/privacy review marks a redacted value public-safe. A wedge
RFC can change internal defaults only with measured evidence.

- local card body cache: disabled
- queue: Postgres-backed queue
- object storage: S3-compatible interface, provider pinned in deployment RFC before first raw/source artifact storage
- public card candidate quota: disabled until public-pilot gates pass; exact
  quota is private operator configuration
- anonymous public search: disabled until M6/DEC-013 acceptance; exact
  post-launch public rate limits are private operator configuration
- rerank: disabled for free anonymous users
- raw/source retention max TTL: short and private-deployment configured; no
  indefinite raw/source retention
- approval challenge TTL: short-lived and private-deployment configured
- write-capable delegated token TTL: short-lived and private-deployment
  configured
- read-only delegated token TTL: short-lived and private-deployment configured
- global retrieval budget: bounded by private operations configuration
- exact/FTS fallback budget: bounded by private operations configuration
- rerank budget: bounded by private operations configuration

M1 storage boundary: private candidate metadata and redacted draft bodies may
live in Postgres only after the M1 protected-data durability gate passes. Raw
or source artifacts remain disabled until M2 or a deployment RFC pins object
storage, encryption, purge, and signed access.

M1 collection transport boundary:

- M1 uses an internal web console or internal HTTPS harness plus optional local
  CLI wrapper for `private_candidate_collection` consent/acknowledgement.
- External MCP, hooks, and production delegated-agent access remain M5 and must
  not be required for M1 acknowledgement.
- Any M1 local CLI wrapper is not the external MCP/CLI product surface; it
  records acknowledgement only for single-workspace private validation and cannot
  create public publication consent.

M1 protected-data durability gate:

- synthetic fixtures may run before this gate; non-synthetic private candidate
  metadata and redacted draft bodies may not
- `local_private_dogfood` structured cards are the closed-launch P0 exception:
  they may be stored before this gate only when created by explicit
  operator-bounded submission, marked non-shared, excluded from
  team/public/hosted/product projections, covered by no-log canary tests, and
  revoke/purge capable
- encrypted backup and WAL archiving are configured for the deployment profile
- the deployment RFC pins concrete Postgres provider/topology, region, PITR
  command path, WAL verification, restore drill transcript, failover/cutover
  proof, client reconnect behavior, and connection-pool settings
- a restore rehearsal proves the cluster starts quarantined, replays
  revocation tombstones, consent expiry, discard/purge effects, and
  idempotency effects before serving
- acknowledged safety effects, including revocation, approval withdrawal,
  discard, purge, and idempotent write completion, use synchronous commit
  before success is returned
- RB-007 has at least the M1 drill commands, owner, verification query, and
  reconciliation checklist

## Postgres and Migration Requirements

MVP DDL RFC must define:

- table columns and nullability
- `(tenant_id, id)` primary or unique keys for tenant-scoped tables
- composite foreign keys that include `tenant_id`
- current version enforced only by `experience_cards.current_version_id`; M0 must reject `card_versions.is_current` and any current-version partial unique index unless a future accepted RFC changes the single-pointer rule
- partial unique index for one active public approval per card version
- `card_events(tenant_id, card_id, event_seq)` unique
- `card_edges(tenant_id, source_card_version_id, edge_type, target_card_version_id)` unique
- any current-card edge uniqueness must be a derived projection constraint, not the canonical `card_edges` constraint
- self-edge prohibition
- JSONB validation policy
- outcome/status/quality compatibility checks
- source artifact TTL and encryption columns in the future storage RFC; M0 placeholder tables must not define real raw/source storage behavior unless required by a concrete M0 foreign key
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

Postgres operational requirements before M1 stores non-synthetic private
candidates or before M2 external consent/revocation exposure:

- automated base backup at least daily
- continuous WAL archiving with monitored lag
- restore test at least weekly and before release promotion
- documented PITR command path and target-time selection
- RTO targets for exact/FTS search restoration and protected writes are private
  operations configuration
- General RPO target for non-safety queue state and replayable events is private
  operations configuration.
  Acknowledged revocations, approvals, and idempotency effects require
  synchronous commit before success is returned. External append-only safety
  journals are out of scope for MVP unless a future accepted RFC defines the
  provider, schema, ordering cursor, replay, monitoring, and failover drills.
  If failover/PITR cannot prove completeness through the last
  acknowledged safety effect, affected tenants/namespaces must be quarantined
  to `no_suggestion` reads and protected writes disabled until reconciliation
  proves the fence complete.
- failover only to a replica within RPO and with revocation/event fences verified
- corruption recovery path that rebuilds exact/FTS projections from canonical rows and `card_events`

M3 exact/FTS retrieval additionally requires search-specific restore probes and
index rebuild drills using the same HA/PITR foundation.

## Event Ordering

`card_events` must include:

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

Projection updates use optimistic concurrency: update only when the current version or event sequence matches the expected value. Conflicts create retryable errors, not silent overwrites.

`event_seq` is per card and cannot be used as a global replay cursor. Every
projection-driving `card_events` and `domain_events` row must also receive a
strictly increasing `event_stream_position` allocated in the same transaction
as the event. Index manifests, outbox reconciliation, and runbooks use
inclusive `event_stream_position` ranges and replay hashes over both card and
domain events.

## Revocation Fence

Revocation is independent of lifecycle status. Every read path checks tombstones before returning a card, artifact, search result, cache entry, derived artifact, or raw/source object.

Required fields:

- `card_revocation_event_id` or `domain_revocation_event_id`
- `tenant_id`
- `subject_type`
- `subject_id`
- `card_id`, nullable except for card, card-version, source-artifact, and derived-artifact revocations that are card-derived
- `card_version_id`, nullable except for exact card-version revocation
- `reason`
- `revoked_by`
- `created_at`
- `revocation_epoch`

Authenticated tenant-bound search responses include scoped `revocation_epoch`.
Public or anonymous search responses must not expose raw revocation epochs,
index generations, or freshness counters tied to private or tenant activity.
Clients must reject cached protected data when the server epoch is newer or
unavailable.

## Queue Contract

MVP uses a Postgres-backed queue with:

- at-least-once delivery
- no ordering guarantee across different logical objects
- per-logical-object idempotency keys
- visibility timeout: private operations configuration
- lease renewal: private operations configuration
- max attempts: private operations configuration
- backoff: exponential with jitter
- DLQ retention: private operations configuration
- redrive requires operator action and reason
- poison jobs keep original payload digest and error history
- jobs and DLQ rows store object IDs, digests, schema version, lane, and
  routing metadata by default; they must not store raw/source bodies,
  unpublished redaction text, full card bodies, stack traces, secrets, private
  paths, or customer data. If a body payload is unavoidable, a queue RFC must
  require envelope encryption, short TTL, redacted operator views,
  revocation-triggered purge, and tests proving `queue peek` cannot expose it.

Allowed `jobs.status` values are `ready`, `leased`, `succeeded`, `dead`, and
`cancelled`. DLQ is represented by `jobs.status = 'dead'` plus immutable
`job_attempts` history; there is no separate `dead_letter_jobs` table in M1.

Core tables:

- `jobs`
- `job_attempts`
- `idempotency_keys`
- `outbox_events`

M1 queue implementation uses this contract unless an accepted queue RFC
supersedes it before code starts:

- `jobs`: `tenant_id`, `id`, `outbox_event_id`, `lane`, `logical_object_type`,
  `logical_object_id`, `payload_digest`, `payload_json`, `status`, `priority`,
  `available_at`, `lease_owner`, `lease_token`, `lease_expires_at`,
  `attempt_count`, `max_attempts`, `created_at`, `updated_at`
- `job_attempts`: `tenant_id`, `job_id`, `attempt_no`, `worker_id`,
  `lease_token`, `started_at`, `finished_at`, `result`, `error_class`,
  `sanitized_error`
- `outbox_events`: `tenant_id`, `id`, `source_event_type`,
  `source_card_event_id`, `source_domain_event_id`,
  `event_stream_position`, `lane`, `logical_object_type`,
  `logical_object_id`, `payload_digest`, `payload_class`, `payload_json`,
  `created_at`, `published_at`
- event append and outbox insert happen in the same transaction
- `source_event_type` is bounded to `card` or `domain`; exactly one of
  `source_card_event_id` or `source_domain_event_id` is present, the populated
  column must match `source_event_type`, and `event_stream_position` must match
  the referenced event row
- `outbox_events` has a unique source-work key:
  `(tenant_id, source_event_type, coalesce(source_card_event_id,
  source_domain_event_id), lane, logical_object_type, logical_object_id)`.
  If SQL expression uniqueness is avoided, the migration must materialize a
  non-null `source_event_id` generated from the populated source column and
  make that generated column part of the unique key.
- `jobs.outbox_event_id` references `outbox_events(tenant_id, id)` and active
  jobs are unique by `(tenant_id, outbox_event_id)` while status is `ready` or
  `leased`. Reconciliation must return the existing job for the same outbox
  row instead of creating duplicate active work.
- workers claim jobs with `FOR UPDATE SKIP LOCKED`, set a new `lease_token`,
  increment `attempt_count`, and can only complete the job while holding that
  token
- lease renewal is capped by private operations configuration; expired leases
  can be reclaimed
- failed jobs move to DLQ after `max_attempts`, preserving payload digest and
  sanitized error history
- redrive requires operator identity, reason, and audit event
- lane indexes cover `(lane, status, priority, available_at)`,
  `(status, lease_expires_at)`, `(lane, status, created_at)`, and
  `(tenant_id, logical_object_type, logical_object_id, status)`
- `payload_class` is a bounded discriminator per lane. M1 allows only
  metadata-only payloads under the configured size limit; body-bearing payloads
  require a later queue RFC with encryption, TTL, and redacted operator views.
- reconciliation scans `card_events`, `domain_events`, and `outbox_events` by
  `event_stream_position` to recreate missing queue work idempotently
- queue DDL must define tenant-scoped PKs, bounded status/lane values, FKs from
  `job_attempts` to `jobs`, unique `(tenant_id, job_id, attempt_no)`,
  lease-token-held completion checks, outbox exactly-one source-event CHECK,
  composite references to `(tenant_id, event_id, event_stream_position)` on the
  matching card or domain event, the outbox source-work unique key, the
  `jobs.outbox_event_id` FK, active-job uniqueness per outbox row, idempotency
  unique indexes, and lane indexes whose leading columns match claim queries

Workers are not allowed to define correctness. Correctness comes from constraints, event sequence, idempotency, and reconciliation.

Safety-critical queue lanes are isolated. `revocation`, `approval_publish`, `consent`, `tombstone`, and `event_projection` must have reserved workers, DB connections, alerts, and redrive controls that cannot be exhausted by embedding, rerank, analytics, public candidate ingestion, or dedupe work.

Initial local minimums before M1 code starts: reserve worker and database
capacity for each safety-critical lane, cap best-effort lane consumption by
private operations configuration, and shed public candidate ingestion before
safety-critical queue age exceeds the private safety threshold.
Before M2, approval, consent, revocation, and tombstone paths must add
per-route max in-flight limits, DB pool reservations, hot-spot shedding, and
admission pause rules. Deployment-specific sizing may raise these numbers but
cannot remove the reservation. Release drills must load-test to failure and
prove best-effort lanes cannot consume safety lane leases, worker slots, DB
connections, or redrive quota.

Default M1/M2 local overload budgets until a deployment RFC replaces them are
private operator configuration, not public-facing material. They must reserve
safety-lane worker and DB capacity, cap shared best-effort consumption, pause
tenant/public candidate admission under safety-lane pressure, and cap DLQ
redrive unless an incident commander raises it after a dry-run impact summary.

## Cost Circuits

Budget controls are active controls, not only telemetry.

Initial circuits:

- disable rerank when the private daily rerank budget threshold is reached
- pause embedding jobs when the private daily embedding budget threshold is
  reached
- throttle tenant submissions when review backlog exceeds capacity
- stop anonymous search when anonymous spend exceeds daily budget
- force exact/FTS only when vector latency exceeds circuit threshold
- pause public candidate admission under duplicate flood

Every circuit needs an audit event and an operator override path.

Circuits must be scoped before they are global. Valid scopes are dependency, tenant, namespace, route, queue lane, and feature. Global circuits require incident commander approval unless the risk is auth bypass, revocation failure, corruption, or unsafe data serving.

Circuit contract:

| Circuit | Scope | State machine | Trip signal source | Fallback | Owner |
|---|---|---|---|---|---|
| auth/revocation fence | tenant, namespace, route | closed, open, half-open | private operations thresholds and freshness probes | fail closed; no body, no protected write | security/privacy owner |
| queue admission | queue lane, tenant | closed, open, half-open | backlog, retry, DLQ, and reviewer-capacity thresholds | reject or defer admission with idempotent status | queue owner |
| search dependency | dependency, index generation, namespace | closed, open, half-open | latency, error, freshness, and restore probes | exact/FTS fallback or `no_suggestion` | retrieval owner |
| vector/rerank/budget | dependency, tenant, feature | closed, open, half-open | private cost and latency thresholds | disable vector/rerank; preserve exact/FTS where safe | cost owner |
| public landing route | route | closed or withdrawn | RB-LP-001 probes and signoff freshness | remove active links; 404/410/pending without forms or analytics | LP operator |

Half-open probes are synthetic or operator-authorized only. A circuit cannot
move from open to closed until the owner records probe evidence, affected
tenant/namespace scope, cache invalidation needs, and the audit event.

## MVP Operations Readiness

MVP runbooks are blocking implementation artifacts, not placeholders. The first concrete skeletons live in `docs/architecture/operations.md` and must be implemented as executable dashboards, alerts, commands, and operator docs before the milestone that exposes the path.
`docs/architecture/operations.md` is part of the normative launch-review bundle
for any milestone that depends on runbooks, probes, alert thresholds, or
first-five-minute operator actions; implementation plans must not review
`implementation-readiness.md` alone for operations clearance.

Required runbooks:

- `RB-LP-001` public landing degradation/publication-gate incident: blocker
  before any public landing URL, including a static information-only prototype.
  It covers direct-route checks for `/architecture` and forbidden product
  routes, static-host rollback, CDN/static cache purge, inert-control synthetic
  checks, accessibility regression response, monitored security/privacy contact,
  and stale public-document withdrawal.
- `RB-LP-001` must name the static host and include its routing/header artifact
  (`_headers`, `_redirects`, Pages/Workers config, nginx config, or
  equivalent), no-SPA-fallback rule, route denylist probes, expected HTTP
  statuses, sitemap/noindex behavior, cache purge command, and analytics/form
  absence checks. The local `site/index.html` prototype alone does not satisfy
  public URL readiness.
- `RB-001` search latency spike: M3 blocker.
- `RB-002` index freshness breach: M4 blocker.
- `RB-003` queue backlog or DLQ growth: M1 blocker.
- `RB-004` emergency card revocation: M2 blocker.
- `RB-005` failed migration or index cutover: M0 for schema rollback discipline, M4 for index cutover.
- `RB-006` backend dependency outage: M3 blocker.
- `RB-007` Postgres backup, restore, failover, or corruption event: M1 blocker
  for non-synthetic private candidate storage, M2 blocker for external
  consent/revocation, M3 blocker for retrieval restore drills.
- `RB-008` consent and revocation UX degradation: M2 blocker.

Each required runbook must include actionable first 5 minutes, metrics, diagnostic queries, commands, kill switches, verification, reconciliation, and owner. A template alone does not satisfy readiness.

Deployment readiness is also an MVP contract. Services must expose distinct startup/liveness/readiness behavior with the probe thresholds in `docs/architecture/operations.md`, and readiness must fail closed for auth, revocation, migration compatibility, and unknown active index generation. Alerting must use the taxonomy in `docs/architecture/operations.md` and every paging alert must link exactly one `RB-*` runbook.

M3 release gates:

- exact/FTS availability, latency, timeout, stale-serve, queue-age, and DLQ alerts use the numeric thresholds in `docs/architecture/operations.md`
- every API request, worker job, operator command, revocation, and index operation emits the required trace/log correlation fields
- failure drills pass for search fallback, auth/revocation uncertainty, queue backlog, DLQ redrive, failed migration rollback, Postgres PITR restore, and backup freshness alerting

Public and high-risk review flow gates:

- public or high-risk review flows are blocked until a review-operations telemetry schema defines queue depth, reviewer capacity, review latency, decision outcomes, reopen/reversal rates, escalation reasons, abuse signals, and audit correlation fields
- reviewer capacity gates must use p90 and p95 review-time budgets by risk band, reviewer staffing assumptions, escalation-pool availability, calibration cadence, emergency revocation reserve, and oldest high-risk item age; median review time alone cannot pass launch
- WEDGE-001 review supply must be documented before M1 private writer queue:
  reviewer roles, qualification rubric, calibration fixtures, compensation or
  staffing source, escalation coverage, high-risk reproduction lab profile,
  max cards per reviewer per week by risk band, and the admission pause rule
  when supply is below forecast demand
- budget circuits and billing gates are blocked until a cost-metering RFC defines billable units, attribution dimensions, sampling/rounding rules, reconciliation, audit events, override handling, and tenant-visible reporting

Launch slices:

| Slice | User value | Required gates | Deferred |
|---|---|---|---|
| Closed-launch private backend loop | preserve and retrieve operator-written structured cards through the Greencloud closed-launch backend | explicit structured card submission, no raw transcript/file ingestion, bounded local-private source class, exact/FTS retrieval-panel metadata, revoke/purge, clear non-shared status, approval-required write candidate preview | production auth, trusted consent UI, hosted/team/public corpus, vector/rerank, billing |
| Single-workspace protected dogfood | preserve and retrieve protected session-derived candidate drafts inside one workspace | WEDGE-001 RFC accepted, seed protocol accepted, `private_candidate_collection` consent/acknowledgement, tenant isolation tests, exact/FTS on private fixtures, and `non_synthetic_body_persistence_gate` before product-path non-synthetic storage | team namespace sharing, public publication, anonymous search, billing |
| Team namespace alpha | team-shared private retrieval over consenting design-partner sessions | review supply plan, private-retention consent, `team_namespace_grant` consent/grant, team sharing comprehension, revocation fence, exact/FTS retrieval panel, cost metering dry run | public corpus expansion, curated packs, inline hints |
| Public pilot | public retrieval over approved WEDGE-001 cards | public privacy attack model, useful visible summary-rate gate, high-risk verification capacity, reviewer QA, abuse budgets, public-card approval/revocation E2E | contributor marketplace, paid rerank, broad third-party integrations |

Budget circuits and paid limits are fail-passive until meter reconciliation
passes. If cost meters are delayed, missing, duplicated, or disagree with audit
events, user-visible throttling and billing enforcement stay disabled, dry-run
alerts fire, and tenant-visible correction records are produced after replay.

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
