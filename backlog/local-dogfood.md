# Local Dogfood Backlog

## LD-001: Codex Plugin Local Install

Status: done

Acceptance:

- `knudg@knudg-local` is enabled in Codex config.
- `$knudg` skill is visible in a new Codex session.
- Plugin manifest and skill validation pass.

Evidence:

- `tests/test_knudg_plugin_manifest.py`
- `codex debug prompt-input '$knudg test'`

## LD-002: Local Server Profile

Status: done

Acceptance:

- `local` profile points at `http://127.0.0.1:8787`.
- active profile is `local`.
- server status returns ready.
- capabilities returns OK and can be pinned.

Evidence:

- `npm run knudgctl -- config show --profile local`
- `npm run knudgctl -- server status`
- `npm run knudgctl -- server capabilities --pin --allow-insecure-loopback`

## LD-003: Process Hygiene

Status: done

Goal:

Prevent local dogfood from leaving duplicate `knudg_dev_server.py` processes.

Acceptance:

- Add a documented command or helper that lists active Knudg dev server
  processes and identifies the port.
- Add a safe stop command/helper for local-only dev servers.
- Do not kill unrelated Python or Node processes.

Suggested verification:

- Unit test command formatting where practical.
- Manual process listing on Windows.

Evidence:

- `scripts/knudg_dev_server_ctl.py`
- `tests/test_knudg_dev_server_ctl.py`
- `npm run dev:server:ctl -- list`
