# M0 Contract Split

This note separates the M0 data-kernel pieces that are stable implementation
foundation from legacy local-only pieces. The loopback server, synthetic
retrieval harness, local writer draft helper, and local role wrappers have been
removed from active implementation; remaining local-only items are support
machinery for tests and must not become protected-data paths.

## Stable M0 Foundation

These pieces are implementation foundation for later milestones:

- tenant-scoped identity pattern with `(tenant_id, id)` keys
- namespace-scoped card ownership
- immutable `card_versions.payload_json` plus canonical payload digest
- `experience_cards.current_version_id` as the only current-version pointer
- append-only `card_events` and `domain_events`
- global `event_stream_position` as the replay cursor
- lifecycle transition table and transition guard
- idempotency keys with request-digest conflict rejection
- consent records bound to exact artifacts and policy digests
- revocation tombstones checked before reads
- audit event append-only behavior
- outbox/jobs as the local Postgres-backed queue kernel

These contracts can be expanded, but later code should not bypass them with a
parallel lifecycle, current-version marker, ad hoc event cursor, or separate
authorization model.

## Local-Only M0 Pieces

These pieces are local development scaffolding only:

- HS256 request-context verification inside Postgres
- `claim_signing_keys.verify_secret` as the verifier secret store
- local `pgcrypto` HMAC verification as key custody
- synthetic/local fixture data used by tests
- local HS256 development claims and local DB helper commands

These pieces may support tests. They must not be used for non-synthetic
private/team protected data, shared dev with protected fixtures, staging,
production, public search, public publication, or enterprise deployment.

## Verifier Swap Boundary

Application and client code must depend on a request-context verifier contract,
not on HS256 or the physical `claim_signing_keys` table.

Before M1 handles non-synthetic private/team protected data, Knudg needs an
accepted verifier profile that provides:

- asymmetric or external KMS/Vault-style verification
- key custody outside ordinary database backup compromise
- key ID rotation and emergency disable
- audience binding
- nonce/replay protection
- short expiry
- disabled/expired/unknown key fail-closed behavior
- tests proving the RLS call sites do not change when the verifier backend
  swaps
- CI or environment assertions that fail if local HS256 is enabled outside the
  local development profile

## Protected-Data Gate

Before any non-synthetic private candidate metadata or redacted draft body is
stored, all of these must be true:

- WEDGE-001 is accepted.
- Private-use notice and acknowledgement are implemented.
- Protected-data durability gate passes.
- Non-local request-context verifier profile is accepted and tested.
- Restore starts quarantined and replays revocation, consent expiry,
  discard/purge, and idempotency effects before serving.
- No test/support helper may ingest raw logs, transcripts, source files,
  private repo names, secrets, tokens, or arbitrary workspace files.

## Implementation Rule

Future slices may use M0 stable foundation tables and functions. Future slices
must not turn local-only scaffolding into a protected-data path by accident. If
a slice shares data beyond the local machine, it must go through the one pipe
defined in [target-model.md](target-model.md): upload to the backend feeds the
throttled queue, the GLM filter is the sole publication gate, and revoke always
works. private stays local and is never uploaded.
