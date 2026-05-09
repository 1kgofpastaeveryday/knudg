# Adversarial Design Review - 2026-05-09 R2

Status: historical review artifact, non-normative.

This review used the updated `adversarial-review` skill configuration with fresh reviewer agents. Reviewers were given only the current repository review targets and lane-specific instructions, with no prior review summaries or fix context injected into their prompts.

## Configuration

| Field | Value |
|---|---|
| Date | 2026-05-09 |
| Project | Knudg |
| Tier | Mid |
| Rounds | 1 |
| Live QA | Not requested |
| Reviewer lanes | Attack Surface, Production Stress, Assumption Challenger, Implementation Reality, Coherence Auditor |
| Output | `docs/plans/adversarial-review-2026-05-09-r2.md` |

## Review Targets

- `README.md`
- `user-said.md`
- `docs/README.md`
- `docs/architecture/*.md`
- `docs/product/*.md`
- `docs/decisions/README.md`
- `docs/rfcs/0001-m0-schema-event-log.md`
- Existing review artifacts under `docs/plans/`

## Verdict

**Result: Conditional pass for design direction, fail for implementation readiness.**

The average scores are above the hard fail threshold, but the review found multiple Tier 1 blockers that affect first implementation choices. The strongest convergence is that M0 cannot safely start as written: RFC 0001 is still draft-like, migration tooling is open, DDL details are missing, idempotency semantics are internally inconsistent, lifecycle lookup/transition tables are under-specified, and plan artifacts still conflict with current gates.

## Scores

| Lane | Correctness | Completeness | Implementability | Resilience |
|---|---:|---:|---:|---:|
| Attack Surface | 7 | 6 | 6 | 5 |
| Production Stress | 7 | 5 | 6 | 5 |
| Assumption Challenger | 7 | 5 | 6 | 5 |
| Implementation Reality | 5 | 5 | 4 | 6 |
| Coherence Auditor | 6 | 6 | 5 | 6 |
| **Average** | **6.4** | **5.4** | **5.4** | **5.4** |

## Cross-Lane Convergence

The same failure modes appeared across independent lanes:

- **M0 gate ambiguity:** Implementation Reality, Coherence, and Production Stress all found that M0 start conditions conflict across RFC 0001, Decision Backlog, Implementation Readiness, and historical plan text.
- **Traceability weakness:** Assumption Challenger, Coherence, and Implementation Reality all flagged mojibake in `user-said.md` and the temporary authority of English summaries as a product-intent risk.
- **Authorization and publish boundaries:** Attack Surface and Coherence both found that roles, reviewer publish, user approval, service accounts, and worker permissions are not precise enough to implement safely.
- **Privacy leak surfaces:** Attack Surface and Assumption Challenger converged on rare metadata combinations, developer-tooling wedge privacy friction, public search oracle behavior, and revocation semantics.
- **Operational underspecification:** Production Stress and Implementation Reality both found that queues, migrations, index generations, and runbooks are named but not yet executable contracts.

## Tier 1 Findings

### R2-T1-01 M0 implementation gate is contradictory and not DDL-ready

**Converged from:** Implementation Reality, Coherence Auditor, Production Stress.

`focused-rereview-2026-05-09.md` says M0 can start, while RFC 0001 remains draft-like and leaves the migration framework and local Postgres setup open. `DEC-012` is still open before M0 code, and Implementation Readiness requires table columns and nullability that RFC 0001 does not yet define.

**Required fix:** Make one current source of truth for the M0 gate. Before implementation, RFC 0001 should define all M0 table columns, types, nullability, PK/FK constraints, `ON DELETE` / `ON UPDATE`, RLS skeletons, migration tooling, local DB setup, and test command. Historical plans should not read like current permission to start.

### R2-T1-02 Idempotency key uniqueness cannot detect digest conflicts

**Converged from:** Implementation Reality.

The current design includes `request_digest` in the uniqueness key. That prevents the database from naturally detecting reuse of the same idempotency key with a different payload, even though Agent Access requires that case to be a hard error.

**Required fix:** Make the unique constraint digest-independent, for example `(tenant_id, operation, logical_object_id, operation_version, idempotency_key)`. Store `request_digest` as a comparison column with status/result/expiry/lock state.

### R2-T1-03 Lifecycle lookup and transition model is incomplete for M0

**Converged from:** Implementation Reality, Coherence Auditor.

