# M3 Retrieval Backlog

M3 is the crawler/search side of the original idea. It turns sanitized current
work profiles into up to three candidate cards, or abstains.

Priority note:

Retrieval work should now serve the local private vertical loop before broader
production search. The immediate target is searching stored
`local_private_dogfood` cards from `task_profile.v0` and returning
retrieval-panel metadata. `local_private_dogfood` is a source class; local-only
visibility, sharing state, publication state, and lifecycle state are separate
fields. Production authorized exact/FTS projections,
index-generation manifests, vector search, reranking, and public search remain
deferred until local retrieval proves useful.

## M3-RT-001: Retrieval Skeleton Contract

Status: done

Acceptance:

- Private/team `SearchProfile` rejects raw/private fields.
- Public request rejects tenant, namespace, object, and fingerprint selectors.
- MCP JSON-RPC fixture supports `tools/list` and `tools/call`.
- Default behavior is `no_suggestion`.

Evidence:

- `scripts/knudg_retrieval.py`
- `tests/test_retrieval_skeleton.py`
- `docs/operations/retrieval-skeleton.md`

## M3-RT-002: Synthetic Exact/FTS Harness

Status: done

Goal:

Add a synthetic-only retrieval harness over approved/private synthetic cards.

Acceptance:

- Uses only synthetic or explicitly local-safe cards.
- Authorizes tenant/namespace before candidate generation.
- Applies revocation fence before returning metadata.
- Returns retrieval-panel shaped metadata only, not raw commands or full bodies.
- Abstains when confidence is below configured local threshold.

Evidence:

- `scripts/knudg_synthetic_retrieval.py`
- `tests/test_knudg_synthetic_retrieval.py`
- `docs/operations/synthetic-retrieval-harness.md`

## M3-RT-003: Retrieval Panel Shape

Status: done

Acceptance:

- Define response schema for retrieval-panel cards.
- Include outcome type, quality state, freshness, provenance, and risk label.
- Exclude executable command text for high-risk/unverified cards.
- Add tests for no_suggestion, withheld safety, deprecated/superseded, and
  revoked cases.

Evidence:

- `schemas/retrieval-panel-v0.schema.json`
- `tests/test_retrieval_panel_schema.py`

## M3-RT-004: Real Exact/FTS Search

Status: gated

Gate:

- Requires M3 gates, task-profile shape, and evaluation corpus.

Acceptance:

- Implement Postgres FTS/exact SQL over authorized card projections.
- Define score normalization and abstention threshold.
- Add replay fixtures and latency probes.

Local note:

- `knudgctl search local-exact-fts` now provides a synthetic-only DB scan over
  stored `experience_cards`/`card_versions` and returns retrieval-panel
  metadata. This is useful dogfood for the persistence-to-search path, but it
  is not the authorized production exact/FTS projection.

Next local step:

- Done for the local-only P0 path: `knudgctl local search` searches
  `local_private_dogfood` cards from `task_profile.v0` and returns
  retrieval-panel metadata. The local contract defines indexed fields,
  exact-match fields, rank formula, top-k, abstention threshold, and
  `no_suggestion` cases.
- Return only opaque card/version IDs, digest, local-only status, outcome type,
  freshness bucket, coarse match reason, and local-card handoff. Do not return
  source paths, hostnames, executable command text, raw error strings, private
  repo/tooling fingerprints, or card bodies.
- Apply local revoke/purge fences before ranking and prove search after revoke
  or purge returns `no_suggestion`.
- Handoff references are non-bearer: short-lived, scoped to the local
  principal/workspace/session, checked against revocation/purge state at open
  time, and invalidated by revoke or purge.
- This extension remains local-only; production protected-data search is still
  gated separately.
- Keep production protected-data search gated.

## M3-RT-005: Local Dev Server Synthetic Retrieval Endpoint

Status: done

Goal:

Make the synthetic retrieval harness reachable through the local loopback dev
server for dogfood without opening protected search.

Acceptance:

- Add `POST /v1/synthetic-retrieval/search`.
- Accept only JSON bodies containing a sanitized synthetic request and
  caller-provided synthetic corpus.
- Do not read corpus files from disk or query product tables.
- Keep `route_classes.search = disabled` and protected/public retrieval
  disabled in capabilities.
