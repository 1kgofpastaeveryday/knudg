# Operations

The active agent path must degrade safely. Knudg should never block the main agent from continuing work.

Read-path fallback order:

1. full hybrid retrieval with rerank
2. hybrid retrieval without rerank
3. exact/FTS only
4. cached pointer revalidation when the central service is reachable
5. no suggestion

The local cache fallback cannot serve stale card bodies. MVP forbids local card body caching. It can only reuse card IDs and metadata to revalidate against the central service.
If central authorization, revocation, or freshness checks are unavailable, the
cached pointer path returns `no_suggestion`; it is not an offline retrieval
mode.

## Rollout Controls

Retrieval should not begin as automatic injection. Rollout order:

1. offline replay against labeled tasks
2. shadow retrieval that logs would-have-shown cards
3. explicit retrieval-panel suggestions
4. thin inline hints for one wedge
5. broader public/shared corpus exposure

Every stage needs exit criteria, per-integration kill switches, and a no-suggestion fallback. Harmful suggestion rate, prompt-injection pass rate, user dismissal rate, and time-to-fix improvement are stage gates.

## Public Documentation Publication

Public architecture pages and public README/docs are generated only from a
signed public-doc manifest. Route states are:

- `absent`: no route or public artifact exists
- `draft_internal`: internal source material exists but is not public-safe
- `signed_public`: manifest has owner, reviewer, source digests, allowed
  excerpts, exclusion checks, route binding, review date, stale-review deadline,
  and security/privacy contact
- `withdrawn`: prior public artifact is no longer safe or current and must
  return 410 or a generic pending/withdrawn state

The manifest is the canonical enforcement surface for `/architecture` and any
public docs entrypoint. CI must reject generated public artifacts containing
private threshold values, private runbook command names, raw queue names,
private paths, private operational defaults, or historical review output.

## Public Search Response Equivalence

Public search must make empty index, no authorized match, rare private
fingerprint, redacted result, safety withholding, revoked data, and not-indexed
cases indistinguishable to anonymous callers. The public response uses one
schema, one status family, a normalized body, bounded latency padding or
equivalent timing envelope, and no per-fingerprint `Retry-After`. Black-box
tests compare those cases before any public search launch.

## SLOs and Telemetry

Required SLOs and telemetry:

- query success rate
- p50/p95/p99 retrieval latency
- dependency timeout rate
- circuit-breaker open rate
- index freshness lag
- approval backlog age
- redaction/review backlog age
- admission backlog age
- dedupe/novelty rejection rate
- compaction lag
- stale/deprecated card serve rate
- queue depth and oldest job age
- DLQ count
- cost per query and rerank rate
- cost per submitted candidate
- cost per approved card
- cost per rejected candidate
- cost per reindex and re-embedding batch
- cost per revocation propagation
- review minutes per public card
- free-tier abuse spend

M3 numeric SLOs are private launch-control configuration for exact/FTS
retrieval-panel delivery. Public docs may say that availability, latency,
timeout, freshness, queue-age, and DLQ thresholds exist, but must not publish
the exact values. Internal release artifacts hold the values, owners, page
thresholds, ticket thresholds, and evidence links.

## Provisional Operational Defaults

These are binding private defaults until a wedge RFC replaces them with
measurements. Do not publish exact values in public docs:

- global retrieval deadline: private operations value
- exact/FTS fallback deadline: private operations value
- rerank deadline: private operations value
- dependency timeout: private operations value per downstream call unless lower is required by the global budget
- circuit scope: prefer dependency, tenant, namespace, route, queue lane, or feature-level circuits; global circuits require incident commander approval unless auth, revocation, or corruption risk is active
- circuit open: private per-scope failure, error-rate, and latency thresholds
- half-open: private per-scope probe budget until the owner-defined success threshold passes
- circuit auto-clear: forbidden for auth, revocation, backup/restore, and data-integrity circuits; operator verification is required
- no-suggestion fail-closed: any auth, revocation, freshness, or safety uncertainty
- force exact/FTS only: vector latency over private budget window
- disable rerank: daily rerank budget reaches private threshold
- pause embedding jobs: daily embedding budget reaches private threshold
- after M6/DEC-013 launch gates pass, anonymous search hard cap: private
  per-route public budget; before those gates, anonymous public search is
  disabled
- public candidate cap: private per-tenant daily budget
- raw/source retention maximum TTL: private deployment policy
- local card body cache: disabled
- emergency deny manifest reader max staleness: private operations value; stale, unverifiable,
  or unavailable manifests force protected reads to `no_suggestion`

## Trace and Log Correlation Contract

Every API request, worker job, queue attempt, approval action, index generation, revocation, and operator command must carry:

- `trace_id`
- `span_id`
- `correlation_id`
- `tenant_id`
- `actor_id` or `system_actor`
- `request_id`
- `job_id`, when async work is involved
- `card_id` and `card_version_id`, when card-scoped
- `index_generation`, when search or indexing is involved
- `revocation_epoch`, when protected reads are involved

