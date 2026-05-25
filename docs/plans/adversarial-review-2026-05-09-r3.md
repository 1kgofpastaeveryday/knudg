# Adversarial Design Review - 2026-05-09 R3

## Review Configuration

- Date: 2026-05-09
- Project: Knudg repository root
- Focus: Codex Subconscious Sidecar / concise interventions design
- Tier: full
- Rounds: 1
- Live QA: not requested
- Execution mode: Codex-native subagents
- Reviewers:
  - Attack Surface
  - Production Stress
  - Assumption Challenger
  - Implementation Reality
  - Schema & Data Integrity
  - Coherence Auditor
  - UX Reviewer

## Review Targets

- `AGENTS.md`
- `README.md`
- `docs/README.md`
- `docs/rfcs/0002-codex-subconscious-sidecar.md`
- `docs/rfcs/0001-m0-schema-event-log.md`
- `docs/architecture/agent-access.md`
- `docs/architecture/overview.md`
- `docs/architecture/security-privacy.md`
- `docs/architecture/data-model.md`
- `docs/architecture/retrieval.md`
- `docs/architecture/operations.md`
- `docs/architecture/implementation-readiness.md`
- `docs/product/strategy.md`
- `docs/product/intent-crosswalk.md`

## Scoring Summary

| Reviewer | Correctness | Completeness | Implementability | Resilience | Weighted Avg |
|---|---:|---:|---:|---:|---:|
| Attack Surface | 4 | 2 | 3 | 2 | 3.00 |
| Production Stress | 4 | 2 | 3 | 2 | 3.00 |
| Assumption Challenger | 4 | 3 | 3 | 3 | 3.40 |
| Implementation Reality | 4 | 3 | 3 | 3 | 3.40 |
| Schema & Data Integrity | 3 | 2 | 4 | 2 | 2.90 |
| Coherence Auditor | 3 | 3 | 4 | 3 | 3.25 |
| UX Reviewer | 4 | 3 | 4 | 3 | 3.63 |
| **Average** | **3.71** | **2.57** | **3.43** | **2.57** | **3.23** |

PASS/FAIL: **FAIL**. Completeness and resilience averages are below 3, and multiple lanes report Tier 1 blockers.

## Cross-Lane Convergence

### Issues Identified By 3+ Reviewers

| Issue | Reviewers | Tier | Confidence |
|---|---|---|---|
| Watch-task writes bypass consent, local-state limits, and tenant/data boundaries | Attack Surface, Production Stress, Assumption Challenger, Implementation Reality, Schema, Coherence, UX | Tier 1 | HIGH |
| Codex/session JSONL observation lacks a sanitized outbound profile and stable event-source decision | Attack Surface, Assumption Challenger, Implementation Reality, Coherence | Tier 1/Tier 2 | HIGH |
| Codex OAuth backend lacks a documented credential/scope/storage contract | Attack Surface, Assumption Challenger, Implementation Reality, Coherence | Tier 1 | HIGH |
| Local stores lack atomicity, idempotency, versioning, replay, and corruption recovery | Production Stress, Schema, Implementation Reality | Tier 1/Tier 2 | HIGH |
| Active notes are a prompt-injection / stale-context surface without trust labels, TTL, or lifecycle | Attack Surface, Production Stress, Assumption Challenger, Coherence, UX | Tier 1/Tier 2 | HIGH |
| `interrupt` is specified without reliable delivery, acknowledgement, rollout, kill switch, or fatigue controls | Production Stress, Assumption Challenger, UX | Tier 1/Tier 3 | HIGH/MEDIUM |
| RFC 0002 conflicts with existing Knudg local-state and central-search positioning | Implementation Reality, Assumption Challenger, Coherence, UX | Tier 1/Tier 2 | HIGH |

### Issues Identified By 2 Reviewers

| Issue | Reviewers | Tier | Confidence |
|---|---|---|---|
| Intervention schema conflicts with examples and lacks JSON Schema/versioning | Implementation Reality, Schema, UX | Tier 1/Tier 2 | HIGH |
| Draft RFC is already leaking into operational `AGENTS.md` behavior | Attack Surface, Assumption Challenger, Coherence | Tier 3/Tier 2 | MEDIUM |
| Sidecar rollout lacks shadow-mode/evaluation metrics | Assumption Challenger, Coherence, UX | Tier 2/Tier 3 | HIGH |
| Backend outage behavior lacks circuit breaker/retry/health telemetry | Production Stress, Coherence | Tier 1/Tier 3 | HIGH |

