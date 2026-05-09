# Retrieval Model

Knudg should not rely on one vector per card.

Use a multi-signal retrieval pipeline:

- dense vector search for semantic similarity
- BM25/sparse search for exact terms
- exact matching for sanitized error signatures, public package names, public API surfaces, normalized command families, and stack-frame fingerprints
- metadata filters for language, OS, framework, agent tool, domain
- quality scoring for solved_many, verified, disputed, unknown_clarified, and failed_only cards, plus lifecycle demotion for deprecated or superseded cards
- reranking for paid or high-value queries

Potential embeddings:

- goal embedding
- symptom embedding
- solution embedding
- failed path embedding
- unknown/constraint embedding
- environment tags
- error signature hash

Query flow:

```text
current work
  -> outbound query profile
  -> authorization scope
  -> shard selection within authorized public/private/team corpus
  -> BM25 + exact + vector candidates
  -> score fusion
  -> optional rerank
  -> up to 3 concise cards, if confidence threshold clears
  -> fenced sidecar or thin agent injection
```

Search must abstain when confidence is low. Returning no card is a valid result.

Authorization is a precondition for candidate generation, not a cleanup step after candidate generation. Query planners must choose public/private/team shards and tenant/namespace filters before BM25, exact, vector, or reranking work begins. If the selected vector backend cannot preserve recall and latency under selective tenant or namespace filters, the serving path must use a physically separated index, partitioned index, or exact/BM25 fallback for that scope.

Raw stack traces, raw command text, private path fragments, and private repo identifiers are never exact-match inputs for public search. Public exact match uses normalized fingerprints only.

Public search privacy rules:

- rare fingerprints must meet the wedge `k` distinct-tenant threshold and minimum cohort size before public matching
- response timing and reason codes must be normalized across no-match, redacted, not-indexed, and rare-fingerprint cases
- privacy budgets and per-subject/IP rate limits apply before candidate generation
- rare queries must return `no_suggestion` with a generic abstention, not a count, nearest match, or rarity explanation

## Injection Contract

Retrieved cards are untrusted evidence. The client must render them as non-executable data and must never convert card text into tool calls without independent agent/user validation.

Supported delivery modes:

- `bootstrap`: before work starts, only for high-confidence public or authorized private cards
- `sidecar`: visible suggestion outside the main prompt, preferred during rollout
- `inline_hint`: bounded prompt injection for one active task
- `no_suggestion`: required when confidence, freshness, authorization, or safety checks fail

Minimum constraints:

- at most 3 cards
- explicit token budget set by the client integration
- no hidden instructions
- no card text above system, developer, user, or tool policy
- commands and code are rendered as candidate evidence, not actions
- each card includes quality state, outcome type, freshness, provenance, and deprecated/disputed flags
- every integration has a kill switch and can fall back to sidecar or no suggestion
- command, package, repository, install, migration, and credential-bearing cards are excluded from sidecar and inline delivery until verification clears

## MVP Retrieval Quality Gates

- exact error signature recall@3
- hybrid retrieval recall@10
- unknown/failed-only useful retrieval rate
- usefulness win rate against a no-Knudg baseline
- remote shared corpus usefulness excluding same-session local cache
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
- object storage: disabled until M2 or deployment RFC; when enabled, use an S3-compatible provider with immutable content-addressed objects
- queue: Postgres-backed queue for MVP; any managed queue replacement requires a decision update

The query contract must define:

- pre-filter versus post-filter behavior
- tenant and namespace filters before candidate generation, ranking, and reranking
- vector model name and dimension
- distance operator
- HNSW/IVFFlat parameters
- fallback exact search path
- score normalization between exact, BM25, vector, quality, and freshness signals
- stale/deprecated/disputed demotion rules
- display and ranking differences for solved, failed-only, inconclusive, and unknown-clarified cards

## Serving Consistency

The canonical Postgres event log is authoritative. Search indexes and object storage are projections.

Visibility rules:

- `candidate_created`, `pending_admission`, `deferred`, `pending_redaction`, `pending_review`, `awaiting_user_approval`, `approved_private`, `approved_for_publication`, `rejected`, and `published` are not public-searchable
- `approved_private` is visible only to authorized owner/team scopes
- `approved_for_publication` and `published` are visible only to authorized owners/reviewers until indexed
- `indexed_hot` and `indexed_main` are searchable according to namespace and tenant policy
- `deprecated` and `superseded` can appear only when explicitly requested or when used as provenance for a replacement
- `revoked` is never returned

The full status-to-visibility matrix lives in [Data Model](data-model.md). Retrieval implementations must not define their own visibility policy.

Every search response includes:

- card ID
- card version
- namespace
- outcome type
- quality state
- freshness status
- index generation
- revocation epoch
- source event range

Cache keys must include tenant, namespace, card version, quality state, revocation epoch, and index generation. Status changes emit invalidation events. If invalidation is delayed beyond the freshness SLO, serving must prefer no result over stale guidance.

MVP vector defaults are intentionally conservative until a wedge evaluation corpus exists:

- distance: cosine
- pgvector operator class: `vector_cosine_ops`
- HNSW `m`: 16
- HNSW `ef_construction`: 64
- query `ef_search`: 80, tunable per request class
- tenant/private scopes: partitioned or physically separated indexes before vector candidate generation
- fallback: exact/FTS when authorized filters are too selective for vector recall

The retrieval RFC can change these values only with recall, latency, and cost measurements.
