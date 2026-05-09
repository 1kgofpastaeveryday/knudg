# Adversarial Design Review - 2026-05-09

## Review Configuration

- Date: 2026-05-09
- Project: `D:\working\knudg`
- Focus: General full adversarial review after intent-drift fixes
- Tier: full
- Reviewers: 7 total, all `gpt-5.5`
  - Attack Surface
  - Production Stress
  - Assumption Challenger
  - Implementation Reality
  - Schema & Data Integrity
  - Coherence Auditor
  - UX Reviewer
- Execution mode: Codex-native subagents
- Live QA: not requested
- Rounds: 1/1
- Review targets:
  - `README.md`
  - `user-said.md`
  - `docs/README.md`
  - `docs/architecture/*.md`
  - `docs/product/*.md`
  - `docs/plans/*.md`

## Scoring Summary

| Reviewer | Correctness | Completeness | Implementability | Resilience | Weighted Avg |
|---|---:|---:|---:|---:|---:|
| Attack Surface | 6 | 5 | 5 | 4 | 5.25 |
| Production Stress | 6 | 4 | 5 | 4 | 5.00 |
| Assumption Challenger | 7 | 5 | 6 | 5 | 6.00 |
| Implementation Reality | 6 | 5 | 4 | 6 | 5.25 |
| Schema & Data Integrity | 5 | 5 | 5 | 5 | 5.00 |
| Coherence Auditor | 6 | 5 | 5 | 6 | 5.50 |
| UX Reviewer | 6 | 4 | 5 | 5 | 5.13 |
| **Average** | **6.00** | **4.71** | **5.00** | **5.00** | **5.30** |

PASS/FAIL: **PASS by threshold, but not implementation-ready.** No average axis is <= 3. The design direction is coherent enough to continue, but full-tier review found many blocking specs missing before MVP implementation.

## Cross-Lane Convergence

### Issues identified by 3+ reviewers

| Issue | Reviewers | Tier | Confidence |
|---|---|---|---|
| MCP/CLI/hooks and agent access contract are missing | Attack Surface, Implementation Reality, Coherence Auditor, UX | Tier 1-2 | HIGH |
| Consent and derived artifact policy are still not concrete enough | Assumption Challenger, Schema & Data Integrity, UX, Attack Surface | Tier 1 | HIGH |
| Revocation is promised as immediate but not enforceable across states, caches, indexes, derived artifacts | Production Stress, Schema & Data Integrity, Attack Surface, UX | Tier 1-3 | HIGH/MEDIUM |
| State machine / lifecycle is too abstract for implementation | Implementation Reality, Schema & Data Integrity, Coherence Auditor | Tier 1-2 | HIGH |
| Operations controls are telemetry-only: missing thresholds, budgets, runbook steps, queue contract | Production Stress, Attack Surface, Implementation Reality | Tier 1-2 | HIGH |
| Human approval/review is underspecified and may become rubber-stamp consent | UX, Assumption Challenger, Attack Surface | Tier 1-3 | HIGH/MEDIUM |

### Issues identified by 2 reviewers

| Issue | Reviewers | Tier | Confidence |
|---|---|---|---|
| Tenant isolation/RLS and delegated token model need concrete specs | Attack Surface, Schema & Data Integrity | Tier 1 | HIGH |
| Raw artifact encryption/retention needs key management and explicit UX | Attack Surface, UX | Tier 1 | HIGH |
| Public corpus quality governance is not operationally defined | Assumption Challenger, Production Stress | Tier 1 | HIGH |
| pgvector/index implementation details are not fixed | Implementation Reality, Schema & Data Integrity | Tier 1-2 | HIGH/MEDIUM |
| Review reports and deferred decisions need current/historical/ADR tracking | Coherence Auditor, Assumption Challenger | Tier 2-3 | MEDIUM |

## Tier 1 - Immediate Fix Required

### T1-01 Agent access and delegated token model are underspecified

