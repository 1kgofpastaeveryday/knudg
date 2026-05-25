# Core Status

## What Is Designed

The original product center from `user-said.md` is represented in the current
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
- `docs/architecture/summoned-roles.md`
- `docs/architecture/retrieval.md`
- `docs/architecture/consent-revocation-ux.md`
- `docs/architecture/security-privacy.md`
- `docs/architecture/implementation-readiness.md`
- `docs/rfcs/0001-m0-schema-event-log.md`
- `docs/rfcs/0003-wedge-001-agentic-coding-tooling.md`

## What Is Implemented

- Local Codex plugin/skill access path.
- Local dev server health/capabilities.
- Client profile configuration and capability pinning.
- Card payload schema, canonicalization, and digest helpers.
- Local synthetic writer draft helper.
- Synthetic corpus builder for local retrieval fixtures.
- M0 SQL migration, rollback, RLS, event log, revocation tombstones, consent
  records, approval challenge binding, outbox/jobs, and CLI checks.
- Retrieval/API/MCP skeleton that validates bounded request shapes and abstains.
- Synthetic retrieval harness, retrieval-panel response schema, local dev-server
  synthetic retrieval endpoint, and `knudgctl server synthetic-search`.
- Local DB exact/FTS scan for stored synthetic cards through
  `knudgctl search local-exact-fts`.
- `knudgctl writer status`, `writer reconcile --dry-run`,
  `writer enqueue-next`, `writer run-next`, `writer sweep`, and local
  approval-handoff placeholders for redacted local writer queue orchestration.
- Summoned role verdict schema plus local synthetic searcher, writer, and nudger
  wrappers that return compact verdicts.
- Local task-profile builder and one-command synthetic dogfood path.
- Synthetic retrieval replay metrics for the current hybrid fixture.
- Local private vertical loop for explicit operator-written cards:
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

The project has crossed from concept into working local synthetic and
local-private loops. Synthetic writer drafts can become synthetic corpus
fixtures, be retrieved through the local harness or loopback server, and flow
through compact summoned role verdicts. Explicit local-private cards can be
captured, searched from a later task profile, revoked, and purged with
non-skipped Postgres evidence. It has not crossed into product-path
non-synthetic protected-data ingestion, real private/team search, trusted
consent UI, or public publication.
