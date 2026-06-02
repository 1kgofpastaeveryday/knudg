# Production Readiness Backlog

## Launch Gate Manifest Contract

Status: draft scaffold implemented

Every launch, alpha, public-document, enterprise, or non-synthetic storage gate
is closed unless a signed `launch-gate-manifest` says otherwise. The manifest
is the canonical pass/fail artifact and contains:

- gate ID, owner, status, review expiry, and blocking dependents
- authority document path and accepted revision
- public-safe status label plus private threshold reference when thresholds are
  intentionally not published
- required machine-checkable fixture names and CI result references
- evidence URI for restore drills, auth tests, consent UX tests, abuse tests,
  load tests, schema validation, or reviewer-capacity measurements as relevant
- rollback target and stale-review behavior

Private launch-control numbers remain outside public docs, but the manifest
must expose enough public-safe labels and fixture references for CI and release
review to prove whether the gate is open or closed.

Current scaffold:

- `schemas/launch-gate-manifest.schema.json`
- `fixtures/launch-gate-manifest.draft.json`
- `scripts/validate_launch_gate_manifest.py`
- `docs/operations/launch-gate-manifest.md`
- `tests/test_launch_gate_manifest.py`

The `non_synthetic_body_persistence_gate` is closed until all of these pass in
the manifest: accepted WEDGE-001 when the source is wedge data,
`private_candidate_collection` consent/acknowledgement for short-lived
candidate drafts, protected-data durability, audit persistence, PR-006
database-side intake safety, and no-log ingress constraints. Redacted draft
bodies, pending approval queue bodies, review escrows, and any durable
candidate body are non-synthetic body persistence unless explicitly marked as
synthetic fixture data with server-verified fixture provenance. Promotion to
`approved_private` or retention beyond the candidate TTL additionally requires
`private_retention` consent.

Sealed review escrow bootstrap is synthetic-only while PR-006 is blocked. Real
non-synthetic escrow storage additionally requires exact
`intake_review_escrow` consent, protected-data durability, audit persistence,
no-log ingress, and the PR-006 escrow schema/tests to pass.

## PR-001: WEDGE-001 Acceptance

Status: blocked

Gate:

- `docs/rfcs/0003-wedge-001-agentic-coding-tooling.md` is still `draft gate`.

Acceptance:

- Named owners, evidence links, measured pass/fail thresholds, seed protocol,
  reviewer supply plan, baseline systems, and commercial validation are filled.
- Estimated thresholds may be recorded as draft planning inputs, but they do
  not satisfy PR-001 and cannot open M1 product ingestion.
- 30-50 dry-run candidates validate the protocol.
- At least 100 labeled seed candidates exist before M1 ingestion. Before the
  non-synthetic storage gate is active, this evidence must be synthetic,
  public-link-only, or stored in a protected manual research artifact with
  explicit consent, retention, reviewer access, and exclusion from product
  tables. Manual research artifacts must also have opaque participant IDs,
  access audit, DLP screening, revocation/purge path, retention expiry, owner
  review, and a prohibition on promotion into product tables before PR-006.
- Pre-product seed artifacts have a separate schema and cannot become product
  `experience_cards` by copying rows. After PR-006, promotion is one-way:
  regenerate the canonical candidate/card artifact through the accepted intake,
  redaction, consent, digest, review, and audit path, then link back to the
  seed artifact by opaque research ID only.

## PR-002: Protected-Data Durability

Status: blocked

Acceptance:

- Managed Postgres provider/topology is selected.
- Backup/WAL/PITR and restore drill are proven.
- Restored cluster starts quarantined and replays revocation/consent effects
  before serving.
- Production profile pins initial protected-data bounds before non-synthetic
  storage: RPO, RTO, restore-quarantine exit criteria, revocation replay SLA,
  connection-pool partitioning, P0 reserved capacity, and failover drill
  evidence. Exact numeric values may be private launch-control material, but
  the profile must expose public-safe labels and machine-checkable test
  fixtures.

## PR-003: Consent/Revocation Human UI

Status: blocked, draft scaffold implemented

Acceptance:

- Trusted approval and revocation surfaces exist.
- MVP launch-blocking consent gates are split and tested as
  `private_candidate_collection_consent`, `private_retention_consent`,
  `team_namespace_grant_consent`, `public_publication_consent`, and
  `intake_review_escrow_consent` when ambiguous raw ingress can enter a sealed
  human-review escrow.
