# Development

## Local Tooling

Most local scripts are exposed through `package.json` so the same command names
work from Codex, PowerShell, and CI-style checks.

```powershell
npm run knudgctl -- --help
npm run task-profile -- --help
npm run dev:closed-api -- --help
npm run post:private-card -- --help
```

The default client profile is intentionally inert. A newly enabled local plugin
may require a fresh Codex session before `$knudg` appears. The active agent path
uses a pinned closed-launch backend and live `knudgctl` commands; legacy
loopback fixture servers and synthetic dogfood commands have been removed.

```powershell
npm run knudgctl -- server status
npm run knudgctl -- server capabilities
npm run knudgctl -- live profile build --input tmp\task-profile-builder-input.json
npm run knudgctl -- live nudge --task-profile tmp\task-profile.json
```

The closed-launch backend must keep public publication, public/admin routes,
and trusted consent completion disabled until their gates are accepted.

For local private-card posting, `npm run post:private-card` prints the effective
API URL before sending the request. Local development may use
`KNUDG_API_URL=http://127.0.0.1:8765`; hosted Greencloud closed-launch posting
requires an explicit current `KNUDG_API_URL` from deployment-local operator
docs. The old Azure App Service endpoint is rejected as stale configuration.

## Local Postgres

Start the default database:

```powershell
docker compose up -d postgres
```

Install test dependencies:

```powershell
npm run setup:python
```

Apply migrations:

```powershell
npm run py -- scripts/migrate.py up
```

Rollback migrations:

```powershell
npm run py -- scripts/migrate.py down
```

To use an existing Postgres instance, set `DATABASE_URL` before running the
migration runner or tests.

## M0 Schema Tests

```powershell
npm run py -- -m pytest tests/test_m0_schema.py
```

## Gate Checks

The current local gate validators are runnable through npm:

```powershell
npm run m3:gates
npm run review:gates
npm run circuit:gates
npm run runbook:manifest
npm run launch:gates
npm run intake:gates
npm run auth:gates
npm run consent:gates
npm run tns:audit
npm run experience:surfaces
npm run abuse:identity
npm run abuse:identity-enforcement
npm run raw:detail-escrow
npm run dashboard:company-store
npm run gates:all
```

Landing page checks are separate from backend gates:

```powershell
npm run check:lp
npm run smoke:lp
```