Logs must be structured JSON and must never contain raw source bodies, secrets, credentials, or unpublished redaction text. Metrics exemplars and audit events must include `trace_id` or `correlation_id` so an incident can follow a user request through search, queue, Postgres, index, and revocation checks.

Observability security model:

- lower-trust logs use pseudonymous tenant, actor, card, and card-version IDs
  or scoped handles instead of raw identifiers
- raw tenant/card identifiers are restricted to assigned operator, reviewer, or
  break-glass views with audit
- log retention, export, and third-party processor use require a private
  deployment policy and cannot inherit public-card consent
- public/support dashboards cannot expose tenant IDs, card IDs,
  revocation epochs, index generations, or per-card activity timelines
- tests must prove redaction and RBAC before production observability launch

## Initial Runbooks

Every paging alert must have a runbook. Initial runbooks:

- `RB-001` search latency spike
- `RB-002` index freshness breach
- `RB-003` queue backlog or DLQ growth
- `RB-004` emergency card revocation
- `RB-005` failed migration or index cutover
- `RB-006` backend dependency outage
- `RB-007` Postgres backup, restore, failover, or corruption event
- `RB-008` consent and revocation UX degradation
- `RB-LP-001` public landing route degradation or publication-gate incident

Runbooks must include symptoms, first 5 minutes, dashboards, diagnostic queries, safe mitigations, kill switches, rollback commands, customer impact, verification, reconciliation, and owner.

MVP runbooks use placeholder command names until the deployment RFC pins concrete service names, namespaces, and dashboards. A blocking runbook is not satisfied by prose: each named command must have a runnable `knudgctl` stub or checked operational script, even if local/dev returns `not configured`, and drills must execute the command path. Every command path must define flags, required operator role, dry-run behavior when a mutation is possible, JSON output schema, stable exit codes, and the audit event it emits. Release drills must attach command transcripts proving the documented path ran.

Every milestone with a blocking runbook must ship a
`runbook_command_manifest` artifact. The manifest lists each command, flags,
operator role, dry-run behavior, mutation guard, stable exit codes, JSON output
schema, emitted audit event, owning runbook, and drill transcript path. A
milestone fails if any referenced command lacks a manifest row, runnable stub
or script, auth check, audit event, and successful drill transcript for the
target deployment profile.

`RB-LP-001` is maintained as a route/publication runbook under
`docs/operations/landing-page-runbook.md`. It is part of the public URL launch
gate even though it is not a backend paging runbook: host routing, headers,
analytics absence, localization routes, cache purge, rollback, and withdrawal
proof must pass before any public landing URL is treated as live.

### `RB-001` Search Latency Spike

- Symptoms: search latency, timeout rate, or client `service_degraded`
  responses exceed private operations thresholds.
- First 5 minutes: confirm scope by tenant/namespace and `served_from`; check
  dependency latency; disable rerank or force exact/FTS when private thresholds
  require it; keep no-suggestion fallback enabled.
- Dashboard: `Search / Latency and Degraded Modes`, filtered by `tenant`, `namespace`, `served_from`, and `index_generation`.
- Metrics: `search_request_duration_ms{quantile}`, `search_timeout_total`, `search_abstention_total{reason}`, `dependency_request_duration_ms{dependency}`, `circuit_breaker_state`, `rerank_request_total`, `vector_query_duration_ms`.
- Queries/commands: `knudgctl search stats --window <private-window> --by served_from,tenant`; `knudgctl deps check`; percentile latency query over the private incident window.
- Kill switches: `knudgctl circuit set rerank disabled --reason RB-001`; `knudgctl circuit set vector disabled --reason RB-001`; `knudgctl rollout set inline_hints disabled`.
- Rollback: `knudgctl circuit clear rerank --after-green <private-window>`; `knudgctl circuit clear vector --after-green <private-window>`.
- Customer impact: slower or missing suggestions; active agent work must continue without blocking.
- Verification: p95 and timeout rate under private recovery thresholds for the private verification window, no increase in stale/deprecated card serves, and clients return `no_suggestion` or exact/FTS results instead of blocking.
- Reconciliation: file incident with affected tenants, circuits changed, cost impact, and whether index or dependency work is needed.
- Owner: search on-call.

## Overload Control

M1 queue and M2 consent/revocation deployments must define concrete overload
budgets before release. M3 search adds retrieval-specific budgets, but the
safety lanes are not allowed to wait until search exists:

- per-route max in-flight requests for `search_similar`, `get_card`, approval, revocation, and ingestion
- per-tenant fair-share limits and tenant hot-spot shedding
- priority order: revocation and tombstone propagation, approval/consent, direct reads, exact/FTS search, indexing, embeddings, reranking, ingestion, analytics
- queue length and oldest-age limits per lane
- `429` for caller-specific rate or budget exhaustion, `503` for service overload, and `Retry-After` only when the server can honor the retry inside the client deadline
- load-test-to-failure gates proving best-effort lanes cannot delay revocation or approval safety lanes
- reserved DB pool connections, worker slots, and queue admission tokens for
  `revocation`, `approval_publish`, `consent`, `tombstone`, and
  `event_projection`
