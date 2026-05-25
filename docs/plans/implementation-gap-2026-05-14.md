# Implementation Gap Review - 2026-05-14

Status: compatibility implement-loop handoff, not a strict implement-loop PASS artifact

This review compares the current design documents with the repository
implementation after local Postgres validation became available. It is an
implement-loop-style pre-loop inventory, not a closed implement-loop run.

## Implement-Loop State

- State: compatibility implementation loop active; strict-evidence PASS remains
  blocked.
- Reason: existing review-loop records are prose ledgers with PASS summaries,
  but they do not contain reconstructable implement-loop baseline evidence:
  source hashes, lane-authored judgment JSON, accessed-path evidence, verdict
  envelopes, and immutable reviewed-source bundles.
- Review backend: advisory only in this session; no PASS-eligible read-isolated
  backend evidence was established before implementation.
- Allowed output from this run: source inventory, implemented slices, local
  verification status, and practical use-ready handoff.

## Verification Baseline

Current local verification passes:

```powershell
python -m pytest
python -m pytest tests/test_m0_schema.py
npm run check:lp
npm run gates:all
```

Observed results on May 14, 2026:

- Python test suite: 116 passed
- M0 schema tests: 60 passed
- Static landing-page checks: passed
- Gate validators: passed
- Local Postgres: `knudg-postgres` healthy on `localhost:54329`

## Implemented Surfaces

### M0.0 DDL and local migration harness

Implemented:

- `docker-compose.yml` local Postgres
- `scripts/migrate.py` up/down runner
- `migrations/0001_m0_schema.up.sql`
- `migrations/0001_m0_schema.down.sql`
- local integration tests in `tests/test_m0_schema.py`

Covered by tests:

- empty DB apply, reapply, rollback
- down migration leaves cluster roles intact
- core lookup seed rows
- composite tenant FK enforcement for namespace grants
- global event-position bijection
- lifecycle transition guard
- RLS claim spoof denial
- membership and namespace-grant revalidation after revocation
- revocation tombstone hides card and card version
- approval challenge binding to exact digest/policy/challenge
- idempotency conflict on same key with different request digest
- static DDL guard against `card_versions.is_current`

### Static landing page

Implemented:

- English, Japanese, and Simplified Chinese static pages
- localized 404 pages
- no-script/no-form/no-action static checks
- Cloudflare Workers static deployment config
- security headers and smoke-test script
- public landing-page operations runbook

Covered by `npm run check:lp`.

### Pre-M1 validation planning

Implemented:

- RFC 0003 draft gate for WEDGE-001
- Pre-M1 validation protocol
- WEDGE-001 validation workbook
- publication-control requirements

Not yet satisfied:

- real prospect registry entries
- seed dry-run evidence
- 100 labeled seed candidates
- measured reviewer capacity
- commercial validation evidence
- numeric pivot thresholds

## Remaining Gap List

### G1 - Strict implement-loop baseline is not reconstructable

Design source:

- implement-loop skill baseline contract
- `.codex/review-loop/*.md` PASS ledgers

Current implementation:

- PASS ledgers exist, but only as prose summaries.
- No reconstructable evidence bundle was found with source hashes, lane JSON,
  accessed-path manifests, and verdict envelopes.

Required next action:

- Run a read-only baseline-binding review-loop over the current source-of-truth
  set with hash-bound lane evidence, or accept that ongoing work is ordinary
  implementation outside strict implement-loop PASS semantics.

### G2 - M0 event append API/function is implemented

Design source:

- `docs/rfcs/0001-m0-schema-event-log.md`
- `docs/architecture/implementation-readiness.md`

Current implementation:

- `card_events`, `domain_events`, `event_stream_positions`, lifecycle guards,
  and bijection triggers exist.
- `knudg_append_card_event(...)` exists for narrow M0 app-user lifecycle
  events, checks optimistic concurrency, validates lifecycle transitions,
  updates card projection, writes `event_stream_positions`, and records
  idempotency in one transaction.
- Application roles cannot insert card events or idempotency rows directly.
- Tests cover valid append/replay, stale current-version rejection, projection
  mismatch rejection, invalid transition rejection, and app-role direct-write
  denial.

Why this matters:

- The design says application roles must append events only through an event
  append path that checks optimistic concurrency, updates projections, and
  inserts the ledger row in one transaction.

Required next action:

- Add operation-specific append functions for worker/admin lifecycle events as
  those M0/M1 surfaces are implemented.

### G3 - Card payload JSON schema and canonical digest profile are implemented

