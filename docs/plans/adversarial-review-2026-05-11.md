# Adversarial Design Review - 2026-05-11

## Review Configuration

- Project: Knudg repository root
- Focus: landing page design, product positioning, implementation readiness
- Tier: mid
- Reviewers: 5 total, all `gpt-5.5` subagent lanes
- Execution mode: Codex subagents
- Live QA: not requested
- Rounds: 2 review rounds plus final hardening pass
- Review targets:
  - `README.md`
  - `docs/product/strategy.md`
  - `docs/product/landing-page-design.md`
  - `docs/architecture/consent-revocation-ux.md`

## Scoring Summary

| Reviewer | Correctness | Completeness | Implementability | Resilience | Weighted Avg |
| --- | ---: | ---: | ---: | ---: | ---: |
| Attack Surface | 5 | 4 | 5 | 4 | 4.75 |
| Production Stress | 5 | 3 | 5 | 3 | 4.25 |
| Assumption Challenger | 6 | 4 | 5 | 5 | 5.13 |
| Implementation Reality | 6 | 4 | 4 | 5 | 4.88 |
| Coherence Auditor | 5 | 4 | 5 | 4 | 4.63 |
| **Average** | **5.4** | **3.8** | **4.8** | **4.2** | **4.73** |

PASS/FAIL: **FAIL**. Production Stress scored Completeness and Resilience at
`3`, which triggers the review threshold. Multiple lanes also reported Tier 1
findings.

## Cross-Lane Convergence

Issues identified by 3+ reviewers:

| Issue | Reviewers | Tier | Confidence |
| --- | --- | --- | --- |
| CTA destination and launch/access state are unresolved | Production Stress, Implementation Reality, Assumption Challenger, Coherence Auditor | Tier 1/Tier 2 | HIGH |
| Consent/revocation copy is too compressed or overclaims | Attack Surface, Production Stress, Implementation Reality, Assumption Challenger, Coherence Auditor | Tier 1/Tier 2 | HIGH |
| Access paths imply future MCP/CLI/hooks/API are currently available | Attack Surface, Production Stress, Coherence Auditor | Tier 2 | HIGH/MEDIUM |
| Product mocks omit untrusted/degraded/abstention states | Attack Surface, Production Stress, Implementation Reality | Tier 1 | HIGH |
| Japanese copy is corrupted or not launch-ready | Attack Surface, Production Stress, Assumption Challenger, Implementation Reality, Coherence Auditor | Tier 1/Tier 3 | HIGH |

Issues identified by 2 reviewers:

| Issue | Reviewers | Tier | Confidence |
| --- | --- | --- | --- |
| "Internet of solved agent problems" overclaims public network maturity | Attack Surface, Assumption Challenger, Coherence Auditor | Tier 2/Tier 3 | HIGH/MEDIUM |
| Proof section lacks metric/state contract | Production Stress, Assumption Challenger | Tier 2/Tier 3 | HIGH/MEDIUM |
| Accessibility requirements need implementable acceptance details | Implementation Reality, Assumption Challenger, Coherence Auditor | Tier 2/Tier 3 | MEDIUM/HIGH |

## Selected Fixes

Accepted for the fix round:

- Explicitly mark launch state as private design-partner access, no broad public
  corpus/search, and no production external MCP/CLI/hooks/API.
- Change CTA copy and define `/design-partner-access` and `/architecture` route
  targets with data-minimizing intake requirements.
- Replace absolute revocation copy with bounded copy that states what Knudg can
  block and what already-delivered copies cannot be erased.
- Split public publication from team namespace sharing.
- Add concrete approval, withdrawal, revocation, cleanup, and handoff states.
- Add untrusted, summary-only, withheld-detail, abstention, degraded, rate-limit,
  and stale-revocation states to hero/product mocks.
- Replace undefined card metadata with fields mapped to the product state model.
- Remove launch copy that implies broad public internet-scale coverage.
- Remove Japanese localization copy from implementation inputs until a formal
  localization pass.
- Add accessibility, responsive, performance, analytics, navigation, and font
  acceptance details.

Parked or not fixed in this round:

- Competitor positioning on the LP remains an open product choice.
- Exact public architecture explainer content is not authored in this round.

## Raw Reviewer Output Index

Raw reviewer outputs were produced by these subagent lanes in the current
thread:

- Attack Surface: `019e14e2-983b-7973-93a6-4578e4a88778`
- Production Stress: `019e14e2-988d-7bf2-a1c0-87cd2fca2689`
- Assumption Challenger: `019e14e2-98e8-7da0-8ba0-7564149ada93`
- Implementation Reality: `019e14e2-994b-7ef0-8c65-00f4253c3cf2`
- Coherence Auditor: `019e14e2-9a14-70a3-b9d7-6cdd07383816`

## Statistics

- Total material findings: 46
- Tier 1: 13
- Tier 2: 22
- Tier 3: 11
- Cross-lane convergence (3+): 5
- Cross-lane convergence (2): 3
- Average weighted score: 4.73/10

## Round 2 Summary

After the first fix round, all five reviewer lanes scored above the failure
threshold.

| Reviewer | Correctness | Completeness | Implementability | Resilience | Weighted Avg |
| --- | ---: | ---: | ---: | ---: | ---: |
| Attack Surface | 7 | 6 | 6 | 5 | 6.25 |
| Production Stress | 6 | 5 | 5 | 4 | 5.25 |
| Assumption Challenger | 6 | 5 | 5 | 4 | 5.25 |
| Implementation Reality | 6 | 4 | 4 | 5 | 4.88 |
| Coherence Auditor | 6 | 5 | 6 | 5 | 5.63 |
| **Average** | **6.2** | **5.0** | **5.2** | **4.6** | **5.45** |

PASS/FAIL: **PASS by the configured adversarial-review scoring rule** because
no axis average was `<= 3`.

Round 2 still produced implementation-hardening findings. The orchestrator
accepted the high-confidence findings and made a final hardening pass:

- replaced "approved troubleshooting history" with scoped public-publication
  approval language
- scoped revocation claims to selected card/version or selected permission
- added intake privacy, retention, provider, abuse, failure-state, and analytics
  constraints
- added a public/private/reviewer audience-state matrix
- split private single-workspace dogfood, team namespace dogfood after consent
  UI, local consent/control handoffs, and future external retrieval access
- added a writer-flow section
- added canonical consent/revocation mock values
- removed Japanese localization copy from implementation inputs until a formal
  localization pass
- added public architecture publication checklist, mobile nav behavior, status
  token matrix, INP budget, font/icon source rules, and launch dashboard checks

Remaining parked choices:

- pricing language
- competitor positioning
- whether and when to run Japanese localization after English MVP validation