- automatic admission pause rules for public candidates, embeddings, rerank,
  analytics, and dedupe when safety lane oldest age or DB pool reserve crosses
  threshold

For MVP, normal circuit state is stored in a Postgres-backed
`operational_circuits` table protected by RLS and audit triggers. Each row has
scope, state, TTL, event history, manual override reason, actor, correlation
ID, and half-open concurrency budget. Coarse emergency kill switches also have
an out-of-DB control path: signed static config, deployment environment
override, or edge/proxy deny rule. The emergency path takes precedence over
Postgres state, has a short TTL, records an operator reason, and must be
reconciled into `operational_circuits` after the database recovers. When
Postgres and emergency state disagree, the stricter state wins until an
operator verifies probes, records the conflict resolution, and clears or
extends the emergency TTL. Reconciliation imports the signed emergency record,
preserves both timestamps, links the operator ticket, emits an audit event,
and requires a canary proof before serving a less restrictive state. Drills
must prove operators can disable public wedge, inline hints, vector/rerank,
and noncritical writes while Postgres cannot accept circuit writes. Auth,
revocation, data-integrity, and backup circuits fail closed if circuit state is
unavailable; cost and quality circuits use the last known safe state for the
private stale-state TTL. A later deployment RFC may move normal circuit state to Redis
or a managed control plane only if it preserves audit history, RPO, operator
authz, stale-state TTLs, and circuit-store outage drills.

Circuit control-plane matrix:

| Circuit family | Normal store | Emergency store | Postgres-unavailable behavior | Stale emergency behavior | Close requirement |
|---|---|---|---|---|---|
| auth/revocation/data-integrity/backup | `operational_circuits` plus safety probes | signed emergency deny/config manifest | fail closed for protected reads and writes | remain closed; page operator | owner probe, tenant/namespace reconciliation, audit event |
| public wedge and publication | `operational_circuits` | signed rollout/edge disable config | publication/search disabled | remain disabled; no auto-clear | reviewer/operator signoff and canary proof |
| landing route and route denylist | host config plus release manifest | edge/proxy deny rule | serve inert static page or 404/410 only | keep deny rule until RB-LP-001 probe passes | route probes, cache purge proof, audit event |
| vector/rerank/cost | `operational_circuits` | signed feature-disable config | disable dependency; exact/FTS or `no_suggestion` only | keep disabled after TTL until owner reviews spend/freshness | budget/latency probe and owner signoff |
| noncritical writes/admission | `operational_circuits` | signed admission pause config | pause or reject with idempotent status | keep paused; no background retries without owner | backlog and DB reserve probes |

When normal and emergency stores disagree, the strictest state wins. No circuit
auto-clears while the control-plane store is unavailable.

M3 circuit-control DDL must define `operational_circuits` before implementation:
`tenant_id uuid null`, `id uuid not null`, `scope_type text not null`,
`scope_key text not null`, `state text not null`, `reason_code text not null`,
`opened_by uuid not null`, `manual_override boolean not null`,
`half_open_limit integer not null default 1`, `ttl_expires_at timestamptz null`,
`created_at timestamptz not null`, `updated_at timestamptz not null`,
`cleared_at timestamptz null`, `audit_event_id uuid not null`, and
`correlation_id uuid not null`. `state` is bounded to `closed`, `open`,
`half_open`, and `last_known_safe`; `scope_type` is bounded to dependency,
tenant, namespace, route, queue lane, feature, or global. A partial unique index
allows one active circuit per `(tenant_id, scope_type, scope_key)` where
`cleared_at is null`; global circuits use a sentinel tenant key or a separate
global uniqueness rule. RLS permits service reads for readiness and operator
writes only through audited commands. Negative tests cover stale TTL handling,
conflicting emergency and DB states, unauthorized clears, and strictest-state
selection.

Agent-facing releases require black-box canaries for every exposed transport and namespace class. Canaries must verify that revoked cards never return, stale indexes abstain, public `no_suggestion` remains generic, private diagnostics stay tenant-bound, degraded reasons match the response contract, and retry/circuit behavior stops within the documented budgets.

### `RB-002` Index Freshness Breach

