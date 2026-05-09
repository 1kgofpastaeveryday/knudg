# Product Strategy

Knudg should not begin as a broad public memory network. The first wedge should target one high-repetition, low-privacy-friction domain where reuse can be measured.

The wedge is a measurement strategy, not the global product ontology. Shared schema, consent, retrieval safety, outcome types, and agent access contracts must remain domain-general so Knudg does not collapse into a developer-worklog database.

Candidate wedge:

- developer tooling failures for agentic coding environments
- package manager and framework migration errors
- CI/test/build failures with public dependencies
- iOS/TestFlight and mobile build pipeline issues

MVP success requires evidence that retrieval improves outcomes in that wedge.

## MVP Gates

- at least 100 labeled seed cards in one wedge as bootstrap inventory, followed by stratified holdout evaluation before public expansion
- exact-error recall@3 above the baseline search approach
- separate evaluation bands for exact-error, semantic-only, failed-only, unknown-clarified, deprecated, and disputed cards
- useful retrieval for failed-only and unknown-clarified cards
- measurable time-to-fix improvement in replayed tasks
- measurable improvement from remote shared corpus excluding same-session local cache
- harmful suggestion rate below a defined threshold
- no-suggestion rate, first-session useful suggestion rate, sidecar open/read rate, and disable-after-no-suggestion rate measured by wedge
- public-card approval and revocation flow tested end to end
- wedge privacy friction measured: public approval rate, redaction minutes per card, rare identifier rate, duplicate error rate, and useful retrieval rate
- tenant isolation tests passing for private/team namespace paths
- gross-margin guardrail for free and paid query paths
- review capacity and stale-card removal gates passing for the wedge
- public corpus, private/team corpus, and same-session local cache evaluated separately

MVP also needs stop conditions:

- pause public corpus expansion if public-only retrieval does not beat baseline on replayed tasks
- pause public corpus expansion if privacy friction exceeds the wedge threshold or public-only retrieval underperforms private/team/local baselines
- pause public candidate admission if review backlog exceeds the configured capacity
- keep billing disabled if query gross margin and approved-card cost are not measured
- keep inline hints disabled if harmful suggestion or dismissal rate exceeds the wedge threshold

Deferred until after these gates:

- broad public contributor incentives
- paid reranking tiers
- enterprise SSO/RBAC beyond the minimal tenant model
- large-scale data lake compaction
- curated packs
- multi-backend search abstraction

## Monetization

The product should not charge primarily for local memory.

Likely monetization paths:

### Public Retrieval API

Free low-rate public search, paid high-rate API/MCP usage.

Charge for:

- higher query limits
- lower latency
- better reranking
- more context-aware results
- usage-based retrieval volume

### Team Private Namespace

Teams pay for private experience indexes:

- internal repo work history
- CI failure resolution
- PR/review patterns
- migration notes
- incident workarounds
- private agent experience

### Enterprise Governance

Enterprise features:

- SSO
- RBAC
- audit logs
- policy-based redaction
- private deployment/VPC/on-prem
- retention controls
- compliance controls

### Verified Knowledge Layer

Public DB can be free, while quality layers are paid:

- verified cards
- solved_many ranking
- deprecated detection
- disputed answer warnings
- high-confidence-only mode
- curated packs

For MVP, `quality_state` values are operator-assigned only:

- `unreviewed`: generated but not reviewed
- `solved_once`: one approved source session
- `solved_many`: multiple independent approved source sessions
- `verified`: reviewer-approved with reproduced or externally validated evidence
- `disputed`: credible conflicting evidence exists

Deprecation is represented by lifecycle `status = deprecated`, not by `quality_state`.

Automated promotion based on contributor reputation, ranking outcomes, or monetized quality tiers is deferred to a separate ranking and governance spec.

Derived artifacts such as canonical trails and curated packs are product surfaces, not just storage optimizations. They need their own provenance, version, consent inheritance policy, and revocation behavior before launch.

### Curated Packs

Sell or sponsor packs:

- Next.js migration trails
- Python packaging trails
- iOS/TestFlight failure trails
- Kubernetes incident trails
- CUDA/PyTorch setup trails
- Codex/Claude Code/Cursor workflow trails

### Contributor Incentives

DB growth should not rely only on company-funded ingestion.

Possible incentives:

- credits for useful public cards
- bounty requests for missing trails
- verified contributor program
- revenue share for curated packs
- reputation/attribution for maintainers

## Unit Economics

The business should not assume that a shared corpus becomes cheaper just because the corpus is reusable. The first wedge implementation RFC must estimate and then measure:

- cost per submitted candidate
- cost per approved public card
- cost per rejected candidate
- review minutes per public card
- embedding and re-embedding cost per card version
- hot-index and main-index storage cost
- cost per query with and without reranking
- cost per revocation propagation
- cost of free-tier abuse and rate-limit enforcement

Billing should not launch until these costs are measured against retrieval value. The core monetization thesis is shared retrieval infrastructure, not paid local memory.

## Key Risks

- privacy leaks
- noisy or low-quality cards
- prompt injection through public cards
- stale/deprecated solutions
- duplicated cards
- over-trusting a single solved example
- high retrieval cost from free users
- poor ranking causing distraction instead of acceleration

Mitigations:

- explicit user consent before publish
- redact before approval
- approval bound to exact redacted artifact digest
- raw logs not published
- card-level provenance
- quality states: unreviewed, solved_once, solved_many, verified, disputed
- lifecycle states for superseded, deprecated, and revoked cards
- domain/environment filters
- public/private split
- object-level authorization before retrieval and ranking
- tenant keys in database, cache, object, and index layers
- rate limits, spend caps, and abuse throttles
- hostile-card and prompt-injection tests
- non-executable card rendering
- no-result abstention when confidence is low
- revocation/tombstone propagation across indexes and caches
