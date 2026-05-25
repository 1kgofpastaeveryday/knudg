# Development

## Local Tooling

Most local scripts are exposed through `package.json` so the same command names
work from Codex, PowerShell, and CI-style checks.

```powershell
npm run knudgctl -- --help
npm run writer:draft -- --help
npm run task-profile -- --help
npm run retrieval:skeleton -- --help
npm run retrieval:synthetic -- --help
```

The default client profile is intentionally inert. A newly enabled local plugin
may require a fresh Codex session before `$knudg` appears. If the active profile
is `cloud`, local dogfood commands can return `not_configured`; switch to the
`local` profile and point it at the loopback server before expecting
capabilities to pass.

```powershell
npm run dev:server -- --host 127.0.0.1 --port 8787
npm run knudgctl -- config set-server --profile local --server-url http://127.0.0.1:8787
npm run knudgctl -- server status
npm run knudgctl -- server capabilities
```

The loopback server is synthetic-only. It must not be used for protected
retrieval, publication, consent/revocation, hosted cloud, or shared-team
deployment.

## Local Postgres

Start the default database:

```powershell
docker compose up -d postgres
```

Install test dependencies:

```powershell
python -m pip install -r requirements-dev.txt
```

Apply migrations:

```powershell
python scripts/migrate.py up
```

Rollback migrations:

```powershell
python scripts/migrate.py down
```

To use an existing Postgres instance, set `DATABASE_URL` before running the
migration runner or tests.

## M0 Schema Tests

```powershell
python -m pytest tests/test_m0_schema.py
```

## Local Private Dogfood

After local Postgres is running and migrations are applied, run the private
vertical smoke loop:

```powershell
npm run dogfood:local-private
```

The smoke creates an ephemeral tenant, namespace, and principal in the local
database, then runs `local capture`, `local search`, `local revoke`,
`local purge`, and `local verify-fences` against the fixture pair:

```powershell
fixtures/local-private-card.sample.json
fixtures/local-private-task-profile.sample.json
```

Expected result: `ok` is `true`, the initial search decision is `cards_found`,
the post-revoke search decision is `no_suggestion`, and `purged_bodies` is `1`.
This path is local-only and keeps publication disabled.

## Synthetic Dogfood

Run the local writer-draft to synthetic retrieval path without Postgres or
protected product data:

```powershell
npm run writer:draft -- draft-card --input tmp\writer-draft.json
npm run task-profile -- build --input tmp\task-profile-input.json
npm run retrieval:synthetic -- build-corpus --payload tmp\writer-result.json
npm run roles -- searcher-profile-nudge-synthetic --input tmp\task-profile.json --corpus tmp\corpus.json
```

When local Postgres is running and migrations are applied, stored synthetic
cards can be searched from the M0 tables:

```powershell
npm run knudgctl -- search local-exact-fts --tenant <tenant-id> --namespace <namespace-id> --task-profile tmp\task-profile.json
```

For a complete walkthrough, use
[Local Synthetic Dogfood Runbook](operations/local-synthetic-dogfood-runbook.md).
This path is only a local/M0 safety scaffold. `submit_candidate` for
non-synthetic content remains blocked until PR-006 intake safety,
protected-data durability, audit persistence, and the
`non_synthetic_body_persistence_gate` are open.

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
npm run gates:all
```

Landing page checks are separate from backend gates:

```powershell
npm run check:lp
npm run smoke:lp
```