Design source:

- `docs/rfcs/0001-m0-schema-event-log.md`

Current implementation:

- `schemas/card-payload-v1.schema.json` and digest vectors are checked in.
- `scripts/card_payload.py` provides the application-side canonical digest
  helper used by tests.
- `knudg_submit_candidate(...)` accepts raw JSON text, rejects duplicate keys,
  non-ASCII keys, and non-portable numbers, validates payload shape, and
  computes the canonical SHA-256 digest server-side.
- `card_versions` enforces the digest algorithm, lowercase hex digest shape,
  canonical digest equality, and card payload v1 schema checks.

Required next action:

- Revisit the payload profile when additional card schema versions are designed.

### G4 - Card revocation epoch allocation is implemented; domain revocation helpers remain

Design source:

- `docs/rfcs/0001-m0-schema-event-log.md`
- `docs/architecture/implementation-readiness.md`

Current implementation:

- `tenant_revocation_epochs` table exists.
- `revocation_tombstones.revocation_epoch` exists and is checked positive.
- `knudg_revoke_subject(...)` exists for M0 card and card-version subjects.
- Card/card-version revocation allocates the tenant epoch transactionally,
  appends a `revoked` card event, inserts the tombstone, updates the card
  projection to `revoked`, and records idempotency in one transaction.
- Duplicate card/card-version revoke calls are serialized by an
  operation-scoped transaction advisory lock before idempotency lookup.
- M0 card-version revocation is intentionally limited to the current card
  version. Historical-version revocation needs a separate operation because it
  should not update the whole card projection as `revoked`.
- The tombstone consistency trigger verifies that card tombstones reference a
  matching `revoked` card event, actor, and expected current version, and that
  card-version tombstones bind to the same `expected_current_version` as the
  tombstoned version.
- Idempotent replay revalidates current namespace claims and submit/admin scope
  before returning the prior revoke effect.
- Tests cover card and card-version revoke, monotonic epoch allocation,
  idempotent replay/conflict, tombstone read denial for card, card-version,
  namespace, tenant, and approval artifacts, and card-version/card mismatch
  rejection, wrong-version card event binding rejection, non-current
  card-version rejection, and replay denial after namespace grant revocation.

Required next action:

- Add operation-specific tenant/namespace domain revocation functions when M0
  needs admin/break-glass revoke workflows.
- Keep direct privileged domain tombstone writes restricted to audited
  migration/operator paths until tenant/namespace revoke helpers allocate
  epochs and append domain events transactionally.

### G5 - Consent termination and withdrawal path are implemented

Design source:

- `docs/rfcs/0001-m0-schema-event-log.md`
- `docs/architecture/consent-revocation-ux.md`

Current implementation:

- `consent_records` and `approval_challenges` exist.
- Exact challenge binding and one active public approval are enforced.
- `knudg_revoke_consent_record(...)` terminates a consent row with a
  `consent_terminated` domain event, event stream position, idempotency row,
  and current caller reauthorization.
- `knudg_withdraw_publication_approval(...)` moves an approved-for-publication
  card to `publication_withdrawn`, writes `approval_withdrawn`, terminates the
  active public consent with that card event, and is idempotent.
- Tests cover consent-only termination, idempotent replay/conflict, active
  public consent removal, challenge reuse rejection, withdrawal-before-publish,
  missing active consent denial, and replay denial after namespace grant
  revocation.

Required next action:

- Add the trusted human UI ceremony around these operations before public/team
  publication flows.
- Add reviewer publish/worker paths that recheck active public consent at
  publish time.

### G6 - Audit hardening has a guarded M0 path

Design source:

- `docs/rfcs/0001-m0-schema-event-log.md`
- `docs/architecture/operations.md`

Current implementation:

- `audit_events` exists and is append-only.
- `sanitized_detail` is checked by `knudg_private.audit_detail_is_sanitized`
  for length, newlines, secret/token/credential markers, private paths, and
  raw-snippet-like detail.
- `knudg_insert_audit_event(...)` gives app/worker roles a guarded audit write
  path bound to current signed claims.
- M0 protected revoke/consent operations emit audit rows in the same
  transaction.
- Tests cover guarded audit insertion, secret-like/path/raw-snippet rejection,
  append-only audit rows, and protected-operation audit emission.

Required next action:

- Expand sanitizer classes as real production audit samples arrive.
- Add audit emission to later worker/admin functions as those protected
  operation paths are implemented.

