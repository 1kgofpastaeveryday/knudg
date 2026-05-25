# Adversarial Design Review - 2026-05-09 R4

## Review Configuration

- Date: 2026-05-09
- Project: Knudg repository root
- Focus: Codex subconscious sidecar design after RFC 0002 rewrite
- Tier: full
- Reviewers: 7 requested, 6 completed
  - Completed subagent lanes: Attack Surface, Production Stress, Assumption Challenger, Implementation Reality, Schema & Data Integrity, Coherence Auditor
  - Failed lane: UX Reviewer was shut down before completion
  - `codex exec` lanes: none
  - Live QA: not requested
- Review targets:
  - `AGENTS.md`
  - `README.md`
  - `docs/README.md`
  - `docs/architecture/*.md`
  - `docs/product/*.md`
  - `docs/rfcs/0001-m0-schema-event-log.md`
  - `docs/rfcs/0002-codex-subconscious-sidecar.md`

## Scoring Summary

| Reviewer | Correctness | Completeness | Implementability | Resilience | Weighted Avg |
| --- | ---: | ---: | ---: | ---: | ---: |
| Attack Surface | 5 | 3 | 4 | 3 | 4.00 |
| Production Stress | 5 | 3 | 4 | 2 | 3.88 |
| Assumption Challenger | 5 | 4 | 4 | 4 | 4.38 |
| Implementation Reality | 5 | 3 | 3 | 4 | 3.88 |
| Schema & Data Integrity | 4 | 3 | 4 | 3 | 3.63 |
| Coherence Auditor | 4 | 4 | 3 | 4 | 3.75 |
| UX Reviewer | unavailable | unavailable | unavailable | unavailable | unavailable |
| **Average, completed lanes** | **4.67** | **3.33** | **3.50** | **3.33** | **3.92** |

PASS/FAIL: **FAIL**.

Reason: multiple completed lanes scored at least one axis `<= 3`, and Production Stress scored Resilience `2`. The design is substantially clearer than the prior version, but it is still not implementation-ready.

## Round Comparison

| Round | Average Weighted Score | Status |
| --- | ---: | --- |
| R3 | 3.23 | FAIL |
| R4 | 3.92 | FAIL |

Main improvement: the rewritten RFC now clearly separates the sidecar from Knudg's normative architecture, removes Letta compatibility, excludes external writes, blocks Codex OAuth pending a credential RFC, and makes `interrupt` non-v0.

Remaining blockers are lower-level but still critical: the local state contract, projection safety, schema consistency, credential/backend contract, and AGENTS runtime behavior are not yet precise enough to implement.

## Cross-Lane Convergence

Issues identified by 3+ reviewers:

| Issue | Reviewers | Tier | Confidence |
| --- | --- | --- | --- |
| `StoredIntervention` schema is impossible because it intersects incompatible `schemaVersion` literals | Implementation Reality, Schema & Data Integrity, Coherence Auditor | 1 | HIGH |
| Local sidecar state conflicts with Knudg's local-state and non-personal-memory guardrails | Attack Surface, Assumption Challenger, Implementation Reality, Schema & Data Integrity, Coherence Auditor | 1-3 | HIGH/MEDIUM |
| Active notes projection is unsafe or underspecified as an agent-readable file | Attack Surface, Production Stress, Assumption Challenger, Schema & Data Integrity, Coherence Auditor | 1-2 | HIGH |
| Event source remains blocking and JSONL/app-server/plugin-hook paths are not specified | Assumption Challenger, Implementation Reality, Production Stress, Coherence Auditor | 1-2 | HIGH/MEDIUM |
| SQLite/local event store lacks an enforceable DDL and integrity contract | Production Stress, Implementation Reality, Schema & Data Integrity | 1-2 | HIGH |
| Backend/credential/privacy contract is too thin for OpenAI Responses or API-key use | Attack Surface, Assumption Challenger, Implementation Reality, Coherence Auditor | 1-2 | HIGH |

Issues identified by 2 reviewers:

| Issue | Reviewers | Tier | Confidence |
| --- | --- | --- | --- |
| Watch tasks create a second local queue/product surface without enough schema or ownership | Assumption Challenger, Schema & Data Integrity | 2 | MEDIUM |
| Dedupe/idempotency uses undefined or unstable fields | Production Stress, Schema & Data Integrity | 2-3 | MEDIUM/HIGH |
| Safety rules lack concrete detectors, fixtures, and renderer tests | Attack Surface, Implementation Reality | 1-3 | MEDIUM/HIGH |
| Evaluation gates are named but not operational or traceable to product gates | Assumption Challenger, Coherence Auditor | 2-3 | MEDIUM/HIGH |

