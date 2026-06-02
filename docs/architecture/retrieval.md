# Retrieval Model

Knudg should not rely on one vector per card.

Use a multi-signal retrieval pipeline. The detailed research-backed strategy for
task-profile generation, hybrid retrieval, fusion, and evaluation lives in
[Search Strategy](search-strategy.md).

Core retrieval signals:

- dense vector search for semantic similarity
- Postgres FTS rank for exact terms in MVP; BM25-capable sparse search requires a later backend decision
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

## SearchProfile Request Schema

Authenticated private/team/enterprise agents send a sanitized `SearchProfile`,
never raw transcript text. `SearchProfile` is not accepted on anonymous public
routes. Required fields:

- `schema_version`
- `request_id`
- `requested_tenant_scope`: private, team, or enterprise; a requested filter,
  never authority
- `requested_namespace_ids`; requested filters that the server intersects with
  signed `AuthContext` grants, rejecting overbroad or stale namespace requests
- `delivery_mode_requested`: `bootstrap` or `retrieval_panel` for MVP; `inline_hint` is reserved for a later hostile-card red-team gate
- `goal_category`
- `sanitized_error_signature`; `error_signature_hash` is allowed only for private/team clients using a server-issued namespace-private hash profile
- `public_packages_claimed`
- `public_frameworks_tools_claimed`
- `language_runtime`
- `coarse_os`
- `dependency_major_versions`
- `repo_shape_category`
- `risk_flags_claimed`
- `latency_budget_ms`
- `privacy_budget_class_claimed`

Forbidden fields include raw logs, full stack traces, absolute paths, usernames, hostnames, private repo names, customer names, secrets, tokens, full file contents, and unredacted command output. Requests with forbidden fields are rejected before candidate generation.

Search and hook ingress use the same pre-instrumentation no-log boundary as
candidate intake. Gateways, app middleware, schema validators, metrics,
tracing, audit, queues, DLQs, and cache-key builders must suppress raw request
bodies before validation. Rejected forbidden fields may leave only protected
tenant-keyed fingerprints, schema version, coarse reject class, actor class,
and correlation ID. Tests must prove forbidden search/hook payload fragments do
not appear in logs, traces, metrics, DLQs, audit payloads, cache keys, model
inputs, or rejected-response bodies.

`SearchProfile` is a closed JSON schema, not a bag of sanitized strings. Every
text field has a max byte length, Unicode normalization profile, control
character ban, terminal escape ban, confusable handling, and per-field grammar.
Closed enums are required wherever the product can enumerate values, including
`goal_category`, `requested_tenant_scope`, `delivery_mode_requested`, coarse
OS/runtime, and risk flags. Fields eligible for embedding or reranking must be explicitly
listed by schema version; all other fields are excluded from model input,
cache-key text, telemetry text, and audit payloads.

Client-supplied publicness, risk, and privacy-budget values are claims, not
authority. Retrieval, ranking, public eligibility, abuse accounting, and
visibility decisions consume only server-derived verdicts:

- classifier version
- publicness verdict
- risk verdict
- privacy-budget decision
- reject or downgrade reason
- canonicalized package/tool coordinates after registry, deny-list, allow-list,
  confusable, typosquat, and private-identifier checks where applicable

If server classification cannot prove the claimed publicness or risk level, the
request is rejected, downgraded to private/team scope, or returns
`no_suggestion` according to the caller's authorization and safety policy.

Identity is not part of `SearchProfile`. Actor subject, delegated-token
audience, proof key, and tenant membership live only in the signed
`AuthContext` and audit fields. Retrieval, ranking, embedding, reranking,
cache keys, and public telemetry must not consume actor identity fields.

Authenticated private/team clients use `SearchProfile` with server-validated
tenant and namespace scope from `AuthContext`. Anonymous public search uses a
separate `PublicSearchRequest` and must reject `SearchProfile`, `tenant_scope`,
`requested_tenant_scope`, `namespace_ids`, `requested_namespace_ids`, public hashes, object IDs, internal card IDs, and client-side
fingerprints.

