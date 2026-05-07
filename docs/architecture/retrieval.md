# Retrieval Model

Knudg should not rely on one vector per card.

Use a multi-signal retrieval pipeline:

- dense vector search for semantic similarity
- BM25/sparse search for exact terms
- exact matching for error codes, package names, stack traces, commands
- metadata filters for language, OS, framework, agent tool, domain
- quality scoring for solved_many, verified, and disputed cards, plus lifecycle demotion for deprecated or superseded cards
- reranking for paid or high-value queries

Potential embeddings:

- goal embedding
- symptom embedding
- solution embedding
- failed path embedding
- environment tags
- error signature hash

Query flow:

```text
current work
  -> outbound query profile
  -> shard selection
  -> BM25 + exact + vector candidates
  -> authorization filter
  -> score fusion
  -> optional rerank
  -> up to 3 concise cards, if confidence threshold clears
  -> fenced agent injection
```

Search must abstain when confidence is low. Returning no card is a valid result.

## MVP Retrieval Quality Gates

- exact error signature recall@3
- hybrid retrieval recall@10
- usefulness win rate against a no-Knudg baseline
- stale or harmful suggestion rate
- prompt-injection pass rate on hostile-card tests
- p50 and p95 latency from active agent request to suggestion
- cost per query with and without reranking

The initial target is not "always return top 3." The target is "return up to 3 only when confidence clears the threshold."

The exact confidence formula is intentionally not fixed here. MVP should define the formula in the wedge-specific ranking spec after an evaluation corpus exists. Until then, abstention is governed by offline gates and conservative operator-configured thresholds.

## Search Backend Decisions

The MVP should use one keyword backend and one vector strategy before adding alternatives.

Initial recommendation:

- canonical metadata: Postgres
- keyword search: Postgres full-text search for MVP
- vector search: pgvector HNSW indexes for MVP
- object storage: R2 or S3 with immutable content-addressed objects
- queue: one Postgres-backed queue or one managed queue, not multiple interchangeable options

The query contract must define:

- pre-filter versus post-filter behavior
- tenant and namespace filters before ranking
- vector model name and dimension
- distance operator
- HNSW/IVFFlat parameters
- fallback exact search path
- score normalization between exact, BM25, vector, quality, and freshness signals
- stale/deprecated/disputed demotion rules

## Serving Consistency

The canonical Postgres event log is authoritative. Search indexes and object storage are projections.

Visibility rules:

- `candidate_created`, `pending_redaction`, `pending_review`, and `awaiting_user_approval` are never searchable
- `approved` is visible only to authorized owners/reviewers until indexed
- `indexed_hot` and `indexed_main` are searchable according to namespace and tenant policy
- `deprecated` and `superseded` can appear only when explicitly requested or when used as provenance for a replacement
- `revoked` is never returned

Every search response includes:

- card ID
- card version
- namespace
- quality state
- freshness status
- index generation
- source event range

Cache keys must include tenant, namespace, card version, quality state, and index generation. Status changes emit invalidation events. If invalidation is delayed beyond the freshness SLO, serving must prefer no result over stale guidance.
