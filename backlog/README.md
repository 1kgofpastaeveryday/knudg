# Knudg Backlog

This directory is the implementation queue for Knudg. It translates the product
intent in `user-said.md` and the architecture docs into small, testable slices.

## Current Readiness

Knudg's core is designed at the architecture/RFC level, but only the lower
foundation is implemented.

| Area | Design state | Implementation state | Notes |
|---|---|---|---|
| Codex local plugin/client | designed | local dogfood ready | `$knudg` skill, local profile, dev server, status/capabilities, and pinning work. |
| M0 trust/data kernel | designed | largely implemented | SQL migration, RLS, event log, revocation, consent records, outbox/jobs, and tests exist. |
| Structured card payload | designed | implemented as schema/digest helper and local writer draft | Validates canonical payload shape and digest; synthetic drafts can feed the local corpus builder. |
| Private writer flow | designed | local private dogfood ready plus local/synthetic scaffolding | Explicit local-private capture, candidate submission tests, and private approval paths exist; `knudgctl writer status/reconcile/enqueue-next/run-next/sweep` and local approval handoff placeholders operate without exposing bodies. |
| Knowledge crawler/retrieval | designed | local private dogfood ready | Request validation, abstention, retrieval-panel shape, synthetic corpus search, local dev-server endpoint, `knudgctl server synthetic-search`, local DB exact/FTS scan over stored synthetic cards, and `knudgctl local search` over `local_private_dogfood` cards exist; real protected exact/FTS/vector search remains gated. |
| Summoned Knudg roles | designed | local dogfood ready | Role verdict schema plus local synthetic searcher, writer, nudger, task-profile builder, and one-command dogfood wrappers exist; future subconscious adapter remains deferred. |
| Consent/revocation UX | designed | not implemented as UI | DB primitives exist; trusted human UI remains launch-blocking before public/team sharing. |
| Shared/public corpus | gated | not implemented | Blocked until WEDGE-001 validation, public privacy gates, reviewer supply, and consent/revocation E2E. |

Implemented primitives and local dogfood labels do not open product gates.
The local private path with `source_class = local_private_dogfood` is now
implemented for explicit operator-written cards in one local workspace, local
Postgres only, no raw transcripts or arbitrary file ingestion, no team/public
sharing, and revoke/purge. This path exists to validate whether Knudg is useful
before more production/shared hardening. Product-path non-synthetic session
capture still remains closed unless the relevant signed launch-gate manifest is
open.

The current local scaffolding is usable: a writer draft can produce a
canonical digest, a task profile can be built from explicit safe metadata, a
synthetic corpus can be built from that draft, replay metrics can run over the
fixture set, stored synthetic cards can be searched from local M0 tables, and
the loopback server or summoned roles can return compact retrieval-panel
metadata/verdicts. DB-backed writer-runner and local DB retrieval evidence
still require local Postgres. The local private vertical loop can capture one
explicit local card, search it during a later task, revoke it, and purge it.

`agent-subconscious` is not the Knudg canonical store. It may observe local
agent work, extract candidate facts, and propose local drafts. Knudg owns the
canonical schema, consent/approval/revocation state, shared database, retrieval
contracts, and publication gates.

The current agent-native direction is summoned roles first. The main agent may
start bounded searcher, writer, nudger, and reviewer roles for a task, receive
compact verdicts, and decide whether to open a panel or handoff. This lets
Knudg dogfood writer/searcher/nudger behavior without finishing a fully
automatic subconscious sidecar.

## Operating Rules

- Prefer vertical slices that are usable in local dogfood.
- Do not add new production/shared gates, enterprise governance, vector/rerank,
  billing, or public corpus work until the local private vertical loop is
  usable and measured.
- Allow `local_private_dogfood` before production gates only as an immutable
  source class for explicit local operator-authored cards with no raw
  transcript/file ingestion and no team/public sharing.
- Keep local private cards out of hosted sync, production projections,
  embeddings, publication consent rows, product candidate queues, exports, and
  review/admin surfaces.
- Do not store non-synthetic private candidate metadata or draft bodies until
  the `non_synthetic_body_persistence_gate` is satisfied.
- Treat local/synthetic writer work as scaffolding for the future product path,
  not as a public publication path.
- Keep retrieval abstention-first until authorization, revocation fences,
  exact/FTS semantics, and safety gates are implemented.
- Treat `exploration_depth` as local root-cause discipline for whether a client
  stops at a solved path or pushes toward publication-grade evidence. It does
  not authorize broader data collection or bypass synthetic-only guards.
- Update task status when a slice is implemented, blocked, or superseded.

## Task Files

- [core-status.md](core-status.md): current design/implementation map.
- [local-dogfood.md](local-dogfood.md): plugin/client/server dogfood tasks.
- [m0-data-kernel.md](m0-data-kernel.md): trust/data kernel follow-through.
- [m1-writer.md](m1-writer.md): private writer queue, candidate draft, consent, and approval tasks.
- [summoned-roles.md](summoned-roles.md): sub-agent role contract and local dogfood tasks.
- [m3-retrieval.md](m3-retrieval.md): crawler/search/retrieval-panel path.
- [backend-roadmap.md](backend-roadmap.md): backend path to use-ready and production-ready.
- [production-readiness.md](production-readiness.md): production, team, and public-pilot blockers.

## Next Recommended Slice

`UR-BE-000` is done for the local-only P0 scope. Keep dogfooding it with
explicit local cards before broadening production/shared infrastructure.

`M1-WR-004` and production `M3-RT-004` remain gated by WEDGE-001,
protected-data, and retrieval-quality gates. The next order is local vault
support only if approval-preview dogfood needs it, then protected-data
durability, intake safety, product submit, trusted approval/revocation UI, and
production exact/FTS projections.
