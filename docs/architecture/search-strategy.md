# Search Strategy

Knudg retrieval should be driven by the current work state, not by a manually
written search box query alone.

The retrieval unit is a structured task profile:

```text
current work
  -> task profile
  -> multi-query generation
  -> authorized shard selection
  -> exact/FTS + vector candidates
  -> fusion
  -> rerank
  -> compact verdict or retrieval panel
```

Manual search remains useful, but it is only one input. The searcher role should
derive retrieval signals from the active task, recent safe workspace metadata,
test failures, edited file paths, public package names, symbols, coarse runtime
details, and explicit user text. The main agent should not have to repeatedly
invent search terms as a prerequisite for Knudg value.

## Research-Backed Principles

Use hybrid retrieval by default.

Dense retrieval is useful for semantic similarity, but technical work depends
heavily on exact identifiers such as error codes, file paths, functions,
migration names, package names, and test names. BM25/FTS and exact matching must
remain first-class even after vector search is available.

Generate multiple queries from one task profile.

Conversational query rewriting and classic query expansion both point to the
same product shape: the raw user prompt is often underspecified for retrieval.
Knudg should produce a small bounded set of query views:

- exact identifier query
- sparse keyword query
- semantic summary query
- hypothetical relevant-card query
- structured metadata filters

Fuse before reranking.

For MVP, simple reciprocal-rank-style fusion is preferable to an opaque learned
ranking stack. It lets exact/FTS, vector, and metadata retrievers each contribute
without requiring a large labeled corpus on day one. Learned rerankers can be
added after Knudg has replay fixtures and quality labels.

The removed local synthetic harness previously used `rrf_v0` over five bounded
query views: `exact_identifiers`, `sparse_keywords`, `semantic_summary`,
`hypothetical_relevant_card`, and `structured_filters`. That remains useful
prior art for future M3 ranking work, but it is no longer an active runtime
or serving contract.

Retrieve adaptively.

Retrieval should run at work boundaries where new evidence changes the task:
task start, before high-risk edits, after test failures, after tool errors, and
before drafting a reusable card. Always-on fixed top-k retrieval risks lowering
agent quality by adding irrelevant context.

Abstention is part of ranking quality.

Returning `no_suggestion` is a successful retrieval result when confidence,
authorization, freshness, or safety is weak. Search quality gates must measure
bad suggestions and missed abstentions, not just recall.

## Task Profile Shape

`task_profile.v0` is the local/searcher-side profile that can later compile
into the protected `SearchProfile` request described in [Retrieval Model](retrieval.md).
It must not contain raw transcripts, private file contents, hostnames, usernames,
secrets, or unredacted command output.

The current schema artifact is
[`schemas/task-profile-v0.schema.json`](../../schemas/task-profile-v0.schema.json).

Candidate fields:

- `schema_version`
- `explicit_query`: bounded sanitized user or agent search intent
- `intent`: `debug`, `implement`, `review`, `docs`, `migration`, `test`, or
  `research`
- `repo_shape_category`
- `subsystems`
- `safe_file_refs`: relative paths only when safe for the target scope
- `symbols`: functions, commands, table names, schema names, or test names
- `error_fingerprints`: normalized and scope-safe only
- `public_packages`
- `public_frameworks_tools`
- `language_runtime`
- `coarse_os`
- `dependency_major_versions`
- `risk_tags`
- `recent_event_kinds`: task start, edit, test failure, tool failure, review,
  approval handoff

The central service remains responsible for authority. Client-supplied fields
are claims and filters, not proof of publicness, authorization, or publication
eligibility.

## Knowledge Card Retrieval Fields

Knowledge cards should include retrieval-specific fields instead of relying on
full card bodies for search.

Recommended fields:

- `triggers.keywords`
- `triggers.symbols`
- `triggers.error_fingerprints`
- `scope.repo_shape_category`
- `scope.language_runtime`
- `scope.frameworks_tools`
- `scope.subsystems`
- `embedding_text`
- `outcome_type`
- `quality_state`
- `privacy_state`
- `freshness_state`
- `deprecated_by`
- `supersedes`

`embedding_text` is a compact search representation of when the card is useful.
It is not the canonical body and must not introduce claims that are absent from
the approved card payload. Human-readable Markdown or Obsidian-style files may
mirror these fields, but the canonical schema and database projection remain
authoritative.

## Searcher Role Contract

The summoned searcher role should:

- build or receive a `task_profile.v0`
- create a bounded set of query views
- run exact/FTS and vector retrieval when those backends are enabled for the
  scope
- fuse and rerank candidates
- return only a compact verdict to the main agent

The main agent receives card content only after it explicitly opens an allowed
retrieval panel or read path. This preserves the no-Knudg baseline and prevents
retrieved experience from silently becoming prompt authority.

## Evaluation

Initial metrics:

- exact identifier recall@3
- hybrid recall@10
- nDCG@10 on replay fixtures
- abstention accuracy
- stale or harmful suggestion rate
- prompt-injection pass rate on hostile-card fixtures
- useful-retrieval win rate against no-Knudg baseline
- latency p50/p95 from work event to verdict
- cost per retrieval with and without reranking

Future retrieval evaluation fixtures should be defined by an accepted M3
evaluation design. Historical synthetic fixture work does not approve
protected-data serving or define the active closed-launch search contract.

Evaluate retrieval separately from generation. A generation answer can look good
while retrieval is wrong, and a retrieval result can be relevant while the acting
agent misuses it. Knudg should log enough structured evaluation events to
separate those failures.

## Prior Art

The design is influenced by:

- Rocchio relevance feedback and later query expansion work: raw queries are
  often improved by expansion from relevant context.
- Dense Passage Retrieval: dense vectors are useful for semantic retrieval but
  should not replace lexical and exact paths for technical identifiers.
- BEIR: BM25 remains a robust zero-shot baseline; dense models do not dominate
  every domain.
- ColBERT and SPLADE: late-interaction and learned sparse retrieval are future
  options when Knudg needs better identifier-aware neural ranking.
- Reciprocal Rank Fusion: simple rank fusion is a good MVP fit for combining
  heterogeneous retrievers.
- HyDE: hypothetical document embeddings suggest a way to search for "the card
  that would help this task," but generated hypothetical text must be treated as
  a query artifact, not evidence.
- Rewrite-Retrieve-Read and conversational query rewriting: task prompts often
  need rewriting into retrieval-ready queries.
- Self-RAG, FLARE, and IRCoT: retrieval should be adaptive and on-demand, not a
  fixed context stuffing step.
- Generative Agents and MemGPT: memory systems need structured tiers,
  reflection/summary artifacts, and retrieval policies rather than raw transcript
  stuffing.
- LongMemEval and RAGAS: evaluation should distinguish retrieval quality,
  abstention, temporal update handling, and faithful use of retrieved context.