- Reviewers: Attack Surface, Implementation Reality, Coherence Auditor
- Confidence: HIGH
- Docs: `README.md`, `docs/architecture/security-privacy.md`, `docs/product/intent-crosswalk.md`
- Issue: MCP/CLI/hooks are central to product intent, but method schemas, transport, auth, token scopes, expiry, local storage, refresh, revocation, origin validation, and error behavior are undefined.
- Risk: A stolen local token or fake MCP/hook process can read private/team corpus data, submit poison candidates, or incur paid usage under the victim tenant.
- Required fix: Add `docs/architecture/agent-access.md` with one MVP transport and concrete contracts for `search_similar`, `submit_candidate`, `ask_approval`, `approve_publication`, `revoke_card`, `get_card`, `before_prompt`, and `after_solve`. Define delegated token TTL, audience, tenant/namespace/operation scopes, local storage, rotation, revocation, read/write split, and billing split.

### T1-02 Approval, consent, and derived artifact policy are not implementable

- Reviewers: Assumption Challenger, Schema & Data Integrity, UX, Attack Surface
- Confidence: HIGH
- Docs: `docs/architecture/security-privacy.md`, `docs/architecture/data-model.md`, `docs/architecture/overview.md`, `docs/product/strategy.md`
- Issue: The docs say public consent binds to exact redacted artifacts, but canonical trails, verified rewrites, curated packs, aggregate stats, raw artifact retention, and future monetized bundles do not have a concrete consent matrix.
- Risk: Users may approve one card and later find it used in an edited, monetized, or broader artifact they did not understand or approve.
- Required fix: Add a consent surface matrix covering public card, canonical trail, aggregate stats, verified rewrite, curated pack, model/eval use, and raw retention. For each: default, displayed artifact, inheritance allowed, renewed consent required, revocation effect, monetization allowed.

### T1-03 Revocation is promised but not enforced across all projections and states

- Reviewers: Production Stress, Schema & Data Integrity, Attack Surface, UX
- Confidence: HIGH
- Docs: `docs/architecture/data-model.md`, `docs/architecture/security-privacy.md`, `docs/architecture/retrieval.md`, `docs/architecture/operations.md`
- Issue: `revoked blocks retrieval immediately` is stated, but revocation transitions cover only `indexed_hot` and `indexed_main`. Approved-but-not-indexed, deprecated, superseded, source artifacts, derived artifacts, local caches, and older index generations lack a hard revocation fence.
- Risk: Revoked cards or derived artifacts can remain retrievable through stale indexes, local caches, or canonical trails.
- Required fix: Define tombstone/revocation as an independent deny source checked by every read path. Add transitions or propagation states for `approved`, `deprecated`, `superseded`, derived artifacts, source artifacts, and consent expiration. Add revocation epoch/high-watermark validation to search responses and caches.

### T1-04 State lifecycle and visibility rules are inconsistent

- Reviewers: Coherence Auditor, Implementation Reality, Schema & Data Integrity
- Confidence: HIGH
- Docs: `docs/architecture/data-model.md`, `docs/architecture/retrieval.md`, `docs/architecture/security-privacy.md`
- Issue: `pending_admission`, `deferred`, and `rejected` exist in the data model but are absent from retrieval visibility rules. `visibility=public` is not tied to a clear publish event or actor. User approval, reviewer publish, indexing eligibility, and namespace policy are not integrated.
- Risk: Implementers can accidentally make deferred/rejected cards searchable or set public visibility without the intended approval/publish boundary.
- Required fix: Add a full status-to-visibility matrix and a `card_state_transitions` table with from/to state, actor, event, precondition, idempotency scope, side effects, timeout, and terminal semantics. Add explicit publish event/state.

### T1-05 Tenant isolation, RLS, and data constraints are too abstract