- `*_consent` names are gate/check names. Canonical database consent scopes are
  defined in the data model and include separate scopes for private retention,
  private candidate collection, team namespace grants, public publication,
  intake review escrow, raw/source retention, derived artifacts, commercial use,
  and model/eval use. PR-003 must implement the MVP launch-blocking gates
  without collapsing or aliasing the deferred scopes. Scope aliases are invalid
  in schemas and tests; product surface names live in `surface_type` or policy
  metadata.
- Comprehension gate and accessibility baseline pass.
- Challenge creation and completion schemas cover handoff ID, opaque subject
  handle, digest, expiry, scope, trusted URL/OS handoff, step-up auth,
  completion outcomes, withdrawal, expiration, anti-enumeration failures, and
  serializable consent/tombstone/audit transaction order.
- Trusted surfaces include CSRF/state binding, frame-ancestor/clickjacking
  protection, exact redirect/origin validation, session binding to subject and
  challenge, replay tests, and malicious-client handoff fixtures.
- CLI/MCP can hand off but cannot complete private-retention,
  team-namespace-grant, or publication consent.

Current scaffold:

- `schemas/consent-revocation-gate.schema.json`
- `fixtures/consent-revocation-gate.draft.json`
- `scripts/validate_consent_revocation_gate.py`
- `docs/operations/consent-revocation-gate.md`
- `tests/test_consent_revocation_gate.py`

## PR-004: Non-Local Auth Verifier

Status: blocked, draft scaffold implemented

Acceptance:

- Local HS256 is disabled outside local dev.
- Asymmetric or KMS/Vault verifier profile is accepted and tested, including
  issuer, audience, environment/resource indicator, tenant-claim
  canonicalization, allowed algorithms, JWKS pin/cache/rotation, key revocation,
  DPoP or accepted sender-constrained proof validation, nonce/replay storage,
  clock skew, denylist consistency, outage behavior, and negative tests for
  HS256, `alg=none`, wrong audience, wrong issuer, stale key, stale nonce,
  proof/key mismatch, and cross-resource replay.
- Request-context backend can swap without RLS policy changes.

Current scaffold:

- `schemas/auth-verifier-gate.schema.json`
- `fixtures/auth-verifier-gate.draft.json`
- `scripts/validate_auth_verifier_gate.py`
- `docs/operations/auth-verifier-gate.md`
- `tests/test_auth_verifier_gate.py`

## PR-005: Public Search And Publication

Status: blocked

Acceptance:

- Public privacy attack model passes.
- Public company, place, service, career, or personal-reasoning surfaces are
  closed unless a domain policy explicitly permits the subject type, claim
  type, redaction class, moderation path, reporting path, stale-signal expiry,
  and public display copy.
- Private experience cards cannot be made public by changing namespace
  visibility. Public publication requires a new redacted artifact, exact
  approval, reviewer publish, and public eligibility checks.
- Single-observation negative impressions, staff/interviewer-level details,
  selection status, direct messages, exact dates, receipt/account identifiers,
  and private circumstances are rejected from public serving or routed to
  private-only retention.
- User-submitted public/company/place/service surfaces require an abuse identity
  enforcement lane before launch. Repeat malicious submissions must support
  investigation, ban, appeal, reinstatement, revoke, and purge while keeping
  identity signals out of public, B2B, respondent, and retrieval surfaces.
- Abuse budgets, reviewer QA, high-risk verification, consent/revocation E2E,
  public search thresholds, and cost circuits are accepted.
- Hostile-card and prompt-injection release gates pass, including renderer
  golden tests, seeded malicious-card corpus, prompt-injection pass-rate
  threshold, model/provider requalification, inline rollout kill switch,
  harmful-suggestion rollback drill, and full-body expansion tests.

Current blocked broader-surface preflights:

- `public:candidate-conversion` validates the item 9 public candidate
  conversion request contract. It requires a new redacted artifact digest and
  reports conversion blocked until exact-artifact approval, public search, core
  intake safety, and reviewer publish gates are accepted.
- `b2b:respondent-portal` validates the item 10 respondent portal request
  contract. It permits only a redacted response outline in preflight and keeps
  portal access, response availability, B2B delivery, public serving, identity
  processing, raw escrow, and dashboards disabled.
