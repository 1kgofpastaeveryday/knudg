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

## Operations

- [Cloud Closed-Launch Deployment Template](operations/cloud-closed-launch-runbook.md)
- [Landing Page Runbook](operations/landing-page-runbook.md)

The gate/preflight runbooks that used to be listed here were part of the
human-gated milestone model and were removed in the reshape. See
`docs/architecture/target-model.md` for the current backend shape.

## Architecture

- [Trust Model](architecture/trust-model.md) - conceptual spine; read first
- [Target Model](architecture/target-model.md) - source of truth for what Knudg
  is and the one-pipe backend shape
- [Semantic Search](architecture/semantic-search.md) - pillar ④, hybrid FTS + pgvector
- [Security and Privacy](architecture/security-privacy.md)
- [Data Model](architecture/data-model.md)
- [M0 Contract Split](architecture/m0-contract-split.md)
- [Summoned Role MVP](architecture/summoned-roles.md) - product design only;
  active implementation uses live backend orchestration
- [Retrieval Model](architecture/retrieval.md)
- [Search Strategy](architecture/search-strategy.md)

The human-gated milestone, consent/approval, enterprise-governance,
experience-domains, and public-publication-path docs were retired in the
reshape (see git history); `architecture/target-model.md` is the map back.

## Product

- [Product Strategy](product/strategy.md)
- [Pre-M1 Validation Protocol](product/pre-m1-validation-protocol.md)
- [WEDGE-001 Validation Workbook](product/wedge-001-validation-workbook.md)
- [Private Validation Replay (2026-06-01)](product/private-validation-replay-2026-06-01.md)
- [Codex for OSS Readiness](product/codex-for-oss-readiness.md)
- [Landing Page Design](product/landing-page-design.md)
- [Landing Page Japanese Design](product/landing-page-ja-design.md)
- [Landing Page Simplified Chinese Design](product/landing-page-zh-cn-design.md)

## RFCs

- [RFC 0001 - M0 Schema and Event Log](rfcs/0001-m0-schema-event-log.md)
- [RFC 0003 - WEDGE-001 Agentic Coding Tooling Failures](rfcs/0003-wedge-001-agentic-coding-tooling.md)

## Historical RFCs

- [RFC 0002 - Codex Subconscious Sidecar](rfcs/0002-codex-subconscious-sidecar.md) - superseded, non-normative, and not part of active Knudg production architecture

Draft RFCs are exploratory and non-normative until explicitly accepted. Do not treat draft RFC behavior as implementation-authoritative when it conflicts with `docs/architecture/` or `docs/product/`.

`docs/architecture/target-model.md` is the source of truth. Where any RFC or
older architecture doc conflicts with it, target-model wins. RFC 0001 remains
the constrained M0 schema appendix and `docs/architecture/data-model.md` the
table-level reference for what the migrations build.

## Split Rule

Keep the root README focused on:

- product concept
- core roles
- architecture invariants
- MVP sequence
- links to detailed docs

Move details into `docs/` when a README section grows beyond a short overview or starts carrying normative implementation rules.