- Return retrieval-panel shaped metadata only and reject non-synthetic corpus
  input.

Evidence:

- `tests/test_knudg_dev_server.py`
- `python -m pytest tests/test_knudg_dev_server.py tests/test_knudg_synthetic_retrieval.py tests/test_retrieval_panel_schema.py`

## M3-RT-006: knudgctl Synthetic Retrieval Dogfood Command

Status: done

Goal:

Let local dogfood call the synthetic retrieval endpoint through the configured
`knudgctl` local server profile.

Acceptance:

- Add `knudgctl server synthetic-search --input <request> --corpus <corpus>`.
- Use only loopback local profiles or explicit loopback server overrides.
- Keep non-local cloud/enterprise server support disabled.
- Wrap the retrieval-panel response without exposing card bodies or enabling
  protected-data serving/publication.

Evidence:

- `tests/test_knudg_dev_server.py`

## M3-RT-007: Synthetic Corpus Builder

Status: done

Goal:

Let local dogfood flow from `writer:draft` output into the synthetic retrieval
harness without hand-authoring corpus wrappers.

Acceptance:

- Add `retrieval:synthetic build-corpus`.
- Accept valid synthetic `card-payload-v1` JSON or the `writer:draft`
  `local_draft_only` result wrapper.
- Reject non-synthetic payloads.
- Assign deterministic opaque fixture card/version IDs.
- Do not read workspace files as corpus data beyond explicit payload JSON
  arguments.

Evidence:

- `tests/test_knudg_synthetic_retrieval.py`

## M3-RT-008: Task Profile Schema

Status: done

Goal:

Define the local/searcher-side `task_profile.v0` shape used to derive retrieval
queries from current work before compiling to protected `SearchProfile`.

Acceptance:

- Captures explicit query text, intent, safe file refs, symbols, normalized
  error fingerprints, public packages/tools, runtime, coarse OS, dependency
  majors, risk tags, and recent event kinds.
- Rejects raw transcripts, full stack traces, private file contents, absolute
  paths, hostnames, usernames, secrets, and unredacted command output.
- Documents how `task_profile.v0` maps into private/team `SearchProfile` claims
  and where the server revalidates authority.
- Adds schema tests for accepted minimal profiles and rejected private/raw
  fields.

Evidence:

- `schemas/task-profile-v0.schema.json`
- `tests/test_task_profile_schema.py`
- `docs/architecture/search-strategy.md`

## M3-RT-009: Hybrid Retrieval Fusion Spec

Status: done

Goal:

Define the first wedge ranking spec for exact, FTS, vector-ready, metadata, and
quality signals before protected real retrieval is enabled.

Acceptance:

- Defines query views generated from a task profile: exact identifiers, sparse
  keywords, semantic summary, hypothetical relevant-card text, and structured
  filters.
- Uses simple rank fusion such as reciprocal-rank-style fusion for MVP unless a
  measured wedge corpus justifies another method.
- Keeps authorization and shard selection before candidate generation.
- Defines abstention thresholds, score normalization, freshness/deprecation
  demotion, and quality-state handling.
- Adds offline fixtures for recall@k, nDCG@k, abstention accuracy, and stale or
  harmful suggestion rate.

Evidence:

- `docs/architecture/search-strategy.md`
- `docs/operations/m3-retrieval-gates.md`
- `fixtures/m3-retrieval-*`
- `scripts/knudg_synthetic_retrieval.py`
- `tests/test_knudg_synthetic_retrieval.py`

## M3-RT-010: Searcher Role Task-Profile Dogfood

Status: done

Goal:

Let the summoned searcher role produce compact verdicts from task profiles
instead of requiring the main agent to hand-author search strings.

Acceptance:

- Adds a local synthetic command that accepts a `task_profile.v0` file and a
  synthetic corpus.
- Generates bounded query views without echoing raw/private input.
- Returns only `knudg_role_verdict.v0` with opaque refs and
  `offer_retrieval_panel` or abstention.
- Does not read workspace files beyond explicit task-profile and corpus
  arguments.

Evidence:

- `scripts/knudg_roles.py`
- `tests/test_knudg_role_verdict.py`