- `abuse:identity-enforcement` validates the item 11 real abuse identity and
  BAN operations preflight contract. It accepts only blocked/preflight requests:
  no identity resolution, no protected fingerprint creation, no subject rows,
  no real ban/rate-limit/suspension effects, no audit writes, and no public,
  B2B, respondent, retrieval, export, ranking, raw escrow, or dashboard
  exposure.
- `raw:detail-escrow` validates the item 12 raw detail escrow preflight
  contract. It accepts only blocked/preflight requests: no raw detail storage,
  no escrow handle, no encrypted payload, no key material, no reviewer lease or
  decrypt operation, no raw model input, no raw validator/audit/client echo,
  and no public, B2B, retrieval, export, ranking, identity, or dashboard
  exposure.
- `dashboard:company-store` validates the item 13 company/store dashboard
  preflight contract. It accepts only blocked/preflight requests: no dashboard
  serving, no aggregate signal query, no single-observation display, no
  review-suppression surface, no B2B delivery, no respondent portal, no public
  serving, no identity processing, no raw detail, no retrieval/export/ranking,
  and no private moderation or source-detail exposure.

## PR-005A: Public Documentation Release Gate

Status: blocked

Acceptance:

- Public README, landing routes, architecture explainers, and public `/architecture`
  pages require a signed public-document manifest before publication.
- Manifest generation checks source allowlists, source digests, allowed
  excerpts, launch-control threshold exclusions, private operational default
  exclusions, stale-review deadlines, rollback target, owner/reviewer signoff,
  and CI validation result.
- Withdrawal or stale review returns the public route to 404/410/pending without
  exposing internal docs.

## PR-006: Core Intake Safety Gate

Status: blocked, draft scaffold implemented

Acceptance:

- Database-side candidate intake safety gate is implemented for all
  non-synthetic candidate content before admission, body storage, redaction,
  review routing, indexing, or retrieval projection.
- `SubmitCandidate` request/response schema, scanner output schema, no-tool
  classifier output schema, coarse reason-code enum, audit event schema,
  quarantine metadata schema, and idempotent replay behavior are accepted.
- `SubmitCandidate` ingress bounds are machine-validated: max payload bytes,
  max canonical bytes, accepted encodings/content types, archive/decompression
  policy, streaming scanner cutoff, model-token cap, pre-parser rejection, and
  non-oracular oversized-payload response mapping.
- Derived-feature-only classifier fallback has a schema with exact feature
  fields, max cardinality, no-raw-value guarantees, output limits, and fixtures
  proving raw identifiers do not reach prompts, logs, or model inputs.
- Deterministic scanners and any classifier run under protected-data controls;
  external responses are non-oracular and never expose matched values, offsets,
  detector names, customer/repo existence hints, entropy scores, or classifier
  confidence.
- Database constraints or transactional tests prove no body is stored for
  `redact_then_retry`, `human_review_required`, or `reject`.
- `human_review_required` has either a sealed encrypted review escrow with TTL,
  reviewer step-up auth, audit, purge, and no-index guarantees, or it is
  disabled and ambiguous content returns `redact_then_retry`/`retry_later`.
- Raw ingress fingerprints use tenant-keyed HMAC or equivalent protected
  digests with key IDs, rotation, and security-only visibility; raw SHA digests
  are not exposed in audit, exports, client responses, or admin search.
- Gate outage, audit outage, model/provider outage, DLQ/replay, probing-budget,
  false-positive, and false-negative review paths are tested.
- Operation profile pins private launch-control labels for scanner/classifier
  deadlines, retry caps, queue max age/depth, circuit-open thresholds,
  per-tenant concurrency, reserved P0 capacity, classifier call caps, audit
  buffer limits, and load-shedding order.
- Provisional API, transaction-order, quarantine allowlist, audit durability,
  overload, and response-shape contracts in
  `docs/architecture/enterprise-governance.md` are replaced by
  machine-validated schemas and fixtures.
- The schema proves submitted payloads enter only through a volatile no-log gate
  boundary, and synthetic bypass is allowed only with server-verified fixture
  provenance.
