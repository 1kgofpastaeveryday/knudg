# Azure Closed-Launch Runbook

Status: closed-launch Azure PostgreSQL dev DB and API host provisioned

This runbook tracks the first Azure dev deployment for Knudg. The deployment
goal is a closed-launch private substrate, not public/team launch.

## Current Scope

- Subscription: Azure for Students
- Region: `japaneast`
- Resource group: `rg-knudg-dev`
- Launch state: closed
- Public/team/product routes: closed
- Paid resource creation: allowed only inside the active subscription budget
  guard and Azure for Students free-credit/free-service envelope

## Cost Guard First

Do not create Container Apps, storage, Key Vault, or other additional paid
resources until the current budget state has been rechecked. PostgreSQL and the
F1 App Service host were created only after the subscription-level budget guard
was visible through Azure CLI.

Active guard observed through `az consumption budget list`:

- Subscription budget: `pofo-student-monthly-guard-subscription`
  - Scope: subscription `Azure for Students`
  - Amount: 500 JPY/month
  - Notifications: actual 10%, actual 25%, actual 50%, actual 80%,
    forecast 100%
  - Contact: `g4152067@dokkyo.ac.jp`

Desired additional guard:

- Resource-group budget: `knudg-dev-rg-monthly-5usd`
  - Scope: `rg-knudg-dev`
  - Amount: 500 JPY/month, or equivalent low monthly dev threshold in the
    billing currency
  - Notifications: actual 50%, actual 80%, actual 100%, forecast 100%
- Subscription budget: recommended secondary guard
  - Amount: already active at 500 JPY/month while using Azure for Students
  - Notifications: actual 50%, actual 80%, actual 100%, forecast 100%

Budget alerts are not hard spending caps. They are an early-warning layer only.
Keep Azure for Students spending limits and portal cost views enabled.

## Current Azure State

Created:

```powershell
az group create `
  --name rg-knudg-dev `
  --location japaneast `
  --tags project=knudg environment=dev launch=closed owner=codex cost_guard=budget-first
```

Budget creation attempted through `az rest` and `az consumption budget create`,
but the Azure account returned `RBACAccessDenied` / interactive-auth errors for
creating `Microsoft.Consumption/budgets` and `Microsoft.CostManagement/budgets`.
Listing existing budgets now works.

Verified role assignments for `g4152067@dokkyo.ac.jp` at subscription scope:

- `Owner`
- `Owner`
- `Cost Management Contributor`

The Azure CLI can mint a management-plane bearer token and list RBAC role
assignments, so the current blocker appears specific to Cost Management budget
creation authorization or subscription/billing-scope support.

Created after confirming the subscription-level budget:

- PostgreSQL Flexible Server: `knudg-pg-dev-823765`
  - FQDN: `knudg-pg-dev-823765.postgres.database.azure.com`
  - SKU: `Standard_B1ms`
  - Tier: `Burstable`
  - PostgreSQL: `16`
  - Storage: `32` GiB
  - Backup retention: `7`
  - Geo-redundant backup: disabled
  - Storage autogrow: disabled
  - Public network access: enabled
  - Firewall: limited to the operator public IP used during provisioning
  - Tags: `project=knudg environment=dev launch=closed visibility=private cost_guard=subscription-budget-500jpy`
- Database: `knudg`
- Azure provider registered: `Microsoft.DBforPostgreSQL`
- Azure provider registered: `Microsoft.Web`
- Server parameter override: `azure.extensions=pgcrypto`
- App Service Plan: `asp-knudg-dev-f1`
  - Region: `japaneast`
  - SKU: `LinuxFree` / F1
  - Tags: `project=knudg environment=dev launch=closed visibility=private cost_guard=subscription-budget-500jpy`
- Closed API Web App: `knudg-api-dev-390745`
  - URL: `https://knudg-api-dev-390745.azurewebsites.net`
  - Runtime: `PYTHON:3.12`
  - Startup command: `python scripts/knudg_closed_api.py --host 0.0.0.0 --port 8000 --quiet`
  - App setting: `DATABASE_URL` stored in Azure App Service configuration
    using the least-privilege `knudg_api_app` PostgreSQL login, not the
    migration/admin login.
  - App setting: `KNUDG_SERVER_ID=azure-closed-launch`
  - App setting: `KNUDG_OPERATOR_TOKEN` stores the closed-launch operator token
  - App settings `KNUDG_PRIVATE_TENANT_ID`, `KNUDG_PRIVATE_NAMESPACE_ID`, and
    `KNUDG_PRIVATE_PRINCIPAL_ID` bind the private operator workspace
  - Public URL exposes health/capability disclosure plus one token-gated
    sanitized private publish route. Public search, public publication, MCP,
    reviewer/admin, worker, and consent/revocation routes remain disabled.
- PostgreSQL firewall:
  - Operator IP retained for local migration and smoke checks.
  - App Service current outbound IPs were added.
  - App Service possible outbound IPs were added with ARM deployment
    `knudg-appsvc-postgres-firewall` after App Service readiness initially
    failed with `ConnectionTimeout`.
- App Service access restrictions:
  - Main site default action: `Deny`
  - SCM site default action: `Deny`
  - Allow rule: operator current IP `27.94.92.211/32`
