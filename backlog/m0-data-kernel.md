# M0 Data Kernel Backlog

## M0-DK-001: Migration And RLS Contract

Status: done

Acceptance:

- Empty apply, re-apply, rollback work.
- Lookup seeds, tenant-scoped constraints, event cursor bijection, RLS claim
  spoof denial, lifecycle transitions, and revocation tests pass.

Evidence:

- `migrations/0001_m0_schema.up.sql`
- `migrations/0001_m0_schema.down.sql`
- `tests/test_m0_schema.py`

## M0-DK-002: App-Role Submit Candidate Function

Status: done

Acceptance:

- App role can submit a candidate only with valid claims and submit scope.
- Payload is canonicalized and rejects duplicate keys, non-ASCII keys, unsafe
  numbers, projection-owned fields, and invalid outcome shape.
- Idempotent replay returns the original effect; digest conflict fails.

Evidence:

- `knudg_submit_candidate`
- `tests/test_m0_schema.py`
- `tests/test_card_payload_schema.py`

## M0-DK-003: Queue/Outbox Kernel

Status: done

Acceptance:

- Outbox enqueue is idempotent.
- Workers can claim, complete, fail, and dead-letter jobs with lease ownership.
- Direct app-role job mutation is denied.
- CLI queue stats and redacted peek are available.

Evidence:

- `knudg_enqueue_outbox_job`
- `knudg_claim_job`
- `knudg_complete_job`
- `knudg_fail_job`
- `tests/test_m0_schema.py`

## M0-DK-004: M0 Contract Split

Status: done

Goal:

Split the large M0 SQL migration into follow-up implementation notes or smaller
auditable migration slices before expanding M1/M2.

Acceptance:

- Document which parts of `0001_m0_schema` are stable foundation and which are
  local-M0-only.
- Identify any code paths that depend on local HS256 and must be swapped before
  protected private/team data.
- Add a checklist for future migration split or hardening.

Evidence:

- `docs/architecture/m0-contract-split.md`
- `tests/test_m0_contract_split.py`