RFC 0001 says lifecycle values use lookup tables plus transition tables, but Required Tables only includes `card_state_transitions`. The design also requires compatible `status`, `outcome_type`, `quality_state`, `evidence_strength`, actor role, and publication preconditions.

**Required fix:** Either add lookup tables such as `card_statuses`, `card_event_types`, `actor_roles`, `outcome_types`, `quality_states`, and `evidence_strengths`, or explicitly use fixed CHECK constraints for M0. If lookup tables are chosen, define FKs, terminal flags, public-searchable flags, actor preconditions, and operation names.

### R2-T1-04 User approval, reviewer publish, and Publish UI are not separated

**Converged from:** Coherence Auditor.

Security docs require user approval and reviewer publish before public indexing, but Agent Access only defines `approve_publication`, and Consent UX labels the user-facing action as `Publish redacted card`. The role matrix says users cannot publish while reviewers can publish after approval.

**Required fix:** Separate `approve_publication` from `reviewer_publish`. User approval should create the consent record; reviewer publish should perform the state transition to `published` under reviewer scope. Rename UI copy to avoid implying user-side publish, and encode the split in `card_state_transitions`.

### R2-T1-05 Worker and service-account authority is too broad

**Converged from:** Attack Surface.

The security model says all operations are object-authorized, but non-human subjects are only specified as generic service accounts / workers. Redaction, indexing, review queue, revocation, and reconciliation workers have very different blast radii.

**Required fix:** Define worker roles such as `redactor`, `indexer`, `revoker`, and `review_queue_worker`; assign each permitted operations, tables, state transitions, job payload signatures, credential lifetime, rotation rules, RLS policies, and audit events.

### R2-T1-06 Public search can become a rare-fingerprint oracle

**Converged from:** Attack Surface, Assumption Challenger.

Public queries allow package/framework/OS/runtime/repo-shape metadata. Rare combination suppression is named, but no k value, minimum cohort size, timing normalization, reason-code rounding, or cross-account privacy budget is defined.

**Required fix:** Define exact public-search privacy rules before public indexing: k-anonymity threshold, minimum cohort size, uniform negative responses, timing buckets, rounded `no_suggestion` reasons, query privacy budgets, and cross-IP/account/device rate limits.

### R2-T1-07 Hostile cards can still reach users through sidecar display

**Converged from:** Attack Surface, Assumption Challenger.

High-risk package, URL, command, and repository advice is blocked from inline hints until verified, but sidecar display remains possible with warning text. Reviewer approval alone is not enough for supply-chain-sensitive cards.

**Required fix:** Treat command/package/repo/credential-bearing cards as hidden from both inline and sidecar surfaces until verified. Verification should require sandbox reproduction, malicious URL / typosquat scanning, and reviewer approval. Links and package names should be structured fields with verification state.

### R2-T1-08 Intent traceability still depends on mojibake and summaries

**Converged from:** Assumption Challenger, Coherence Auditor, Implementation Reality.

`user-said.md` is the stated anchor for drift review, but many Japanese source quotes are mojibake. `DEC-011` temporarily makes English summaries authoritative. That is not enough for external review or high-confidence product intent traceability.

**Required fix:** Either recover source text before treating those claims as normative, or create stable `INTENT-###` records with source location, quote availability, summary, confidence, mapped design anchors, and verification method. Mojibake-only intent should not silently become a normative requirement.

### R2-T1-09 Consent and derived-artifact tables may freeze semantics too early

**Converged from:** Assumption Challenger.

RFC 0001 lists `consent_records` and `derived_artifacts` despite putting consent UI, public corpus, and billing out of scope. Consent surfaces include canonical trails, curated packs, aggregate stats, and model/eval use, but M0 acceptance criteria do not yet define the semantics.

**Required fix:** If M0 creates consent/derived tables, include artifact type, digest binding, policy version, commercial flag, revocation semantics, and inheritance rules. If those cannot be decided yet, keep M0 skeletons out of the normative schema.

### R2-T1-10 Runbooks and operational circuits are not executable

**Converged from:** Production Stress.

Operations docs name runbooks, circuit breakers, queue recovery, and index migrations, but lack concrete first-five-minute actions, diagnostic queries, thresholds, rollback commands, owners, and redrive preconditions.

**Required fix:** Materialize runbooks for emergency revocation, queue backlog, search latency spikes, and index freshness breaches. Define hard caps for spend, queue age, DLQ count, queue depth, review backlog, and degradation actions.

