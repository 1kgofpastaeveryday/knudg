# Data Model

The database stores structured, compact, agent-readable cards rather than raw transcripts.

Logical card views combine immutable version payloads with current-state
projections. `card_versions.payload_json` is the source of truth for
version-scoped semantic content. `experience_cards`, namespace rows, event
state, and consent/revocation rows are the source of truth for identity,
visibility, lifecycle, approval, and deny decisions.

## Experience Card Fields

Record/projection-owned required fields:

- `card_id`: stable UUID
- `tenant_id`: owner tenant UUID, including public-card publisher tenant
- `namespace_id`: public/private/team/enterprise namespace UUID
- `visibility_view`: read-model/generated-view field derived from namespace visibility; not a base `experience_cards` column and not stored in `payload_json`
- `card_schema_version`: integer
- `status`: lookup key, one of `candidate_created`, `pending_admission`, `deferred`, `pending_redaction`, `pending_review`, `awaiting_user_approval`, `approved_private`, `approved_for_publication`, `discard_pending`, `publication_withdrawn`, `published`, `indexed_hot`, `indexed_main`, `rejected`, `superseded`, `deprecated`, `revoked`
- `quality_score`: derived score, nullable until indexed
- `created_at` and `updated_at`: timestamps

Version payload required fields:

- `domain`: lookup key, initially `technical_work`,
  `personal_reasoning`, `career_private`, `place_service_experience`,
  `public_experience_candidate`, or `public_aggregate_signal`
- `experience_intent`: domain-specific lookup key such as `solved_path`,
  `failed_path`, `decision_revisited`, `company_experience`,
  `interview_experience`, `place_experience`, `service_quality_signal`, or
  `public_aggregate_signal`
- `subject`: structured object for the public or private subject of the
  experience; for technical cards this may be package/tool/environment
  metadata, and for company/place/service cards it may include a public subject
  name while keeping people, selection details, and private identifiers out of
  the public payload
- `claim_type`: lookup key, one of `factual_observation`,
  `subjective_impression`, `inference`, `aggregate_summary`, or
  `unverified_report`
- `outcome_type`: lookup key, one of `solved`, `failed_only`, `inconclusive`, `unknown_clarified`
- `goal`: non-empty text
- `symptom`: non-empty text
- `environment`: structured object
- `context_fingerprint`: structured object with normalized public identifiers
- `successful_path`: ordered list, nullable until solved
- `failed_paths`: ordered list, default empty
- `known_unknowns`: ordered list, default empty
- `observations`: ordered list, default empty; required when
  `outcome_type=inconclusive` unless `eliminated_hypotheses` is non-empty
- `eliminated_hypotheses`: ordered list, default empty; required when
  `outcome_type=inconclusive` unless `observations` is non-empty
- `scope_limits`: ordered list, default empty
- `evidence_strength`: lookup key, one of `single_session`, `multi_session`, `reproduced`, `external_reference`, `operator_judgment`
- `twist`: nullable text
- `quality_state`: lookup key, one of `unreviewed`, `solved_once`, `solved_many`, `verified`, `disputed`
- `safety`: structured object with `safety_class`, executable-advice flags, URL/package/repository indicators, credential/billing/deletion/network-call indicators, verification state, and withheld reason when blocked
- `privacy`: structured object
- `provenance`: structured object

Optional fields:

- `domain_policy`: structured object with retrieval policy, public eligibility,
  retention default, redaction class, and cross-domain search restrictions
- `deprecation`: structured object with reason, replacement, and event ID
- `supersession`: structured object with replacement card ID and event ID
- `contradictions`: list of linked card IDs
- `embedding_refs`: list of vector records by model/version

Example:

```yaml
experience_card:
  card_id: "uuid"
  tenant_id: "uuid"
  namespace_id: "uuid"
  visibility_view: "private"
  card_schema_version: 1
  domain: "technical_work"
  experience_intent: "solved_path"
  subject:
    type: "technical_environment"
    public_name: null
  claim_type: "factual_observation"
  outcome_type: "solved"
  goal: "setup X in a Node monorepo"
  symptom: "dependency Y is deprecated"
  environment:
    os: "macOS"
    language: "Node.js"
    package_manager: "pnpm"
    agent_tool: "Codex"
  context_fingerprint:
    packages:
      - "Y"
    error_signature: "ERR_PACKAGE_PATH_NOT_EXPORTED"
    repo_shape: "vite + pnpm + monorepo"
  twist: "official docs still mention the deprecated package"
  successful_path:
    - "replace Y with Z"
    - "pin version A"
  failed_paths:
    - "reinstalling Y"
    - "clearing package manager cache"
    - "using old install script"
  known_unknowns:
    - "whether package Z works on Windows is not verified"
  scope_limits:
    - "validated only on pnpm major version 9"
  evidence_strength: "single_session"
  quality_state: "solved_once"
  status: "approved_private"
  privacy:
    approval: "private_approved"
    redactions:
      - "repo name"
      - "absolute paths"
      - "tokens"
  provenance:
    source_event_ref: "card:<uuid>@stream:<position>"
    contributor_id: "uuid"
    reviewer_id: null
  quality_score: null
```

Domain fields are logical schema requirements for future generalized
experience cards. The closed-launch local-private implementation may continue
using its constrained payload shape until the migration/design pass updates the
physical card schema. The current model scopes cards to technical work only; broader personal,
career, company, place, or service domains were retired (see
[target-model.md](target-model.md)).

## Canonical Tables

The vector index is never the source of truth. The canonical model is an append-only event log with derived current-state projections.

Core tables:

- `namespaces`: public/private/team/enterprise namespace metadata
- `abuse_subjects`: protected anti-abuse identity and enforcement subjects
  keyed by tenant/service scope, using protected fingerprints and encrypted raw
  identifiers only when policy requires them; not card content and not
  searchable experience
- `abuse_events`: append-only trust-and-safety decisions, evidence digests,
  actor, case reason, enforcement state transitions, appeal/reinstatement, and
  correlation to affected candidate/card IDs without exposing raw identity
  values
- `managed_guidance`: enterprise-scoped instruction, routing, and guardrail objects with owner, reviewer, scope predicates, strength, lifecycle, effective window, digest, and override policy
- `managed_guidance_events`: append-only lifecycle, review, revocation, read, conflict, and override-request events for managed guidance
- `candidate_intakes`: pre-admission intake rows for non-synthetic submit idempotency, protected input fingerprint, gate verdict, coarse reason classes, escrow state, expiry, and audit correlation
- `candidate_review_escrows`: encrypted, TTL-bound, single-use human-review leases for ambiguous raw ingress; not candidate bodies, not indexed, not model-readable, and purged or rejected on expiry
- `intake_submissions`: exact-consent binding artifacts for submitted payloads before sealed review escrow; store only tenant, namespace, intake ID, protected fingerprint, tenant-keyed `protected_artifact_digest`, digest key ID/profile, source-class summary, TTL, and policy/challenge references; not card bodies, not indexed, and not retrieval subjects
- `experience_cards`: stable card identity, `tenant_id`, namespace, current state, latest version, and rebuildable semantic projections from the current version
- `card_versions`: immutable redacted card versions with `payload_json jsonb` as the canonical card body, schema version, deterministic payload digest, and model/toolchain metadata
- `redacted_private_experience_records`: dormant DDL scaffold for future
  career/place/service experience storage after redaction; no app/worker write
  grant, not retrieval-visible, no raw source, no raw escrow, and no
  public/B2B/identity/dashboard enablement
- `card_events`: append-only state changes with actor, event type, previous state, next state, per-card sequence, global event stream position, expected version, causation/correlation IDs, and idempotency key
- `consent_records`: approval, revocation, expiration, and exact artifact/policy/challenge digest binding
- `derived_artifacts`: canonical trails, curated packs, aggregate metadata, source manifests, and consent inheritance policy
- `revocation_tombstones`: mandatory read-path deny records for tenants, namespaces, cards, card versions, source artifacts, derived artifacts, and index generations
- `card_edges`: supersedes, deprecated_by, contradicts, duplicate_of, variant_of
- `verification_records`: active and historical verification/reproduction records keyed by card version with reviewer identity, environment, inputs/outputs evidence digests, version bounds, remaining risk, authorization, and revocation state
- `source_artifacts`: private candidate metadata and object storage manifests
- `search_index_manifests`: index generation, global event stream source range, processor version, and replay hash
- `audit_events`: append-only security and governance trail
- `public_card_handles`: future public-search handle table with route scope,
  random opaque handle, tenant/card/version FK, generation, expiry, revoked
  state, rotation event, and audit relation. It is deferred until public search
  gates; public routes must not expose internal card IDs.

Signed release artifacts outside M0 product tables:

