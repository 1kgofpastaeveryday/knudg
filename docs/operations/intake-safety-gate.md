# Intake Safety Gate

Status: draft scaffold, non-synthetic submit disabled

`fixtures/intake-safety-gate.draft.json` is the PR-006 scaffold for the
database-side intake safety gate. It records disabled non-synthetic submit,
disabled body persistence, disabled review escrow, ingress bounds, required
future schemas, decision outcomes, no-raw-value guarantees, and blockers.

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
