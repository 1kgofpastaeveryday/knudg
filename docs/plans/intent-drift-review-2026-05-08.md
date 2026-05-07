# Intent Drift Review - 2026-05-08

## Review Configuration

- Project: `D:\working\knudg`
- Focus: `user-said.md` と現行設計 docs の意図差分
- Tier: mid, adapted for intent drift review
- Reviewers: 4 total
  - Trust Boundary / Attack Surface: gpt-5.4 subagent
  - Implementation Reality: gpt-5.3-codex subagent
  - Production Stress: gpt-5.4 subagent
  - Assumption Challenger: gpt-5.4 subagent
- Claude-only lanes: skipped by design
- Review targets:
  - `user-said.md`
  - `README.md`
  - `docs/README.md`
  - `docs/architecture/overview.md`
  - `docs/architecture/security-privacy.md`
  - `docs/architecture/data-model.md`
  - `docs/architecture/retrieval.md`
  - `docs/architecture/operations.md`
  - `docs/product/strategy.md`

## Executive Summary

現行設計は、ユーザー意図の大枠にはかなり沿っている。特に「personal memory ではない」「local-only ではない」「central search infrastructure」「MCP/CLI」「redaction and consent」「candidate paths, not truth」は、README と architecture docs に反映されている。

ただし、実装に入ると意図からズレる可能性が高い未固定点が残っている。大きいものは以下。

1. `retrieval.md` の query flow が認可を candidate generation 後に置いており、README/security の「ranking/reranking 前に認可」と矛盾する。
2. 同意が exact redacted card digest に束縛されている一方、canonical trail / curated pack / compaction artifact への派生同意が未定義。
3. 「無知の知」「未解決だが有用な制約」「clarified unknowns」が schema/ranking 上の first-class object になっていない。
4. 巨大共有DBの intake 制御、重複抑制、新規性判定、人手 review 原価、再index 原価が薄い。
5. local cache と thin injection の境界が緩く、将来 local memory / prompt pollution 方向へ戻る余地がある。

結論: **方向性は PASS、実装前仕様としては FAIL 寄りの CONDITIONAL PASS**。現時点で「設計がユーザー意図と別物になっている」とは言えないが、上記の未固定点は後から直すと schema、consent、retrieval topology に波及する。

## Scoring Summary

| Reviewer | Correctness | Completeness | Implementability | Resilience | Weighted Avg |
|---|---:|---:|---:|---:|---:|
| Trust Boundary | 5 | 5 | 6 | 6 | 5.38 |
| Implementation Reality | 7 | 6 | 6 | 7 | 6.50 |
| Production Stress | 6 | 4 | 5 | 4 | 5.00 |
| Assumption Challenger | 7 | 5 | 7 | 6 | 6.25 |
| **Average** | **6.25** | **5.00** | **6.00** | **5.75** | **5.78** |

PASS/FAIL: **CONDITIONAL PASS**. No average axis is <= 3, but completeness and resilience are weak for an implementation-ready design.

## Cross-Model Convergence

### Issues identified by 3+ reviewers

| Issue | Reviewers | Tier | Confidence |
|---|---|---|---|
| Unknowns / failed-only / clarified uncertainty are not first-class enough | Implementation Reality, Production Stress, Assumption Challenger | Tier 1-2 | HIGH/MEDIUM |
| Local cache / thin injection boundary can drift toward local memory or prompt pollution | Trust Boundary, Implementation Reality, Production Stress, Assumption Challenger | Tier 1-2 | HIGH/MEDIUM |
| Consent does not cover derived artifacts such as canonical trails or curated packs | Trust Boundary, Assumption Challenger | Tier 1 | HIGH |
| Retrieval authorization order conflicts with security invariant | Trust Boundary, Production Stress | Tier 1 | HIGH |

### Issues identified by 2 reviewers

| Issue | Reviewers | Tier | Confidence |
|---|---|---|---|
| Massive shared DB needs intake, dedupe, novelty, and backlog admission controls | Production Stress, Implementation Reality | Tier 1-3 | HIGH/MEDIUM |
| Product can visually narrow into dev tooling worklogs unless global ontology boundaries are explicit | Assumption Challenger, Production Stress | Tier 2 | MEDIUM |
| Requirements traceability from `user-said.md` to design docs is missing | Assumption Challenger, Implementation Reality | Tier 3 | MEDIUM |

## Tier 1 - Immediate Fix Required

### T1-01: Retrieval authorization order contradicts the trust boundary

