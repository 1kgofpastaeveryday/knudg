# Cloud Closed-Launch Deployment Template

This document is a public-safe template for deploying Knudg to a managed cloud
environment. It intentionally omits real resource names, account identifiers,
operator emails, IP addresses, tokens, and connection strings.

For local development, prefer `docker-compose.yml` and `.env.example`.

Deployment-local SSH aliases, hostnames, service paths, backup paths, and
restart commands must stay in ignored operator notes or the deployment
provider's private runbook. Do not commit them to this public repository. In
this workspace, the private closed-backend deploy/restart note is kept under
`.codex/knudg/` and is intentionally ignored by git.

Hosted Greencloud or other managed-cloud deployments must be configured
explicitly through deployment-local settings. Do not rely on committed hosted
endpoint defaults. For operator publish tooling, set `KNUDG_API_URL` to the
current reviewed API origin before posting a private card.

## Scope

- Deploy a private Knudg API and Postgres database.
- Keep public publication, team sharing, reviewer admin routes, and hosted
  consent completion disabled unless the relevant gates are implemented and
  tested.
- Store all secrets in the cloud provider's secret/configuration service, not
  in this repository.

## Required Settings

Set these environment variables in your deployment environment:

```text
DATABASE_URL=<postgres connection string>
KNUDG_OPERATOR_TOKEN=<strong random operator token>
KNUDG_SERVER_ID=<deployment identifier>
KNUDG_PRIVATE_TENANT_ID=<uuid>
KNUDG_PRIVATE_NAMESPACE_ID=<uuid>
KNUDG_PRIVATE_PRINCIPAL_ID=<uuid>
KNUDG_API_URL=<current reviewed API origin for operator publish tools>
```

Do not commit real values.

## Database

Use Postgres 16+.

Required extensions are managed by migrations. Run migrations with a role that
has migration privileges, then run the API with the least-privilege runtime
role.

```powershell
npm run py -- scripts/migrate.py up
```

## API

Run:

```powershell
npm run py -- scripts/knudg_closed_api.py --host 0.0.0.0 --port 8000
```

Expose only the routes required for your deployment. For a private deployment,
place the API behind authentication, firewall rules, or a private network
boundary.

For a direct SSH/systemd deployment, the deployment-local runbook should cover:

- non-interactive SSH connectivity check
- service status check before mutation
- backup of every changed runtime file
- copy to a remote staging directory before install
- compile check with the deployment virtual environment before restart
- `systemctl reset-failed` only after a known failed restart loop
- service restart and `active/running` verification
- post-restart health checks and feature-specific smoke checks
- rollback from timestamped backups

## Validation

After deployment:

```powershell
npm run knudgctl -- server status
npm run knudgctl -- server capabilities
npm run py -- -m pytest tests/test_knudg_closed_api.py tests/test_knudg_live_agent.py
```

Expected private deployment properties:

- publication disabled unless explicitly enabled by a reviewed product path
- public search disabled
- protected hosted retrieval disabled unless implemented
- operator token required for private write/search routes
- no raw transcript ingestion

## Cost Guard

Configure provider-level budgets and alerts before creating managed database or
compute resources. Budget alerts are not hard spending caps; keep provider cost
views enabled.