- `public_doc_manifests`: signed public-document release artifact with route
  binding, source allowlist, source digests, allowed excerpts, exclusion checks,
  owner, reviewer, review date, stale-review deadline, security/privacy contact,
  state (`absent`, `draft_internal`, `signed_public`, `withdrawn`), rollback
  target, and CI validation result. It is stored with release artifacts, not in
  M0 card tables, unless a later RFC moves public-doc governance into product
  storage.

M0 physical inclusion matrix:

| Table | M0 physical status | Notes |
|---|---|---|
| `namespaces` | real M0 | required for tenant/namespace scoping |
| `abuse_subjects` | deferred until broader-domain or public submission gate | not needed for closed-launch operator-only path; required before user-submitted public/company/place/service surfaces |
| `abuse_events` | deferred until broader-domain or public submission gate | append-only enforcement/audit lane; no public or business-facing identity disclosure |
| `managed_guidance` | deferred until enterprise milestone | design contract only; no M0 FK depends on it |
| `managed_guidance_events` | deferred until enterprise milestone | design contract only; guidance is not an experience card |
| `candidate_intakes` | real M0/M1 before non-synthetic submit | required before any non-synthetic candidate body persistence |
| `intake_submissions` | real M0/M1 before non-synthetic review escrow | digest-only artifact binding for exact `intake_review_escrow` consent; no raw body |
| `candidate_review_escrows` | real only if `human_review_required` is enabled | otherwise ambiguous raw intake must return `redact_then_retry` or `retry_later` |
| `experience_cards` | real M0 | canonical card identity and current pointer |
| `card_versions` | real M0 | immutable redacted payload versions |
| `redacted_private_experience_records` | dormant DDL scaffold | physical table shape for item 8; product writes, retrieval visibility, public conversion, B2B delivery, identity processing, raw escrow, and dashboards remain blocked |
| `card_events` | real M0 | append-only lifecycle/event source |
| `consent_records` | real M0 | minimum private/public approval and termination model |
| `revocation_tombstones` | real M0 | read-path deny fence |
| `card_edges` | real M0 | supersession/deprecation/duplicate links |
| `verification_records` | deferred until verified/high-risk display | required before `quality_state=verified` can be emitted |
| `audit_events` | real M0 | security/governance trail |
| `public_card_handles` | deferred until public search | no public search in M0; define before M6/DEC-013 public handles |
| `public_doc_manifests` | release artifact, not M0 table | required before any public `/architecture` route; governed by Operations public-document state machine |
| `derived_artifacts` | do not create in M0 | no M0 FK requires it; derived/commercial/curated-pack behavior is deferred |
| `source_artifacts` | do not create in M0 | no raw/source storage behavior in M0; private candidate metadata lives in card/admission rows until a storage RFC accepts object storage |
| `search_index_manifests` | empty FK placeholder only if revocation tombstones require it | otherwise do not create in M0; index generation behavior starts in retrieval/index milestones |

This matrix distinguishes logical canonical concepts from physical M0 tables.
RFC 0001 must follow the matrix for M0 migrations unless this document is
updated in the same change.

Required constraints:

- tenant-scoped tables use `(tenant_id, id)` primary or unique keys
- cross-table foreign keys include `tenant_id`
- abuse identity tables are not experience-card tables. They support
  submission denial, hold-for-review, ban, appeal, reinstatement, revocation,
  and purge, but are never indexed for retrieval and are never exposed to
  public or respondent/business surfaces.
- protected identity fingerprints must be keyed, rotatable, scoped by purpose,
  and non-enumerable. Raw identifiers require encryption, TTL or retention
  class, case-scoped access, and audit.
- domain is a retrieval and consent boundary. Cross-domain search requires
  explicit authorization and response labeling; public search can read only
  public artifacts and public aggregate signals, never private domains.
- company, place, and product names may be stored as subject names when policy
  allows, but person-level details, selection status, private messages, exact
  dates, account/receipt IDs, and non-public operational details are redacted by
  default.
