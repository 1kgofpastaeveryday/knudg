# Adversarial Review 2026-05-14: G2 M0 Event Append Path

Status: PASS after targeted Round 4

## Scope

Reviewed the M0 event append path against RFC 0001 and the executable schema/tests:

- `migrations/0001_m0_schema.up.sql`
- `tests/test_m0_schema.py`
- M0 event append requirements from `docs/rfcs/0001-m0-schema-event-log.md`

## Round 1/2 Converged Blockers

- No canonical creation append path existed. Cards could be created directly without `card_created`.
- `knudg_append_card_event` was too generic and could advance privileged lifecycle events without side effects.
- Read-only namespace grants could append events.
- `SECURITY DEFINER` functions included `public` in `search_path`.
- Idempotency replay could race stale projection checks.
- Event read policies did not apply the revocation fence.

## Fixes Applied

- Added `knudg_submit_candidate(...)` as the creation command. It atomically inserts:
  - `experience_cards`
  - first `card_versions` row
  - `card_created` event at `event_seq = 1`
  - `event_stream_positions` ledger row
  - `idempotency_keys` record
- Restricted `knudg_append_card_event(...)` to app-user, submit/admin-scoped, side-effect-free app-user lifecycle events:
  - `discard_requested`
  - `discard_restored`
  - `approval_digest_invalidated`
- Changed append replay to recheck card namespace, revocation fence, and submit/admin namespace grant before returning an idempotent result.
- Removed `public` from `SECURITY DEFINER` function search paths and fully qualified public table references.
- Added `principal_has_namespace_scope(...)` for command-scope authorization.
- Tightened payload checks to match the M0 version payload fields from the data model.
- Changed `idempotency_keys` app/worker RLS policy to read-only and kept writes behind definer command functions.
- Restricted `card_events` reads through namespace and revocation checks and revoked direct app/worker select from `domain_events`.

## Tests Added/Updated

- Submit candidate through `knudg_submit_candidate`.
- Idempotent replay and digest conflict for creation.
- Append after canonical `card_created`, with event sequence starting at `2`.
- Read-only namespace grant cannot submit or append.
- Direct table mutation remains denied.
- Revoked card hides direct card/version/event reads.
- Append idempotency replay is denied after revocation.
- Static guard rejects `SECURITY DEFINER` functions with `public` in `search_path`.

## Verification

- `python -m pytest tests/test_m0_schema.py -q`: 18 passed
- `python scripts\migrate.py down; python scripts\migrate.py up`: passed
- Targeted Round 4 reviewer verdict: PASS, no blocking findings

## Parked Follow-Ups

- Full migration runner safety: advisory lock, failed down-state recording, concurrent index path, invalid-index detection.
- Operation-specific command functions for approval, publish, revoke, version creation, indexing, supersession, and deprecation side effects.
- Claim nonce/replay hardening and stronger actor-role binding beyond the current app-user G2 path.
- Event-position trigger performance improvement from global scan to row-local validation plus offline reconciliation.
- Documentation reconciliation for source-of-truth precedence, lifecycle table duplication, and revocation subject routing.
