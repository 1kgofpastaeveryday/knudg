# Data Model

The database stores structured, compact, agent-readable cards rather than raw transcripts.

## Experience Card Fields

Canonical required fields:

- `card_id`: stable UUID
- `tenant_id`: owner tenant UUID, including public-card publisher tenant
- `namespace_id`: public/private/team/enterprise namespace UUID
- `visibility`: enum, one of `private`, `team`, `public`
- `card_schema_version`: integer
- `status`: enum, one of `candidate_created`, `pending_redaction`, `pending_review`, `awaiting_user_approval`, `approved`, `indexed_hot`, `indexed_main`, `rejected`, `superseded`, `deprecated`, `revoked`
- `goal`: non-empty text
- `symptom`: non-empty text
- `environment`: structured object
- `context_fingerprint`: structured object with normalized public identifiers
- `successful_path`: ordered list, nullable until solved
- `failed_paths`: ordered list, default empty
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
  quality_state: "solved_once"
  status: "approved"
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
- `card_events`: append-only state changes with actor, event type, previous state, next state, and idempotency key
- `consent_records`: approval, revocation, expiration, and payload digest binding
- `card_edges`: supersedes, deprecated_by, contradicts, duplicate_of, variant_of
- `source_artifacts`: private candidate metadata and object storage manifests
- `search_index_manifests`: index generation, source event range, processor version, and replay hash
- `audit_events`: append-only security and governance trail

Required constraints:

- tenant-scoped tables include `tenant_id`
- cross-table foreign keys include `tenant_id` where applicable
- card versions are immutable
- one current version per card
- one active public approval per public card version
- state transitions must follow the transition table
- unique idempotency keys for ingestion, approval, indexing, and state transitions
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
  -> pending_redaction
  -> pending_review
  -> awaiting_user_approval
  -> approved
  -> indexed_hot
  -> indexed_main

candidate_created -> rejected
pending_redaction -> rejected
pending_review -> rejected
awaiting_user_approval -> rejected
indexed_hot -> superseded
indexed_main -> superseded
indexed_hot -> deprecated
indexed_main -> deprecated
indexed_hot -> revoked
indexed_main -> revoked
```

No state transition can skip redaction or review for public cards. `revoked` blocks retrieval immediately. Physical deletion is separate from logical revocation and must respect audit, legal, and retention rules.

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