- managed guidance is not stored in `experience_cards`, is never indexed as a solved path, and must have an active approval, effective window, non-revoked state, and deterministic payload digest before delivery
- `candidate_intakes.protected_input_fingerprint` is a tenant-keyed HMAC or equivalent protected fingerprint, never a public raw-content digest
- card versions are immutable
- one current version per card, enforced only by `experience_cards.current_version_id`
- one active public approval per public card version
- consent records carry explicit `scope` (`private_candidate_collection`, `private_retention`, `team_namespace_grant`, `public_publication`, `intake_review_escrow`, `raw_source_retention`, `derived_artifact`, `commercial_use`, `model_eval_use`), optional `surface_type` for product-specific derived surfaces, subject type, artifact/version binding, challenge digest, expiry, and termination event; scopes never inherit permission from each other
- consent scope enum values are canonical. Deprecated aliases such as `public_publish`, `canonical_trail`, `aggregate_stats`, `verified_rewrite`, `curated_pack`, `commercial_derived`, and `model_eval` are not valid `consent_records.scope` values; if product surfaces use those names, they must be stored as `surface_type` or policy metadata under the canonical scope and must fail closed if treated as scope values.
- derived artifacts must reference source card versions and consent inheritance policy
- state transitions must follow the transition table
- unique idempotency keys for ingestion, approval, reviewer publish, indexing, and state transitions
- per-card event sequence is unique as `(tenant_id, card_id, event_seq)`
- global `event_stream_position` is monotonic across card and domain events and is the only freshness cursor for projections and indexes
- outcome type, quality state, and evidence strength must satisfy compatibility checks
- index rows must point back to card version, source event, processor version, and content hash

M0 stores canonical version payload fields in `card_versions.payload_json
jsonb`. `payload_json` must satisfy the schema for `card_schema_version` before
insert, must omit projection-owned fields such as tenant, namespace,
visibility, status, timestamps, and current-version pointer, and
`payload_digest` must be computed from the canonicalized JSON. Version payloads
and digests are immutable at the database layer; later corrections create a
new version.

`experience_cards` may cache payload-derived fields such as `outcome_type`,
`quality_state`, and `evidence_strength` for query planning, but those
projections are updated only by the event append path and are rebuildable from
the current version plus event log. Namespace visibility remains the only
visibility source of truth.

Consent records are artifact-specific. A public approval must bind the exact
card version or derived artifact that was shown to the user, the approval
policy version and digest, and the challenge ID and digest. At most one active
public approval may exist for a card version. Publish and derived-use checks
must fail closed if any bound value differs from the active artifact or policy.

## Idempotency

Idempotency key format:

```text
tenant_id + operation + logical_object_type + logical_object_id + operation_version + idempotency_key
```

`request_digest` is stored with the key but is not part of the uniqueness scope. For mutating operations, durable effect identity is permanent; `expires_at` may expire the cached response body, but it must not allow the same logical idempotency key to create a second mutation. Non-mutating operations may define shorter replay windows only in their own operation class. A key collision with a different request digest is a hard error. A key replay with the same request digest returns the original effect reference or retained response.

## Card Lifecycle

The `status` enum, visibility matrix, and transition summary in this document
are the M0 implementation baseline. RFC 0001 may provide additional rationale
or transition tests, but it must not add lifecycle states, public visibility, or
publication paths unless this data-model document is updated in the same change.
If RFC 0001 conflicts with this file, this file wins for implementation.

`indexed_hot` and `indexed_main` are current serving-eligibility projections in
the card status enum, not a substitute for index membership rows. Real index
membership remains generation-specific and must be represented by index
projection tables/manifests keyed by card version, index kind, index generation,
processor version, source event range, content hash, and revocation epoch.

State transitions are explicit. Private approval and public publication are
separate branches:

```text
candidate_created
  -> pending_admission
  -> pending_redaction
  -> pending_review
  -> awaiting_user_approval
  -> approved_private

pending_review
  -> awaiting_user_approval
  -> approved_for_publication
  -> published
  -> indexed_hot
  -> indexed_main

candidate_created -> rejected
pending_admission -> deferred
deferred -> pending_admission
deferred -> rejected
pending_admission -> rejected
pending_redaction -> rejected
pending_review -> rejected
awaiting_user_approval -> rejected
awaiting_user_approval -> pending_redaction
approved_private -> revoked
approved_private -> indexed_hot
approved_private -> indexed_main
approved_for_publication -> publication_withdrawn
approved_for_publication -> pending_redaction
approved_for_publication -> rejected
approved_for_publication -> revoked
publication_withdrawn -> awaiting_user_approval
publication_withdrawn -> revoked
candidate_created -> discard_pending
pending_admission -> discard_pending
deferred -> discard_pending
pending_redaction -> discard_pending
pending_review -> discard_pending
awaiting_user_approval -> discard_pending
discard_pending -> pending_review
discard_pending -> revoked
rejected -> revoked
published -> revoked
published -> deprecated
published -> superseded
indexed_hot -> superseded
indexed_main -> superseded
indexed_hot -> deprecated
indexed_main -> deprecated
indexed_hot -> revoked
indexed_main -> revoked
superseded -> revoked
deprecated -> revoked
```