- Symptoms: `index_freshness_lag_seconds` exceeds the wedge budget, `stale_index` abstentions rise, or new approved/revoked cards do not appear in the active generation.
- First 5 minutes: compare the global event stream head with the active index manifest source range; pause new index cutovers; verify worker leases; replay revocation events first; prefer exact/FTS or no suggestion over stale vector output.
- Dashboard: `Indexing / Freshness and Generations`, filtered by `generation`, `namespace`, and `worker_type`.
- Metrics: `index_freshness_lag_seconds`, `index_generation_active`, `indexer_jobs_oldest_age_seconds`, `event_stream_head_position`, `index_manifest_end_position`, `revocation_replay_lag_seconds`, `stale_card_serve_total`.
- Queries/commands: `knudgctl index status --generation active`; `knudgctl queue inspect --type index`; `select max(event_stream_position) from event_stream_positions;`; `select generation, source_start_position, source_end_position, replay_hash, state from search_index_manifests order by created_at desc limit 5;`.
- Kill switches: `knudgctl circuit set vector disabled --reason stale-index`; `knudgctl index cutover pause`; `knudgctl workers pause indexer --after-current-job`.
- Rollback: `knudgctl index cutover rollback --to <previous_generation>` when the active generation is stale or suspect.
- Customer impact: new cards may be missing and revoked cards must be hidden through no-suggestion/exact fallback.
- Verification: active manifest reaches source event head or bounded lag, revoked cards are absent from `search_similar` and `get_card`, and `stale_index` abstentions return to baseline.
- Reconciliation: run `knudgctl index reconcile --generation active --from-position <event_stream_position>` and record skipped/failed cards and the replay hash.
- Owner: indexing on-call.

### `RB-003` Queue Backlog or DLQ Growth

- Symptoms: safety-critical lane oldest age, any-lane growth, DLQ growth, worker lease renewals, or protected-operation dependency on stuck jobs exceed private queue thresholds.
- First 5 minutes: identify queue type, oldest job, tenant hot spots, and poison payload digest; scale workers only after confirming the database is healthy; stop redrive until cause is known.
- Dashboard: `Queues / Backlog and DLQ`, filtered by `lane`, `status`, `tenant`, and `worker_pool`.
- Metrics: `job_queue_depth{lane,status}`, `job_oldest_age_seconds{lane,status}`, `job_attempt_total{lane,status}`, `job_dlq_total{lane}`, `job_lease_renewal_total`, `worker_heartbeat_age_seconds`, `db_lock_wait_seconds`.
- Queries/commands: `knudgctl queue stats --all`; `knudgctl queue peek --lane <lane> --oldest 10`; `select lane, count(*), min(created_at) from jobs where status in ('ready','leased') group by 1;`; `select lane, count(*) from jobs where status = 'dead' group by 1;`. `queue peek` redacts `payload_json` and shows only IDs, digests, lane, status, attempts, and sanitized error metadata.
- Kill switches: `knudgctl admission pause --reason queue-backlog`; `knudgctl workers pause <type>` for poison floods; `knudgctl circuit set embeddings disabled --reason queue-backlog`.
- Rollback: clear admission/embedding pauses only after oldest age falls and poison jobs are isolated.
- Customer impact: submissions, approvals, publication, embeddings, or index freshness may lag; search should continue from current projections.
- Verification: oldest age falls for the private recovery window, DLQ count stops rising, successful attempt rate recovers, and no duplicate side effects appear for idempotent writes.
- Reconciliation: redrive DLQ only with `knudgctl queue redrive --job <id> --reason <ticket>` after fixing root cause; run projection reconciliation for affected object types.
- Owner: platform on-call.

### `RB-004` Emergency Card Revocation

- Symptoms: harmful, private, stale, unsafe, or legally sensitive card must be removed from every read path immediately.
- First 5 minutes: create tombstone and bump revocation epoch. If Postgres is
  unavailable, write a signed emergency deny manifest entry scoped to
  tenant/namespace/card/version with TTL, operator, reason, and signature, then
  force affected reads to check that manifest before cache, index, or card
  serving. Disable cache metadata fallback for affected tenant/namespace if
  epoch propagation is uncertain; replay revocation into active and candidate
  indexes; verify `get_card` and `search_similar` fail closed.
- Dashboard: `Trust / Revocation Propagation`, filtered by `tenant`, `namespace`, and `card_id`.
- Metrics: `revocation_event_total`, `revocation_epoch`, `revocation_propagation_lag_seconds`, `revoked_read_block_total`, `stale_card_serve_total`, `cache_revalidation_failure_total`.
- Queries/commands: `knudgctl revoke card <card_id> --tenant <tenant> --reason <reason> --emergency`; `knudgctl revoke deny-manifest append --tenant <tenant> --card <card_id> --ttl 30m --reason <ticket>` when Postgres is unavailable; `knudgctl revocation status <card_id>`; `knudgctl search probe --must-not-return <card_id>`; `select * from revocation_tombstones where card_id = '<card_id>' order by created_at desc;`; `select * from tenant_revocation_epochs where tenant_id = '<tenant>';`.
- Kill switches: `knudgctl circuit set namespace:<namespace> no-suggestion --reason emergency-revocation`; `knudgctl rollout set inline_hints disabled --tenant <tenant>`.
- Rollback: revocation is not rolled back in-place; create a new reviewed restore event only after policy approval.
- Customer impact: affected cards disappear immediately; broader namespace may receive no suggestions while propagation is verified.
- Verification: tombstone or signed emergency deny manifest exists, server epoch increments when Postgres is available, all protected reads return `stale_or_revoked` or `no_suggestion`, active index excludes the card, and cache metadata is rejected when epoch is unavailable or older.
- Reconciliation: import signed deny-manifest entries into Postgres, create the canonical tombstone/event if missing, audit all artifacts and derived indexes for the card/version, notify affected tenant owner, and open follow-up for root cause and policy state.
- Owner: trust and safety on-call plus search on-call.