`PublicSearchRequest` fields are:

- `schema_version`
- `request_id`
- `goal_category`
- sanitized public tool/framework/package family where already public
- coarse OS/runtime family
- dependency major versions where already public
- bounded public error category or normalized public symptom phrase
- `delivery_mode_requested`: `retrieval_panel` only until a later public-search
  gate accepts another mode

The server selects eligible public shards and threshold policy only after
DEC-013/M6 gates pass. Negative tests must prove anonymous public routes reject
every authenticated `SearchProfile` field that could select tenant, namespace,
object, threshold, or fingerprint scope.

For public search, clients send sanitized components, not public fingerprints.
The server computes versioned keyed HMAC fingerprints with `key_id`, rotation
window, dual-read migration rules, and audit events. Unknown client-supplied
hashes are rejected on public paths because they are enumeration and
correlation primitives.

Query flow:

```text
current work
  -> task profile / outbound query profile
  -> bounded multi-query generation
  -> authorization scope
  -> enterprise guidance lookup for scoped directives/routing/guardrails
  -> shard selection within authorized public/private/team corpus
  -> FTS/exact + vector candidates
  -> score fusion
  -> optional rerank
  -> up to 3 concise cards, if confidence threshold clears
  -> fenced retrieval panel or inline_hint only after the hostile-card gate
```

Search must abstain when confidence is low. Returning no card is a valid result.

Enterprise guidance is not ranked as an experience card. If enabled for the
tenant, the retrieval service evaluates scoped managed guidance before card
candidate generation and returns applicable guidance in a separate response
field. Guidance can affect display, routing, approval requirements, or
abstention, but it must not be merged into card ranking signals or treated as
proof that a technical path works.

Guidance evaluation consumes only server-attested `GuidanceContext`, not raw
client claims. Stale, revoked, unauthorized, expired, conflicted, and absent
guidance use normalized timing and coarse response shapes. Guidance-specific
probing budgets apply before predicate evaluation.

Authorization is a precondition for candidate generation, not a cleanup step after candidate generation. Query planners must choose public/private/team shards and tenant/namespace filters before FTS, exact, vector, or reranking work begins. If the selected vector backend cannot preserve recall and latency under selective tenant or namespace filters, the serving path must use a physically separated index, partitioned index, or exact/FTS fallback for that scope.

Raw stack traces, raw command text, private path fragments, and private repo identifiers are never exact-match inputs for public search. Public exact match uses normalized fingerprints only.

Public search privacy rules:

- rare fingerprints must meet private operator-configured distinct-tenant and
  minimum cohort-size thresholds before public matching
- each public wedge must define its configured `k`, cohort-size floor, abuse
  budgets, rate-limit budgets, and recovery owner in a private, access-controlled
  ranking/security spec before launch
- public materials may disclose only broad privacy posture, public stop-condition
  categories, recovery contact role, and opaque threshold-version labels; they
  must not publish numeric `k`, cohort floors, abuse budgets, rate-limit
  budgets, or accepted privacy thresholds
- response timing and reason codes must be normalized across no-match, redacted, not-indexed, and rare-fingerprint cases
- privacy budgets and per-subject/IP rate limits apply before candidate generation
- rare queries must return `no_suggestion` with a generic abstention, not a count, nearest match, or rarity explanation
- public abuse budgets must track per-subject, per-IP, per-API-key, and per-fingerprint-family probing across the active wedge
- budget exhaustion must not disclose which term, fingerprint family, authorization state, safety gate, or rarity threshold caused abstention
- recovery from a threshold, budget, or index incident is fail-closed: public search returns generic abstention until the owner verifies counts, invalidates affected cache entries, bumps `threshold_version`, and records the incident in the audit log

## Injection Contract

Retrieved cards are untrusted evidence. The client must render them as non-executable data and must never convert card text into tool calls without independent agent/user validation.