## Tier 1 - Immediate Fix Required

### 1. Fix The Stored Intervention Type

`StoredIntervention = DraftIntervention & { schemaVersion: "stored_intervention.v0" }` is unsatisfiable because `DraftIntervention.schemaVersion` is already `"draft_intervention.v0"`.

Required fix:

- define a shared base type without `schemaVersion`
- define `DraftIntervention` and `StoredIntervention` as separate variants
- optionally store `draftSchemaVersion: "draft_intervention.v0"` on stored rows
- add JSON Schema examples that validate both variants

### 2. Stop AGENTS From Making Draft RFC Behavior Operational

`AGENTS.md` currently tells Codex to check `.codex/subconscious/active-notes.md` if the sidecar experiment is enabled. Reviewers flagged this because RFC 0002 is explicitly draft, non-normative, and blocked before implementation.

Required fix:

- make the enablement gate concrete, for example a checked config flag plus existing readable projection
- state that this is outside Knudg normative architecture
- define precedence: active notes are always advisory and never implementation-authoritative
- fail closed when the projection is missing, stale, malformed, or unverifiable

### 3. Define The Local Privacy Boundary Before Any Active Notes

The sidecar stores work-derived summaries, topics, offsets, digests, risk classes, and active notes. That is local durable state. It currently conflicts with Knudg's stated local-state limit unless framed as a separate local tool with its own privacy contract.

Required fix:

- make encryption-at-rest, OS keychain secret handling, file permissions, purge verification, and sync/backup exclusion explicit
- shorten or justify default retention
- state whether this is non-Knudg local plugin state or update architecture docs to allow it
- prohibit Knudg-derived card content in active notes until revocation/freshness metadata exists

### 4. Harden Active Notes As An Untrusted Projection

The active notes file is a prompt-injection and local-file integrity surface. The RFC says it is disposable, but not how it is generated, verified, or rejected.

Required fix:

- generate with temp file, fsync, atomic replace, and a DB high-water mark
- include generation timestamp, schema version, event sequence, and projection digest
- define stale/partial/corrupt read behavior as fail-closed
- reject symlinks, junctions, reparse points, and hardlinks for state/projection paths
- treat Markdown as untrusted data, not instructions

### 5. Pick Or Narrow The Event Source

The design still depends on an undecided producer. JSONL is explicitly experimental, while app-server and plugin-hook paths are named but not specified.

Required fix:

- split `prototype-spike` from `implementation-spec`
- make v0 only the event-source spike plus offline sanitizer/backend evaluation, or choose one supported event path
- define file discovery, source identity, offsets, partial writes, rotation, truncation, invalid JSON, duplicates, and deprecation behavior

## Tier 2 - Decide Before Implementation

### 1. Add Concrete SQLite DDL And Recovery Rules

Column inventories are not enough. The RFC needs primary keys, uniqueness, nullability, enum checks, indexes, migration tracking, append-only behavior, WAL/busy-timeout policy, corruption checks, quarantine rules, and replay tests.

### 2. Specify Backend Adapter Behavior

`OpenAIResponsesBackend` needs a real contract:

- model allowlist
- request shape
- structured-output schema and strict validation
- `store=false` or explicit retention policy
- disabled remote tools/MCP/background behavior unless separately approved
- refusal/invalid-output handling
- timeout/retry/backoff/circuit-breaker policy
- cost and rate-limit controls

### 3. Define Digest, ID, And Dedupe Semantics

`sessionIdHash`, `workspaceIdHash`, `sourceRangeDigest`, `observationDigest`, `contentDigest`, and generated IDs need canonicalization rules, HMAC/salt policy, encoding, collision handling, and rotation behavior.

The current dedupe key also depends on `normalizedSummary`, which is undefined and may vary with model wording.

### 4. Reduce V0 Scope

Several reviewers converged on narrowing v0 to:

- event-source spike
- sanitizer fixtures
- offline draft generation
- no active notes until projection safety exists
- no watch tasks until there is a first-class local job schema
- no CLI dismiss/clear/purge beyond what is needed for the spike