## Tier 2 Findings

### R2-T2-01 Object storage milestone is inconsistent

`DEC-003` makes object storage a M1 blocker, while Implementation Readiness says M1 can keep candidate metadata and redacted drafts in Postgres and keep raw/source artifacts disabled until M2 or a deployment RFC.

**Decision needed:** Move `DEC-003` to M2 / first artifact storage use, or make object storage a real M1 requirement and define the contract.

### R2-T2-02 Agent access timing conflicts with product intent

Product docs say agent-native access should come before human-facing polish, while Implementation Readiness places full external MCP/hooks in M5 and allows only internal CLI/API harness in M3.

**Decision needed:** Decide whether M3 needs a real agent-facing thin client for `search_similar`, sidecar rendering, failure semantics, and `no_suggestion` behavior. Full MCP can remain M5 if the earlier client validates the agent loop.

### R2-T2-03 M1 queue and outbox contract is disconnected from M0

M1 requires `jobs`, `job_attempts`, `idempotency_keys`, and `outbox_events`, but RFC 0001 only includes `idempotency_keys`. The transaction boundary between `card_events` and queue/outbox behavior remains undefined.

**Decision needed:** Either include outbox shape in M0 or create a M1 RFC that defines transaction boundary, payload digest, dedupe key, retry/redrive rules, and stuck-job recovery.

### R2-T2-04 pgvector partitioning and tenant filtering affect earlier schema choices

Retrieval docs name HNSW defaults and tenant/private separation but leave pgvector parameters and physical namespace partitioning open. This affects M0/M3 schema if embeddings need tenant and visibility boundaries.

**Decision needed:** Define `embedding_records` partition keys, public/team/private physical separation, operator class, dimensions, NULL policy, and fallback behavior before M4 implementation.

### R2-T2-05 Developer tooling wedge privacy and value assumptions are untested

The first wedge assumes CI/build/mobile tooling failures are high-repeat and low-friction. Those logs often contain private repo shape, internal package names, customer identifiers, device names, or unreleased dependencies.

**Decision needed:** Measure privacy friction before committing the wedge: publication approval rate, redaction time, rare identifier rate, duplicate error rate, and useful retrieval rate. Promote low-friction wedges; keep high-friction wedges private/team-only.

### R2-T2-06 Seed-card gate is too weak as a validation claim

The product gate of 100 labeled seed cards may be enough to bootstrap, but not enough to validate recall, harmful suggestion rate, or remote shared-corpus value across OS, package manager, framework, agent, exact-error, semantic-only, failed-only, and disputed categories.

**Decision needed:** Treat 100 cards as bootstrap inventory, then define stratified holdout sets and minimum sample bands by retrieval scenario.

### R2-T2-07 Reviewer quality model is under-specified

The docs rely on reviewer publish and operator-assigned quality state, but do not define rubric, double-review triggers, disagreement handling, reviewer fatigue monitoring, audit sampling, or demotion rules.

**Decision needed:** Define reviewer rubric and quality-state transition rules by M1/M2, not only near M6 monetization surfaces.

### R2-T2-08 Delegated read tokens are replayable bearer credentials

Agent Access defines 60-minute read tokens with client instance ID and keychain storage, but not proof-of-possession, request signing, nonce/JTI replay detection, or device-bound keys.

**Decision needed:** For private/team search, use DPoP/mTLS-like proof-of-possession or another request-bound token design with short TTL, nonce/JTI checks, token-family revocation, and anomaly detection.

### R2-T2-09 Raw artifact key management lacks acceptance criteria

Envelope encryption, KMS key ID, rotation, emergency rotation, and crypto-shred are named, but DEK/KEK separation, cryptoperiod, KMS IAM, backup purge, and compromise response are not operationalized.

**Decision needed:** Make key management a M2 blocker with cryptoperiods, rotation triggers, key disable/destroy behavior, backup handling, break-glass decrypt, and audit reconciliation.

## Tier 3 Findings