### G7 - Break-glass has a minimal audited emergency revoke path

Design source:

- `docs/rfcs/0001-m0-schema-event-log.md`
- `docs/architecture/security-privacy.md`

Current implementation:

- `break_glass_cases` exists.
- App/worker roles cannot read or write `break_glass_cases` directly.
- `knudg_break_glass_revoke_subject(...)` exists for M0 emergency card and
  current-card-version revocation.
- The function requires a `break_glass_admin` actor role, an active unexpired
  tenant membership with `membership_role = 'break_glass_admin'`, an active
  unexpired case, permitted operation scope, target scope matching
  tenant/namespace/card or card version, idempotency, epoch allocation,
  tombstone/event writes, and audit emission in one transaction.
- Tests cover ordinary actor denial, case scope denial, expired case denial,
  permitted-operation mismatch, non-current card-version denial,
  namespace-scoped emergency revoke without a namespace claim, replay, audit
  emission, and app/worker direct case table denial.

Required next action:

- Add break-glass paths for consent termination, withdrawal, and future
  tenant/namespace/domain revocation only when those operational commands are
  required.
- Add post-access review workflow and operator command stubs.

### G8 - M1 queue/outbox skeleton is implemented

Design source:

- `docs/architecture/implementation-readiness.md`
- `docs/architecture/operations.md`

Current implementation:

- `outbox_events`, `jobs`, and `job_attempts` tables exist with tenant scope,
  lane/status checks, idempotency keys, payload digests, attempt tracking,
  leases, DLQ state, and event-stream-position binding.
- `knudg_enqueue_outbox_job(...)` creates an idempotent outbox event and ready
  job for an existing event stream position.
- `knudg_claim_job(...)` leases ready jobs with `FOR UPDATE SKIP LOCKED`,
  worker-identity claims, `allowed_operations`, and attempt rows.
- `knudg_complete_job(...)` marks the leased job succeeded and marks the outbox
  completed.
- `knudg_fail_job(...)` schedules retry or dead-letters after max attempts,
  with sanitized error detail.
- App/worker roles can inspect tenant-scoped queue rows but cannot insert or
  mutate queue tables directly; writes go through security-definer functions.
- Tests cover idempotent enqueue/conflict, direct-write denial, worker identity
  and `allowed_operations` requirements, non-blocking claim of ready jobs while
  another is leased, completion, sanitized failure rejection, and DLQ
  transition.

Required next action:

- Add redrive/reconciliation commands and `knudgctl` stubs before relying on
  the queue operationally.
- Keep non-synthetic protected-data rollout gated on the M1 Postgres HA/PITR
  requirements and RFC 0003 acceptance.

### G9 - Required `knudgctl` operational command stubs are implemented for local M0

Design source:

- `docs/architecture/operations.md`

Current implementation:

- Operations docs reference `knudgctl` commands for queue, revoke, db, circuit,
  index, deps, consent, and rollout flows.
- `scripts/knudgctl.py` exists with JSON output and stable exit codes:
  `0 = ok`, `2 = not_configured`, `3 = usage_error`, `4 = unavailable`.
- `npm run knudgctl -- ...` is wired through `package.json`.
- Implemented DB-backed local commands include `migrate status`, `db status`,
  `revocation status`, `queue stats`, `queue peek`, and `outbox reconcile
  --dry-run`.
- Runnable stubs return `not_configured` for backup/PITR/failover, queue
  redrive apply, circuit/dependency/search/index/consent/notifications/deploy
  commands until the backing operational integrations exist.
- Tests cover JSON output, stable not-configured exit, DB status, migration
  status, revocation status, queue stats, and queue peek payload redaction.

Required next action:

- Implement mutating redrive/reconciliation commands once operator auth and
  audit command transcripts are ready.
- Add command transcript fixtures to release drills as each runbook graduates
  from local stub to configured operation.

### G10 - WEDGE-001 opaque evidence helper is implemented; real evidence is still missing

Design source:

- `docs/rfcs/0003-wedge-001-agentic-coding-tooling.md`
- `docs/product/wedge-001-validation-workbook.md`

Current implementation:

- The workbook and protocol shape exist.
- `scripts/wedge_evidence.py` validates private research snapshot metadata and
  writes repo-safe WEDGE-001 summaries with only opaque IDs, snapshot digests,
  counts, consent-state counts, decision counts, risk counts, and median/p90
  timing summaries.
