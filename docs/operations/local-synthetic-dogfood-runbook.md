# Local Synthetic Dogfood Runbook

Status: local synthetic-only operator path

This runbook proves the current use-ready path without Postgres, protected
retrieval, consent UI, publication, or product-table writes.

## Preflight

Run from the repository root:

```powershell
python -m pytest tests/test_knudg_client_config.py tests/test_knudg_dev_server.py tests/test_knudg_writer.py tests/test_knudg_synthetic_retrieval.py tests/test_retrieval_skeleton.py
```

Expected result: all selected tests pass. Postgres is not required for this
synthetic path.

## 1. Create A Synthetic Writer Draft

```powershell
$work = New-Item -ItemType Directory -Force tmp\knudg-local-dogfood

@'
{
  "schema_version": "writer-draft-v0",
  "request_id": "draft_req_local_001",
  "source_class": "synthetic",
  "outcome_type": "solved",
  "goal": "configure Knudg local server profile",
  "symptom": "knudgctl server status failed because the local server URL was missing",
  "environment": {
    "agent_tool": "Codex",
    "coarse_os": "windows"
  },
  "context_fingerprint": {
    "repo_shape": "python-node-local-plugin"
  },
  "successful_path": [
    "start the loopback dev server",
    "set the local profile server URL",
    "check server status and capabilities"
  ],
  "failed_paths": [],
  "known_unknowns": [],
  "scope_limits": [
    "synthetic local dogfood only"
  ],
  "risk_flags": []
}
'@ | Set-Content -Encoding UTF8 $work\writer-draft.json

npm run writer:draft -- draft-card --input $work\writer-draft.json > $work\writer-result.json
```

Expected result: `writer-result.json` has `status: "local_draft_only"` and a
`payload_digest`. It does not write to Postgres.

## 2. Build A Synthetic Corpus

```powershell
npm run retrieval:synthetic -- build-corpus --payload $work\writer-result.json > $work\corpus.json
```

Expected result: `corpus.json` has `schema_version:
"synthetic-corpus-v0"` and one synthetic card.

## 3. Create A Task Profile

```powershell
@'
{
  "schema_version": "task-profile-builder-input-v0",
  "explicit_query": "configure Knudg local server profile",
  "intent": "debug",
  "repo_shape_category": "python-node-local-plugin",
  "subsystems": ["local-dev-server"],
  "safe_file_refs": ["docs/operations/local-dev-server.md"],
  "symbols": ["knudgctl"],
  "error_fingerprints": ["server-url-missing"],
  "public_packages": ["pypi:jsonschema"],
  "public_frameworks_tools": ["Codex"],
  "language_runtime": "python-3.12",
  "coarse_os": "windows",
  "dependency_major_versions": [],
  "risk_tags": [],
  "recent_event_kinds": ["task_start"]
}
'@ | Set-Content -Encoding UTF8 $work\task-profile-input.json

npm run task-profile -- build --input $work\task-profile-input.json > $work\task-profile.json
```

Expected result: `task-profile.json` is valid `task_profile.v0`. The builder
does not inspect the referenced files.

## 4. Create A Synthetic Retrieval Request

```powershell
@'
{
  "schema_version": "synthetic-retrieval-v0",
  "request_id": "retrieval_req_local_001",
  "auth_context": {
    "tenant_id": "tenant_local",
    "namespace_ids": ["ns_local"],
    "revocation_epoch": 0
  },
  "search_profile": {
    "schema_version": "search-profile-v0",
    "request_id": "profile_req_local_001",
    "tenant_scope": "private",
    "namespace_ids": ["ns_local"],
    "delivery_mode_requested": "retrieval_panel",
    "goal_category": "configure Knudg local server profile",
    "sanitized_error_signature": "local server URL was missing",
    "public_packages_claimed": ["knudgctl"],
    "public_frameworks_tools_claimed": ["Codex"],
    "language_runtime": "python-3.12",
    "coarse_os": "windows",
    "dependency_major_versions": [],
    "repo_shape_category": "python-node-local-plugin",
    "risk_flags_claimed": [],
    "latency_budget_ms": 250,
    "privacy_budget_class_claimed": "private_team"
  }
}
'@ | Set-Content -Encoding UTF8 $work\request.json
```

## 5. Search Directly

```powershell
npm run retrieval:synthetic -- search --input $work\request.json --corpus $work\corpus.json
```

Expected result: `decision` is `cards_found`, `delivery_mode` is
`retrieval_panel`, and returned cards contain metadata only. The response must
not include `successful_path`.

## 6. Run The One-Command Local Dogfood Path

The one-command path takes the explicit synthetic writer draft and explicit
task profile JSON, builds the synthetic corpus in memory, runs the searcher
profile through the nudger, and returns a compact verdict plus opaque refs.

```powershell
npm run dogfood:local -- --draft-input $work\writer-draft.json --task-profile-input $work\task-profile.json
```

Expected result: `schema_version` is `local-dogfood-result-v0`, the nested
`role_verdict.role` is `nudger`, and refs are opaque fixture refs only. The
response must not include card bodies, `successful_path`, raw commands, private
paths, or publication state.

## 7. Run Replay Metrics

```powershell
npm run retrieval:replay -- --input fixtures\m3-retrieval-hybrid-fixtures.json
```

Expected result: `schema_version` is `retrieval-replay-report-v0`, metric floors
pass for recall@3, recall@10, nDCG@10, abstention accuracy, and stale or harmful
suggestion rate.

## 8. Search Through The Loopback Server

Start the server in one terminal:

```powershell
npm run dev:server -- --host 127.0.0.1 --port 8787
```

In another terminal:

```powershell
npm run knudgctl -- config set-server --profile local --server-url http://127.0.0.1:8787
npm run knudgctl -- server status
npm run knudgctl -- server capabilities
npm run knudgctl -- server synthetic-search --input $work\request.json --corpus $work\corpus.json
```

Expected result:

- `server status` reports `route_classes.search: "disabled"` and
  `route_classes.synthetic-retrieval: "synthetic_only"`.
- Postgres, migration, and revocation epoch components are `not_configured` in
  the temporary loopback server unless a future server actually probes them.
- `server synthetic-search` returns the retrieval-panel result without printing
  the local `server_url`, card bodies, raw commands, or publication state.

## Expected Abstention And Failure Modes

`no_suggestion` is expected when the query does not overlap the synthetic
corpus, the corpus is empty, the card is revoked, the tenant/namespace is not
authorized, or the score is below `--min-score`.

Writer-runner and sweeper paths are local/synthetic only:

```powershell
npm run knudgctl -- writer status --tenant <tenant_id>
npm run knudgctl -- writer enqueue-next --tenant <tenant_id> --dry-run
npm run knudgctl -- writer run-next --tenant <tenant_id> --dry-run
npm run knudgctl -- writer sweep --tenant <tenant_id> --dry-run
npm run knudgctl -- writer approval-handoff create --tenant <tenant_id> --card <card_id> --dry-run
npm run knudgctl -- writer approval-handoff inspect --tenant <tenant_id> --handoff <handoff_id>
```

Non-synthetic body persistence, publication, and trusted consent completion
remain closed. CLI/MCP paths can create or inspect local handoff state, but they
cannot complete consent.

## Cleanup

```powershell
npm run dev:server:ctl -- stop --port 8787
Remove-Item -Recurse -Force tmp\knudg-local-dogfood
```

This cleanup removes only the temporary runbook files and the local dev server
process for the selected port.
