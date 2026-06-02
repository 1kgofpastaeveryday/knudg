# Operational Circuit Gate Scaffold

Status: draft scaffold, live circuit mutation disabled

The circuit gate scaffold records DEC-015 operational circuit defaults for the
critical circuit families described in `docs/architecture/operations.md`.
It does not create the `operational_circuits` table and does not enable live
control-plane mutation.

## Files

- `schemas/circuit-gates.schema.json` defines the gate fixture shape.
- `fixtures/circuit-gates.draft.json` records the current circuit-family
  defaults.
- `scripts/validate_circuit_gates.py` validates that critical families exist
  and that unsafe enablement remains disabled.

## Command

```powershell
npm run circuit:gates
```

Expected current result:

```json
{"live_mutation_enabled": false, "public_publication_enabled": false, "status": "ok"}
```

## Boundary

The scaffold may name circuit families, store classes, owner roles, runbook IDs,
and blocking gates. It must not contain real incident tickets, customer impact
details, tenant identifiers, private thresholds, operator identities, emergency
manifest keys, or live circuit state.

Live circuit mutation and public publication remain disabled until circuit DDL,
audit events, operator authorization, emergency manifest verification,
strictest-state selection tests, and outage drills all pass.