- Reviewers: Schema & Data Integrity, Attack Surface
- Confidence: HIGH
- Docs: `docs/architecture/security-privacy.md`, `docs/architecture/data-model.md`
- Issue: Tenant-scoped tables must include `tenant_id`, but table-by-table composite keys, FK patterns, RLS policies, `WITH CHECK`, worker/admin roles, and BYPASSRLS controls are not specified.
- Risk: Implementers may use single-column FKs or app-only tenant filters, creating cross-tenant reads/writes.
- Required fix: Standardize `(tenant_id, id)` keys for tenant-scoped tables, composite FKs, RLS policies per role, admin/break-glass exceptions, and DDL-level test expectations.

### T1-06 Raw artifact encryption and retention lack key management

- Reviewers: Attack Surface, UX
- Confidence: HIGH
- Docs: `docs/architecture/security-privacy.md`, `docs/architecture/overview.md`
- Issue: Raw artifacts must be encrypted, but KMS/envelope encryption, tenant keys, key rotation, break-glass decrypt, pre-signed URL TTL, crypto-shred, and retention UX are not defined.
- Risk: A storage or admin compromise exposes raw logs, stack traces, private repo names, customer names, or residual secrets.
- Required fix: Define tenant-scoped envelope keys, per-object data keys, rotation, decrypt roles, two-person break-glass, audit, TTL expiry, key destruction, and raw retention consent UI.

### T1-07 Production controls are not operationally actionable

- Reviewers: Production Stress, Attack Surface, Implementation Reality
- Confidence: HIGH
- Docs: `docs/architecture/operations.md`, `docs/architecture/overview.md`, `docs/product/strategy.md`
- Issue: Fallback order, circuit breakers, queue/backlog, cost metrics, and runbook names exist, but no thresholds, budgets, deadlines, queue delivery contract, redrive rules, or force-degraded procedures exist.
- Risk: Search path, redaction/review queues, reranking, embeddings, and reindexing can overload, stall, or run up costs before operators know what to stop.
- Required fix: Add provisional operational defaults: per-dependency deadlines, global retrieval budget, circuit open/half-open, no-suggestion fail-closed, queue visibility timeout, retry cap, DLQ retention/redrive, intake quota, review capacity, spend caps, and first-5-minutes runbook steps.

### T1-08 Human approval UX is too weak for privacy-critical consent

- Reviewers: UX, Assumption Challenger
- Confidence: HIGH
- Docs: `docs/architecture/security-privacy.md`, `docs/architecture/data-model.md`
- Issue: Approval UI shows exact artifact and redaction summary, but there is no flow for request-more-redaction, keep-private, discard, raw opt-in, derived-use choices, consent history, or revocation status.
- Risk: Consent becomes a checkbox rather than informed permission. Users cannot selectively approve or understand outcomes.
- Required fix: Define consent/revocation cockpit requirements for CLI or web: public preview, redaction diff, residual risk, separate raw retention, derived-use choices, deny/edit path, digest invalidation after edits, revoke status, and audit history.

## Tier 2 - Decide Before Implementation

### T2-01 pgvector and index contracts need concrete values

- Reviewers: Implementation Reality, Schema & Data Integrity
- Confidence: HIGH
- Docs: `docs/architecture/retrieval.md`, `docs/architecture/data-model.md`
- Required fix: Define embedding table design, vector dimensions, distance operator, HNSW params, tenant/namespace partition or partial index strategy, SQL patterns, exact fallback, active generation uniqueness, high-watermark, and revocation replay watermark.

### T2-02 DDL-level schema RFC is required

- Reviewers: Implementation Reality, Schema & Data Integrity
- Confidence: HIGH
- Docs: `docs/architecture/data-model.md`
- Required fix: Produce `schema.sql` or a schema RFC with PK/FK, partial unique indexes, nullable rules, JSONB validation policy, `ON DELETE` choices, `card_edges` uniqueness, `consent_records` uniqueness, source artifact constraints, and outcome/status compatibility checks.

### T2-03 Queue and provider decisions block implementation