- `npm run wedge:evidence -- ...` is wired through `package.json`.
- `docs/operations/wedge-001-evidence.md` documents the helper boundary.
- Tests cover safe summary generation, summary schema allowlisting,
  raw/private-looking value rejection, raw-value-safe error output, code-only
  rejection reasons, unknown field rejection, and
  unclear-rights/public-candidate rejection.
- No actual private prospect registry snapshot, dry-run summary, seed corpus
  summary, reviewer capacity evidence, or commercial validation summary exists
  yet in the allowed opaque-reference format.

Required next action:

- Run the 30-50 candidate dry run outside product tables using the helper to
  validate the private snapshot export.
- Commit only generated opaque summaries if publication to the repository is
  explicitly approved.
- Update RFC 0003 only after evidence exists.

### G11 - Retrieval/search/API/MCP abstention skeleton is implemented

Design source:

- `docs/architecture/retrieval.md`
- `docs/architecture/agent-access.md`
- `docs/architecture/implementation-readiness.md`

Current implementation:

- `scripts/knudg_retrieval.py` exists as a non-ingesting contract skeleton for
  private/team search profiles, public search requests, and single-request MCP
  JSON-RPC tool envelopes.
- `npm run retrieval:skeleton -- ...` is wired through `package.json`.
- `docs/operations/retrieval-skeleton.md` documents the disabled serving
  boundary.
- Private/team `SearchProfile` requests are shape-checked and return
  `no_suggestion` with `service_degraded` until a backend is configured.
- Public search requests reject tenant, namespace, object, and fingerprint
  selectors and return only generic abstention fields.
- MCP `tools/list` exposes a stubbed `search_similar` tool and `tools/call`
  returns a `no_suggestion` content payload. Unsupported methods use JSON-RPC
  error envelopes.
- Tests cover private abstention, raw-field rejection, public authenticated
  selector rejection with indistinguishable generic abstention, public
  raw-value generic abstention, static no-DB-access guards, MCP tool
  listing/calling, and JSON-RPC method errors.

Status:

- Serving remains intentionally disabled.
- No exact/FTS index, vector table, ranking, reranking, hook integration,
  delegated-token verifier, or protected-data retrieval exists.
- Still a future milestone gap for M3/M5 before real candidate generation.

Required next action:

- Keep blocked until M3 exact/FTS gates and DEC-014A internal protected-data
  proof profile are accepted.

## Recommended Next Slice

### G12 - M3 retrieval gate scaffold is implemented; protected-data serving remains disabled

Design source:

- `docs/architecture/retrieval.md`
- `docs/architecture/agent-access.md`
- `docs/decisions/README.md`

Current implementation:

- `schemas/m3-retrieval-gates.schema.json` defines the exact/FTS and DEC-014A
  gate fixture shape.
- `fixtures/m3-retrieval-gates.draft.json` records the current draft scaffold
  with protected-data enablement fixed to `false`.
- `scripts/validate_m3_gates.py` validates the scaffold and blocks premature
  accepted status if exact/FTS rank formula, tokenizer, score normalization, or
  authoritative DEC-014A accepted proof profile are missing. DEC-014A
  acceptance is read from `docs/decisions/README.md`; the fixture cannot
  self-assert it. Accepted status also requires existing exact/FTS and DEC-014A
  evidence artifacts.
- `npm run m3:gates` validates the current scaffold.
- `docs/operations/m3-retrieval-gates.md` documents the disabled serving
  boundary.
- Tests cover schema validity, disabled protected-data enablement, rejection of
  enablement, blocking premature accepted status, and blocking self-asserted
  DEC-014A acceptance while the authoritative decision backlog remains open.

Status:

- This is decision scaffolding only. It does not accept DEC-014A, define a live
  ranking spec, create indexes, or enable protected-data retrieval.

Required next action:

- Fill the exact/FTS fixtures and DEC-014A proof-profile RFC when M3 is ready.
- Keep protected-data serving disabled until the gate fixture, auth interop
  tests, revocation fence tests, and operator circuit runbook all pass.

## Recommended Next Slice

### G13 - DEC-018 review operations gate scaffold is implemented; reviewer publish remains disabled

Design source:

- `docs/decisions/README.md`
- `docs/architecture/security-privacy.md`
- `docs/product/strategy.md`
- `docs/product/wedge-001-validation-workbook.md`

Current implementation:

- `schemas/review-ops-gates.schema.json` defines the DEC-018 review-ops gate
  fixture shape.
- `fixtures/review-ops-gates.draft.json` records reviewer lane, assignment,
  high-risk verification, malicious-card test, and pause-rule scaffolding.