- Confidence: HIGH
- Docs: `README.md`, `docs/architecture/security-privacy.md`, `docs/architecture/retrieval.md`
- Issue: README/security say search authorization happens before ranking/reranking. `retrieval.md` says `BM25 + exact + vector candidates -> authorization filter -> score fusion`. That allows unauthorized corpus rows into candidate generation.
- Why this is intent drift: the user wanted a public/private/shared experience infrastructure with privacy as a core control. Candidate-generation-after-global-scan weakens the public/private boundary.
- Recommendation: change query flow to authorize shard/filter scope before candidate generation. Define public corpus, private/team corpus, and wedge shard selection before BM25/vector lookup. Explicitly document pre-filter behavior and fallback when vector filtering is selective.
- Sources: [NIST Privacy Framework](https://www.nist.gov/privacy-framework), [pgvector docs](https://github.com/pgvector/pgvector)

### T1-02: Derived artifact consent is undefined

- Confidence: HIGH
- Docs: `docs/architecture/security-privacy.md`, `docs/architecture/overview.md`, `docs/product/strategy.md`, `docs/architecture/data-model.md`
- Issue: Consent binds to exact redacted card digest, but the design also compresses cards into canonical trails and may sell curated packs. It is unclear whether a user-approved card can be aggregated, rewritten, sold, or included in derived artifacts without renewed consent or explicit inheritance rules.
- Why this is intent drift: the user explicitly required transparency about what is and is not published. A derived canonical trail is a new publication surface unless bounded.
- Recommendation: define `public_card`, `canonical_trail`, `curated_pack`, and `aggregate_metadata` as separate versioned artifacts. Specify consent inheritance, opt-out, and re-consent rules for each. At minimum, deterministic transformation of already-public redacted card versions can be allowed, but editorial rewriting or monetized packaging should need explicit policy.
- Sources: [W3C PROV Overview](https://www.w3.org/TR/prov-overview/), [NIST AI RMF Core](https://airc.nist.gov/airmf-resources/airmf/5-sec-core/)

### T1-03: Unknowns are not first-class design objects

- Confidence: HIGH
- Docs: `README.md`, `docs/architecture/data-model.md`, `docs/architecture/retrieval.md`, `docs/product/strategy.md`
- Issue: The schema is still centered on solved incident cards: `successful_path`, `solved_once`, `solved_many`, `verified`. `failed_paths` exists, but unresolved knowledge, clarified constraints, and known unknowns do not have their own type, lifecycle, retrieval policy, or display semantics.
- Why this is intent drift: the user explicitly said to store "無知の知" as well as success/failure paths. Without a first-class representation, the product will become solved-dev-incident search.
- Recommendation: add `outcome_type` such as `solved`, `failed_only`, `inconclusive`, `unknown_clarified`, and fields such as `known_unknowns`, `scope_limits`, `blocked_by`, `evidence_strength`, `next_check`. Define separate ranking/injection policies for unknown cards.
- Sources: [NIST AI RMF Core](https://airc.nist.gov/airmf-resources/airmf/5-sec-core/), [W3C PROV Overview](https://www.w3.org/TR/prov-overview/)

### T1-04: Massive shared DB intake is underspecified

- Confidence: HIGH
- Docs: `README.md`, `docs/architecture/overview.md`, `docs/architecture/operations.md`, `docs/product/strategy.md`
- Issue: The public write pipeline is `candidate_created -> redaction -> review -> user approval -> index`, but there is no intake admission stage for duplicate detection, novelty scoring, review capacity, quota, or backlog shedding.
- Why this is intent drift: the user was explicitly worried about 1M-scale adoption, huge DB growth, indexing, writing, and operating cost. A human-review-dependent pipeline without intake controls becomes a card factory that cannot stay fresh.
- Recommendation: add `dedupe/novelty/admission` before redaction/review. Define cluster matching, novelty threshold, public-corpus quota, sideline/drop states, backlog max age, and operator review capacity limits.
- Sources: [AWS Well-Architected - fail fast and limit queues](https://docs.aws.amazon.com/wellarchitected/2023-04-10/framework/rel_mitigate_interaction_failure_fail_fast.html), [Pinecone bulk import docs](https://docs.pinecone.io/guides/index-data/import-data)

## Tier 2 - Decide Before Implementation

### T2-01: MCP/CLI/hooks contract is too thin

- Confidence: HIGH
- Docs: `README.md`, `docs/architecture/overview.md`, `docs/architecture/retrieval.md`
- Issue: MCP/CLI is mentioned, but hooks such as `before_prompt` and `after_solve` have no event schema, I/O contract, failure semantics, or transport priority.
- Recommendation: add a minimal agent access spec with `search_similar`, `writer.ask_approval`, `before_work`, `during_work`, and `after_solve` contracts. Keep it schema-first and transport-neutral.

### T2-02: Local state policy is looser than the user intent

- Confidence: HIGH
- Docs: `docs/architecture/overview.md`, `docs/architecture/operations.md`
- Issue: The docs allow `recent retrieval caches`. The user only allowed local current-work query material and pending writer approval queues.
- Recommendation: for MVP, make local cache session-scoped, encrypted, short TTL, and bodyless by default. If card bodies are cached, require explicit opt-in and strict purge behavior.

### T2-03: Thin injection lacks an enforceable injection contract

- Confidence: HIGH
- Docs: `README.md`, `docs/architecture/retrieval.md`, `docs/architecture/security-privacy.md`
- Issue: "fenced" and "up to 3 concise cards" are not enough to prevent prompt pollution. There is no token budget, mode distinction, or mandatory no-suggestion behavior.
- Recommendation: define injection modes: `bootstrap`, `sidecar`, `inline_hint`, `no_suggestion`. Add max cards, max tokens, non-instruction format, precedence warning, abstention threshold, and per-tool kill switch.
- Sources: [OWASP Top 10 for LLM Applications](https://owasp.org/www-project-top-10-for-large-language-model-applications/)

### T2-04: Unit economics are missing

- Confidence: HIGH
- Docs: `docs/product/strategy.md`, `docs/architecture/operations.md`
- Issue: Monetization paths are listed, but there is no cost model for embedding, review, reindex, revocation propagation, free-tier abuse, or hot/main double indexing.
- Recommendation: add COGS metrics and MVP gates: `cost_per_approved_card`, `cost_per_rejected_candidate`, `cost_per_query`, `cost_per_reindex`, `cost_per_revocation`, `review_minutes_per_public_card`, and free-tier abuse budget.

### T2-05: Dev-tooling wedge can harden into the whole product

- Confidence: MEDIUM
- Docs: `README.md`, `docs/product/strategy.md`, `docs/architecture/data-model.md`
- Issue: The first wedge is correctly narrow, but all examples are developer tooling / CI / migration. There is no explicit rule that global schema and ontology must remain domain-general.
- Recommendation: keep the wedge, but add a boundary: wedge-specific examples must not hard-code the global ontology. Split common schema from wedge extensions.

### T2-06: Rollout assumes injection too early

- Confidence: MEDIUM
- Docs: `README.md`, `docs/architecture/retrieval.md`, `docs/architecture/operations.md`
- Issue: The retrieval flow ends in agent injection, but rollout stages like shadow mode, observe-only, sidecar suggestion, and kill switches are not specified.
- Recommendation: define rollout order: `offline replay -> shadow retrieval -> explicit sidecar suggestion -> thin auto-injection for one wedge -> broader shared corpus`.

## Tier 3 - Future Risk

### T3-01: Requirements traceability is missing

- Confidence: MEDIUM
- Docs: all design docs
- Issue: `user-said.md` contains strong negative requirements, but docs do not have an intent-to-design crosswalk.
- Recommendation: add `docs/product/intent-crosswalk.md` mapping each non-goal and invariant to the design sections that enforce it.

### T3-02: Re-embedding and reindex migration are thin

- Confidence: MEDIUM
- Docs: `docs/architecture/data-model.md`, `docs/architecture/retrieval.md`, `docs/architecture/overview.md`
- Issue: Version fields exist, but dual-read, dual-write, canary namespace, cold-card defer, cutover, and rollback behavior are not specified.
- Recommendation: add an index migration section with `index_generation` rollout, rollback, revocation replay SLA, and cold-card re-embedding policy.

### T3-03: Canonical trail compaction could turn candidate paths into "truth"

- Confidence: MEDIUM
- Docs: `docs/architecture/overview.md`, `docs/product/strategy.md`
- Issue: The design says cards are candidate paths, but compaction into canonical trails could become a representative answer unless governance is explicit.
- Recommendation: make canonicalization reversible, keep cluster manifests with original cards, preserve minority variants, and require review thresholds for merging.

## Suggested Fix Order

1. Fix `retrieval.md` authorization ordering and exact-match privacy language.
2. Add consent rules for derived artifacts and canonical trails.
3. Extend card schema with `outcome_type` and unknown/constraint fields.
4. Add local state and injection contracts.
5. Add intake admission, dedupe, novelty, backlog, and review-capacity rules.
6. Add COGS and shared-corpus MVP gates.
7. Add intent crosswalk to prevent future drift.

## Raw Reviewer Output Summary

Raw outputs converged strongly on the same issues:

- Trust Boundary found authorization ordering and derived consent as Tier 1.
- Implementation Reality found thin injection, local cache, hooks, quality transitions, and unknowns.
- Production Stress found intake saturation, authorization topology, unknown semantics, unit economics, rollout control, reindexing, and canonicalization risk.
- Assumption Challenger found derived consent, unknowns, top-3 search narrowing, dev-worklog framing, local-only proof gaps, and missing traceability.

