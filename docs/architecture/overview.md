# Architecture Overview

Knudg is central infrastructure, not local-first storage. Local state should be limited to temporary current-work summaries, pending writer approval queues, and session-scoped retrieval cache metadata.

Local retrieval cache must not become a personal memory layer. By default it stores only card IDs, card versions, freshness metadata, and ranking metadata. Card bodies may be cached only with explicit user or tenant policy, encryption at rest, short TTL, and purge on revocation.

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
- `pending_admission`
- `pending_redaction`
- `pending_review`
- `awaiting_user_approval`
- `approved`
- `indexed_hot`
- `indexed_main`
- `deferred`
- `rejected`
- `superseded`
- `deprecated`
- `revoked`

The canonical lifecycle is defined in [Data Model](data-model.md). This list is an enum inventory, not an alternate ordering.

Before redaction/review, public candidates must pass admission control:

- dedupe against existing public, team, and private-scope candidates the caller can access
- novelty scoring against canonical trails and open clusters
- abuse, spam, and quota checks
- review-capacity checks for the target wedge
- backlog age controls that can sideline, defer, or reject low-novelty candidates

Admission control does not decide truth. It decides whether Knudg should spend review/indexing budget on the candidate now.

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
- admission, dedupe, novelty, and review decisions are recorded as events and can be audited

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

Canonical trails are derived artifacts, not new ground truth. They must be reversible to their source card versions through a cluster manifest. A minority variant must not be discarded just because the majority path works in another environment.

Derived artifacts have their own versions, provenance, and consent policy. A deterministic aggregation of already-public redacted card versions can inherit publication status only when the derived artifact exposes no new private detail and the policy says inheritance is allowed. Editorial rewrites, curated packs, monetized bundles, or artifacts that change meaning require explicit policy review and may require renewed consent.

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