- `scripts/validate_review_ops_gates.py` validates the scaffold and blocks
  self-asserted accepted status unless `docs/decisions/README.md` marks DEC-018
  accepted and an existing review-ops evidence artifact is present.
- `npm run review:gates` validates the current scaffold.
- `docs/operations/review-ops-gates.md` documents the disabled surface boundary.
- Tests cover schema validity, disabled reviewer publish/public display/high-risk
  body expansion, rejection of enabled surfaces, blocking self-asserted DEC-018
  acceptance, every-high-risk-lane dual-review requirements, and mixed-lane
  regression coverage.

Status:

- This is review-ops decision scaffolding only. It does not enable reviewer
  publish, public display, high-risk body expansion, reviewer assignment, or
  public corpus expansion.

Required next action:

- Draft and accept the DEC-018 review-ops RFC before implementing reviewer
  queues or high-risk public display.
- Keep reviewer publish, public display, and high-risk body expansion disabled
  until calibration tests, malicious-card tests, pause rules, reproduction lab,
  and reviewer session hardening pass.

## Recommended Next Slice

### G14 - Operational circuit gate scaffold is implemented; live mutation remains disabled

Design source:

- `docs/decisions/README.md`
- `docs/architecture/operations.md`
- `docs/architecture/implementation-readiness.md`

Current implementation:

- `schemas/circuit-gates.schema.json` defines the DEC-015 operational circuit
  gate fixture shape.
- `fixtures/circuit-gates.draft.json` records critical circuit-family defaults
  for auth/revocation/data-integrity/backup, public wedge/publication, landing
  route denylist, vector/rerank/cost, and noncritical writes/admission.
- `scripts/validate_circuit_gates.py` validates required families, fail-closed
  behavior, family-specific stale emergency behavior, no auto-clear for all
  circuit families, duplicate-family rejection, and disabled live mutation.
- `npm run circuit:gates` validates the current scaffold.
- `docs/operations/circuit-gates.md` documents the disabled control-plane
  boundary.
- Tests cover schema validity, disabled live mutation/public publication,
  rejection of enabled surfaces, required family presence, auth/revocation
  fail-closed behavior, no auto-clear for every family, stale behavior mismatch,
  and duplicate-family rejection.

Status:

- This is circuit decision scaffolding only. It does not create
  `operational_circuits`, verify emergency manifests, authorize operators, or
  mutate live circuit state.

Required next action:

- Implement `operational_circuits` DDL and audited operator commands only after
  the circuit DDL, audit, operator authz, emergency manifest verifier,
  strictest-state selection tests, and outage drills are ready.

## Recommended Next Slice

### G15 - Runbook command manifest scaffold is implemented; deployment drills are not claimed

Design source:

- `docs/architecture/operations.md`

Current implementation:

- `schemas/runbook-command-manifest.schema.json` defines the runbook command
  manifest shape.
- `fixtures/runbook-command-manifest.draft.json` maps initial runbook commands
  to `knudgctl` stubs, operator roles, dry-run behavior, mutation guards,
  stable exit codes, JSON output schemas, audit events, and transcript status.
- `scripts/validate_runbook_manifest.py` validates core runbook command
  coverage across RB-001 through RB-008, duplicate IDs, dry-run/apply
  requirements for guarded mutation drafts, and blocks drill-passed claims
  without schema-valid transcript artifacts bound to the manifest row.
- `npm run runbook:manifest` validates the current scaffold.
- `docs/operations/runbook-command-manifest.md` documents that the manifest is
  not a drill transcript.
- Tests cover schema validity, non-passed draft state, blocking drill-passed
  claims without transcripts, missing transcript/path mismatch, dry-run
  requirements for mutation drafts, guarded mutation requirements, required
  runbook coverage, duplicate IDs, and non-`knudgctl` command rejection.

Status:

- This is manifest scaffolding only. It does not claim successful deployment
  drills, operator authz, real dashboards, or configured integrations.

Required next action:

- Attach real drill transcript artifacts only after each command path is run in
  the target deployment profile.
- Expand manifest coverage as runbook commands graduate from prose to stubs.

## Recommended Next Slice

### G16 - Gate validator meta-check is implemented

Design source:

- G10 through G15 scaffold validator pattern

Current implementation:

- `fixtures/wedge-evidence.sample.json` provides a repo-safe sample for
  `wedge:evidence validate`.
- `npm run gates:all` runs wedge evidence validation plus M3, review-ops,
  circuit, and runbook manifest validators.