For the summoned-role MVP, retrieval first returns a compact role verdict, not
card content in the acting prompt. The searcher role may return
`no_actionable_signal` when a searched backend produces no useful signal, or say
that a suggestion is available and recommend `offer_retrieval_panel`; the main
agent then decides whether to open a retrieval panel. This preserves a no-Knudg
baseline and keeps experience retrieval from degrading the main agent's active
reasoning context.

Knudg clients may also attach bounded exploration guidance that is separate
from retrieved cards and enterprise-managed directives. This guidance is a
client-side work contract, not evidence that a technical path works and not a
permission to bypass higher-priority agent, user, tool, privacy, or safety
policy.

The client setting is `exploration_depth`:

- `off`: no Knudg exploration guidance is injected
- `hard`: add a root-cause-biased hint for debugging, recurring failures,
  environment traps, and implementation decisions; the agent should prefer a
  durable fix over a superficial workaround when evidence and budget allow
- `harder`: add publication-candidate discipline; the agent should distinguish
  symptoms, confirmed root cause, failed paths, temporary workaround, durable
  fix, applicability scope, uncertainty, and non-public details before a future
  writer proposes a reusable card

`harder` does not create, approve, or publish knowledge. It only shapes the
current agent's investigation so a later writer can draft a better bounded card
after the user explicitly approves the exact redacted artifact. The guidance
must preserve abstention-first behavior: when evidence is insufficient, the
agent should say what remains unknown rather than invent a root cause.

Supported delivery modes, matching the search response `delivery_mode` field:

- `bootstrap`: before work starts, only for high-confidence public or authorized private cards
- `retrieval_panel`: visible suggestion outside the main prompt, preferred during rollout
- `inline_hint`: non-MVP; allowed only after a separate red-team gate proves a two-phase or two-agent architecture where a read-only evaluator consumes raw retrieved text and the acting agent receives only a structured, non-instructional fit/risk summary
- `no_suggestion`: required when confidence, freshness, authorization, or safety checks fail

Summoned role verdicts are not a new card delivery mode. They are pre-display
client orchestration signals. A `suggestion_available` verdict means references
exist; it is not useful task output unless the main agent validates and uses the
signal. A verdict that recommends `offer_retrieval_panel` still resolves to
`retrieval_panel` or `no_suggestion` before any card is shown.

Managed guidance delivery uses the same surface modes but a separate payload
section. A directive or routing record may be shown in the retrieval panel or a
future controlled inline policy summary only when the client can preserve its
owner, strength, scope, freshness, override policy, and conflict state.

Minimum constraints:

- at most 3 cards
- explicit token budget set by the client integration
- no hidden instructions
- no card text above system, developer, user, or tool policy
- commands and code are rendered as candidate evidence, not actions
- each card includes quality state, outcome type, freshness, provenance, and deprecated/disputed flags
- delivery must downgrade to `retrieval_panel` or `no_suggestion` when the client requested mode is unsupported, unsafe, or above rollout stage; public cards default to `retrieval_panel` or citation-only summaries outside the acting agent prompt
- every integration has a kill switch and can fall back to retrieval panel or no suggestion
- command, package, repository, install, migration, and credential-bearing cards are excluded from retrieval-panel and inline delivery until verification clears

High-risk summary displays are separately gated. Before verification clears,
unverified high-risk cards return only generic withheld metadata and must not
appear as retrieval-panel cards. Verified high-risk cards may show the minimum
non-executable summary described in Security and Privacy. Full card expansion
requires per-request server authorization, an audit event, revocation recheck,
and the non-executable rendering contract. The default MVP authority is not a
transferable client body lease; if a later deployment introduces one, it must
follow the signed single-use lease constraints in Agent Access.

## MVP Retrieval Quality Gates

