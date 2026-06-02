# Cloud Closed-Launch Deployment Template

This document is a public-safe template for deploying Knudg to a managed cloud
environment. It intentionally omits real resource names, account identifiers,
operator emails, IP addresses, tokens, and connection strings.

For local development, prefer `docker-compose.yml` and `.env.example`.

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
python scripts/migrate.py up
```

## API

Run:

```powershell
python scripts/knudg_closed_api.py --host 0.0.0.0 --port 8000
```

Expose only the routes required for your deployment. For a private deployment,
place the API behind authentication, firewall rules, or a private network
boundary.

## Validation

After deployment:

```powershell
npm run knudgctl -- server status
npm run knudgctl -- server capabilities
python -m pytest tests/test_knudg_closed_api.py tests/test_knudg_live_agent.py
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