`approve_private` is emitted only by the trusted
`complete_private_retention_approval` human-session endpoint. It records user
consent for exact private retention and moves `awaiting_user_approval` to
`approved_private`. `approved_private` is not a public-publication
precondition. It may become `indexed_hot` or `indexed_main` only inside
authorized private/team index projections whose namespace policy,
private-retention consent, revocation epoch, and safety metadata are current.
Those projections are not public search eligibility and must not create public
handles.

Later public publication from a private card creates a new `experience_card`
in the public candidate branch only after the trusted source-owner
`complete_publication_from_private_request` handoff completes and a validated
redacted first-version payload is ready. If the handoff is complete but no
redacted first version exists yet, the system records only a redaction work
item or retryable handoff state and creates no public card row. The new public
card is created at `candidate_created`, then advances through the normal
admission, redaction, review, user public-approval, and reviewer-publish
events. It is linked to the private source by a non-public
`derived_from_private_card` edge visible only to authorized owner/reviewer
contexts. It has its own card ID, lifecycle, namespace, version digest,
approval challenge, consent record, review result, and abuse/safety gates. It
must not mutate the existing private card out of `approved_private`,
`indexed_hot`, or `indexed_main`, and it cannot reuse private-retention consent
as public-publication consent.

`complete_publication_approval` records user consent for the exact public artifact and
moves `awaiting_user_approval` to `approved_for_publication`; it does not
publish. `reviewer_publish` is the only operation that can move
`approved_for_publication` to `published`, and it must recheck redaction,
review outcome, approval digest, derived-use policy, namespace eligibility, and
abuse gates at transition time.

If a reviewer rejects after public approval, `approved_for_publication` may move
to `rejected`. The transaction terminates or invalidates the active
`public_publication` consent for that exact artifact, writes the rejection
reason, and prevents `reviewer_publish`. Preserving any private copy requires a
separate private-retention consent path; public approval never implies private
retention.

No public state transition can skip redaction, review, user approval, and reviewer publish. Revocation can run from any non-revoked state visible to a user, including rejected, superseded, and deprecated cards. `revoked` blocks retrieval immediately through `revocation_tombstones`, even if projections or indexes are stale. Physical deletion is separate from logical revocation and must respect audit, legal, and retention rules.

Revocation creates both a `revoked` event and one or more tombstones. Tombstone
epochs are tenant-local monotonic counters; all tombstones from one revoke
operation share `revocation_epoch`, one typed event reference, and `revoked_by`.
Card and card-version revocations reference the card lifecycle event; tenant,
namespace, artifact, and index-manifest revocations reference a domain event.

Admission is allowed to defer or reject low-novelty, duplicate, abusive, or over-quota candidates before redaction/review. It must not mark a card as true or false.

Before admission, non-synthetic candidate intake must pass an intake safety gate.
The gate records scanner and classifier versions, reason codes, verdict, escrow
state, and whether any body was stored. Its internal verdict enum is `accept`,
`redact_then_retry`, `human_review_required`, `reject`, or `retry_later`.
`redact_then_retry`, `human_review_required`, and `reject` store no candidate
body. `human_review_required` stores a `candidate_intakes` metadata row and,
only when enabled, a sealed `candidate_review_escrows` lease for human review;
otherwise it degrades to `redact_then_retry` or `retry_later`. A model-assisted
gate can tighten or block intake, but it cannot approve publication, bypass
deterministic scanner findings, or bypass consent.

The gate is core ingestion behavior, not enterprise-only behavior. Enterprise
deployments may add tenant-specific detector configuration, but every
non-synthetic candidate path must satisfy the base gate before candidate body
storage. The M1 physical schema must include a constraint or equivalent
transactional invariant proving that `body_stored = false` whenever the intake
verdict is `redact_then_retry`, `human_review_required`, or `reject`.

