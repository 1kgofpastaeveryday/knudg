# Local Dev Server

This temporary loopback server lets developers dogfood custom-server config
without enabling hosted cloud, enterprise, auth, protected retrieval, or write
paths.

Start it:

```powershell
npm run dev:server
```

The server prints a JSON startup line:

```json
{"server_id":"local-dev","server_url":"http://127.0.0.1:8787","status":"listening"}
```

Use the printed `server_url` with `knudgctl`:

```powershell
npm run knudgctl -- config set-server --profile local --server-url http://127.0.0.1:8787
npm run knudgctl -- server status
npm run knudgctl -- server capabilities
npm run knudgctl -- server capabilities --pin --allow-insecure-loopback
npm run knudgctl -- config show --profile local
```

Run a synthetic retrieval fixture through the configured server:

```powershell
npm run knudgctl -- server synthetic-search --input path\to\request.json --corpus path\to\corpus.json
```

For a complete writer-draft to retrieval-panel walkthrough, see
[Local Synthetic Dogfood Runbook](local-synthetic-dogfood-runbook.md).

Implemented endpoints:

- `GET /health/live`
- `GET /health/startup`
- `GET /health/ready`
- `GET /capabilities`
- `POST /v1/synthetic-retrieval/search`

The server binds to loopback only. It reports synthetic local readiness:
protected retrieval, publication, consent/revocation, and search serving remain
disabled. Postgres, migration, and revocation epoch components are reported as
`not_configured` unless a future server actually probes them. The synthetic
retrieval endpoint requires caller-provided synthetic fixtures and does not
read product tables or corpus files. Do not use this server for production or
shared-team deployment.

## Process Hygiene

List only Knudg local dev server processes:

```powershell
npm run dev:server:ctl -- list
```

Dry-run a stop for one port:

```powershell
npm run dev:server:ctl -- stop --port 8787 --dry-run
```

Stop one Knudg dev server port:

```powershell
npm run dev:server:ctl -- stop --port 8787
```

Stop all detected Knudg dev servers:

```powershell
npm run dev:server:ctl -- stop --all
```

The control helper matches only command lines that run
`scripts/knudg_dev_server.py`; it does not target unrelated Python, Node, npm,
or Codex processes.
