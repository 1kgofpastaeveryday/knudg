# Semantic Search (pillar ④)

Goal: find knudg by **task similarity / fuzzy meaning**, not just keyword match.
Today retrieval is FTS only (`knudg_closed_api_search` over a `tsvector`), which
is the keyword behavior the project explicitly does not want as the whole story.

This note fixes the approach and the few load-bearing decisions; it does not
specify DDL or ranking weights (those are tuned during implementation). It
complements `target-model.md`.

## Approach: hybrid, not replacement

Keep FTS, add vector similarity, combine. FTS is strong for exact terms
(package names, error fingerprints); vectors capture "similar work" when wording
differs. Hybrid ranking = weighted FTS rank + vector cosine similarity, with the
same abstention / `no_suggestion` and retrieval-panel-only output as today.

## Infra

- Postgres image: stock `postgres:16` has no pgvector. Switch to
  `pgvector/pgvector:pg16` (dev compose + any deployment).
- `CREATE EXTENSION vector` in a new migration.
- Add an `embedding vector(N)` column to `local_private_search_documents`
  (alongside the existing `search_vector tsvector`), plus an HNSW index for
  cosine distance.
- `N` (dimension) is fixed by the embedding model — so the provider decision
  below blocks the migration.

## Embedding provider (pluggable; DECISION NEEDED)

Model the provider like the final-filter provider: one `embed(texts) -> vectors`
seam, provider chosen by config, so it is swappable and self-host can run
offline. The default is a real choice with tradeoffs:

| Option | Latency (per query) | Offline / self-host | Dependency | Dim |
|---|---|---|---|---|
| **Local model (recommend)** e.g. `fastembed` BGE-small (ONNX, no torch) | low, in-process | yes, fully offline | one Python pkg + model download (~tens of MB) | 384 |
| NVIDIA NIM embeddings | network round-trip per query/card | needs API + key | reuses existing NVIDIA infra | ~1024 |
| Other hosted API (OpenAI etc.) | network | no | API + key | varies |

Recommendation: **local model (fastembed / BGE-small, dim 384)**. Search is
latency-sensitive (250 ms budget) and the project values self-host; an API
round-trip per search is the wrong default. NVIDIA stays available as a swappable
provider (it is already wired for the filter), but it should not be the search
default. The provider is config-selected so this is reversible.

## Flow

- Capture: after the deterministic redaction passes and the card is stored,
  embed its search text (same fields the FTS uses) and store the vector. Embed
  is best-effort: if the provider is unavailable, store the card without a vector
  and fall back to FTS-only for it (degrade, don't fail capture).
- Backfill: a one-shot job embeds existing cards' search documents.
- Search: embed the query terms, run hybrid ranking in `knudg_closed_api_search`
  (or a new search function), keep top-k + abstention threshold.

## Invariants (unchanged)

- Retrieval-panel output only; never card bodies in results.
- Revocation fence and `purged`/`revoked` filtering apply to vector rows exactly
  as to FTS rows (a revoked card is not vector-retrievable).
- Same `min_score` / abstention contract; hybrid score must still be able to
  abstain to `no_suggestion`.

## Increments

1. Provider decision (above) → fix dimension.
2. pgvector image + `CREATE EXTENSION` migration + `embedding` column + HNSW index.
3. Pluggable embed provider; capture-time embed (best-effort) + backfill job.
4. Hybrid ranking in the search function + `closed_api` wiring; `served_from`
   becomes e.g. `closed_private_hybrid`.
5. Tests: vector retrieval finds a semantically-similar card that FTS misses;
   revoked/purged cards are not vector-retrievable; provider-down degrades to FTS.

## Out of scope

- Re-ranking models, cross-encoders, query expansion — later if hybrid is not
  enough.
- Public/shared-corpus search — that is the ③ shared pipe, deferred per
  target-model.