Publication, withdrawal, and revocation transitions use one serializable
transition protocol. The transaction locks the card row, current version,
active consent record, applicable approval challenge, tombstone subject rows,
and current tenant revocation epoch. It then checks expected status/version and
active consent scope, writes exactly one lifecycle or consent event with the
next global event position, creates required tombstones for withdrawal or
revocation, and only then updates current-state projections. If
`reviewer_publish` races with `withdraw_publication_approval` or `revoke`, the
loser returns the already-committed terminal result and cannot publish.

`deferred` is a re-evaluation state, not a final state. Deferred candidates require a reason code, retry-after timestamp, and owning queue. They can return to `pending_admission` or move to `rejected`.

`discard_pending` is the undoable user-discard state. It removes private
retrieval projections immediately, starts the undo window, and can restore to
`pending_review` only during that window. When the undo window expires or the
user confirms discard, it moves to `revoked`; physical purge is a post-revoke
cleanup job/effect, not a lifecycle state. `rejected` is a review/audit
terminal state and is not the undo state.

`publication_withdrawn` is the post-approval withdrawal state. It invalidates
reviewer publish, terminates the public consent, creates read-path tombstones
for the affected public artifact/card version/index subjects when any public
projection could exist, and can start a separate private-retention challenge by
returning to `awaiting_user_approval`. It does not silently create
`approved_private`.

## Visibility Matrix

| Status | Searchable | Reader scope |
|---|---|---|
| `candidate_created` | no | owner/reviewer only |
| `pending_admission` | no | owner/reviewer only |
| `deferred` | no | owner/reviewer only |
| `pending_redaction` | no | owner/reviewer only |
| `pending_review` | no | owner/reviewer only |
| `awaiting_user_approval` | no | owner/reviewer only |
| `approved_private` | no public search | owner/shared tenant only |
| `approved_for_publication` | no public search | owner/reviewer only |
| `discard_pending` | no; private retrieval projections removed | owner only during undo window; reviewer audit as policy allows |
| `publication_withdrawn` | no | owner/reviewer only until private-retention decision or revocation |
| `published` | not until indexed | authorized owner/reviewer; public only after indexed |
| `indexed_hot` | yes | namespace and tenant policy |
| `indexed_main` | yes | namespace and tenant policy |
| `rejected` | no | owner/reviewer only when retained for review/audit |
| `superseded` | explicit only | provenance/replacement views only |
| `deprecated` | explicit only | provenance/replacement views only |
| `revoked` | never | audit/admin only |

Every read still checks revocation tombstones first.

## Outcome Semantics

Outcome type controls how a card is searched and injected:

- `solved`: has a successful path and may be ranked as a candidate fix
- `failed_only`: has useful failed paths but no successful path
- `inconclusive`: records work that did not settle the issue but narrows the search space; it is never ranked or labeled as a candidate fix
- `unknown_clarified`: records a known unknown, missing dependency, invalid assumption, or boundary that future agents should know

Unknown and failed-only cards are not second-class data. They need embeddings, exact-match fingerprints, provenance, and quality scoring because the product should preserve experience, not only recipes.

Outcome compatibility rules:

- `solved` requires a non-empty `successful_path`
- `failed_only` requires a non-empty `failed_paths` and an empty `successful_path`
- `inconclusive` requires a non-empty `observations` or `eliminated_hypotheses`, an empty `successful_path`, and no `verified` quality state unless the verification record proves only the observation, not a fix
- `unknown_clarified` requires a non-empty `known_unknowns`
- `verified` requires `evidence_strength` of `reproduced` or `external_reference` and a linked active verification record containing reviewer identity, verification activity, environment, input/output evidence, version bounds, remaining risk, and external-reference manifest when applicable
- `solved_many` requires `evidence_strength` of `multi_session`, `reproduced`, or `external_reference`
- `disputed` requires at least one `contradicts` edge or dispute event

## Versioning and Migration

Cards, APIs, indexes, embeddings, and storage manifests all need explicit versions.

Required version fields:

- `card_schema_version`
- `api_version`
- `embedding_model`
- `embedding_dimension`
- `processor_version`
- `index_generation`
- `agent_tool`
- `agent_tool_version`

Schema changes must use expand/contract migrations. Large-table constraints and indexes must be introduced with lock-aware phased migrations. Rollback plans must be written before changes that affect card visibility, authorization, storage layout, or index semantics.

Index and embedding migrations must support dual-read or dual-write during cutover. The first wedge implementation RFC must define canary namespace behavior, cold-card re-embedding deferral, rollback criteria, and revocation replay SLA for every index generation.