- Aggregate stats and model/eval revocation need k values, cohort rules, dataset manifests, revocation ledgers, and user-visible exceptions for non-removable historical use.
- Canonical trails risk looking like truth instead of candidate paths unless responses include variant coverage, known contradictions, minority environment warnings, and `not_validated_for` fields.
- `no_suggestion` may be safe but low-value; MVP gates should track first-session useful suggestion rate, disable rate after abstentions, sidecar open/read rate, and no-suggestion rate by wedge.
- Monetization surfaces can distort ranking and review incentives; future decisions should define paid influence, sponsored labeling, reviewer independence, and conflict-of-interest rules.
- Historical review artifacts need explicit status labels and index coverage so old implementation recommendations do not compete with current architecture/RFC/decision files.

## Recommended Fix Order

1. **Freeze current gate authority:** Update `docs/README.md`, plan headers, Decision Backlog, and RFC 0001 so only one place defines whether M0 can start.
2. **Upgrade RFC 0001 to implementation-ready:** Add DDL, migration tool, local DB setup, lifecycle lookup/transition choices, idempotency semantics, RLS skeletons, and test command.
3. **Repair publication and worker authorization:** Split user approval from reviewer publish and define non-human worker roles with least privilege.
4. **Define public search privacy rules:** Add k-anonymity/cohort thresholds, timing/reason normalization, privacy budgets, and metadata suppression behavior.
5. **Decide M1/M2 storage and queue boundaries:** Resolve object storage milestone, outbox/queue schema, runbook thresholds, and key-management acceptance criteria.
6. **Reframe product validation gates:** Treat 100 cards as bootstrap, validate wedge privacy friction, and add public/shared/private/local comparison rules.

## Reviewer Inventory

### Attack Surface

- Tier 1: worker/service-account granularity, public search oracle, hostile sidecar cards.
- Tier 2: bearer token replay, raw artifact key management.
- Tier 3: aggregate stats and model/eval revocation.
- Scores: correctness 7, completeness 6, implementability 6, resilience 5.
- External anchors cited: OWASP API Security Top 10, OWASP LLM Top 10, NIST SP 800-57.

### Production Stress

- Tier 1: non-executable runbooks, undefined backpressure/cost circuits, queue stuck-state/redrive gaps, index generation state machine gaps.
- Tier 2: object storage milestone inconsistency, local metadata cache TTL/invalidation, black-box health checks and alert ownership.
- Scores: correctness 7, completeness 5, implementability 6, resilience 5.
- External anchors cited: Google SRE overload guidance, Azure Circuit Breaker pattern.

### Assumption Challenger

- Tier 1: mojibake traceability, premature consent/derived-artifact semantics.
- Tier 2: dev-tooling wedge privacy assumption, 100-card validation weakness, HITL quality assumption, agent access timing, public corpus vs private/team/local value.
- Tier 3: monetization incentives, canonical trail truthiness, no-suggestion value.
- Scores: correctness 7, completeness 5, implementability 6, resilience 5.
- External anchors cited: HHS traceability guidance, NIST AI RMF/AIRC, IBM data quality dimensions.

### Implementation Reality

- Tier 1: M0 gate contradictions, idempotency digest conflict, missing lifecycle lookup tables.
- Tier 2: pgvector tenant/namespace contract, M1 queue/outbox connection, migration harness contract.
- Tier 3: HNSW operational cost, mojibake traceability.
- Scores: correctness 5, completeness 5, implementability 4, resilience 6.
- External anchors cited: PostgreSQL docs, pgvector docs, Idempotent Consumer pattern.

### Coherence Auditor

- Tier 1: user approval / reviewer publish / Publish UI mismatch.
- Tier 2: M0 gate mismatch, M1 object storage mismatch, agent access MVP/M5 mismatch, historical plan status ambiguity.
- Tier 3: mojibake traceability, consent UX vs human-facing polish wording.
- Scores: correctness 6, completeness 6, implementability 5, resilience 6.
- External anchors cited: Google Cloud ADR guidance, ISO/IEC/IEEE 42010, NASA requirements verification matrix guidance.

## Statistics

| Metric | Count |
|---|---:|
| Reviewer lanes | 5 |
| Tier 1 raw findings | 14 |
| Tier 2 raw findings | 21 |
| Tier 3 raw findings | 13 |
| Consolidated Tier 1 findings | 10 |
| Consolidated Tier 2 findings | 9 |
| Consolidated Tier 3 finding groups | 5 |

## Bottom Line

The architecture intent is still coherent, but the next useful work is not more broad design. The immediate work is to make M0 executable and unambiguous: RFC 0001, Decision Backlog, authorization boundaries, and public-search privacy rules should be tightened before writing the first durable schema or queue worker.