#### Emergency Deny Manifest Control Plane

Before M2 external consent/revocation exposure, the deployment RFC must pin one
emergency deny control plane. The MVP default is a signed append-only manifest
stored in the deployment control plane or edge configuration store, not in the
application database. Each entry includes `manifest_id`, monotonic manifest
sequence, tenant, namespace, subject type, subject ID, optional card/card
version, reason code, operator ID, second approver for broad scopes, creation
time, expiry, signing key ID, and signature.

Readers fetch or receive the manifest before serving protected data and cache it
for at most the private emergency-manifest staleness budget. If the manifest is stale, unverifiable, expired without
Postgres reconciliation, or unavailable during an incident, protected reads
return `no_suggestion` and protected writes pause. Signing keys are held by the
deployment control plane, rotated through an operator runbook, and never stored
in the repository or application database. Every API, search, index, cache,
object-storage, and full-card expansion path has a canary proving that a
manifest entry blocks the subject before serving.

The reconciliation command is `knudgctl revoke deny-manifest reconcile --since
<manifest_sequence> --tenant <tenant> --dry-run|--apply`. It imports signed
entries into Postgres, creates missing canonical revocation events/tombstones,
links the emergency audit record, and refuses to clear the manifest until
canaries pass on all read paths. Drill transcripts for append, reader observe,
stale-manifest fail-closed, reconciliation, and clear are M2 release artifacts.

### `RB-005` Failed Migration or Index Cutover

- Symptoms: migration fails, invalid concurrent index appears, active index generation serves errors, or cutover causes authorization/freshness regressions.
- First 5 minutes: stop further deploy steps; keep old generation active; pause cutover; check migration lock state and invalid indexes; disable vector if active generation is suspect; do not drop old generation until reconciliation completes.
- Dashboard: `Deploy / Migrations and Cutovers`, filtered by `migration`, `generation`, and `release`.
- Metrics: `migration_state`, `db_migration_duration_seconds`, `db_invalid_index_total`, `index_cutover_total{result}`, `search_error_total{generation}`, `authz_denial_total`, `revocation_replay_lag_seconds`.
- Queries/commands: `knudgctl deploy halt`; `knudgctl index cutover rollback --to <previous_generation>`; `knudgctl migrate status`; `select indexrelid::regclass from pg_index where not indisvalid;`; `select generation, state, source_start_position, source_end_position from search_index_manifests order by created_at desc;`.
- Kill switches: `knudgctl circuit set vector disabled --reason failed-cutover`; `knudgctl workers pause migrator`; `knudgctl rollout set public_wedge disabled`.
- Rollback: run the prewritten migration rollback or keep the expanded schema dormant; for index failures, return to the previous active generation.
- Customer impact: writes or new search generation may be paused; old generation must remain available or search returns no suggestion.
- Verification: old generation serves within budget, authz and revocation probes pass, invalid indexes are removed or rebuilt with an approved plan, and migration status is stable.
- Reconciliation: compare source event range between old and failed generation; replay missed revocations; write rollback record before retry.
- Owner: release captain plus database on-call.

### `RB-006` Backend Dependency Outage

- Symptoms: vector DB, object storage, reranker, embedding provider, auth provider, or Postgres dependency errors exceed circuit threshold.
- First 5 minutes: identify dependency and blast radius; open its circuit when private failure or latency thresholds are exceeded; preserve protected write idempotency; route read path to lower dependency mode or no suggestion.
- Dashboard: `Platform / Dependencies and Circuits`, filtered by `dependency`, `service`, and `region`.
- Metrics: `dependency_request_total{dependency,result}`, `dependency_request_duration_ms{dependency}`, `circuit_breaker_state{dependency}`, `protected_operation_error_total{reason}`, `search_abstention_total{reason}`, `object_storage_error_total`, `authz_check_error_total`.
- Queries/commands: `knudgctl deps check --all`; `knudgctl circuit status`; `knudgctl search probe --mode exact`; `knudgctl auth probe`; `knudgctl storage probe`.
- Kill switches: `knudgctl circuit set <dependency> disabled --reason dependency-outage`; `knudgctl admission pause --reason dependency-outage`; `knudgctl rollout set inline_hints disabled`.
- Rollback: `knudgctl circuit half-open <dependency>` after the private green window, then clear only after probe and protected-operation success.
- Customer impact: affected features return degraded reasons; search may fall back or abstain, writes may pause when idempotency or consent cannot be guaranteed.
- Verification: affected operations return machine-readable degraded reasons, main agent work is not blocked, queues stop accumulating non-retryable failures, and dependency health recovers for the private green window before half-open.
- Reconciliation: replay retryable jobs, redrive DLQ with reason, audit idempotency conflicts, and record any skipped candidate/index work.
- Owner: platform on-call.

