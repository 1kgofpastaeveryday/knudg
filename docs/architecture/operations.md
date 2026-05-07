# Operations

The active agent path must degrade safely. Knudg should never block the main agent from continuing work.

Read-path fallback order:

1. full hybrid retrieval with rerank
2. hybrid retrieval without rerank
3. exact/BM25 only
4. session-scoped local metadata cache if still within freshness policy
5. no suggestion

The local cache fallback cannot serve stale card bodies by default. It can only reuse card IDs and metadata to revalidate against the central service, unless a tenant explicitly enables encrypted short-TTL card-body caching.

## Rollout Controls

Retrieval should not begin as automatic injection. Rollout order:

1. offline replay against labeled tasks
2. shadow retrieval that logs would-have-shown cards
3. explicit sidecar suggestions
4. thin inline hints for one wedge
5. broader public/shared corpus exposure

Every stage needs exit criteria, per-integration kill switches, and a no-suggestion fallback. Harmful suggestion rate, prompt-injection pass rate, user dismissal rate, and time-to-fix improvement are stage gates.

## SLOs and Telemetry

Required SLOs and telemetry:

- query success rate
- p50/p95/p99 retrieval latency
- dependency timeout rate
- circuit-breaker open rate
- index freshness lag
- approval backlog age
- redaction/review backlog age
- admission backlog age
- dedupe/novelty rejection rate
- compaction lag
- stale/deprecated card serve rate
- queue depth and oldest job age
- DLQ count
- cost per query and rerank rate
- cost per submitted candidate
- cost per approved card
- cost per rejected candidate
- cost per reindex and re-embedding batch
- cost per revocation propagation
- review minutes per public card
- free-tier abuse spend

This document does not set numeric production SLO targets yet. Numeric SLOs belong in the first wedge implementation RFC after baseline latency, cost, and corpus quality are measured.

## Initial Runbooks

Every paging alert must have a runbook. Initial runbooks:

- search latency spike
- index freshness breach
- queue backlog growth
- redaction/review backlog growth
- admission backlog or duplicate flood
- emergency card revocation
- failed migration or index cutover

## Failure Semantics

Dependency failures should degrade toward no suggestion rather than blocking active work.

Worker failures should be handled with:

- bounded retries
- exponential backoff with jitter
- idempotency keys
- dead-letter queues
- stuck-state sweepers
- replay from canonical events
- reconciliation between source of truth and projections

## Index Migration Operations

Embedding and index model changes are routine operations for a large corpus. Each index generation must define:

- source event range
- dual-read or dual-write window
- canary namespace
- freshness lag budget
- cold-card deferral rules
- revocation replay SLA
- rollback criteria and command path
