# Adversarial Design Review - 2026-05-07

## Review Configuration

- Date: 2026-05-07
- Project: `D:\working\knudg`
- Focus: General
- Tier: full
- Reviewers: 5 total - 3x gpt-5.4, 2x gpt-5.3-codex
  - gpt-5.4: Attack Surface, Production Stress, Assumption Challenger
  - gpt-5.3-codex: Implementation Reality, Schema & Data Integrity
  - Execution mode: Codex-native subagents for all lanes
  - Note: Claude-only Coherence Auditor / UX / Live QA lanes were skipped per GPT-only request.
- Rounds: 1/1
- Review targets:
  - `D:\working\knudg\README.md`

## Scoring Summary

| Reviewer | Correctness | Completeness | Implementability | Resilience | Weighted Avg |
|---|---:|---:|---:|---:|---:|
| Attack Surface | 4 | 2 | 3 | 2 | 3.00 |
| Production Stress | 4 | 2 | 3 | 1 | 2.88 |
| Assumption Challenger | 5 | 4 | 6 | 3 | 4.75 |
| Implementation Reality | 4 | 3 | 3 | 3 | 3.38 |
| Schema & Data Integrity | 4 | 3 | 5 | 3 | 3.88 |
| **Average** | **4.2** | **2.8** | **4.0** | **2.4** | **3.58** |

PASS/FAIL: **FAIL**. Completeness and Resilience averages are <= 3.

## Cross-Model Convergence

Issues identified by 3+ reviewers:

| Issue | Reviewers | Tier | Confidence |
|---|---|---|---|
| Missing tenant/object authorization and namespace isolation | Attack Surface, Schema & Data Integrity, Assumption Challenger | Tier 1 | HIGH |
| Public-card prompt injection / hostile retrieved content trust boundary is not specified | Attack Surface, Assumption Challenger | Tier 1 | HIGH |
| Consent, redaction, revocation, and privacy are not defined as enforceable workflows | Attack Surface, Assumption Challenger, Schema & Data Integrity | Tier 1/Tier 3 | HIGH/MEDIUM |
| Canonical schema, constraints, state machine, and event model are missing | Implementation Reality, Production Stress, Schema & Data Integrity, Assumption Challenger | Tier 1/Tier 2/Tier 3 | HIGH |
| Queue/index/write pipeline lacks idempotency, retry, ordering, visibility, and recovery semantics | Implementation Reality, Production Stress, Schema & Data Integrity, Assumption Challenger | Tier 1/Tier 3 | HIGH |
| Search/retrieval quality and index/query contracts are underspecified | Implementation Reality, Assumption Challenger, Production Stress | Tier 1/Tier 3 | HIGH |
| Migration/versioning/rollback strategy is missing | Production Stress, Schema & Data Integrity, Assumption Challenger | Tier 1/Tier 2 | HIGH |

Issues identified by 2 reviewers:

| Issue | Reviewers | Tier | Confidence |
|---|---|---|---|
| Monitoring, SLOs, runbooks, and overload controls are absent | Production Stress, Assumption Challenger | Tier 2/Tier 3 | HIGH/MEDIUM |
| MCP/API credential and protocol contract is not implementable yet | Attack Surface, Implementation Reality | Tier 2/Tier 1 | HIGH |
| Hot/main index freshness, cache invalidation, and stale/deprecated serving rules are missing | Production Stress, Implementation Reality | Tier 3 | HIGH/MEDIUM |
| Object storage provenance, keying, retention, and integrity linkage are not specified | Implementation Reality, Schema & Data Integrity | Tier 1/Tier 2 | HIGH/MEDIUM |
| MVP scope is too broad before retrieval/schema correctness is proven | Implementation Reality, Assumption Challenger | Tier 2/Tier 3 | HIGH |

## Tier 1 - Immediate Fix Required

- Define object-level authorization and tenant isolation before any public/private namespace implementation.
- Treat every retrieved card as untrusted input. Add a non-executable rendering format, provenance, action gating, and hostile-card tests.
- Redact before approval, bind approval to an immutable redacted digest, and define revocation/deletion propagation across storage, indexes, caches, and archives.
- Add a canonical data model: card IDs, versions, immutable events, consent records, edges, tenant keys, constraints, and legal state transitions.
- Choose queue semantics for MVP and document idempotency keys, retries, DLQ/redrive, ordering assumptions, and reconciliation.
- Define retrieval quality gates: benchmark corpus, recall/usefulness metrics, abstention policy, stale-card harm metric, and baseline comparison against no Knudg.
- Specify the consistency model across append-only truth, metadata DB, object storage, hot index, main index, and compaction.
- Add migration/versioning policy for schema, protocol, vectors, indexes, and card format evolution.

## Tier 2 - Decide Before Implementation

- Freeze one keyword backend and one vector/index strategy for MVP; the listed search engines are not interchangeable at the ranking-contract level.
- Write the MCP/CLI/API contract: transport, auth, versioning, methods, payloads, errors, and session behavior.
- Specify credentials: scoped tokens, rotation, revocation, read/write separation, service-to-service auth, and local agent token storage.
- Add observability and SLOs: query latency, error rate, saturation, index lag, approval backlog age, compaction lag, stale-card rate, and alert actions.
- Define soft-delete, retention, purge, tombstone, and legal erasure semantics.
- Decide the product wedge and corpus density target before relying on a public network effect.

## Tier 3 - Future Risk

- Canonical compression can remove the exact environment details that make a fix valid; keep variant graphs and contradiction links.
- Platform/model/toolchain drift will rot embeddings and card usefulness unless cards, embeddings, and evals are versioned.
- Unit economics and latency are currently unbounded; active-session retrieval needs p50/p95 budgets and per-query cost gates.
- Contributor incentives and verified layers need abuse controls, reputation thresholds, and quarantine paths.

## Raw Reviewer Outputs

### Attack Surface - gpt-5.4

## Tier 1 - Immediate Fix Required