### `RB-007` Postgres Backup, Restore, Failover, or Corruption Event

The accepted MVP production topology for any non-synthetic protected data is
managed Postgres HA with daily base backups, continuous WAL archiving, PITR
restore drills, replica failover within RPO, reserved revocation/tombstone
connections, and restore into a quarantined new cluster before cutover. Before
M1 accepts any non-synthetic private candidate metadata or redacted draft body,
the deployment RFC must bind this to a concrete provider, region topology,
client reconnect behavior, connection-pool settings, promotion gates, PITR
command execution, WAL verification, restore drill transcript, cutover proof,
and tested commands. Availability targets cannot exceed the deployed Postgres
topology.

Safety-critical fences have stricter durability than the general RPO. MVP
requires synchronous commit for acknowledged revocations, approvals,
withdrawals, discard/purge effects, and idempotency effects before
acknowledging success. An external append-only safety journal is out of scope
until a future RFC defines provider, schema, ordering cursor, encryption,
retention, replay into restored Postgres, lag metrics, corruption checks, and
failover drills. If a failover or PITR target cannot prove synchronous effects
through the last
acknowledged commit, affected tenants/namespaces are quarantined: protected
reads return `no_suggestion` or `stale_or_revoked`, and protected writes are
disabled until reconciliation proves the fence complete.

During a Postgres outage, emergency card or namespace deny intent can be
recorded in a signed append-only emergency deny manifest outside the database.
Reads check this manifest before cache, index, or card serving. The manifest is
scoped by tenant/namespace/card/version, has a short TTL, records operator,
reason, and signature, and must be reconciled into Postgres when the database
recovers.

- Symptoms: Postgres primary unavailable, replica lag over RPO, failed backup, PITR restore requested, suspected corruption, checksum failure, unreconciled migration damage, or impossible event-sequence gaps.
- First 5 minutes: freeze destructive maintenance; pause non-critical writes and public candidate admission; keep read paths in exact/FTS or no-suggestion mode; confirm latest successful base backup and WAL archive; identify RPO/RTO target and affected tenants.
- Dashboard: `Database / Backups Replication and Integrity`, filtered by `cluster`, `region`, `tenant`, and `release`.
- Metrics: `postgres_up`, `postgres_replica_lag_seconds`, `postgres_wal_archive_lag_seconds`, `postgres_backup_age_seconds`, `postgres_backup_success_total`, `postgres_restore_test_age_seconds`, `postgres_checksum_error_total`, `db_corruption_suspect_total`, `db_failover_total`.
- Queries/commands: `knudgctl db status`; `knudgctl db backup status`; `knudgctl db pitr plan --target <timestamp>`; `knudgctl db restore-test status`; `knudgctl db failover --target <replica> --reason <ticket>`; `select pg_is_in_recovery();`; `select now() - pg_last_xact_replay_timestamp() as replica_lag;`.
- Kill switches: `knudgctl admission pause --reason db-incident`; `knudgctl workers pause noncritical`; `knudgctl rollout set public_wedge disabled`; `knudgctl circuit set writes protected-only --reason db-incident`.
- RTO/RPO: private deployment RTO/RPO values govern exact/FTS service restoration, write restoration, and general queue/non-safety event recovery. Acknowledged revocations, approvals, and idempotency effects require safety-fence proof or tenant quarantine.
- Rollback/failover: fail over only to a replica within RPO and with revocation/event fences intact. PITR restore must restore into a new cluster, run integrity and tenant-isolation checks, then promote by cutover; never overwrite the only known-good cluster.
- Corruption recovery: isolate suspect tables or indexes, disable affected read modes, rebuild projections from `card_events`, reindex exact/FTS from canonical rows, and compare event counts, tombstones, approvals, and idempotency keys before serving.
- Verification: latest base backup age and WAL archive lag are under private recovery thresholds, restored cluster passes migration, RLS, revocation, event sequence, and search probes, and no protected read serves data with unknown freshness.
- Reconciliation: record data-loss window if any, replay outbox/jobs from durable events, rebuild projections, notify affected tenant owners, and attach restore logs to the incident.
- Owner: database on-call plus release captain.

### `RB-008` Consent and Revocation UX Degradation

- Symptoms: approval handoff creation fails, pending-publication withdrawal is
  unavailable, comprehension-gate pass/fail events stop, consent history cannot
  load, revocation handoff creation fails, notification backlog exceeds the
  wedge budget, or accessibility canaries fail.
- First 5 minutes: pause reviewer publish, public publication, and team-sharing
  publication; keep
  revocation endpoints prioritized; verify trusted browser/OS handoff health,
  challenge signing, step-up auth, consent history reads, and notification
  queue age. Do not allow CLI/MCP fallback to complete consent.