- Search and hook ingress receive equivalent route-level protection before
  private/team search accepts non-synthetic profiles: max request bytes,
  accepted content types and encodings, compression/decompression policy, JSON
  depth and field-count caps, parser timeout, pre-instrumentation suppression,
  forbidden-field rejection fixtures, and non-oracular rejection mapping.

Current scaffold:

- `schemas/intake-safety-gate.schema.json`
- `fixtures/intake-safety-gate.draft.json`
- `scripts/validate_intake_safety_gate.py`
- `docs/operations/intake-safety-gate.md`
- `tests/test_intake_safety_gate.py`

## TNS-001: Trust-And-Safety Audit Schema

Status: blocked, draft scaffold implemented

Acceptance:

- Trust-and-safety audit schema defines case IDs, actor IDs, purpose binding,
  reason classes, decision digests, subject references, appeal references, and
  immutable event timestamps before real abuse identity processing starts.
- Abuse identity processing remains disabled in draft fixtures.
- Raw identity values are forbidden in fixtures; real subject rows remain
  `none` until protected fingerprint, encryption, role model, and access audit
  profiles are accepted.
- Business dashboards, respondent inquiry, public cards, retrieval panels,
  exports, and ranking features are forbidden identity-disclosure surfaces.
- Repeat malicious submission enforcement has appeal and reinstatement paths
  before high-confidence bans affect public or B2B-facing outputs.
- Negative tests prove identity signals do not leak to public, B2B,
  respondent, retrieval, export, or ranking surfaces.

Current scaffold:

- `schemas/trust-and-safety-audit-v0.schema.json`
- `fixtures/trust-and-safety-audit.draft.json`
- `scripts/validate_trust_and_safety_audit.py`
- `docs/operations/trust-and-safety-audit.md`
- `tests/test_trust_and_safety_audit.py`

## PR-007: Enterprise Governance

Status: blocked

Acceptance:

- Managed guidance schema, lifecycle, revocation, conflict handling, and audit
  events are implemented separately from experience cards.
- Trusted admin UI exists for creating, reviewing, activating, revoking, and
  inspecting enterprise directives, routing records, preferences, and guardrails.
- Agent clients can retrieve scoped guidance without allowing it to override
  platform, tool, user, consent, authorization, revocation, or local operator
  policy.
- Managed guidance uses server-attested `GuidanceContext`, a closed predicate
  schema, explicit decision precedence, guidance epochs, cache invalidation,
  probing budgets, and normalized no-guidance responses.
- High-impact guidance requires two-person approval, destination validation,
  step-up auth, signed payload digest, and emergency revocation drills.
- Enterprise-specific intake detector configuration composes with the core
  intake safety gate rather than replacing it.
- Reviewer audit loop measures sensitive-data misses and false-positive rates
  before non-synthetic enterprise ingestion is enabled.
- `get_managed_guidance` remains disabled or empty until the enterprise RFC
  defines physical schema, state machine, override records, guidance leases,
  rollout states, overload behavior, and migration tests.
- Search and action responses include a canonical `policy_decision` schema and
  signed guidance lease schema; no separate `policy_effect` API field exists.
- High-impact guidance leases are one-time or replay-detected and bind tenant,
  namespace, guidance, actor subject, proof key, integration, transport,
  operation, action parameters, idempotency key, context digest, destination,
  epochs, nonce, and expiry.
- `GuidanceActionIntent` schemas define per-operation canonical JSON,
  destination binding, action-parameter digest algorithm, host/tool
  normalization, and negative fixtures before any action-bound lease can be
  minted. `get_managed_guidance` remains read-only; action-bound leases require
  a dedicated preflight such as `prepare_guided_action` or an accepted equivalent
  schema.
- Host enforcement uses a registered host identity, signed capability statement,
  conformance version, lease-verification and deny-state fixtures,
  cache-invalidation tests, downgrade to `advisory_only` on missing proof, and
  audit events for every enforcement decision.
- Destination/integration registry schemas exist for high-impact routing:
  tenant-scoped keys, versioning, expiry, revocation, audit events, digest
  binding, and lease validation predicates.
- Enterprise admin/reviewer mutation routes are separated from agent-readable
  guidance routes, reject delegated-agent and MCP mutation attempts, and define
  scopes, transport restrictions, two-person approval, step-up auth, object
  predicates, override operations, audit events, and negative authorization
  tests.