## Tier 1 - Immediate Fix Required

### 1. Watch-Task Writes Are Not Safe For V0

The current RFC permits writes to destinations like `D:\career\self-analysis\` and `D:\Users\shared\learnings.md`. Reviewers converged that this violates Knudg's local-state boundary, bypasses the consent/redaction/revocation model, and creates arbitrary-write, tenant-leakage, and trust risks.

Required fix:

- Remove external watch-task writes from v0, or route them through a pending-review queue.
- Add destination allowlists, path canonicalization, symlink/junction defenses, per-destination schemas, audit logs, and undo/delete controls before any external write is allowed.
- Treat shared multi-tenant destinations as out of scope until tenant-scoped consent and revocation are defined.

### 2. Session Observation Must Use A Sanitized Profile

RFC 0002 currently says the observer can read session JSONL/tool calls/failures and send compact chunks to a backend. Existing architecture requires sanitized outbound query profiles that exclude raw logs, private paths, private repo names, secrets, tokens, full file contents, and customer identifiers.

Required fix:

- Make event-source selection a blocking decision.
- Define `SidecarObservationProfile` as a strict sanitized subset of the existing outbound query profile.
- Add redaction tests, max byte/token budgets, denied fields, and fail-closed behavior before any backend call.

### 3. Codex OAuth Needs A Separate Credential RFC

Reviewers agreed that preserving Codex OAuth as an adapter is not enough. The RFC does not define token source, storage, scopes, TTL, admin restrictions, revocation, or whether a third-party sidecar may use local Codex credentials.

Required fix:

- Make `OpenAIResponsesBackend` or a documented backend the default for v0.
- Move `CodexOAuthBackend` behind a separate compatibility RFC.
- Require OS keychain storage, no plaintext token reads/logging, explicit scopes/audience, revocation behavior, and no model-visible bearer tokens.

### 4. Active Notes Are A Persistent Injection Surface

The RFC tells the main agent to read `.codex/subconscious/active-notes.md`, but active notes lack non-executable rendering, trust labels, provenance, TTL, dismissal, stale cleanup, and injection filtering.

Required fix:

- Treat `active-notes.md` as a disposable projection, not source of truth.
- Store structured interventions/events separately and regenerate Markdown.
- Add TTL, source/provenance, confidence, risk class, stale status, dismissal, and explicit instruction to ignore any note that attempts to override higher-priority policy.

### 5. Local Store Integrity Is Undefined

The v0 store set lacks write ownership, file locks, atomic writes, fsync/checkpoint semantics, replay, idempotency, schema versioning, corruption repair, and retention.

Required fix:

- Define a local append-only event log or SQLite-backed store.
- Add `schema_version`, `event_seq`, `idempotency_key`, `request_digest`, `source_offset`, `content_digest`, and rebuildable projections.
- Commit offsets only after durable intervention writes.

## Tier 2 - Decide Before Implementation

### 1. Decide Whether RFC 0002 Is Knudg Architecture Or A Separate Local Plugin

RFC 0002 redefines sidecar as a second-opinion agent, while existing Knudg docs use sidecar as a delivery mode for central retrieval. This is a product and architecture fork.

Decision needed:

- Either split this as a separate local Codex plugin design, or define how `Intervention` maps to Knudg's existing retrieval response, delivery modes, trust labels, and no-suggestion behavior.

### 2. Collapse Or Gate `interrupt`

`interrupt` implies immediate delivery, but the current integration only has active notes and an open question about UI/terminal notifications.

Decision needed:

- V0 should probably support only `silent` and `note`.
- Re-enable `interrupt` only after a synchronous delivery path, acknowledgement, rate limits, snooze/dismiss, kill switch, and accessibility behavior exist.

### 3. Fix The Intervention Schema

The schema and examples disagree: `note-on-risk` is not a valid urgency, sidecar output omits required bus-enriched fields, and there is no JSON Schema.

Decision needed:

- Separate sidecar output schema from stored intervention schema.
- Add JSON Schema, schema version, producer version, required fields, enum validation, and compatibility rules.

### 4. Define Rollout And Evaluation

The RFC asserts sidecar second opinion value but does not define evaluation gates.

Decision needed:

- Add shadow mode, labeled review set, note precision target, false-interrupt budget, dismissal rate, disable rate, harmful suggestion rate, and per-workspace kill switch.

## Tier 3 - Future Risk

- The active-note cap of five entries is not an attention policy; ranking, expiry, dismissal, and overflow recovery need rules.
- Local intervention records need retention, compaction, purge, and deletion commands.
- Notification accessibility requirements are absent for UI/terminal interrupt channels.
- RFC 0002 is too broad for one decision record; split future decisions into event source, local-state boundary, intervention schema, credential backend, active notes, watch tasks, and rollout.
- `AGENTS.md` currently points to a draft RFC. Mark this experimental or avoid operationalizing draft behavior.

## Raw Reviewer Output Digest

### Attack Surface

Tier 1 findings:

- Sidecar can exfiltrate session secrets through backend calls.
- Configured watch-task destinations create arbitrary-write and path-traversal risk.
- Active notes are a prompt-injection persistence channel.
- Codex OAuth backend lacks token-boundary requirements.
- Multi-tenant oversight writes can leak one tenant's data into shared notes.

Scores: Correctness 4, Completeness 2, Implementability 3, Resilience 2.

### Production Stress

Tier 1 findings:

- File stores have no atomicity, locking, or corruption recovery.
- Offset processing can lose or duplicate observations after partial failure.
- Backend outage behavior is underspecified and can silently kill the product value.

Scores: Correctness 4, Completeness 2, Implementability 3, Resilience 2.

### Assumption Challenger

Tier 1 findings:

- Codex OAuth backend assumes unsupported credential reuse is safe.
- `local-only` policy creates a raw-transcript exfiltration loophole.
- Watch-task writes bypass consent, audit, and data-boundary rules.
- Interrupt delivery is not reliable enough for "about to do something risky."

Scores: Correctness 4, Completeness 3, Implementability 3, Resilience 3.

### Implementation Reality

Tier 1 findings:

- V0 depends on an unresolved Codex event source.
- Watch-task writes violate the architecture's local-state boundary.
- Backend adapter requires undocumented Codex OAuth behavior.
- Intervention schema is internally inconsistent and not enforceable.

Scores: Correctness 4, Completeness 3, Implementability 3, Resilience 3.

### Schema & Data Integrity

Tier 1 findings:

- Sidecar stores bypass Knudg's canonical data integrity model.
- Active notes are an unversioned projection with no rebuild or corruption recovery.
- Watch-task destinations allow uncontrolled durable writes outside the state boundary.

Scores: Correctness 3, Completeness 2, Implementability 4, Resilience 2.

### Coherence Auditor

Tier 1 findings:

- RFC 0002 creates a local memory/write surface that violates Knudg's local-state boundary.
- Session JSONL observation bypasses the documented sanitized hook/query-profile contract.
- Codex OAuth backend conflicts with Knudg's delegated-token and credential model.

Scores: Correctness 3, Completeness 3, Implementability 4, Resilience 3.

### UX Reviewer

Tier 1 findings:

- Silent watch-task writes bypass consent and recoverability.
- Cloud/backend observation consent is undefined.
- Interruptions are specified before notification fatigue controls exist.

Scores: Correctness 4, Completeness 3, Implementability 4, Resilience 3.

## Statistics

- Total synthesized findings: 22
- Tier 1 synthesized findings: 5
- Tier 2 synthesized findings: 4
- Tier 3 synthesized findings: 5
- Cross-lane convergence 3+: 7
- Cross-lane convergence 2: 4
- Average weighted score: 3.23/10

## Verdict

RFC 0002 is a useful direction but not implementable as written. The design should be revised before coding. The highest-leverage fix is to decide the product boundary first: either this is a separate local Codex sidecar experiment, or it must conform to Knudg's central-search, consent, local-state, and retrieval-safety invariants.
