# M1 Writer Backlog

M1 is the path from solved work to structured candidate cards. Non-synthetic
private candidate storage remains blocked until the
`non_synthetic_body_persistence_gate` passes: `private_candidate_collection`
consent/acknowledgement for short-lived drafts,
protected-data durability, audit persistence, PR-006 database-side intake
safety, and no-log ingress constraints. Promotion to retained private cards
separately requires `private_retention` consent.

Priority note:

Before building the product-facing protected writer path, implement a narrower
local private dogfood writer path. It stores explicit operator-authored cards
with immutable `source_class = local_private_dogfood` in one local workspace.
It must use a positive allowlist schema, reject raw/private/executable content
after canonicalization, avoid raw-body logging, and never create team/public
sharing, hosted sync, publication consent, embeddings, product queue jobs,
exports, review/admin records, or background capture. It exists only to
validate the vertical product value.

## M1-WR-000: Local Private Capture

Status: done

Parent:

- `UR-BE-000` owns closure for the whole local private vertical loop.
  `M1-WR-000` is complete for the local-only P0 scope: the M3 local-private
  search extension, local revoke, local purge, no-log evidence,
  non-promotion evidence, principal/workspace fences, and non-skipped Postgres
  integration evidence pass.

Goal:

Capture one useful, operator-written experience card into the local DB and make
it eligible for local search.

Acceptance:

- Accept `local-private-card-v0` input with `source_class:
  local_private_dogfood`, bounded title, problem/solution summaries, public
  package/tool names, coarse environment tags, public docs URLs, safe
  non-executable command labels, and normalized error fingerprints.
- Store the card in local Postgres with `visibility = local_private`,
  `sharing_state = not_shared`, and `publication_state = never_publishable`.
- Reject secrets, tokens, raw transcripts, logs, stack traces, arbitrary files,
  source contents, private paths, private hostnames, executable command lines,
  raw command output, and cross-field reconstructions without echoing them.
- Return opaque card/version IDs, digest, and local-only status.
- Provide `knudgctl local revoke` and `knudgctl local purge` before declaring
  the feature usable.
- Use the command output, reject classes, canonicalization, DB preflight, and
  local RLS/session-claim rules from `docs/architecture/implementation-readiness.md`.
- Keep product-path non-synthetic candidate collection disabled.

Evidence:

- Non-skipped local Postgres test for capture -> search -> revoke ->
  no_suggestion -> purge -> no_suggestion.
- Negative tests proving forbidden fragments are rejected and absent from
  stdout, stderr, logs, traces, DB rows, generated FTS/search text, queue
  payloads, snapshots, and retrieval-panel metadata.
- Negative tests proving captured cards cannot enter product submit,
  team/public sharing, hosted sync, publication, embeddings, exports, protected
  search, public search, or production projections.

## M1-WR-001: Local Synthetic Writer Draft Helper

Status: done

Goal:

Add a local helper that turns sanitized, synthetic input into a canonical card
payload and digest without inserting into product tables.

Why now:

This creates a tangible knowledge-writer surface while respecting M1 gates.

Acceptance:

- Accept only a bounded JSON input shape for synthetic/local draft creation.
- Generate a `card-payload-v1` object compatible with `scripts/card_payload.py`.
- Refuse raw transcripts, stack traces, secrets, absolute paths, private repo
  names, and arbitrary file ingestion.
- Print canonical JSON and digest.
- Do not write to Postgres or create approval/consent records.
- Add tests for solved, failed-only, unknown-clarified, and rejected raw/private
  input.

Suggested files:

- `scripts/knudg_writer.py`
- `tests/test_knudg_writer.py`
- `docs/operations/local-writer-draft.md`
- `package.json` script `writer:draft`

Evidence:

- `python -m pytest tests/test_knudg_writer.py tests/test_knudg_plugin_manifest.py tests/test_card_payload_schema.py`
- `npm run writer:draft -- draft-card --help`

## M1-WR-002: Local Private-Use Notice Artifact

Status: done

Gate:

- Can be drafted now, but must not imply non-synthetic collection is enabled.

Acceptance:

- Define the local private-use notice copy for future M1 collection.
- Include purpose, collected fields, TTL, readers, opt-out, discard/purge path,
  and whether data leaves local workspace.
- Add tests or static checks that CLI output never says public publication is
  enabled.

Evidence:

- `schemas/private-use-notice-v0.schema.json`
- `fixtures/private-use-notice.local-draft.json`
- `docs/product/local-private-use-notice.md`
- `tests/test_private_use_notice.py`

## M1-WR-003: Pending Approval Queue Model

Status: done

Gate:

- Requires the `non_synthetic_body_persistence_gate` before storing
  non-synthetic data.

Acceptance:

- Define local queue fields for candidate ID, digest, preview path, TTL,
  consent scope, and state.
- Store only redacted draft metadata and body after the
  `non_synthetic_body_persistence_gate` passes.
- Add discard/purge semantics and idempotency.

Evidence:

- `schemas/pending-approval-queue-v0.schema.json`
- `fixtures/pending-approval-queue.model-only.json`
- `docs/operations/pending-approval-queue.md`
- `tests/test_pending_approval_queue_schema.py`

## M1-WR-004: Product-Facing Submit Candidate Flow

Status: gated

Gate:

- Requires accepted WEDGE-001 protocol, non-local auth/protected submit
  authorization when outside local dogfood, and the
  `non_synthetic_body_persistence_gate`.

Acceptance:

- Connect a client submit path to `knudg_submit_candidate`.
- Enforce tenant/namespace claims and submit scope.
- Run the database-side intake safety gate before admission or body storage for
  non-synthetic input.
- Reject or defer non-synthetic body storage unless the
  `non_synthetic_body_persistence_gate` is active.
- Return structured status without leaking raw input.
- Add E2E tests with local Postgres.

## M1-WR-005: Local Writer Queue Status And Dry-Run Reconcile

Status: done

Gate:

- Read-only local/synthetic inspection is allowed now. Apply mode and
  non-synthetic protected-data serving remain disabled.

Acceptance:

- Add `knudgctl writer status` for writer card status counts, writer-lane queue
  counts, and active private approval challenge counts.
- Add `knudgctl writer reconcile --dry-run` to list opaque candidate IDs,
  current-version digests, and recommended next writer action.
- Keep `knudgctl writer reconcile --apply` disabled.
- Do not expose `payload_json`, card bodies, transcripts, command output, or
  private source material.

Evidence:

- `python -m pytest tests/test_m0_schema.py -k writer_status`

## M1-WR-006: Local Writer Queue Enqueue Orchestration

Status: done

Gate:

- Local/synthetic worker job enqueueing is allowed now. Worker execution,
  trusted human approval UI, non-synthetic protected-data serving, and public
  publication remain disabled or separately gated.

Acceptance:

- Add `knudgctl writer enqueue-next --dry-run` to plan next worker jobs for
  local writer cards without mutating queue state.
- Add `knudgctl writer enqueue-next --apply` to enqueue opaque worker jobs for
  the next local writer action.
- Keep payloads limited to card IDs, current-version IDs, source status,
  operation name, worker role, and disabled serving/publication flags.
- Make repeated apply idempotent for the same card/version/action.
- Keep `writer reconcile --apply` disabled.
- Do not expose `payload_json`, card bodies, transcripts, command output, or
  private source material.

Evidence:

- `python -m pytest tests/test_m0_schema.py -k writer_enqueue_next`