- Reviewers: Production Stress, Implementation Reality
- Confidence: HIGH
- Docs: `docs/architecture/overview.md`, `docs/architecture/retrieval.md`
- Required fix: Choose Postgres-backed queue or managed queue for MVP. Define lease, visibility timeout, ordering expectations, consumer concurrency, retry, DLQ, redrive, outbox/inbox tables, object manifest format, key prefix, checksum, encryption, signed access, and purge path.

### T2-04 Public corpus quality and reviewer governance need gates

- Reviewers: Assumption Challenger, Attack Surface
- Confidence: HIGH/MEDIUM
- Docs: `docs/product/strategy.md`, `docs/architecture/security-privacy.md`
- Required fix: Add review capacity/week, stale-card removal SLA, harmful accepted card rate, duplicate merge rate, reviewer disagreement rate, reviewer assignment, conflict of interest, sybil/reputation farming controls, and high-risk card reproduction requirements.

### T2-05 MVP value and economics need kill criteria

- Reviewers: Assumption Challenger, Production Stress, UX
- Confidence: HIGH/MEDIUM
- Docs: `docs/product/strategy.md`, `docs/architecture/retrieval.md`
- Required fix: Separate metrics for public corpus, team/private corpus, and same-session local cache. Add time-to-fix, tool-call count, failed-command count, human-intervention count, query gross margin, approved-card cost, free-tier abuse budget, and public expansion stop conditions.

### T2-06 UI/accessibility requirements must be baseline for consent surfaces

- Reviewers: UX
- Confidence: HIGH
- Docs: `docs/architecture/security-privacy.md`, `docs/architecture/retrieval.md`
- Required fix: Make WCAG 2.2 AA baseline for approval, revocation, warning, and async state UI. Define focus management, keyboard access, ARIA status, labels, target size, error recovery, and reduced motion.

### T2-07 Current/historical review and deferred decisions need tracking

- Reviewers: Coherence Auditor, Assumption Challenger
- Confidence: MEDIUM
- Docs: `docs/README.md`, `docs/plans/*.md`, `docs/product/intent-crosswalk.md`
- Required fix: Mark review reports as historical/current/superseded. Add `docs/rfcs/` or `docs/decisions/` with IDs for deferred provider, queue, SLO, ranking, quality, schema, and consent decisions.

## Tier 3 - Future Risk

- `user-said.md` and README Japanese excerpts are mojibake, weakening traceability evidence.
- Local card body cache opt-in can reintroduce stale or revoked card display if not prohibited in MVP.
- Postgres enum use may create difficult rollback semantics; lookup tables may be safer for lifecycle values.
- Dedupe/variant/duplicate semantics need composite uniqueness or fingerprint manifests.
- Search response lacks machine-readable `decision`, `abstention_reason`, `threshold_version`, `signals`, `served_from`, and latency budget fields.
- Unknown/failed-only cards are first-class conceptually, but outcome-specific index materialization and display templates are not defined.
- Onboarding can become trust-before-value unless first run defaults to search-only/private-only/publish-later.
- Candidate-path-not-truth needs shared labels such as `Verified fix`, `Single-session clue`, `Known failed path`, `Clarified unknown`, `Disputed`, `Deprecated`.

## Raw Reviewer Output Inventory

This section records the raw finding inventory by lane. Full finding text was captured in the Codex subagent outputs for this run; the consolidated Tier sections above are the action-oriented synthesis.

### Attack Surface

- AS-01 Agent delegated token model is too broad and unspecified
- AS-02 Publish approval lacks CSRF/replay/step-up protection
- AS-03 Raw artifact encryption lacks key management
- AS-04 Rate limits/spend caps are too abstract
- AS-05 Hostile card controls are checklist items, not policy
- AS-06 MCP/CLI/hooks attack boundary is undefined
- AS-07 Platform admin/break-glass is overprivileged
- AS-08 Public search fingerprint can leak rare identifiers
- AS-09 Revocation can fail through cache/index artifacts
- AS-10 Billing/admin API is not integrated with tenant isolation
- AS-11 Reviewer reputation can be farmed for poisoning