- **[AS-01]** Multi-tenant authorization model is missing - **Confidence: HIGH**  
  **Docs:** `README.md` - `Infrastructure Direction`, `Database Architecture`, `Team Private Namespace`, `Enterprise Governance`  
  **Issue:** The design introduces `public experience database`, `private/team namespaces`, and future `RBAC`, but never defines how reads, writes, search, ranking, card-state changes, or namespace transitions are authorized at object level.  
  **Evidence:** `README.md` says the central service manages `private/team namespaces` and later lists `RBAC` as an enterprise feature, but the API/search architecture never states how a caller is proved to own a namespace or a card, or whether authorization is enforced before retrieval/reranking. Absence of that decision is the problem.  
  **Recommendation:** Define the authz model now: subject types, namespace ownership, card ownership, per-operation policy, pre-filter vs post-filter authorization, admin boundaries, and tests for object-level and function-level authorization. Treat search as a protected read path, not a special case.  
  **Sources:** [OWASP API Security Top 10 2023](https://owasp.org/API-Security/editions/2023/en/0x11-t10/), [OWASP API1:2023 Broken Object Level Authorization](https://owasp.org/API-Security/editions/2023/en/0xa1-broken-object-level-authorization/)

- **[AS-02]** Public-card prompt injection can steer downstream agents - **Confidence: HIGH**  
  **Docs:** `README.md` - `Knowledge Crawler`, `Search Model`, `Key Risks`  
  **Issue:** The core retrieval path explicitly injects retrieved cards into an active agent, but there is no documented trust boundary, rendering strategy, or tool-execution restriction for untrusted card content.  
  **Evidence:** The crawler “injects only small, relevant suggestions into the main agent” and query flow ends with `top 3 concise cards -> agent injection`. The only mitigation documented is “small injected suggestions, not authoritative answers,” which does not stop indirect prompt injection.  
  **Recommendation:** Treat every retrieved card as hostile input. Specify a non-executable rendering format, strict field quoting, provenance labels, allowlisted fields, output scanning, tool-call isolation, and a policy that retrieved text can never directly become instructions for privileged actions.  
  **Sources:** [OWASP LLM Prompt Injection Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html), [OWASP API Security Top 10 2023](https://owasp.org/API-Security/editions/2023/en/0x11-t10/)

- **[AS-03]** Consent/redaction order can publish secrets and PII - **Confidence: HIGH**  
  **Docs:** `README.md` - `Knowledge Writer`, `Data Unit: Experience Card`, `Write Pipeline`, `Database Architecture`  
  **Issue:** The approval flow is ordered incorrectly for a system handling stack traces, error signatures, repo shape, usernames, and tokens. The user is asked to approve a “sanitized” card before the documented pipeline reaches `pending_redaction`.  
  **Evidence:** The writer prompt says sensitive details “will be removed” before publish, but the state machine is `awaiting_user_approval -> approved -> pending_redaction -> pending_review`. The architecture also keeps an append-only source of truth and raw/card object storage, with no documented rules for pre-redaction storage, retention, or access.  
  **Recommendation:** Redact first, then present the exact post-redaction artifact for approval, then bind approval to that immutable digest. Document secret-detection classes, reviewer gates, raw-candidate storage policy, encryption, retention, and emergency takedown.  
  **Sources:** [NIST Privacy Framework 1.0](https://csrc.nist.gov/pubs/cswp/10/nist-privacy-framework-version-10/final), [OWASP LLM Prompt Injection Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html)

- **[AS-04]** Malicious knowledge-card poisoning is an unmitigated supply-chain channel - **Confidence: HIGH**  
  **Docs:** `README.md` - `Knowledge Writer`, `Data Unit: Experience Card`, `Verified Knowledge Layer`, `Contributor Incentives`, `Key Risks`  
  **Issue:** The system is designed to distribute “successful paths” and package/repository advice, but the doc does not define provenance enforcement, malware/link scanning, reviewer trust thresholds, or quarantine for suspicious public cards.  
  **Evidence:** Example cards recommend replacing dependencies and using repositories; the public DB is central to the product; `verified` is framed as a quality tier, not a mandatory control. There is no documented safeguard against an attacker publishing a plausible fix that points agents to a typosquatted package, malicious repo, or dangerous command.  
  **Recommendation:** Require provenance metadata, reputation thresholds, automated scanning, suspicious-link blocking, manual review for executable advice, and a hard distinction between untrusted community cards and trusted recommendations.  
  **Sources:** [OWASP API Security Top 10 2023](https://owasp.org/API-Security/editions/2023/en/0x11-t10/), [OWASP LLM Prompt Injection Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html)

## Tier 2 - Decide Before Implementation

- **[AS-05]** Agent/MCP credential model is undocumented - **Confidence: HIGH**  
  **Docs:** `README.md` - `Database Architecture`, `MVP Shape`, `Public Retrieval API`, `Team Private Namespace`  
  **Issue:** The design says `API/Auth/Billing` but never specifies token type, scope, expiry, rotation, revocation, device binding, or how agent-side credentials are protected.  
  **Evidence:** The MVP includes a hosted submission/search API and MCP/CLI access, but there is no section defining session lifetime, API key scope, refresh behavior, service-to-service auth, or how compromised workstation tokens are contained. Absence of that design is a security gap.  
  **Recommendation:** Decide the credential model before implementation: short-lived scoped tokens, rotation, revocation, least-privilege scopes, separate read/write credentials, and explicit handling for headless agents and local caches.  
  **Sources:** [OWASP API Security Top 10 2023](https://owasp.org/API-Security/editions/2023/en/0x11-t10/)

- **[AS-06]** Abuse prevention for search and submission flows is underspecified - **Confidence: HIGH**  
  **Docs:** `README.md` - `Search Model`, `Infrastructure Direction`, `Public Retrieval API`, `Contributor Incentives`, `Key Risks`  
  **Issue:** “Rate limits and caching” is too vague for a product whose business model depends on public search, expensive reranking, and community submissions.  
  **Evidence:** The doc promises free public search, paid higher-rate access, and optional reranking, but does not define anonymous vs authenticated quotas, submission throttles, bot mitigation, cost caps, duplicate suppression, or protections for expensive query shapes.  
  **Recommendation:** Specify per-endpoint quotas, authenticated tiers, spend caps, anti-automation controls, duplicate/poison submission throttles, and hard ceilings on candidate set size, batch size, and rerank cost.  
  **Sources:** [OWASP API Security Top 10 2023](https://owasp.org/API-Security/editions/2023/en/0x11-t10/)

- **[AS-07]** Approval flow has no documented CSRF/replay/content-binding protection - **Confidence: MEDIUM**  
  **Docs:** `README.md` - `Knowledge Writer`, `Infrastructure Direction`, `Write Pipeline`  
  **Issue:** The publish/approve action is security-sensitive, but the doc never says how approval is authenticated, bound to a specific redacted payload, or protected against replay.  
  **Evidence:** The design requires explicit user approval and central consent records, yet there is no mention of nonces, one-time approval tokens, same-site protections, re-auth for publish, or binding approval to a stable artifact hash.  
  **Recommendation:** Define approval as a signed, one-time, payload-bound action with expiration, anti-CSRF protections, and audit logging. Approval must fail if the card changes after user review.  
  **Sources:** [OWASP API Security Top 10 2023](https://owasp.org/API-Security/editions/2023/en/0x11-t10/), [NIST Privacy Framework 1.0](https://csrc.nist.gov/pubs/cswp/10/nist-privacy-framework-version-10/final)

## Tier 3 - Future Risk

- **[AS-08]** Consent revocation and purge semantics are absent across caches and indexes - **Confidence: MEDIUM**  
  **Docs:** `README.md` - `Infrastructure Direction`, `Database Architecture`, `Write Pipeline`, `Scaling Principle`, `Enterprise Governance`  
  **Issue:** The architecture is append-only, multi-index, cached, and compacted, but there is no documented mechanism to retract a card everywhere after consent withdrawal, secret exposure, or legal deletion demand.  
  **Evidence:** The doc describes append-only storage, hot/main indexes, local caches, archives, and compaction, but only mentions `retention controls` as a future enterprise feature. No deletion propagation, tombstoning, cache purge, or re-index SLA is described.  
  **Recommendation:** Define revocation semantics now: canonical delete/tombstone records, purge propagation to every index/cache/archive, retrieval blocking during reindex, and operator runbooks for emergency removal.  
  **Sources:** [NIST Privacy Framework 1.0](https://csrc.nist.gov/pubs/cswp/10/nist-privacy-framework-version-10/final), [OWASP API Security Top 10 2023](https://owasp.org/API-Security/editions/2023/en/0x11-t10/)

| Score | 1-10 |
|---|---:|
| Correctness | 4 |
| Completeness | 2 |
| Implementability | 3 |
| Resilience | 2 |

### Production Stress - gpt-5.4

## Tier 1 - Immediate Fix Required

**[PS-01] No dependency-outage or graceful-degradation contract on the read path - Confidence: HIGH**  
**Docs:** `README.md` - `Knowledge Crawler`, `Search Model`, `Infrastructure Direction`, `Database Architecture`  
**Issue:** The design makes the live agent path depend on multiple remote systems, but it never defines what happens when any of them is slow, partitioned, rate-limited, or partially unavailable. That is a production outage path, not an implementation detail.  
**Evidence:** `Knowledge Crawler` says the crawler queries Knudg during an active session and injects suggestions (lines 38-56). `Search Model` adds shard selection, BM25, exact match, vector search, fusion, and optional rerank (lines 141-169). `Database Architecture` adds API, Postgres, object storage, keyword search, vector search, and a queue (lines 199-228). There is no timeout budget, circuit-breaker behavior, fallback order, or “return no suggestion and continue” mode documented anywhere.  
**Recommendation:** Define per-dependency deadlines, circuit-break/open behavior, and explicit degraded modes: exact/BM25-only, cached/stale response, or no-response pass-through. Also document which failures are silent to the user versus surfaced to operators.  
**Sources:** [Azure Circuit Breaker pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/circuit-breaker), [Google SRE: Monitoring Distributed Systems](https://sre.google/sre-book/monitoring-distributed-systems/)

**[PS-02] Async write pipeline has no retry, dedupe, or failed-job recovery semantics - Confidence: HIGH**  
**Docs:** `README.md` - `Database Architecture`, `Write Pipeline`  
**Issue:** The system is explicitly asynchronous and queue-backed, but there is no documented delivery model for worker failure, duplicate delivery, poison jobs, or stuck work. That leaves approval, redaction, indexing, and compaction vulnerable to silent loss or duplication.  
**Evidence:** The architecture names a queue but leaves it as “Postgres-backed queue, Redis, Cloudflare Queues, or similar” (lines 226-227). The write pipeline lists states from `candidate_created` through `indexed_main`, `rejected`, `superseded`, and `deprecated` (lines 244-257), but documents no retry policy, no idempotency key, no lease/visibility timeout, no dead-letter handling, and no re-drive path.  
**Recommendation:** Specify at-least-once vs exactly-once assumptions, idempotency keys per card/version, retry caps, poison-message handling, DLQ/redrive semantics, and a reconciler for stranded work.  
**Sources:** [Azure Circuit Breaker pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/circuit-breaker), [Google SRE: Monitoring Distributed Systems](https://sre.google/sre-book/monitoring-distributed-systems/)

**[PS-03] No authoritative consistency model across source of truth, object storage, and indexes - Confidence: HIGH**  
**Docs:** `README.md` - `Database Architecture`, `Write Pipeline`, `Scaling Principle`, `Key Risks`  
**Issue:** The design splits state across append-only storage, metadata DB, object storage, hot index, main index, and later compaction, but never states which layer is authoritative under partial failure or when a card becomes visible. That is a direct path to stale, duplicate, or contradictory search results.  
**Evidence:** The doc explicitly separates append-only source of truth, metadata DB, processing pipeline, and rebuildable indexes (lines 199-205), then adds hot/main indexing and canonical compaction (lines 259-275). It also names `deprecated`, `superseded`, and quality states (lines 256-257, 388), but never defines visibility rules, replay rules, or repair rules when one projection updates and another does not.  
**Recommendation:** Make one state store authoritative, publish versioned events/outbox records from it, define read visibility rules per state, and add reconciliation/rebuild procedures for projection drift.  
**Sources:** [AWS Builders Library: Ensuring rollback safety during deployments](https://aws.amazon.com/builders-library/ensuring-rollback-safety-during-deployments/), [Azure Circuit Breaker pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/circuit-breaker)

## Tier 2 - Decide Before Implementation

**[PS-04] No monitoring, alerting, or SLO model for the core service paths - Confidence: HIGH**  
**Docs:** `README.md` - whole document; especially `Search Model`, `Database Architecture`, `Write Pipeline`  
**Issue:** There is no observability design for retrieval latency, error rate, saturation, indexing lag, approval backlog age, compaction lag, or stale-card rate. A production system like this cannot be operated safely without defining what to measure and when to page.  
**Evidence:** The README has no monitoring or health section at all. It mentions “quality signals” and “rate limits and caching” (lines 188, 391) but no SLIs/SLOs, no dashboards, no pager conditions, no black-box checks, and no component health endpoints.  
**Recommendation:** Define service-level indicators for query success, p95/p99 latency, index freshness lag, approval backlog age, compaction lag, and saturation. Separate paging alerts from diagnostic telemetry, and attach an action to every page.  
**Sources:** [Google SRE: Monitoring Distributed Systems](https://sre.google/sre-book/monitoring-distributed-systems/), [Azure Circuit Breaker pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/circuit-breaker)

**[PS-05] No rollback-safe migration plan for schema, index, or protocol changes - Confidence: HIGH**  
**Docs:** `README.md` - `Database Architecture`, `Scaling Principle`, `MVP Shape`  
**Issue:** The design assumes mutable Postgres schema, evolving card formats, multiple search indexes, and canonical compaction, but it never defines how to deploy or roll back changes safely while mixed versions are live. In a distributed system with shared persistent state, that omission is dangerous.  
**Evidence:** The doc says indexes are rebuildable (line 204), names multiple persistent layers (lines 214-227), and plans future quality/deprecation/billing changes (lines 394-404). There is no expand/contract plan, no versioned card schema, no dual-read/dual-write strategy, no alias cutover for indexes, and no rollback procedure.  
**Recommendation:** Require backwards-compatible changes by default, two-phase deployment rules for storage/protocol changes, versioned documents/indexes, and explicit rollback verification before any deployment that changes data shape or visibility.  
**Sources:** [AWS Builders Library: Ensuring rollback safety during deployments](https://aws.amazon.com/builders-library/ensuring-rollback-safety-during-deployments/)

**[PS-06] The write-state machine is listed, but not specified - Confidence: HIGH**  
**Docs:** `README.md` - `Write Pipeline`  
**Issue:** Enumerating states without transition rules is not enough for a distributed workflow. The doc does not say who owns each transition, which transitions are legal, what timeouts apply, or how to recover from abandoned intermediate states.  
**Evidence:** The states list (lines 248-257) is the entire state-machine definition. There is no transition table, no preconditions/postconditions, no timeout policy for `awaiting_user_approval` or `pending_review`, and no semantics for when `superseded` or `deprecated` should remove cards from hot/main indexes.  
**Recommendation:** Add a formal state machine: allowed transitions, responsible actor, retry/timeout behavior, terminal states, compensating transitions, and a sweeper for stuck records.  
**Sources:** [Azure Circuit Breaker pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/circuit-breaker), [AWS Builders Library: Ensuring rollback safety during deployments](https://aws.amazon.com/builders-library/ensuring-rollback-safety-during-deployments/)

## Tier 3 - Future Risk

**[PS-07] Freshness and invalidation strategy for cached and deprecated knowledge is missing - Confidence: HIGH**  
**Docs:** `README.md` - `Infrastructure Direction`, `Search Model`, `Scaling Principle`, `Key Risks`, `Verified Knowledge Layer`  
**Issue:** The product explicitly worries about stale/deprecated solutions, but the design never states how cached retrievals, hot-index results, and main-index results are invalidated when a card becomes deprecated, disputed, or superseded. That will eventually serve known-bad guidance as if it were current.  
**Evidence:** The design includes a local cache (lines 176-180), hot/main indexes (lines 259-261), deprecated/superseded links (line 274), and stale/deprecated solutions as a named risk (line 376), but no TTL, version token, invalidation event, or freshness SLA.  
**Recommendation:** Define freshness guarantees per serving tier, propagate invalidation events on status changes, version cache keys by card/status/index generation, and refuse to serve stale data beyond a documented threshold.  
**Sources:** [AWS Builders Library: Ensuring rollback safety during deployments](https://aws.amazon.com/builders-library/ensuring-rollback-safety-during-deployments/), [Google SRE: Monitoring Distributed Systems](https://sre.google/sre-book/monitoring-distributed-systems/)

**[PS-08] No overload-control or runbook story for incidents and backlog growth - Confidence: MEDIUM**  
**Docs:** `README.md` - `Knowledge Crawler`, `Database Architecture`, `Write Pipeline`, `Public Retrieval API`  
**Issue:** The system is meant to run alongside active agent sessions and also handle asynchronous ingestion, but there is no documented admission control, backlog thresholding, or operator playbook for “search latency spike,” “compaction behind,” “queue backlog exploding,” or “partial rebuild aborted.”  
**Evidence:** The crawler operates in-band with active work (lines 38-56), paid plans sell lower latency (lines 288-296), and queue-backed async work is central (lines 226-227, 244-261), yet there is no load-shedding order, no backlog age thresholds, and no runbook section anywhere in the README. Absence of documentation is the issue.  
**Recommendation:** Define overload behavior by tier and component: what gets dropped first, what can serve stale, what blocks publish, and what pages humans. Add short runbooks for the first five incident classes before implementation starts.  
**Sources:** [Azure Circuit Breaker pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/circuit-breaker), [Google SRE: Monitoring Distributed Systems](https://sre.google/sre-book/monitoring-distributed-systems/)

| Score | 1-10 |
|---|---:|
| Correctness | 4 |
| Completeness | 2 |
| Implementability | 3 |
| Resilience | 1 |

### Assumption Challenger - gpt-5.4

## Tier 1 - Immediate Fix Required

**[AC-01] No retrieval quality contract** - **Confidence: HIGH**  
**Docs:** Missing retrieval benchmark, success criteria, abstention policy, stale-card harm metric, and baseline comparison against “no Knudg.”  
**Issue:** The document assumes that hybrid retrieval plus “top 3 concise cards” will improve agent outcomes by default. That may be wrong because retrieval quality is not one-dimensional, and models do not reliably use retrieved context just because it was found. If this assumption is wrong, the product becomes a distraction layer that adds latency, token cost, and false confidence.  
**Evidence:** `README.md` specifies the retrieval pipeline around line 137 and hard-codes top-3 injection around line 402, but there is no eval loop or abstain behavior anywhere in the risks or MVP sections.  
**Recommendation:** Define an eval contract before implementation: recall@k for exact error signatures, usefulness win-rate vs baseline, abstention rate, stale-solution harm rate, and freshness decay tests per domain.  
**Sources:** [Lost in the Middle](https://arxiv.org/abs/2307.03172), `README.md`

**[AC-02] Privacy is treated as a sanitization problem, not a threat-model problem** - **Confidence: HIGH**  
**Docs:** Missing privacy threat model, re-identification analysis, rollback/deletion workflow for public cards, and default visibility rules.  
**Issue:** The design assumes stack traces, dependency versions, repo shape, package names, and failure descriptions can be safely summarized and published with user approval. That may be wrong because combinations of “non-secret” fields can still identify a company, codebase, incident, or customer. If this assumption is wrong, one leak can collapse trust and force the product into private-only mode.  
**Evidence:** The crawler observes detailed environment and failure metadata around line 40; the writer flow around line 62 only promises removal of obvious secrets; public storage is core around line 182.  
**Recommendation:** Make ingestion private by default, require policy-based structured redaction before any public publish path, and document rollback, deletion, and audit procedures before building a shared corpus.  
**Sources:** Internal doc evidence.

**[AC-03] “Small injected suggestions” is not a real trust boundary** - **Confidence: HIGH**  
**Docs:** Missing content trust model, provenance enforcement rules, hostile-card test plan, and action gating policy.  
**Issue:** The design assumes prompt injection risk is adequately reduced by making retrieved content short and non-authoritative. That may be wrong because short suggestions can still alter tool choice, version pins, install commands, or escalation paths. If this assumption is wrong, the public corpus becomes an attack surface against the agents consuming it.  
**Evidence:** Prompt injection is listed as a risk around line 375, but the only concrete mitigation is “small injected suggestions” around line 392. No claim-level trust model is documented.  
**Recommendation:** Treat retrieved cards as untrusted evidence, not instructions; require claim provenance, block imperative action text by default, and add adversarial replay tests with malicious cards.  
**Sources:** Internal doc evidence.

## Tier 2 - Decide Before Implementation

**[AC-04] The network-effect thesis is undocumented product-market risk** - **Confidence: HIGH**  
**Docs:** Missing ICP, initial wedge, cold-start plan, corpus density target, and proof that public cross-user reuse is common enough to matter.  
**Issue:** The document assumes a shared public experience network will become useful before private/team data dominates. That may be wrong because the highest-value failures are often sensitive, local, or low-frequency. If this assumption is wrong, the public corpus never gets dense enough to help, contributor incentives fail, and the real product is private team memory.  
**Evidence:** Strong public-network positioning appears around lines 15, 174, and 406, but there is no quantified reuse-rate or buyer validation anywhere in the file.  
**Recommendation:** Pick one buyer and one narrow domain with high repetition and low privacy friction, then document minimum corpus density and the acquisition path to reach it.  
**Sources:** Internal doc evidence.

**[AC-05] Canonical compression may destroy the only details that make a fix valid** - **Confidence: MEDIUM**  
**Docs:** Missing canonicalization policy, contradiction handling, variant-retention rules, and merge criteria.  
**Issue:** The design assumes many similar cards can be compacted into canonical trails without losing the environment-specific differences that determine whether a fix works. That may be wrong because OS, package manager, framework version, and agent tool are often the actual cause. If this assumption is wrong, ranking will prefer neat generalized cards over ugly correct ones.  
**Evidence:** Compression is described as the moat around lines 265 and 278, while the card schema records highly specific environment fields around line 94. No rule explains what survives compaction.  
**Recommendation:** Keep variant graphs with explicit contradiction links; never collapse away environment-specific branches without measured equivalence.  
**Sources:** [Lost in the Middle](https://arxiv.org/abs/2307.03172), `README.md`

**[AC-06] Platform and toolchain drift is assumed away** - **Confidence: HIGH**  
**Docs:** Missing provider/version compatibility policy, embedding migration plan, re-index triggers, and cross-model quality revalidation.  
**Issue:** The design assumes cards and rankings will stay useful across model, API, and agent-tool changes. That may be wrong because providers deprecate models and move platforms, and behavior shifts even when interfaces survive. If this assumption is wrong, embeddings drift, cards rot faster than deprecation flags can catch them, and retrieval quality decays invisibly.  
**Evidence:** The schema stores `agent_tool` around line 98 and spans multiple tools/ecosystems around lines 19 and 341, but there is no lifecycle policy.  
**Recommendation:** Version cards by provider/model/toolchain, define mandatory re-embedding and re-eval triggers, and maintain retrieval baselines per major platform generation.  
**Sources:** [OpenAI Deprecations](https://developers.openai.com/api/docs/deprecations), `README.md`

## Tier 3 - Future Risk

**[AC-07] Multi-stage indexing assumes eventual consistency will be acceptable without explicit semantics** - **Confidence: HIGH**  
**Docs:** Missing idempotency rules, retry budgets, ordering guarantees, freshness SLOs, and duplicate suppression strategy.  
**Issue:** The architecture assumes append-only truth, async processing, hot index, main index, and approval states can be combined without user-visible inconsistency. That may be wrong because retries duplicate writes, timeouts mask completed side effects, and async stages reorder events. If this assumption is wrong, users will see superseded or unapproved cards, duplicate records, and inconsistent search results across indexes.  
**Evidence:** The staged architecture is around line 199 and the writer state machine around line 246; there is no documented idempotency or retry model.  
**Recommendation:** Define idempotent write keys, monotonic state transitions, replay rules, and index freshness guarantees before building multi-index flows.  
**Sources:** [AWS Builders' Library: Timeouts, retries and backoff with jitter](https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/), `README.md`

**[AC-08] Latency and unit economics are hand-waved** - **Confidence: MEDIUM**  
**Docs:** Missing end-to-end latency SLO, per-query cost budget, reranker gating policy, cache-hit assumptions, and fallback behavior when the service is slow or unavailable.  
**Issue:** The design assumes active-session retrieval is cheap enough to run inline and valuable enough to justify the extra hop. That may be wrong because latency compounds inside agent loops, and retries or reranking can make an overloaded system worse. If this assumption is wrong, free traffic becomes expensive, paid users bypass the product in real workflows, and the value proposition collapses under its own response time.  
**Evidence:** Inline active-session use is core around line 38; reranking is added around line 148; free public search appears around line 288; no latency/cost envelope is documented.  
**Recommendation:** Set p50/p95 budgets from the agent loop backwards, gate expensive ranking on confidence, and prove per-query ROI before offering a free public API.  
**Sources:** [AWS Builders' Library: Timeouts, retries and backoff with jitter](https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/), `README.md`

| Dimension | Score (1-10) |
|---|---:|
| Correctness | 5 |
| Completeness | 4 |
| Implementability | 6 |
| Resilience | 3 |

### Implementation Reality - gpt-5.3-codex

## Tier 1 - Immediate Fix Required

**[IR-01] No implementable canonical schema/constraints for cards and states** - **Confidence: HIGH**  
Docs: Missing DDL spec (PK/FK/unique/check), tenancy model, and state-transition rules.  
Issue: The design names rich fields/states but gives no enforceable relational contract, so dedupe, supersede/deprecate links, and privacy approvals cannot be made reliable.  
Evidence: `README.md` defines card fields and states (`L90-L120`, `L246-L257`) but no IDs, versioning keys, namespace keys, uniqueness, or transition constraints; yet claims append-only SoT (`L199-L205`).  
Recommendation: Add a schema doc now: `experience_cards`, `card_versions`, `card_events`, `consent_records`, `card_edges`; define immutable event log + materialized current state; add transition table and DB constraints.  
Sources: [pgvector README](https://github.com/pgvector/pgvector/blob/master/README.md), [Cloudflare Queues delivery guarantees](https://developers.cloudflare.com/queues/reference/delivery-guarantees/), [MCP transports spec](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports)

**[IR-02] Query pipeline is underspecified for pgvector execution constraints** - **Confidence: HIGH**  
Docs: Missing query templates/index strategy doc for hybrid retrieval.  
Issue: “BM25 + exact + vector + filters” is stated, but pgvector index use is sensitive to `ORDER BY`/`LIMIT` shape and filter behavior under ANN; current design can silently degrade recall/latency.  
Evidence: README claims multi-signal fusion (`L141-L169`) and pgvector-first (`L223-L224`) without query forms; pgvector docs require distance-operator `ORDER BY` + `LIMIT` for index use, and filtering after ANN scan can reduce returned rows unless tuned/iterative scans are enabled.  
Recommendation: Define canonical SQL patterns (pre-filter vs post-filter), distance ops per field, HNSW/IVFFlat defaults (`ef_search`, probes), iterative-scan policy, and fallback exact-search thresholds.  
Sources: [pgvector README](https://github.com/pgvector/pgvector/blob/master/README.md)

**[IR-03] Queue semantics are not fixed, but pipeline correctness depends on them** - **Confidence: HIGH**  
Docs: Missing delivery/idempotency/retry-order contract.  
Issue: Async stateful writer/index flow is impossible to make correct without explicit duplicate-handling and ordering rules.  
Evidence: README defines asynchronous state machine and hot/main indexing (`L244-L261`) and allows multiple queue backends (`L226-L227`) but no dedupe keys or replay policy; Cloudflare Queues is at-least-once, may duplicate, does not guarantee publish order, and has one active consumer per queue.  
Recommendation: Choose one queue for MVP and publish invariants: idempotency key format, exactly-once effect at DB layer, retry/DLQ rules, ordering expectations, and outbox/inbox tables.  
Sources: [Cloudflare Queues delivery guarantees](https://developers.cloudflare.com/queues/reference/delivery-guarantees/), [Cloudflare Queues how it works](https://developers.cloudflare.com/queues/reference/how-queues-works/)

**[IR-04] MCP/CLI API is not a spec, just a bullet** - **Confidence: HIGH**  
Docs: Missing protocol/API contract document.  
Issue: “Build MCP/CLI search interface” is not implementable without transport/version/auth/session/error semantics.  
Evidence: README MVP step 3 is only a label (`L398`); MCP transport spec has strict requirements (JSON-RPC framing, POST/GET behavior, protocol version header, session handling, origin validation/security).  
Recommendation: Freeze MVP on one transport first (`stdio` for local CLI or Streamable HTTP for hosted), then write a minimal compliance contract: methods, payload schemas, error codes, auth, protocol-version policy.  
Sources: [MCP transports spec](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports)

## Tier 2 - Decide Before Implementation

**[IR-05] BM25/search engine choice is deferred too long and blocks relevance behavior** - **Confidence: HIGH**  
Docs: Missing search backend decision record + analyzer/similarity config.  
Issue: Meilisearch/Typesense/OpenSearch/Postgres FTS are not drop-in equivalents; ranking/tokenization/config APIs differ, so fusion/rerank results will drift by backend.  
Evidence: README lists four interchangeable keyword engines (`L220-L221`) while depending on stable hybrid retrieval (`L141-L169`).  
Recommendation: Pick one backend for MVP and lock tokenizer, stemming, stopwords, synonym policy, and score normalization contract before writing fusion logic.  
Sources: [OpenSearch keyword search (BM25)](https://docs.opensearch.org/latest/search-plugins/keyword-search/)

**[IR-06] “Append-only source of truth” conflicts with mutable workflow without event model** - **Confidence: MEDIUM**  
Docs: Missing event-sourcing vs mutable-row decision.  
Issue: States like `superseded/deprecated/rejected` imply mutation, but append-only claim implies immutable events + projections; both are currently mixed.  
Evidence: Append-only SoT (`L201`) + mutable lifecycle (`L248-L257`) + compaction flow (`L261`, `L269-L276`) with no event identity/order model.  
Recommendation: Explicitly model immutable events and derived current-state tables; include causality (`supersedes_card_id`, `deprecated_by_event_id`).  
Sources: [Cloudflare Queues how it works](https://developers.cloudflare.com/queues/reference/how-queues-works/)

**[IR-07] Object storage layer lacks key/version/integrity contract** - **Confidence: MEDIUM**  
Docs: Missing object layout spec and read-after-write/cache behavior notes.  
Issue: “Postgres + R2/S3” is declared, but no object key scheme, content-addressing/versioning, checksum policy, or cache invalidation rules are defined.  
Evidence: Object storage is named (`L217-L218`, `L233-L235`) but there is no storage contract section.  
Recommendation: Define object namespace format, immutable blob IDs, checksum enforcement, manifest linkage to DB rows, and deletion/retention semantics before ingestion code.  
Sources: [Cloudflare R2 consistency model](https://developers.cloudflare.com/r2/reference/consistency/)

## Tier 3 - Future Risk

**[IR-08] Hot-index to main-index compaction has no freshness/rebuild SLOs** - **Confidence: MEDIUM**  
Docs: Missing indexing SLO/runbook.  
Issue: Without freshness targets and replay semantics, users can see non-deterministic ranking between hot/main tiers and stale deprecation status.  
Evidence: Two-tier indexing is required (`L259-L261`) but no lag target, cutover rule, or backfill/replay policy is defined.  
Recommendation: Define freshness SLOs, compaction cadence, replay windows, and consistency checks between canonical DB and search indexes.

**[IR-09] MVP sequencing includes major platform scope before retrieval is hardened** - **Confidence: HIGH**  
Docs: Missing dependency-ordered delivery plan.  
Issue: Team namespaces + billing in MVP adds auth/entitlement complexity before proving retrieval quality and ingestion correctness.  
Evidence: MVP includes MCP/CLI, approval flow, hybrid search, quality flags, namespaces, billing (`L396-L404`) in one tranche.  
Recommendation: Reorder: schema+ingestion correctness -> retrieval quality/evals -> API stability -> namespaces -> billing.

**[IR-10] No explicit eval/benchmark plan for retrieval quality and safety gates** - **Confidence: HIGH**  
Docs: Missing eval dataset + acceptance criteria.  
Issue: Claims about reducing repeated failures cannot be validated without offline/online metrics and safety checks for injected suggestions.  
Evidence: Quality notions exist (`L147`, `L388`) but no measurable targets, eval sets, or fail-safe thresholds are documented.  
Recommendation: Add MVP gates: recall@k / MRR on labeled incidents, hallucination/injection safety checks, and regression benchmarks per release.

| Metric | Score (1-10) |
|---|---:|
| Correctness | 4 |
| Completeness | 3 |
| Implementability | 3 |
| Resilience | 3 |

### Schema & Data Integrity - gpt-5.3-codex

## Tier 1 - Immediate Fix Required

**[T1-01] Tenant isolation is not enforceable at schema level - Confidence: HIGH**  
**Docs:** `README.md` L184-186, L298-319  
**Issue:** “private/team namespaces” are product concepts, but no DB-level tenant key strategy is defined (`tenant_id` in PK/FK, RLS policies, bypass-role rules).  
**Evidence:** The doc names namespaces and enterprise controls but never defines table-level tenant constraints or access predicates.  
**Recommendation:** Require `tenant_id` on all tenant-scoped tables, include it in composite PK/FK paths, and define RLS policy templates + `BYPASSRLS` governance before implementation.  
**Sources:** [PostgreSQL Row Security Policies](https://www.postgresql.org/docs/current/ddl-rowsecurity.html), [PostgreSQL Constraints](https://www.postgresql.org/docs/current/ddl-constraints.html)

**[T1-02] Referential integrity model is unspecified (FK + ON DELETE/ON UPDATE semantics) - Confidence: HIGH**  
**Docs:** `README.md` L199-205, L246-257, L267-275  
**Issue:** Pipeline/state objects are described, but there is no FK graph or cascade/restrict matrix.  
**Evidence:** States and compaction links are listed, but no ownership edges or delete behavior are documented.  
**Recommendation:** Publish a table-by-table FK contract with explicit `ON DELETE`/`ON UPDATE` actions and required indexes on referencing columns.  
**Sources:** [PostgreSQL Constraints](https://www.postgresql.org/docs/current/ddl-constraints.html)

**[T1-03] No safe-migration standard for production schema evolution - Confidence: HIGH**  
**Docs:** Entire README (no migration section)  
**Issue:** No policy for lock-aware changes, backfills, phased constraints, or concurrent index creation.  
**Evidence:** Architecture is defined; migration safety is absent.  
**Recommendation:** Mandate expand/contract operations using `NOT VALID` + `VALIDATE CONSTRAINT`, and concurrent index/constraint adoption patterns for large tables.  
**Sources:** [PostgreSQL ALTER TABLE](https://www.postgresql.org/docs/current/sql-altertable.html)

**[T1-04] Search index lineage/provenance contract is missing - Confidence: HIGH**  
**Docs:** `README.md` L195-205, L259-261  
**Issue:** You state “append-only source of truth” and “rebuildable search indexes,” but there is no documented immutable linkage from index rows to canonical record version/hash.  
**Evidence:** No schema fields or constraints for source-event ID, canonical version ID, or replay determinism.  
**Recommendation:** Add immutable provenance keys (`event_id`, `card_version_id`, content hash, processor version) and uniqueness constraints so every index hit can be traced and rebuilt deterministically.  
**Sources:** [pgvector README](https://github.com/pgvector/pgvector/blob/master/README.md), [PostgreSQL Constraints](https://www.postgresql.org/docs/current/ddl-constraints.html)

**[T1-05] Audit logging requirement is declared but not modeled - Confidence: HIGH**  
**Docs:** `README.md` L311-319  
**Issue:** “audit logs” are listed for enterprise, but no audit schema/append-only log design is defined for approvals, redactions, publishes, or deprecations.  
**Evidence:** No documented actor/action/object/timestamp/change-diff model; no tamper-resistance/retention notes.  
**Recommendation:** Define an append-only audit event schema (or pgaudit + app-level event table) with retention, immutability controls, and query path for investigations.  
**Sources:** [pgAudit](https://www.pgaudit.org/)

## Tier 2 - Decide Before Implementation

**[T2-01] Workflow states are not constrained as enums/transitions - Confidence: HIGH**  
**Docs:** `README.md` L246-257  
**Issue:** State names exist, but legal transitions and terminal states are undefined.  
**Evidence:** No transition matrix, no invalid-transition handling.  
**Recommendation:** Add state enum/check constraints plus a transition policy (DB trigger or app invariant with versioned state machine).  
**Sources:** [PostgreSQL Constraints](https://www.postgresql.org/docs/current/ddl-constraints.html)

**[T2-02] Uniqueness/nullability rules for dedup and approval semantics are missing - Confidence: HIGH**  
**Docs:** `README.md` L122-135, L267-275, L384-389  
**Issue:** Dedup/canonicalization is central, but no composite uniqueness contract is defined; nullable behavior is unspecified.  
**Evidence:** No key definitions for “same card/path/trail” or approval uniqueness per subject/version.  
**Recommendation:** Define composite unique keys and explicit `NOT NULL`/`NULLS NOT DISTINCT` choices for all identity and dedup columns.  
**Sources:** [PostgreSQL Constraints](https://www.postgresql.org/docs/current/ddl-constraints.html)

**[T2-03] pgvector model/dimension/index strategy is under-specified - Confidence: MEDIUM**  
**Docs:** `README.md` L223-224, L150-157  
**Issue:** Multiple embeddings are planned, but no schema decision for model versioning, vector dimensions, or per-model index strategy.  
**Evidence:** “pgvector first” and embedding types are named; no compatibility/index contract.  
**Recommendation:** Decide whether vectors are fixed-dimension per table or multi-model with partition/partial-index strategy; encode model ID + dimension constraints up front.  
**Sources:** [pgvector README](https://github.com/pgvector/pgvector/blob/master/README.md)

**[T2-04] Soft-delete, retention, and revocation semantics are not defined - Confidence: HIGH**  
**Docs:** `README.md` L248-257, L318-319  
**Issue:** “deprecated/superseded/rejected” are states, but hard delete vs tombstone and retention/erasure behavior are unspecified.  
**Evidence:** No lifecycle constraints for records referenced by indexes, audit, and provenance.  
**Recommendation:** Define deletion classes (logical vs physical), retention windows, and FK behavior for revoked/erased content.  
**Sources:** [PostgreSQL Constraints](https://www.postgresql.org/docs/current/ddl-constraints.html)

## Tier 3 - Future Risk

**[T3-01] Write ownership/concurrency control for quality signals is missing - Confidence: MEDIUM**  
**Docs:** `README.md` L147-148, L188-190, L323-330  
**Issue:** Multiple actors/processes can mutate quality/deprecation/reputation, but no conflict-resolution or optimistic-locking design is documented.  
**Evidence:** No version column, no “last writer wins” policy, no reviewer authority model.  
**Recommendation:** Add row versioning (`lock_version`/`updated_at` monotonic checks) and ownership rules by signal type.  
**Sources:** [PostgreSQL Constraints](https://www.postgresql.org/docs/current/ddl-constraints.html)

**[T3-02] Schema versioning/deprecation compatibility is not documented - Confidence: MEDIUM**  
**Docs:** `README.md` L396-404  
**Issue:** MVP says “define schema” once, but no forward/backward compatibility path is defined for card schema evolution.  
**Evidence:** No `schema_version`, no reader compatibility guarantees, no migration policy per API version.  
**Recommendation:** Add explicit schema version fields and compatibility contract for readers, writers, and reindex jobs.  
**Sources:** [PostgreSQL ALTER TABLE](https://www.postgresql.org/docs/current/sql-altertable.html)

**[T3-03] RLS covert-channel risk not addressed for multi-tenant constraints - Confidence: MEDIUM**  
**Docs:** `README.md` L184-186, L315-319  
**Issue:** Even with RLS, constraint checks can leak information if schema/policies are not carefully designed.  
**Evidence:** No mention of this risk in namespace isolation design.  
**Recommendation:** Add a threat model section for cross-tenant inference via unique/FK errors and define mitigation patterns.  
**Sources:** [PostgreSQL Row Security Policies](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)

| Metric | Score (1-10) |
|---|---:|
| Correctness | 4 |
| Completeness | 3 |
| Implementability | 5 |
| Resilience | 3 |

## Statistics

- Total findings: 46
- Tier 1: 19 (HIGH: 19, MEDIUM: 0, LOW: 0)
- Tier 2: 16 (HIGH: 11, MEDIUM: 5, LOW: 0)
- Tier 3: 11 (HIGH: 4, MEDIUM: 7, LOW: 0)
- Cross-model convergence (3+): 7
- Cross-model convergence (2): 5
- Average weighted score: 3.58/10
