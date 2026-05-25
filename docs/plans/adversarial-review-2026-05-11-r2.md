# Adversarial Design Review - 2026-05-11 R2

## Review Configuration

- Project: Knudg repository root
- Focus: static information-only landing page implementation readiness
- Tier: mid-style review loop with broad fix pass and scoped final confirmation
- Reviewers: Codex subagent lanes
- Live QA: not requested; no implementation exists yet
- Review targets:
  - `README.md`
  - `docs/README.md`
  - `docs/product/landing-page-design.md`
  - `docs/product/strategy.md`
  - `docs/product/pre-m1-validation-protocol.md`
  - `docs/rfcs/0003-wedge-001-agentic-coding-tooling.md`
  - `docs/architecture/operations.md`
  - `docs/architecture/implementation-readiness.md`
  - `docs/architecture/agent-access.md`
  - `docs/architecture/retrieval.md`
  - `docs/architecture/consent-revocation-ux.md`
  - `docs/architecture/data-model.md`

## Scoring Summary

Final scoped review judged only the first static LP contract:
`site/index.html` plus `site/styles.css`, information-only, no JavaScript, no
analytics, no forms, no active product routes, no active `/architecture` route,
and no public search/intake/install claims.

| Reviewer | Correctness | Completeness | Implementability | Resilience | Weighted Avg |
|---|---:|---:|---:|---:|---:|
| Implementation feasibility | 8 | 8 | 8 | 9 | 8.13 |
| Security/public exposure | 9 | 8 | 8 | 7 | 8.25 |
| UX/product honesty | 8 | 8 | 7 | 8 | 7.75 |
| Cross-document coherence | 8 | 8 | 8 | 9 | 8.13 |
| **Average** | **8.25** | **8.00** | **7.75** | **8.25** | **8.06** |

PASS: no final scoped review axis is `<= 3`.

## Cross-Lane Convergence

Issues identified by 3+ reviewers:

| Issue | Reviewers | Resolution |
|---|---|---|
| Static LP is implementable only if product actions, public architecture, forms, analytics, install/API/MCP/CLI routes, and public search remain inert/absent | 4 | Preserved in `landing-page-design.md` static prototype contract |
| Public URL launch requires host-level routing/header/runbook controls beyond `index.html` and `styles.css` | 3 | Preserved as separate public deployment gate through `RB-LP-001` |

Issues identified by 2 reviewers:

| Issue | Reviewers | Resolution |
|---|---|---|
| Fixture provenance implied live private dogfood | 2 | Changed to `source class: illustrative static fixture` |
| Fixture detail state was not in allowed values | 1 direct, 1 adjacent fixture concern | Changed to `detail_state=summary_only` |
| `Inconclusive` card type needed LP mapping | 1 direct, 1 coherence-adjacent | Added `outcome_type=inconclusive` mapping |
| `Read Public Architecture` could be misread as an active CTA | 1 direct, 3 route-boundary confirmations | Renamed hero section label to secondary status text and kept route inactive |

## Fix Summary

Accepted and fixed before the final scoped confirmation:

- Information-only LP state: request/register/install/download/API/MCP/CLI
  controls remain disabled, gray, non-navigating, and non-instrumented.
- Public architecture route: `/architecture` remains pending text until a
  signed public-doc manifest exists; public URL launch requires host config and
  `RB-LP-001`.
- Public docs boundary: public-doc manifest, public-doc state machine, CI
  exclusions, and no direct `docs/plans/` or internal docs navigation.
- Static prototype contract: no JavaScript, no analytics, no remote fonts/icons,
  no forms, no generated product routes, no active `/architecture`.
- Fixture consistency: no `candidate_preview`, no `summary_only_non_executable`,
  no `approved private dogfood fixture`.
- Product honesty: WEDGE-001 remains a hypothesis/draft gate; M1 and public URL
  launch are blocked separately from local static LP implementation.
- Supporting architecture consistency: single-workspace private dogfood before
  team namespace alpha, public search response equivalence, observability
  privacy model, M1 protected-data durability, route-class readiness, circuit
  control-plane matrix, and pre-M1 validation protocol.

## Remaining Blockers

Static LP implementation blockers: none.

Out of scope for the two-file static prototype and still intentionally blocked:

- public URL launch until host routing/header artifacts and `RB-LP-001` exist
- active `/architecture` until a signed public-doc manifest exists
- M1 private writer queue until WEDGE-001 acceptance and protected-data gates pass
- team namespace sharing until M2 consent/grant gates pass

## Raw Reviewer Outputs

### Implementation Feasibility

Tier 1: none.

Tier 2: the hero `Read Public Architecture` wording could be misread as an
active link if the implementer skims only hero copy. Later rules correctly
require pending status text while `/architecture` is `draft_internal`.

Tier 3: the LP spec is large, but enough constraints and fixtures exist to
implement safely. Public URL readiness is separate from local static work.

Scores: Correctness 8, Completeness 8, Implementability 8, Resilience 9.

### Security/Public Exposure

Tier 1: none.

Tier 2: public deployment is out of scope for `site/index.html` and
`site/styles.css`; public URL readiness needs static-host config, route denylist
probes, 404/410 behavior, sitemap/noindex behavior, cache purge path, and
analytics/form absence checks.

Tier 3: avoid anchors for disabled CTAs, JavaScript click tracking, remote
fonts/icons, forms, analytics, architecture links, and placeholder product
routes.

Scores: Correctness 9, Completeness 8, Implementability 8, Resilience 7.

### UX/Product Honesty

Tier 1: none.

Tier 2: fixture provenance implied an existing approved private dogfood corpus;
the first prototype should use an illustrative/static fixture. Public URL
runbook/contact requirements are public-launch blockers, not local-static
implementation requirements.

Tier 3: proof copy must remain hypothesis/evaluation language; `/architecture`
must not be linked; disabled request access remains a native disabled button
with adjacent status text.

Scores: Correctness 8, Completeness 8, Implementability 7, Resilience 8.

### Cross-Document Coherence

Tier 1: none.

Tier 2: `detail_state=summary_only_non_executable` was not an allowed value;
fixture provenance over-implied live dogfood.

Tier 3: `Inconclusive` card type needed a mapping; architecture/status links
must render inert.

Scores: Correctness 8, Completeness 8, Implementability 8, Resilience 9.

## Sources Referenced By Reviewer Lanes

- [MDN: disabled attribute](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Attributes/disabled)
- [W3C WCAG 2.2 Understanding](https://www.w3.org/WAI/WCAG22/Understanding/)
- [Netlify routing overview](https://docs.netlify.com/manage/routing/overview/)
- [OWASP API Security Top 10](https://owasp.org/API-Security/)
- [OWASP RAG Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/RAG_Security_Cheat_Sheet.html)
- [Google SRE Monitoring Distributed Systems](https://sre.google/resources/book-update/monitoring-distributed-systems/)
- [Microsoft Azure Circuit Breaker pattern](https://learn.microsoft.com/azure/architecture/patterns/circuit-breaker)

## Statistics

- Final scoped findings: 0 Tier 1, 5 Tier 2, 6 Tier 3
- Blocking static-LP findings after fixes: 0
- Average weighted score: 8.06/10
