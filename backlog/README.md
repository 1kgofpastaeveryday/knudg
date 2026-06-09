# Knudg Backlog

This directory is the implementation queue for Knudg. It translates product
intent and architecture docs into small, testable slices.

## Current Readiness

Knudg's core is designed at the architecture/RFC level, but only the lower
foundation is implemented.

| Area | Design state | Implementation state | Notes |
|---|---|---|---|
| Codex plugin/client | designed | live closed-launch ready | `$knudg` skill, pinned backend status/capabilities, live profile/search/nudge/write-candidate commands, and Greencloud closed-launch pinning work. |
| M0 trust/data kernel | designed | largely implemented | SQL migration, RLS, event log, revocation, consent records, outbox/jobs, and tests exist. |
| Structured card payload | designed | implemented as schema/digest helper | Validates canonical payload shape and digest; legacy local writer-draft helpers have been removed. |
| Private writer flow | designed | backend primitives implemented, product path gated | Candidate submission tests and private approval paths exist; trusted human UI and product-path non-synthetic storage remain gated. |
| Knowledge crawler/retrieval | designed | closed-launch private retrieval implemented | Request validation, abstention, retrieval-panel shape, Greencloud/closed-launch search, and local-private card fences exist; legacy synthetic corpus and loopback server paths have been removed. |
| Summoned Knudg roles | designed | live backend orchestration only | The active skill uses live profile/search/nudge/write-candidate commands; legacy local role wrapper scripts have been removed. |
| Experience domains | design reflected | not implemented | Technical, personal reasoning, career, place/service, public-candidate, and public-aggregate domains are defined as future domain-separated retrieval/consent boundaries. |
| Consent/revocation UX | designed | not implemented as UI | DB primitives exist; trusted human UI remains launch-blocking before public/team sharing. |
| Shared/public corpus | gated | not implemented | Blocked until WEDGE-001 validation, public privacy gates, reviewer supply, and consent/revocation E2E. |

Implemented primitives and local-private labels do not open product gates.
`local_private_dogfood` remains a constrained source class used by the current
closed-launch backend paths, but the old local-only fixture server, synthetic
retrieval harness, synthetic writer draft command, and local role wrappers have
been removed from the active implementation. Product-path non-synthetic session
capture still remains closed unless the relevant signed launch-gate manifest is
open.

`agent-subconscious` is not the Knudg canonical store. It may observe local
agent work, extract candidate facts, and propose local drafts. Knudg owns the
canonical schema, consent/approval/revocation state, shared database, retrieval
contracts, and publication gates.

The current agent-native direction is live closed-launch orchestration first:
build a sanitized task profile, query the pinned backend, return compact nudger
signals, and create only approval-required write candidates.

## Operating Rules

- Prefer vertical slices that exercise the closed-launch backend directly.
- Do not add new production/shared gates, enterprise governance, vector/rerank,
  billing, or public corpus work until the closed-launch private backend loop
  is usable and measured.
- Allow `local_private_dogfood` before production gates only as an immutable
  source class for explicit local operator-authored cards with no raw
  transcript/file ingestion and no team/public sharing.
- Keep local private cards out of hosted sync, production projections,
  embeddings, publication consent rows, product candidate queues, exports, and
  review/admin surfaces.
- Do not store non-synthetic private candidate metadata or draft bodies until
  the `non_synthetic_body_persistence_gate` is satisfied.
- Treat removed local/synthetic writer work as historical scaffolding, not as
  an active implementation path.
- Keep retrieval abstention-first until authorization, revocation fences,
  exact/FTS semantics, and safety gates are implemented.
- Treat `exploration_depth` as local root-cause discipline for whether a client
  stops at a solved path or pushes toward publication-grade evidence. It does
  not authorize broader data collection or bypass synthetic-only guards.
- Update task status when a slice is implemented, blocked, or superseded.

## Task Files

- The current design/implementation map is [docs/architecture/target-model.md](../docs/architecture/target-model.md). The milestone task files below predate it and describe the older private-first/gated model; treat target-model.md as authoritative where they conflict.
- [m0-data-kernel.md](m0-data-kernel.md): trust/data kernel follow-through.
- [m1-writer.md](m1-writer.md): private writer queue, candidate draft, consent, and approval tasks.
- [m3-retrieval.md](m3-retrieval.md): crawler/search/retrieval-panel path.
- [experience-domains.md](experience-domains.md): broader technical/personal/career/place-service domain separation and starter implementation slices.
- [backend-roadmap.md](backend-roadmap.md): backend path to use-ready and production-ready.
- [production-readiness.md](production-readiness.md): production, team, and public-pilot blockers.

## Next Recommended Slice

The current authority is Greencloud closed-launch first. Keep tightening that
path and only broaden product-path ingestion once the relevant gates are open.

`M1-WR-004` and production `M3-RT-004` remain gated by WEDGE-001,
protected-data, and retrieval-quality gates. The next order is protected-data
durability, intake safety, product submit, trusted approval/revocation UI, and
production exact/FTS projections; add local vault support only if the
approval-preview path genuinely requires it.
