# Core Status

## What Is Designed

The original product center is represented in the current
architecture:

- shared, agent-readable experience infrastructure rather than personal memory
- structured reusable cards instead of raw transcripts
- knowledge crawler that searches similar prior work
- knowledge writer that asks for approval after a solved or clarified case
- summoned searcher/writer/nudger roles that can run outside the main prompt
- thin, bounded retrieval injection with abstention
- consent and revocation as launch-blocking human surfaces
- central search/index/storage concerns from the beginning

Primary design sources:

- `README.md`
- `docs/architecture/data-model.md`
- `docs/architecture/retrieval.md`
- `docs/architecture/consent-revocation-ux.md`
- `docs/architecture/security-privacy.md`
- `docs/architecture/implementation-readiness.md`
- `docs/rfcs/0001-m0-schema-event-log.md`
- `docs/rfcs/0003-wedge-001-agentic-coding-tooling.md`

## What Is Implemented

- Codex plugin/skill access path for live closed-launch orchestration.
- Client profile configuration and capability pinning.
- Card payload schema, canonicalization, and digest helpers.
- M0 SQL migration, rollback, RLS, event log, revocation tombstones, consent
  records, approval challenge binding, outbox/jobs, and CLI checks.
- Closed-launch API routes for operator-private structured card submission,
  search, card view, revoke, purge, and publication-candidate preview with
  public publication disabled.
- Retrieval-panel response schema aligned to the closed-launch private search
  response shape.
- `knudgctl writer status`, `writer reconcile --dry-run`,
  `writer enqueue-next`, `writer run-next`, `writer sweep`, and
  approval-handoff support for redacted closed-launch writer queue primitives.
- Live `knudgctl` profile build, search, nudge, and write-candidate commands
  against the pinned closed-launch backend.
- Task-profile builder for explicit safe current-work metadata.
- Local-private storage/search primitives for explicit operator-written cards:
  `knudgctl local preflight-db/capture/search/revoke/purge/verify-fences/audit-boundary`,
  local Postgres body/search side tables, principal/workspace fences,
  retrieval-panel metadata only, and non-skipped Postgres evidence.

## What Is Not Implemented

- Optional subconscious adapter boundary tests.
- Product-facing writer queue for candidate drafts.
- Trusted approval preview/completion UI.
- Real private/team search over product-path non-synthetic cards.
- Production exact/FTS indexes, search projections, and retrieval-panel
  response generation.
- Vector indexes, reranking, or public search.
- Consent/revocation cockpit UI.
- Production deployment, auth, billing, reviewer operations, or public corpus.

## Practical Interpretation

The project has crossed from concept into a working closed-launch private
backend path plus local-private storage primitives. The earlier local-only
synthetic dogfood server, synthetic retrieval harness, writer-draft helper, and
local role wrapper scripts have been removed from active implementation.
Explicit local-private cards can still be captured, searched, revoked, and
purged through backend primitives, but this does not open product-path
non-synthetic protected-data ingestion, trusted consent UI, public publication,
or broad private/team search.
