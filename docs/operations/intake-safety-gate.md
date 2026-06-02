# Intake Safety Gate

Status: draft scaffold, non-synthetic submit disabled

`fixtures/intake-safety-gate.draft.json` is the PR-006 scaffold for the
database-side intake safety gate. It records disabled non-synthetic submit,
disabled body persistence, disabled review escrow, ingress bounds, required
future schemas, decision outcomes, no-raw-value guarantees, and blockers.
It also records symbolic domain coverage so future broader experience domains
are visible to validators while still disabled:

- `technical_work`: closed-launch structured-only
- `personal_reasoning`, `career_private`, `place_service_experience`:
  typed-only, no ingest
- `public_experience_candidate`: blocked, no public conversion
- `public_aggregate_signal`: blocked, no dashboard

It also tracks surface coverage for public candidate conversion, B2B
respondent portal, and company/store dashboard. All three remain blocked.
While review escrow is disabled, ambiguous raw content may only become
`redact_then_retry` or `retry_later`; it must not be stored.

The separate `raw-detail-escrow-request-v0` preflight contract models item 12
without opening this path. It keeps escrow writes, encrypted payload creation,
key handling, reviewer access, model raw input, validator raw echo, audit raw
echo, and client raw echo disabled until PR-003, PR-006, protected-data
durability, purge, TTL, reviewer access, no-raw-echo, and key-profile gates are
accepted.

Validate it:

```powershell
npm run intake:gates
```

This scaffold does not implement scanners, classifiers, review escrow, or
non-synthetic storage. It keeps `knudg_submit_candidate` synthetic-only until
the PR-006 schemas, no-log ingress tests, non-oracular response tests,
no-body-storage negative tests, protected fingerprint profile, and route-level
search/hook ingress protections exist.

Draft fixtures must refer to private limits through `private-threshold:*`
labels. They must not publish raw byte limits, detector internals, customer
identifiers, matched values, offsets, entropy scores, or classifier confidence.
Validator schema errors must report only paths and validator names, not
offending raw values.