- Dashboard: `Trust / Consent Revocation UX`, filtered by `surface`, `tenant`,
  `namespace`, `challenge_type`, and `client`.
- Metrics: `approval_handoff_error_total`, `revocation_handoff_error_total`,
  `withdrawal_error_total`, `comprehension_gate_result_total`,
  `consent_history_load_error_total`, `notification_backlog_age_seconds`,
  `trusted_surface_accessibility_canary_total`.
- Queries/commands: `knudgctl consent status --tenant <tenant>`;
  `knudgctl consent pause-publish --reason RB-008`;
  `knudgctl consent probe --flow approval,withdrawal,revocation`;
  `knudgctl notifications retry --surface consent --dry-run`;
  `select scope, count(*) from consent_records where revoked_at is null group by 1;`.
- Kill switches: `knudgctl consent pause-publish --all --reason ux-degraded`;
  `knudgctl rollout set public_wedge disabled`; `knudgctl notifications pause
  external --surface consent`.
- Break-glass path: when trusted withdrawal or revocation UX is down, an
  incident commander opens a time-bound break-glass case with two human
  approvers and exact tenant, subject, consent record, artifact digest, and
  requested effect. Operators run `knudgctl consent break-glass revoke
  --case <case_id> --tenant <tenant> --subject <subject> --consent-record
  <id> --artifact-digest <digest> --effect
  permission-only|block-card|remove-derived --dry-run|--apply` or
  `knudgctl consent break-glass withdraw-publication --case <case_id> ...`.
  The command writes the same consent termination, withdrawal, tombstone, audit,
  notification, and cleanup events the trusted human surface would have written,
  and refuses to run if the digest or policy no longer matches.
- Accessibility fallback: RB-008 must keep a tested no-JavaScript plain HTML
  consent/revocation route available for keyboard and screen-reader operation,
  or escalate to the break-glass path above with a user-verifiable audit
  receipt. Publish and new approval stay paused while the fallback is active;
  revocation and withdrawal remain prioritized.
- Rollback: resume publish only after approval, withdrawal, revocation,
  consent-history, and notification probes pass for the private recovery window and no stale
  challenge can complete.
- Customer impact: publication and new consent may pause; revocation and
  withdrawal must remain available or escalate to break-glass.
- Verification: public publication and team-sharing publish attempts fail
  closed while paused,
  revocation and withdrawal handoffs complete in a trusted surface or audited
  break-glass path, notification retries are visible in consent history, the
  exact subject/digest is blocked or terminated as requested, and accessibility
  canaries pass.
- Reconciliation: replay notification jobs, expire unsafe challenges, attach
  consent-history audit samples, and record any delayed publication or
  revocation impact.
- Owner: trust UX on-call plus platform on-call.

## Deployment Health Contract

Knudg services must expose separate health, readiness, and startup/liveness endpoints. This follows the Kubernetes split where readiness removes a pod from serving traffic, while liveness/startup control restart behavior.

- `GET /health/live`: process is alive and event loop/worker heartbeat is not wedged. It does not check downstream dependencies. Failure means restart is acceptable.
- `GET /health/ready`: instance can accept its routed traffic class. API readiness checks Postgres connectivity, migration compatibility, auth policy load, current revocation epoch availability, and active index manifest readability. Worker readiness checks queue lease ability, schema compatibility, and required dependency circuits.
- `GET /health/startup`: initialization has completed, config is valid, migrations are compatible, and required secrets are loaded.
- `GET /health/dependencies`: authenticated operator endpoint with per-dependency status, circuit state, and degraded mode. It is not used as the liveness probe.

Readiness must fail closed for auth, revocation fence, migration incompatibility, and unknown active index generation. Readiness may stay true with degraded read dependencies only when the service can return exact/FTS, retrieval-panel-only, or no-suggestion responses within the global deadline.

Route-class readiness is separate. A deployment must expose or label readiness
for `search`, `card-read`, `submit/write`, `trusted-consent-revocation`,
`reviewer-admin`, `worker-lane`, and `landing`. Retrieval/index degradation
must not remove consent/revocation routes from service if their auth,
revocation, database, and challenge dependencies are healthy. Consent/revocation
degradation must not keep reviewer publish ready. Landing readiness is tied to
RB-LP-001 probes, not search/index dependencies.

Probe thresholds:

- API startup: failure threshold 30, period 2 seconds, timeout 1 second.
- API liveness: initial delay 10 seconds, period 10 seconds, timeout 1 second, failure threshold 3.
- API readiness: period 5 seconds, timeout 1 second, failure threshold 2, success threshold 2.
- Worker startup: failure threshold 60, period 2 seconds, timeout 1 second.
- Worker liveness: period 10 seconds, timeout 1 second, failure threshold 6.
- Worker readiness: period 5 seconds, timeout 2 seconds, failure threshold 2, success threshold 2.

Readiness must return the failing component names and degraded mode, but liveness must not restart a process solely because Postgres, vector search, rerank, object storage, or an external provider is unavailable.

