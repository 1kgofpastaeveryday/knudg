# Knudg Docs

This directory contains public project documentation, design notes, schemas,
runbooks, and future-facing specifications for the open-source Knudg backend,
CLI, plugin, and review flows.

Some documents describe gated or not-yet-enabled product surfaces. Those files
must state their status clearly and must not include private deployment
credentials, raw transcripts, personal operator notes, real customer data, or
machine-specific paths.

## Development

- [Local Development](development.md)
- [Pending Approval Queue](operations/pending-approval-queue.md)

## Operations

- [Cloud Closed-Launch Deployment Template](operations/cloud-closed-launch-runbook.md)
- [Landing Page Runbook](operations/landing-page-runbook.md)
- [Launch Gate Manifest](operations/launch-gate-manifest.md)
- [Runbook Command Manifest](operations/runbook-command-manifest.md)
- [WEDGE-001 Evidence](operations/wedge-001-evidence.md)
- [M3 Retrieval Gates](operations/m3-retrieval-gates.md)
- [Review Ops Gates](operations/review-ops-gates.md)
- [Circuit Gates](operations/circuit-gates.md)
- [Intake Safety Gate](operations/intake-safety-gate.md)
- [Auth Verifier Gate](operations/auth-verifier-gate.md)
- [Consent Revocation Gate](operations/consent-revocation-gate.md)
- [Trust and Safety Audit Gate](operations/trust-and-safety-audit.md)
- [Experience Surface Gates](operations/experience-surface-gates.md)
- [Abuse Identity Enforcement Preflight](operations/abuse-identity-enforcement.md)
- [Raw Detail Escrow Preflight](operations/raw-detail-escrow.md)
- [Company Store Dashboard Preflight](operations/company-store-dashboard.md)

## Architecture

- [Architecture Overview](architecture/overview.md)
- [Security and Privacy](architecture/security-privacy.md)
- [Data Model](architecture/data-model.md)
- [Experience Domains](architecture/experience-domains.md)
- [M0 Contract Split](architecture/m0-contract-split.md)
- [Enterprise Governance](architecture/enterprise-governance.md)
- [Agent Access](architecture/agent-access.md)
- [Summoned Role MVP](architecture/summoned-roles.md) - product design only;
  active implementation uses live backend orchestration
- [Retrieval Model](architecture/retrieval.md)
- [Search Strategy](architecture/search-strategy.md)
- [Operations](architecture/operations.md)
- [Consent and Revocation UX](architecture/consent-revocation-ux.md)
- [Implementation Readiness](architecture/implementation-readiness.md)

## Product

- [Product Strategy](product/strategy.md)
- [Public Corpus Growth Roadmap](product/public-corpus-roadmap.md)
- [Intent Crosswalk](product/intent-crosswalk.md)
- [Closed-Launch Private-Use Notice](product/closed-launch-private-use-notice.md)
- [Pre-M1 Validation Protocol](product/pre-m1-validation-protocol.md)
- [WEDGE-001 Validation Workbook](product/wedge-001-validation-workbook.md)
- [Landing Page Design](product/landing-page-design.md)
- [Landing Page Japanese Design](product/landing-page-ja-design.md)
- [Landing Page Simplified Chinese Design](product/landing-page-zh-cn-design.md)

## Decisions

- [Decision Backlog](decisions/README.md)

## RFCs

- [RFC 0001 - M0 Schema and Event Log](rfcs/0001-m0-schema-event-log.md)
- [RFC 0003 - WEDGE-001 Agentic Coding Tooling Failures](rfcs/0003-wedge-001-agentic-coding-tooling.md)

## Historical RFCs

- [RFC 0002 - Codex Subconscious Sidecar](rfcs/0002-codex-subconscious-sidecar.md) - superseded, non-normative, and not part of active Knudg production architecture

Draft RFCs are exploratory and non-normative until explicitly accepted. Do not treat draft RFC behavior as implementation-authoritative when it conflicts with `docs/architecture/`, `docs/product/`, or `docs/decisions/`.

Accepted RFCs are normative only for their declared milestone and scope. For M0
lifecycle, visibility, and publication semantics, `docs/architecture/data-model.md`
is the implementation authority and RFC 0001 is the constrained implementation
appendix. If an RFC and architecture document disagree, the same change must
update the architecture source of truth or the architecture document wins.

## Split Rule

Keep the root README focused on:

- product concept
- core roles
- architecture invariants
- MVP sequence
- links to detailed docs

Move details into `docs/` when a README section grows beyond a short overview or starts carrying normative implementation rules.
