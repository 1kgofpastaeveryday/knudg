# Runbook Command Manifest

Status: draft scaffold, deployment drills not passed

The runbook command manifest records the command contract required by blocking
runbooks. It maps runbook commands to `knudgctl` stubs, operator roles, dry-run
behavior, mutation guards, stable exit codes, JSON output schemas, and audit
events.

## Files

- `schemas/runbook-command-manifest.schema.json` defines the manifest shape.
- `fixtures/runbook-command-manifest.draft.json` records the current scaffold.
- `scripts/validate_runbook_manifest.py` validates command coverage and blocks
  drill-passed claims without attached transcript artifacts.

## Command

```powershell
npm run runbook:manifest
```

Expected current result:

```json
{"command_count": 9, "drill_passed": false, "status": "ok"}
```

## Boundary

The manifest is not a drill transcript. A command can be listed while local M0
returns `not_configured`, but the manifest cannot claim `drill_passed` until
every row has a schema-valid passed transcript artifact under
`docs/operations/drills/` whose command ID, command text, and exit code match
the manifest row.

The scaffold must not contain real incident tickets, tenant IDs, operator
identities, customer impact details, private thresholds, or deployment-specific
hostnames.