- `tests/test_gate_meta.py` verifies every gate fixture has a schema,
  validator, and npm script, verifies `gates:all` includes each gate script,
  and executes all gate validators.
- `tests/test_runbook_manifest.py` now also covers accepted `--apply` guarded
  commands, existing attached transcript paths, and transcript-to-manifest
  binding.
- Cross-slice hardening now prevents unknown JSON keys from echoing raw/private
  key names in evidence and retrieval validation errors.

Status:

- This is validation consolidation only. It does not accept gates, attach real
  drill transcripts, or enable any serving/publication/control-plane surface.

Required next action:

- Keep new scaffold fixtures wired into `gates:all` as they are added.

## Recommended Next Slice

### G17 - M1 private writer flow is implemented for local/synthetic use-ready

Design source:

- `docs/architecture/implementation-readiness.md`
- `docs/architecture/security-privacy.md`
- M1 private writer flow implied by candidate admission, redaction, review,
  exact human approval, and private retention consent.

Current implementation:

- Worker command functions now advance a submitted candidate through the M1
  private writer path without direct table writes:
  `knudg_accept_admission(...)`, `knudg_request_redaction(...)`,
  `knudg_complete_redaction(...)`, and
  `knudg_request_private_approval(...)`.
- `knudg_private.worker_advance_card(...)` centralizes the simple
  worker-driven status transitions with actor-role checks, worker
  `allowed_operations`, optimistic current-version checks, lifecycle guard
  validation, event append, event-stream-position append, projection update,
  and idempotency recording.
- `knudg_complete_redaction(...)` can keep the current version or create an
  immutable redacted `card_versions` row when the payload digest changes, then
  advances the card to `pending_review`.
- `knudg_request_private_approval(...)` creates an exact
  `approval_challenges` row for `private_retention` bound to the current card
  version digest, policy digest, challenge digest, namespace, and subject, then
  advances the card to `awaiting_user_approval`.
- `knudg_approve_private_retention(...)` requires an app-user with current
  namespace claim and submit/admin grant, checks the active challenge against
  the current artifact, writes `private_approved`, inserts the matching
  `consent_records` row, lets the challenge-binding trigger mark the challenge
  used, updates the card to `approved_private`, and records idempotency.
- Tests cover the full synthetic path from `knudg_submit_candidate(...)` to
  `approved_private`, redacted-version creation, challenge binding, private
  consent creation, approval replay/conflict, denied worker operations, and
  submit-scope denial for private approval.

Status:

- This is local/synthetic internal use-ready for the private writer path.
- It does not claim production readiness, real protected-data ingestion, public
  publication, live indexing, HA/PITR, operator circuits, or human UI ceremony.

Required next action:

- Add queue job orchestration around these command functions when real worker
  lanes are wired.
- Add trusted human UI for exact private/public approval artifacts before any
  real private/team/public publication flow.
- Keep protected-data search and public publication disabled until the relevant
  gates move from draft scaffolds to accepted evidence.

## Recommended Next Slice

The next implementable slice is M1 orchestration around the private writer
path:

> Wire the private writer command path into queue/outbox job orchestration and
> `knudgctl` dry-run/status commands, while keeping live protected-data serving
> and public publication disabled.

Rationale:

- G2 through G17 now have narrow trusted DB paths for candidate creation,
  private admission/redaction/review/approval, revocation, consent withdrawal,
  audited break-glass revoke, queue skeletons, operational stubs, evidence
  guardrails, retrieval abstention contracts, and gate validation.
- The next practical gap is not another schema-only command; it is proving that
  worker lanes can pick up and drive the now-existing M1 command functions
  without bypassing idempotency, audit, consent, or circuit boundaries.

Suggested acceptance criteria:

- Queue jobs can drive admission, redaction, and review commands in local
  synthetic fixtures.
- `knudgctl` can inspect private writer queue state and dry-run reconciliation
  without exposing raw card bodies.
- Verification remains green.
- `gates:all` remains green and protected-data serving remains disabled.

## Blocked Before Strict PASS

To close a true implement-loop PASS later, the project needs:

1. A reconstructable read-only baseline-binding review-loop evidence bundle.
2. A PASS-eligible independent review backend with read isolation and
   lane-authored judgment JSON.
3. A trace matrix mapping source sections to requirement and acceptance IDs.
4. Slice review evidence and final repository review-loop evidence.

Until then, this file should be treated as a practical implementation backlog,
not a formal implement-loop success artifact.