### Production Stress

- PS-01 Read-path stop conditions are operationally undefined
- PS-02 Immediate revocation is not guaranteed across projections
- PS-03 Intake/backlog controls remain conceptual
- PS-04 Queue delivery semantics are not fixed
- PS-05 Reindex/embedding rollback is named but not specified
- PS-06 Cost runaway controls stop at telemetry
- PS-07 Local body cache opt-in can cause stale body incidents
- PS-08 Runbook names do not allow on-call recovery

### Assumption Challenger

- AC-T1-01 Card-level consent may not cover derived artifacts
- AC-T1-02 Public corpus quality may not be maintainable by human review alone
- AC-T2-01 "Agents don't start from zero" is not yet a falsifiable value metric
- AC-T2-02 Public global DB may lose to private/team corpus in practical value
- AC-T2-03 Dev-tooling wedge may contaminate global ontology
- AC-T2-04 Monetization may not recover shared infrastructure costs
- AC-T3-01 Intent crosswalk is not requirements traceability
- AC-T3-02 Human-in-the-loop can become rubber-stamp review

### Implementation Reality

- IR-01 MCP/CLI/hooks are not implementation specs
- IR-02 pgvector query contract is not fixed
- IR-03 Lifecycle is not implementable as DB constraints
- IR-04 Canonical tables are not DDL
- IR-05 Queue is not selected and has no delivery contract
- IR-06 Migration policy is too abstract for Postgres realities
- IR-07 Provider boundary blocks worker/object-storage implementation
- IR-08 Search response lacks machine-readable decision/debug contract
- IR-09 Unknown/failed-only cards lack index table design
- IR-10 MVP scope is too large without milestone cuts

### Schema & Data Integrity

- SDI-T1-01 tenant_id/RLS is not an implementation spec
- SDI-T1-02 Revocation does not reach all states
- SDI-T1-03 Consent records and derived artifacts lack constraints
- SDI-T2-01 outcome_type lacks CHECK constraints
- SDI-T2-02 Event sourcing lacks aggregate ordering/optimistic concurrency
- SDI-T2-03 Index manifest cannot guarantee search integrity
- SDI-T2-04 source_artifacts lack FK/TTL/encryption metadata
- SDI-T3-01 Postgres enum lifecycle is undecided
- SDI-T3-02 dedupe/variant uniqueness is undefined

### Coherence Auditor

- T1-01 State enum and retrieval visibility rules disagree
- T1-02 Approval/publish/indexing responsibilities are missing from lifecycle
- T2-01 MCP/CLI/hooks are required but have no spec document
- T2-02 Review reports mix current state and history
- T2-03 `deferred` has no exit semantics
- T3-01 Deferred decisions are not tracked as ADR/RFC backlog
- T3-02 Japanese source quotes are mojibake and weak for traceability

### UX Reviewer

- UX-01 Approval UI records consent but not understanding
- UX-02 Revocation lacks user-visible outcome confirmation
- UX-03 Raw artifact opt-in can be confused with publish consent
- UX-04 sidecar/inline/no_suggestion lack user-facing state semantics
- UX-05 Onboarding risks asking for trust before showing value
- UX-06 Future UI has no accessibility baseline
- UX-07 Curated packs/contributor incentives lack expectation setting
- UX-08 Error recovery is operator-facing, not user-facing
- UX-09 Candidate-not-truth is not translated into labels
- UX-10 Consent/revocation UI cannot be postponed with the polished UI

## Statistics

- Total findings: 63
- Tier 1: 19
- Tier 2: 27
- Tier 3: 17
- Cross-lane convergence (3+): 6
- Cross-lane convergence (2): 5
- Average weighted score: 5.30/10