## Alert Taxonomy

Alerts use consistent labels: `severity`, `service`, `tenant_scope`, `runbook`, `user_impact`, and `degraded_mode`.

| Severity | Page | Meaning | Examples |
|---|---:|---|---|
| `critical` | yes | Unsafe or blocking behavior, privacy risk, data corruption, or revocation failure | revoked card served, auth fence unavailable, failed migration affecting writes |
| `page` | yes | User-visible outage or SLO breach with no automatic recovery | search p95 breach, dependency circuit open for protected writes, DLQ growing |
| `ticket` | no | Needs owner action during business hours | review backlog age, cost circuit near cap, stale canary index |
| `info` | no | Audit or rollout state change | circuit opened by operator, index generation cutover, public wedge paused |

Every paging alert must link one `RB-*` runbook and must name the current degraded mode: `full`, `no_rerank`, `exact_only`, `retrieval_panel_only`, `no_suggestion`, `writes_paused`, or `traffic_blocked`.

## Failure Semantics

Dependency failures should degrade toward no suggestion rather than blocking active work.

Worker failures should be handled with:

- bounded retries
- exponential backoff with jitter
- idempotency keys
- dead-letter queues
- stuck-state sweepers
- replay from canonical events
- reconciliation between source of truth and projections

MVP uses a Postgres-backed queue until `DEC-001` is changed. Queue defaults:

- visibility timeout: private operations value
- max lease renewal: private operations value
- max attempts: private operations value
- backoff: exponential with jitter
- DLQ retention: private operations value
- redrive: operator action with reason
- ordering: no cross-object ordering guarantee
- correctness: constraints, event sequence, idempotency, and reconciliation, not queue order

Safety-critical lanes are isolated from best-effort work:

- `revocation`, `approval_publish`, `consent`, `tombstone`, and `event_projection` lanes have dedicated worker pools, DB connection budgets, queue quotas, and paging alerts.
- `embedding`, `rerank`, `public_candidate_ingest`, `dedupe`, and `analytics` lanes cannot consume safety-critical worker slots or connection reserves.
- Redrive, poison floods, or tenant hot spots in best-effort lanes must not delay revocation, approval publication, consent withdrawal, tombstone propagation, or event projection beyond the M3 thresholds.

## Stuck State and Outbox Recovery

The sweeper is a correctness path. It scans lifecycle projections,
`outbox_events`, and queue state by `event_stream_position`, not by wall-clock
guessing alone.

Minimum stuck-state contract:

| State or gap | Owner lane | Max age before ticket/page | Allowed recovery |
|---|---|---|---|
| `pending_redaction` without live redaction job | redaction | 30 min / 2 h | enqueue idempotent redaction job or move to `deferred` with reason |
| `pending_review` without live review job | review | 30 min / 2 h | enqueue review job or pause admission if reviewer capacity is exhausted |
| `awaiting_user_approval` with expired challenge | approval | 10 min after expiry / 1 h | invalidate challenge and issue new handoff on user request |
| `approved_for_publication` with no reviewer publish attempt | approval_publish | 2 h / 1 business day | page review queue owner; publish remains blocked until reviewer action |
| `published` not indexed hot | index | 5 min / 15 min | enqueue hot-index job or force no-suggestion for affected card |
| `indexed_hot` not compacted to main | compaction | wedge budget / 24 h | enqueue compaction proposal or keep hot index active |
| event row without outbox/job effect | event_projection | 2 min / 5 min for safety lanes | run `knudgctl outbox reconcile --from-position <pos>` |

Outbox telemetry includes unpublished outbox count, oldest unpublished age by
lane, event-stream head to outbox lag, outbox-to-job lag, reconciliation failure
count, and safety-event projection lag. Queue health is not green while an
acknowledged safety event lacks required outbox/job/projection work, even if
`jobs` depth is low.

Queue capacity gates must define per-lane sustainable arrival rate, retry
amplification ceiling, drain-time objective, redrive concurrency, and tenant
fair-share behavior. If backlog cannot drain within the SLO after best-effort
shedding, admission pauses for the affected tenant or public wedge before
safety lanes exceed oldest-age thresholds.

## Index Migration Operations

Embedding and index model changes are routine operations for a large corpus. Each index generation must define:

- source event range
- dual-read or dual-write window
- canary namespace
- freshness lag budget
- cold-card deferral rules
- revocation replay SLA
- rollback criteria and command path

## Failure Drills as Release Gates

Before M2, release candidates must pass emergency revocation and auth/revocation uncertainty drills. Before M3, add search latency fallback, queue backlog, DLQ redrive, failed migration rollback, Postgres PITR restore, and backup freshness alerting. Before M4, add index cutover rollback, stale vector generation, and revocation replay drills. A drill passes only when alerts fire at the documented thresholds, the linked runbook is usable by the on-call, protected reads fail closed, and reconciliation evidence is attached to the release record.