### 5. Define Evaluation Gates Operationally

Metric names need denominators, thresholds, test data, sampling, stop conditions, and a no-sidecar baseline. Include time-to-resolution delta and harmful-suggestion rate, not just note precision.

## Tier 3 - Future Risk

- The term `sidecar` is overloaded with Knudg retrieval sidecar semantics. Rename this component or add a crosswalk.
- Watch tasks can become a hidden queue system even without external writes.
- Local notes could preserve stale or revoked Knudg-derived guidance unless they carry revocation/freshness metadata.
- Event-log language can create false equivalence with RFC 0001's canonical event log.
- Subconscious notes can shift product gravity toward a local memory plugin unless graduation rules are explicit.

## Raw Reviewer Output Summaries

### Attack Surface

Key findings:

- active notes are a workspace-writable prompt-injection channel
- projection generation may write through symlinks/junctions unless explicitly defended
- sanitized free text can still carry secrets or prompt-injection content
- API keys and local SQLite storage need stricter privacy/security rules
- event-source scraping needs source-root and authorization boundaries

Scores: Correctness 5, Completeness 3, Implementability 4, Resilience 3, weighted 4.00.

### Production Stress

Key findings:

- `active-notes.md` can be corrupt, partial, or stale after crashes
- backend failure handling lacks timeouts, retries, backoff, circuit breaker, rate-limit handling, and metrics
- one-writer rule lacks lease/fencing implementation
- JSONL rotation/truncation recovery has no acceptance contract
- local observability and runbooks are missing

Scores: Correctness 5, Completeness 3, Implementability 4, Resilience 2, weighted 3.88.

### Assumption Challenger

Key findings:

- local-only does not remove privacy risk
- Responses backend retention and data-control assumptions are underspecified
- event-source premise depends on unstable Codex internals unless mapped to supported hooks/app-server contracts
- active notes may be ignored, over-weighted, or stale without an acknowledgement and telemetry contract
- watch tasks add product surface and queue semantics

Scores: Correctness 5, Completeness 4, Implementability 4, Resilience 4, weighted 4.38.

### Implementation Reality

Key findings:

- `StoredIntervention` type is unimplementable
- event source is explicitly undecided while v0 depends on it
- active notes create a local memory surface conflicting with product architecture
- SQLite contract is not a buildable schema
- file watching and JSONL tail semantics are underdefined
- backend adapter is too thin to code

Scores: Correctness 5, Completeness 3, Implementability 3, Resilience 4, weighted 3.88.

### Schema & Data Integrity

Key findings:

- `StoredIntervention` type is unsatisfiable
- SQLite event store lacks enforceable constraints
- offset retention can cause duplicate or lost processing
- `event_seq` semantics conflict with RFC 0001 unless renamed/scoped
- digest/ID canonicalization is undefined
- active notes projection lacks atomic write and generation rules
- watch task config lacks schema and identity model

Scores: Correctness 4, Completeness 3, Implementability 4, Resilience 3, weighted 3.63.

### Coherence Auditor

Key findings:

- `AGENTS.md` makes draft RFC behavior operationally authoritative
- `StoredIntervention` schema is internally impossible
- durable local sidecar state violates Knudg local-state limits
- `sidecar` names two incompatible delivery mechanisms
- RFC 0002 bypasses central trust labels and response safety fields
- credential model is inconsistent with existing agent-access rules

Scores: Correctness 4, Completeness 4, Implementability 3, Resilience 4, weighted 3.75.

### UX Reviewer

Unavailable. The subagent did not complete and was shut down before returning findings.

## Statistics

- Completed reviewer lanes: 6/7
- Total synthesized findings: 30
- Tier 1: 12
- Tier 2: 13
- Tier 3: 5
- Cross-lane convergence, 3+ reviewers: 6
- Cross-lane convergence, 2 reviewers: 4
- Average weighted score, completed lanes: 3.92/10

## Next Fix Set

Recommended next fix pass:

1. Correct `StoredIntervention` and schema wording.
2. Move AGENTS active-note behavior behind an explicit, fail-closed local-experiment gate.
3. Rewrite local state as a `local sidecar journal` with concrete SQLite DDL, atomic projection rules, corruption recovery, and retention/privacy rules.
4. Narrow v0 to event-source spike plus offline draft generation, deferring active notes and watch tasks.
5. Add backend and credential requirements for Responses API use before any outbound calls.
