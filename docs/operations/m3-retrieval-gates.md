# M3 Retrieval Gate Scaffold

Status: draft scaffold, protected-data serving disabled

The M3 retrieval gate scaffold records the future exact/FTS and DEC-014A
sender-constrained proof-profile prerequisites without accepting either gate or
enabling protected-data retrieval.

## Files

- `schemas/m3-retrieval-gates.schema.json` defines the gate fixture shape.
- `fixtures/m3-retrieval-gates.draft.json` is the current draft scaffold.
- `fixtures/m3-retrieval-hybrid-fixtures.json` records historical synthetic
  query-view and fusion replay fixture thresholds; it is not an active runtime
  path.
- `scripts/validate_m3_gates.py` validates the fixture and blocks premature
  accepted status when required gate decisions are still unset.
  Accepted status is bound to the authoritative decision backlog:
  `docs/decisions/README.md` must mark DEC-014A accepted before a fixture can
  pass as accepted. A fixture cannot self-assert DEC-014A acceptance.
  Accepted status also requires existing exact/FTS and DEC-014A evidence
  artifacts under `docs/operations/evidence/`; non-`unset` enum fields alone
  are not enough.

## Command

```powershell
npm run m3:gates
```

Expected current result:

```json
{"protected_data_enabled": false, "status": "ok"}
```

## Boundary

The scaffold may name fixture IDs, threshold labels, decision IDs, proof-profile
test names, and blocking gates. It must not contain raw queries, private search
profiles, customer examples, transcripts, tokens, keys, repository URLs, or
protected card data.

Protected-data retrieval remains disabled even if this fixture eventually moves
to `accepted`; enabling serving requires the later implementation gates in
`agent-access.md`, `retrieval.md`, and the relevant accepted auth/retrieval
RFCs.
