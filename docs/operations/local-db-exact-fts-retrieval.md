# Local DB Exact/FTS Retrieval

Status: local synthetic-only DB retrieval slice

`knudgctl search local-exact-fts` searches synthetic cards already stored in
the local M0 tables. It bridges the gap between DB persistence and retrieval
dogfood without enabling non-synthetic protected retrieval, vector search,
reranking, public search, or publication.

## Command

```powershell
npm run knudgctl -- search local-exact-fts --tenant <tenant-id> --namespace <namespace-id> --task-profile path\to\task-profile.json
```

Optional controls:

```powershell
npm run knudgctl -- search local-exact-fts --tenant <tenant-id> --namespace <namespace-id> --task-profile path\to\task-profile.json --limit 3 --min-score 2
```

## Behavior

The command reads `experience_cards` joined to the current `card_versions` row
and returns `retrieval-panel-v0` metadata only. It filters to:

- the explicit tenant and namespace arguments
- statuses `approved_private`, `indexed_hot`, or `indexed_main`
- `privacy.source_class = synthetic`
- `provenance.source_class = synthetic`
- cards and versions not covered by revocation tombstones

The search is a local scan using PostgreSQL `to_tsvector`,
`plainto_tsquery`, and exact token overlap. It is not the production search
projection or index-generation path.

## Output Boundary

Returned cards include opaque card/version IDs, outcome, quality, evidence,
safety labels, synthetic freshness, matched terms, and goal/symptom summary.
They do not include full payload JSON, successful paths, failed paths, command
text, transcripts, source files, protected bodies, or publication state.

`served_from` is `local_db_exact_fts`.

## Gates

This command does not open `M3-RT-004` for real private/team search. The
production path still requires authorized exact/FTS projections, score
normalization, latency probes, no-log ingress, protected-data durability,
trusted consent/revocation UI, and the relevant non-synthetic gates.
