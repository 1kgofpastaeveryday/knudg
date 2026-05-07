# Architecture Overview

Knudg is central infrastructure, not local-first storage. Local state should be limited to temporary current-work summaries, pending writer approval queues, and recent retrieval caches.

The central service manages:

- public experience database
- private/team namespaces
- consent records
- search indexes
- quality signals
- deprecation status
- contributor/reviewer reputation
- billing/rate limits

## Recommended Early Architecture

```text
API/Auth/Billing:
  Cloudflare Workers or a small API server

Canonical metadata:
  Postgres

Raw/card object storage:
  Cloudflare R2 or S3

Keyword search:
  Postgres FTS first

Vector search:
  pgvector first

Queue:
  one explicitly chosen queue with documented delivery semantics
```

For MVP deployment, the implementation must pin exact providers in an implementation RFC. This architecture document intentionally allows R2 or S3 because provider choice is deployment-dependent; the invariant is immutable object manifests, encryption, tenant scoping, retention policy, and canonical DB linkage.

## Write Pipeline

Writing is asynchronous and stateful.

State inventory:

- `candidate_created`
- `pending_redaction`
- `pending_review`
- `awaiting_user_approval`
- `approved`
- `indexed_hot`
- `indexed_main`
- `rejected`
- `superseded`
- `deprecated`
- `revoked`

The canonical lifecycle is defined in [Data Model](data-model.md). This list is an enum inventory, not an alternate ordering.

Do not immediately push every approved card into the main index. Use a small hot index for recent cards, then batch compact into the main index.

Queue processing is at-least-once. Every worker action must be idempotent at the database layer. The queue does not define correctness; Postgres constraints, idempotency keys, and reconciliation jobs do.

Required worker rules:

- each ingestion, approval, redaction, review, indexing, compaction, deprecation, and revocation job has an idempotency key
- retries use bounded exponential backoff with jitter
- poison jobs move to a dead-letter queue after the retry cap
- stranded intermediate states are found by a sweeper
- every derived index entry can be rebuilt from canonical events
- duplicate queue delivery must not create duplicate cards, approvals, or index entries
- state transitions are monotonic except for explicit rejection, deprecation, supersession, or revocation transitions

## Scaling Principle

The database can become extremely large, but the searchable surface should stay compressed.

Raw sessions and repeated work should be transformed into canonical experience trails:

```text
many similar solved cards
  -> cluster
  -> canonical trail
  -> environment-specific variants
  -> deprecated/superseded links
  -> compact agent-readable card
```

Compression must preserve the details that make a fix valid. Canonical trails should keep environment-specific variants instead of collapsing them away.

Variant dimensions:

- operating system
- language/runtime version
- package manager
- framework version
- dependency version
- cloud provider
- agent tool and version
- exact error signature
- command or API surface involved

Cards can be linked as `variant_of` only when the successful path is materially the same under the relevant environment constraints. Contradictory fixes must be linked as `contradicts`, not merged.
