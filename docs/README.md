# Knudg Docs

This directory holds detailed design notes that would make the root README too large.

## Architecture

- [Architecture Overview](architecture/overview.md)
- [Security and Privacy](architecture/security-privacy.md)
- [Data Model](architecture/data-model.md)
- [Agent Access](architecture/agent-access.md)
- [Retrieval Model](architecture/retrieval.md)
- [Operations](architecture/operations.md)
- [Consent and Revocation UX](architecture/consent-revocation-ux.md)
- [Implementation Readiness](architecture/implementation-readiness.md)

## Product

- [Product Strategy](product/strategy.md)
- [Intent Crosswalk](product/intent-crosswalk.md)

## Decisions

- [Decision Backlog](decisions/README.md)

## Plans and Reviews

Plans are historical review artifacts unless a file explicitly says it is a current implementation spec. Current normative design lives under `docs/architecture/`, `docs/product/`, and `docs/decisions/`.

- [Adversarial Review - 2026-05-09](plans/adversarial-review-2026-05-09.md)
- [Adversarial Review - 2026-05-07](plans/adversarial-review-2026-05-07.md)
- [Adversarial Review Fix Loop - 2026-05-07](plans/adversarial-review-2026-05-07-fix-loop.md)
- [Intent Drift Review - 2026-05-08](plans/intent-drift-review-2026-05-08.md)

## Split Rule

Keep the root README focused on:

- product concept
- core roles
- architecture invariants
- MVP sequence
- links to detailed docs

Move details into `docs/` when a README section grows beyond a short overview or starts carrying normative implementation rules.
