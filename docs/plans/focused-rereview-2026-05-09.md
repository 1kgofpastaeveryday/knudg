# Focused Re-Review - 2026-05-09

Status: historical review artifact, non-normative. This file records a point-in-time review result and does not define the current implementation gate. Current gates live in `docs/architecture/implementation-readiness.md`, `docs/decisions/README.md`, and accepted RFCs.

## Review Configuration

- Date: 2026-05-09
- Project: `D:\working\knudg`
- Focus: Re-review after `e1e4517 Address full review implementation blockers`
- Scope:
  - `docs/architecture/agent-access.md`
  - `docs/architecture/consent-revocation-ux.md`
  - `docs/architecture/implementation-readiness.md`
  - `docs/decisions/README.md`
  - touched architecture/product docs
- Method: focused local review against the prior full-review blockers
- Sources checked:
  - PostgreSQL Row Security Policies
  - PostgreSQL CREATE INDEX
  - OWASP API Security Top 10 2023
  - Model Context Protocol authorization and transports

## Result

Status at time of review: **M0 can start after small doc cleanups.**

The previous full-review blockers are materially reduced:

- Agent access now has transport, token, operation, hook, response, and failure contracts.
- Consent/revocation now has a consent surface matrix, approval challenge, raw-retention split, and revocation cockpit.
- Implementation readiness now defines milestones, provisional defaults, queue defaults, migration requirements, event ordering, revocation fence, cost circuits, and runbook template.
- Decision backlog now tracks deferred decisions with defaults.

At the time of this focused review, the design was no longer a "do not implement" design. Later reviews may supersede this readiness assessment; use the current decision backlog and accepted RFCs for implementation gates.

## Findings

### Tier 1 - Immediate Fix Required

No Tier 1 findings.

### Tier 2 - Decide Before Implementation

#### FRR-T2-01 Approval completion is both idempotent and "no replay"

- Confidence: MEDIUM
- Docs: `docs/architecture/agent-access.md`
- Issue: `approve_publication` says idempotency is required but retry is `no replay`. Later, the same doc says retried writes with the same request digest return the original effect.
- Why it matters: implementers may reject legitimate network retries of approval completion, or accidentally allow the approval challenge itself to be replayed.
- Recommendation: clarify that the approval challenge is single-use, while the idempotency key can return the already-completed result for the same digest without creating a second publish effect.

#### FRR-T2-02 Human-only approval boundary should be explicit in Agent Access

- Confidence: MEDIUM
- Docs: `docs/architecture/agent-access.md`, `docs/architecture/security-privacy.md`
- Issue: Security/privacy says agent clients cannot approve publication, but Agent Access lists `approve_publication` as a protected operation without saying it is human-session only.
- Why it matters: a future MCP/CLI implementer could expose approval completion as an agent-callable tool.
- Recommendation: mark `approve_publication` as human-session only. MCP/CLI may open or display the approval challenge, but the agent cannot complete it.

#### FRR-T2-03 Object storage provider remains open while M1 includes private candidates

- Confidence: MEDIUM
- Docs: `docs/architecture/implementation-readiness.md`, `docs/decisions/README.md`
- Issue: M1 includes private writer queue and private candidates, but `DEC-003` object storage provider is open and also blocks M1.
- Why it matters: if M1 needs only metadata and redacted draft text in Postgres, object storage can wait. If M1 stores source artifacts, provider choice blocks M1.
- Recommendation: specify M1 storage boundary. Suggested conservative default: M1 stores candidate metadata and redacted draft bodies in Postgres only; raw/source artifacts stay disabled until M2/deployment RFC pins object storage.

#### FRR-T2-04 M0 requires a DDL RFC, but no RFC skeleton exists

- Confidence: HIGH
- Docs: `docs/architecture/implementation-readiness.md`, `docs/decisions/README.md`
- Issue: M0 says DDL RFC is required, but there is no `docs/rfcs/` skeleton or M0 schema RFC.
- Why it matters: implementation can start only by inventing the RFC shape in code or prose.
- Recommendation: add `docs/rfcs/0001-m0-schema-event-log.md` before code, covering tenant keys, RLS, tables, event ordering, tombstones, idempotency, and migration rules.

### Tier 3 - Future Risk

#### FRR-T3-01 Consent matrix default wording can confuse "surface off" vs "inheritance allowed"

- Confidence: LOW
- Docs: `docs/architecture/consent-revocation-ux.md`
- Issue: Canonical trail row says default `off` and inheritance `yes, only for deterministic aggregation`. That is defensible, but the distinction between product surface disabled and consent inheritance allowed is subtle.
- Recommendation: add one sentence: "Default off means the surface is not launched; if launched, this row controls consent behavior."

#### FRR-T3-02 M5 agent access may be too late for an agent-native product

- Confidence: LOW
- Docs: `docs/architecture/implementation-readiness.md`, `README.md`
- Issue: M3 has retrieval sidecar, but Agent Access is M5. Since access contracts now exist, implementation may need a minimal CLI/API path earlier for M3 testing.
- Recommendation: keep full MCP/hooks at M5, but allow a minimal internal CLI/API harness in M3 for exact/FTS sidecar testing.

## Score

| Axis | Score |
|---|---:|
| Correctness | 7 |
| Completeness | 7 |
| Implementability | 7 |
| Resilience | 7 |

## Recommendation

At the time of this review, the recommended follow-up was:

1. Apply the small doc cleanups above.
2. Create the M0 schema/event-log RFC.
3. Start implementation only after the M0 RFC exists.

M0 implementation should be intentionally narrow:

- Postgres schema
- tenant/RLS policy
- event log
- card state transition table
- tombstones/revocation fence
- idempotency keys
- migration harness

Do not start retrieval, MCP, raw artifact storage, public corpus, or consent UI implementation before M0 is stable.
