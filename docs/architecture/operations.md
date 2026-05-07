# Operations

The active agent path must degrade safely. Knudg should never block the main agent from continuing work.

Read-path fallback order:

1. full hybrid retrieval with rerank
2. hybrid retrieval without rerank
3. exact/BM25 only
4. recent local cache if still within freshness policy
5. no suggestion

## SLOs and Telemetry

Required SLOs and telemetry:

- query success rate
- p50/p95/p99 retrieval latency
- dependency timeout rate
- circuit-breaker open rate
- index freshness lag
- approval backlog age
- redaction/review backlog age
- compaction lag
- stale/deprecated card serve rate
- queue depth and oldest job age
- DLQ count
- cost per query and rerank rate

This document does not set numeric production SLO targets yet. Numeric SLOs belong in the first wedge implementation RFC after baseline latency, cost, and corpus quality are measured.

## Initial Runbooks

Every paging alert must have a runbook. Initial runbooks:

- search latency spike
- index freshness breach
- queue backlog growth
- redaction/review backlog growth
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
