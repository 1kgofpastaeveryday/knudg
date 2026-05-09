# Data Model

The database stores structured, compact, agent-readable cards rather than raw transcripts.

## Experience Card Fields

Canonical required fields:

- `card_id`: stable UUID
- `tenant_id`: owner tenant UUID, including public-card publisher tenant
- `namespace_id`: public/private/team/enterprise namespace UUID
- `visibility`: enum, one of `private`, `team`, `public`
- `card_schema_version`: integer
- `status`: enum, one of `candidate_created`, `pending_admission`, `deferred`, `pending_redaction`, `pending_review`, `awaiting_user_approval`, `approved_private`, `approved_for_publication`, `published`, `indexed_hot`, `indexed_main`, `rejected`, `superseded`, `deprecated`, `revoked`
- `outcome_type`: enum, one of `solved`, `failed_only`, `inconclusive`, `unknown_clarified`
- `goal`: non-empty text
- `symptom`: non-empty text
- `environment`: structured object
- `context_fingerprint`: structured object with normalized public identifiers
- `successful_path`: ordered list, nullable until solved
- `failed_paths`: ordered list, default empty
- `known_unknowns`: ordered list, default empty
- `scope_limits`: ordered list, default empty
- `evidence_strength`: enum, one of `single_session`, `multi_session`, `reproduced`, `external_reference`, `operator_judgment`
- `twist`: nullable text
- `quality_state`: enum, one of `unreviewed`, `solved_once`, `solved_many`, `verified`, `disputed`
- `privacy`: structured object
- `provenance`: structured object
- `quality_score`: numeric, nullable until indexed
- `created_at` and `updated_at`: timestamps

Optional fields:

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
  visibility: "private"
  card_schema_version: 1
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
    approval: "user_approved_public"
    redactions:
      - "repo name"
      - "absolute paths"
      - "tokens"
  provenance:
    source_event_id: "uuid"
    contributor_id: "uuid"
    reviewer_id: null
    card_version_id: "uuid"
    content_hash: "sha256:..."
  quality_score: null
```

## Canonical Tables

The vector index is never the source of truth. The canonical model is an append-only event log with derived current-state projections.

Core tables:

- `namespaces`: public/private/team/enterprise namespace metadata
- `experience_cards`: stable card identity, `tenant_id`, namespace, current state, latest version
- `card_versions`: immutable redacted card versions, schema version, content hash, model/toolchain metadata
- `card_events`: append-only state changes with actor, event type, previous state, next state, aggregate sequence, expected version, causation/correlation IDs, and idempotency key
- `consent_records`: approval, revocation, expiration, and payload digest binding
- `derived_artifacts`: canonical trails, curated packs, aggregate metadata, source manifests, and consent inheritance policy
- `revocation_tombstones`: mandatory read-path deny records for cards, card versions, source artifacts, derived artifacts, and index generations
- `card_edges`: supersedes, deprecated_by, contradicts, duplicate_of, variant_of
- `source_artifacts`: private candidate metadata and object storage manifests
- `search_index_manifests`: index generation, source event range, processor version, and replay hash
- `audit_events`: append-only security and governance trail

Required constraints:

- tenant-scoped tables use `(tenant_id, id)` primary or unique keys
- cross-table foreign keys include `tenant_id`
- card versions are immutable
- one current version per card
- one active public approval per public card version
- derived artifacts must reference source card versions and consent inheritance policy
- state transitions must follow the transition table
- unique idempotency keys for ingestion, approval, indexing, and state transitions
- per-card event sequence is unique as `(tenant_id, card_id, event_seq)`
- outcome type, quality state, and evidence strength must satisfy compatibility checks
- index rows must point back to card version, source event, processor version, and content hash

## Idempotency

Idempotency key format:

```text
tenant_id + operation + logical_object_id + operation_version + request_digest
```

Keys are retained for at least 90 days for user/API operations and at least 1 year for indexing, compaction, migration, and replay operations. The implementation may retain them longer if the replay window is longer. A key collision with a different request digest is a hard error. A key replay with the same request digest returns the original effect.

## Card Lifecycle

State transitions are explicit:

```text
candidate_created
  -> pending_admission
  -> pending_redaction
  -> pending_review
  -> awaiting_user_approval
  -> approved_private
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
approved_private -> rejected
approved_private -> revoked
approved_for_publication -> rejected
approved_for_publication -> revoked
published -> revoked
published -> deprecated
published -> superseded
indexed_hot -> superseded
indexed_main -> superseded
indexed_hot -> deprecated
indexed_main -> deprecated
indexed_hot -> revoked
indexed_main -> revoked
```

No public state transition can skip redaction, review, user approval, and reviewer publish. `revoked` blocks retrieval immediately through `revocation_tombstones`, even if projections or indexes are stale. Physical deletion is separate from logical revocation and must respect audit, legal, and retention rules.

Admission is allowed to defer or reject low-novelty, duplicate, abusive, or over-quota candidates before redaction/review. It must not mark a card as true or false.

`deferred` is a re-evaluation state, not a final state. Deferred candidates require a reason code, retry-after timestamp, and owning queue. They can return to `pending_admission` or move to `rejected`.

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
| `published` | not until indexed | authorized owner/reviewer; public only after indexed |
| `indexed_hot` | yes | namespace and tenant policy |
| `indexed_main` | yes | namespace and tenant policy |
| `rejected` | no | owner/reviewer only |
| `superseded` | explicit only | provenance/replacement views only |
| `deprecated` | explicit only | provenance/replacement views only |
| `revoked` | never | audit/admin only |

Every read still checks revocation tombstones first.

## Outcome Semantics

Outcome type controls how a card is searched and injected:

- `solved`: has a successful path and may be ranked as a candidate fix
- `failed_only`: has useful failed paths but no successful path
- `inconclusive`: records work that did not settle the issue but narrows the search space
- `unknown_clarified`: records a known unknown, missing dependency, invalid assumption, or boundary that future agents should know

Unknown and failed-only cards are not second-class data. They need embeddings, exact-match fingerprints, provenance, and quality scoring because the product should preserve experience, not only recipes.

Outcome compatibility rules:

- `solved` requires a non-empty `successful_path`
- `failed_only` requires a non-empty `failed_paths` and an empty `successful_path`
- `unknown_clarified` requires a non-empty `known_unknowns`
- `verified` requires `evidence_strength` of `reproduced` or `external_reference`
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