- API database role:
  - Login role: `knudg_api_app`
  - Membership: `knudg_app`
  - Secret file on operator machine: `C:\tmp\knudg-azure-api-db.env`
  - Health metadata grant migration: `0004_closed_api_health_grants`
- Private publish DB function:
  - Migration: `0005_closed_private_publish_function`
  - Function: `knudg_closed_private_publish(...)`
  - Grants: execute only to `knudg_app`
  - Purpose: allow the App Service `knudg_api_app` role to create sanitized
    local-private cards without broad direct table write grants.

Secret handling:

- Admin credential was written to `C:\tmp\knudg-azure-db.env` on the operator
  machine for local migration and verification.
- Do not commit this file or copy its values into repository documentation.

## Budget Creation Command

After the account has Cost Management budget permission, create the resource
group budget with the Azure portal or equivalent ARM/REST command. The body
shape should use `Microsoft.Consumption/budgets` with:

- `category`: `Cost`
- `amount`: `5`
- `timeGrain`: `Monthly`
- `filter.dimensions.name`: `ResourceGroupName`
- `filter.dimensions.operator`: `In`
- `filter.dimensions.values`: `["rg-knudg-dev"]`
- notifications to the operator email at 50%, 80%, 100%, and forecast 100%

If the portal allows budget creation while CLI/REST remains blocked, create and
verify the budget in the portal before resuming automation. Do not treat RBAC
role presence alone as sufficient evidence that the cost guard is active.

## Next Paid Resources

Create only after rechecking budget guards:

1. Any public, team, or non-local-private API route
   - Capabilities must continue to report public/team/product routes closed
     until a signed launch-gate manifest says otherwise.
   - Do not expose write/search routes publicly before auth and intake gates.
2. Any paid service beyond the current DB and F1 API host
   - Recheck the active budget state first.

## Verification Before Proceeding

Before creating paid resources, record:

```powershell
az consumption budget list --output table
az group show --name rg-knudg-dev --output table
```

PostgreSQL verification recorded:

```powershell
az postgres flexible-server show --resource-group rg-knudg-dev --name knudg-pg-dev-823765 --output table
az resource list --resource-group rg-knudg-dev --output table
python scripts\knudgctl.py local preflight-db
```

`local preflight-db` result:

- `status`: `ok`
- `local_private_schema_ready`: `true`
- `postgres.server_version`: `16.13`
- `postgres.database`: `knudg`
- `extensions.pgcrypto.schema`: `knudg_crypto`
- Applied migrations:
  - `0001_m0_schema`
  - `0002_local_private_dogfood`
  - `0003_local_private_payload_contract`
  - `0004_closed_api_health_grants`
  - `0005_closed_private_publish_function`

Azure DB local-private smoke result:

- `ok`: `true`
- `capture_status`: `captured`
- `initial_search_decision`: `cards_found`
- `post_revoke_search_decision`: `no_suggestion`
- `purged_bodies`: `1`
- `publication_enabled`: `false`

Closed API verification:

- `GET /health/live`
  - `status`: `ok`
- `GET /health/ready`
  - HTTP status: `200`
  - `status`: `ready`
  - `components.postgres`: `ready`
  - `components.migration`: `applied`
  - `components.local_private_schema`: `ready`
  - `launch_state`: `closed`
- `GET /capabilities`
  - `deployment_type`: `azure_closed_launch`
  - `capability_resource_origin`: `https://knudg-api-dev-390745.azurewebsites.net`
  - `features.search`: `false`
  - `features.synthetic_retrieval`: `false`
  - `features.protected_retrieval`: `false`
  - `features.publication`: `false`
  - `features.write`: `false`
  - `features.operator_private_publish`: `true`
  - `features.mcp_streamable_http`: `false`
- `POST /v1/private/cards:publish`
  - Auth: `Authorization: Bearer <KNUDG_OPERATOR_TOKEN>`
  - Approval binding: `X-Knudg-Artifact-Digest` must match the canonical
    digest of the exact sanitized local-private card
  - Success HTTP status: `201`
  - `status`: `private_published`
  - `publication_scope`: `private`
  - `public_publication_enabled`: `false`
  - `team_publication_enabled`: `false`
  - `searchable_in_private_namespace`: `true`
- `POST /v1/search`
  - HTTP status: `404`
  - `status`: `closed`
  - `launch_state`: `closed`

Manual private publish from the operator machine:

```powershell
$api = Get-Content C:\tmp\knudg-azure-api.env | ConvertFrom-StringData
$env:KNUDG_API_URL = $api.KNUDG_AZURE_API_URL
$env:KNUDG_OPERATOR_TOKEN = $api.KNUDG_OPERATOR_TOKEN
python scripts\knudg_post_private_card.py --input fixtures\local-private-card.sample.json --print-digest
python scripts\knudg_post_private_card.py --input fixtures\local-private-card.sample.json --workspace closed-launch-manual --approve-digest <printed-digest>
```

This is private publish only. The card enters the hosted private namespace as
`approved_private` and can be found by private local-search fixtures. It is not
public-search eligible and cannot satisfy public/team publication gates.