Before M3 implementation, the first wedge ranking spec must define canonical
exact/FTS SQL, tokenizer and language config, extracted text or `tsvector`
storage, rank formula, abstention thresholds, score normalization, replay
fixtures, and the baseline search system. Before M4, the embedding/index schema
RFC must define vector table shape, partition keys, model/version/dimension
metadata, HNSW settings, recall/latency benchmarks, and fallback to exact/FTS.

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
- vector search: pgvector HNSW indexes for MVP only after M4 filtered recall/latency benchmarks pass
- object storage: disabled until M2 or deployment RFC; when enabled, use an S3-compatible provider with immutable content-addressed objects
- queue: Postgres-backed queue for MVP; any managed queue replacement requires a decision update

The query contract must define:

- pre-filter versus post-filter behavior
- tenant and namespace filters before candidate generation, ranking, and reranking
- vector model name and dimension
- distance operator
- HNSW/IVFFlat parameters
- fallback exact search path
- score normalization between exact, FTS rank, vector, quality, and freshness signals
- stale/deprecated/disputed demotion rules
- display and ranking differences for solved, failed-only, inconclusive, and unknown-clarified cards

M4 is blocked until pgvector is benchmarked under tenant, namespace,
lifecycle, safety/risk, and embedding-kind filters. If filtered HNSW recall or
latency misses the wedge threshold, the serving path must use physically
separated indexes, partitioned indexes, exact/FTS fallback, or a dedicated
vector service before production serving.

## Serving Consistency

The canonical Postgres event log is authoritative. Search indexes and object storage are projections.

Visibility rules:

- `candidate_created`, `pending_admission`, `deferred`, `pending_redaction`, `pending_review`, `awaiting_user_approval`, `approved_private`, `approved_for_publication`, `discard_pending`, `publication_withdrawn`, `rejected`, and `published` are not public-searchable
- `approved_private` is visible only to authorized owner/team scopes
- `approved_for_publication` and `published` are visible only to authorized owners/reviewers until indexed
- `indexed_hot` and `indexed_main` are searchable according to namespace and tenant policy
- `deprecated` and `superseded` can appear only when explicitly requested or when used as provenance for a replacement
- `revoked` is never returned

The full status-to-visibility matrix lives in [Data Model](data-model.md). Retrieval implementations must not define their own visibility policy.

`indexed_hot` and `indexed_main` in lifecycle/status prose are serving
eligibility projections, not the complete index membership model. Actual hot
and main index membership is stored in projection/index tables keyed by tenant,
namespace, card version, index kind, index generation, processor version,
source event range, content hash, and revocation epoch. A card can be
`published` while absent from a specific index generation, and a stale
projection must not override the canonical lifecycle, consent, safety, or
revocation checks.

Protected authenticated search responses include:

- card ID
- card version
- namespace
- outcome type
- quality state
- freshness status
- index generation
- revocation epoch
- source event range

Public or anonymous responses receive only opaque freshness and threshold
labels. They must not expose raw revocation epochs, index generations, source
event ranges, ranking signal names, candidate counts, rare-term diagnostics, or
numeric privacy threshold values.

Cache keys must include requester tenant, publisher tenant for public results,
namespace, card version, quality state, revocation epoch, and index generation.
Status changes emit invalidation events. Public search must validate epochs and
tombstones for every publisher tenant represented in the returned result set
before body expansion and before serialization. If any involved epoch is
missing, stale, or advances during the request, serving must prefer no result
over stale content.

Managed guidance cache keys additionally include guidance ID/version, policy
version, tenant guidance epoch, effective window, and `GuidanceContext` digest.
Directive, routing, and guardrail responses are not served
stale-while-revalidate. Clients must revalidate the guidance epoch before
acting on high-impact guidance.

MVP vector defaults are intentionally conservative until a wedge evaluation corpus exists:

- distance: cosine
- pgvector operator class: `vector_cosine_ops`
- HNSW `m`: 16
- HNSW `ef_construction`: 64
- query `ef_search`: 80, tunable per request class
- tenant/private scopes: partitioned or physically separated indexes before vector candidate generation
- fallback: exact/FTS when authorized filters are too selective for vector recall

The retrieval RFC can change these values only with recall, latency, and cost measurements.
