# Launch Gate Manifest

Status: draft scaffold, all production gates closed

`fixtures/launch-gate-manifest.draft.json` is the machine-checkable launch gate
manifest scaffold for production readiness. It records gate ownership,
authority documents, public-safe status labels, private threshold references,
required fixtures, CI result references, evidence references, rollback targets,
and stale-review behavior.

Validate it:

```powershell
npm run launch:gates
```

The draft manifest intentionally keeps every gate closed. It does not open
non-synthetic storage, public publication, public search, enterprise guidance,
trusted consent completion, or production auth. The
`non_synthetic_body_persistence_gate` cannot open unless its prerequisite gates
also open with evidence references.

The manifest must not contain private paths, raw evidence, customer identifiers,
or public launch-control threshold values. Use opaque `evidence:*`,
`ci:*`, and `private-threshold:*` references instead.
