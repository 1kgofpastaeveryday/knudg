# Backend Roadmap

This page is the active backend implementation map after retiring the legacy
local-only dogfood runtime. Older local fixture servers, synthetic retrieval
harnesses, synthetic writer drafts, and local role wrapper commands are no
longer active implementation paths.

## Current Baseline

Implemented and still active:

- M0 migration, RLS, tenant/namespace/principal model, event log, consent
  records, revocation tombstones, jobs/outbox, and local development claims.
- Canonical card payload schema, digest helpers, and schema validators.
- Client configuration, status/capabilities checks, closed-launch pinning, and
  live `knudgctl` profile/search/nudge/write-candidate commands.
- Greencloud/closed-launch API surface for operator-private structured card
  submission, private search, card view, revoke, purge, and publication
  candidate preview.
- `local_private_dogfood` as a constrained source class used by the current
  closed-launch private path, with public publication disabled.
- Gate validators for launch manifest, auth verifier, intake safety,
  consent/revocation, review operations, circuits, runbook manifest, and
  WEDGE evidence.

Removed from active implementation:

- Loopback local dev server and process controller.
- Synthetic retrieval harness and replay command.
- Non-ingesting retrieval skeleton command.
- Synthetic writer-draft command.
- Local summoned-role wrapper command.
- One-command local dogfood smoke command.

## Still Closed

- Product-path non-synthetic session capture.
- Trusted approval, consent, and revocation human UI.
- Public publication and public search.
- Team namespace sharing.
- Vector/rerank.
- Production billing and public corpus ingestion.
- Reviewer/admin mutation routes.

## Current Priority

1. Keep the closed-launch backend narrow: bounded structured cards only,
   publication disabled, public/admin routes disabled, and retrieved cards
   advisory.
2. Only broaden product-path ingestion, trusted consent/revocation UI, or
   shared/team/public retrieval.
3. Decide a future replacement name/migration for the constrained
   `local_private_dogfood` source class.
4. Move remaining support-only local DB helpers under a clearer support
   namespace if the public CLI surface starts to matter.

## Triage Decisions

- `README.md` and `docs/architecture/implementation-readiness.md` now center
  Greencloud closed-launch instead of the old local-private vertical loop.
- `docs/architecture/summoned-roles.md` is product design only; live backend
  orchestration is authoritative for active implementation.
- `schemas/retrieval-panel-v0.schema.json` follows the actual closed-launch
  private search response.
- `knudgctl local *` and `knudgctl writer *` remain support/test machinery,
  not preferred active operator paths.
- `backlog/production-readiness.md` remains the blocker list for any
  product-path non-synthetic, team, public, or trusted consent surface.
